"""Unit tests for graph query functions — Neo4j driver is fully mocked."""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit


def _mock_run(query, params=None):
    """Dispatch mock Neo4j results based on query content.

    Note: find_foods_for_snp query contains both ':SNP' and ':Food', so the
    Food check must come before the generic SNP check.
    """
    snp_id = str((params or {}).get("snp_id", ""))
    trait = str((params or {}).get("trait_name", ""))

    if "Food" in query and "rs1801133" in snp_id:
        return [{"food": "Spinach", "path_nodes": ["rs1801133", "MTHFR", "Folate metabolism", "Folate", "Spinach"]}]
    if "SNP" in query and "rs1801133" in snp_id:
        return [{"node_ids": ["rs1801133", "MTHFR", "Folate metabolism"], "rel_types": ["LOCATED_IN", "AFFECTS"]}]
    if "Nutrient" in query and "Folate metabolism" in trait:
        return [{"nutrient": "Folate", "path_nodes": ["Folate", "Folate metabolism"]}]
    if "shortestPath" in query:
        return [{"path_nodes": ["rs1801133", "MTHFR", "Spinach"], "rel_types": ["LOCATED_IN", "RELATED"]}]
    if "count(r)" in query:
        return [{"edge_count": 35}]
    if "count(n)" in query:
        return [{"node_count": 30}]
    return []


# ---------------------------------------------------------------------------
# find_paths_from_snp
# ---------------------------------------------------------------------------

@patch("src.db.neo4j_client.Neo4jClient.run", side_effect=_mock_run)
@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_paths_from_snp_returns_list(mock_driver, mock_run):
    mock_driver.return_value = MagicMock()
    from src.graph.queries import find_paths_from_snp
    result = find_paths_from_snp("rs1801133")
    assert isinstance(result, list)
    assert len(result) >= 1


@patch("src.db.neo4j_client.Neo4jClient.run", side_effect=_mock_run)
@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_paths_from_snp_result_has_node_ids(mock_driver, mock_run):
    mock_driver.return_value = MagicMock()
    from src.graph.queries import find_paths_from_snp
    result = find_paths_from_snp("rs1801133")
    assert "node_ids" in result[0]
    assert isinstance(result[0]["node_ids"], list)


# ---------------------------------------------------------------------------
# find_foods_for_snp
# ---------------------------------------------------------------------------

@patch("src.db.neo4j_client.Neo4jClient.run", side_effect=_mock_run)
@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_foods_for_snp_returns_list(mock_driver, mock_run):
    mock_driver.return_value = MagicMock()
    from src.graph.queries import find_foods_for_snp
    result = find_foods_for_snp("rs1801133")
    assert isinstance(result, list)
    assert len(result) >= 1


@patch("src.db.neo4j_client.Neo4jClient.run", side_effect=_mock_run)
@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_foods_for_snp_result_has_food_and_path(mock_driver, mock_run):
    mock_driver.return_value = MagicMock()
    from src.graph.queries import find_foods_for_snp
    result = find_foods_for_snp("rs1801133")
    assert "food" in result[0]
    assert "path_nodes" in result[0]


# ---------------------------------------------------------------------------
# find_nutrients_for_trait
# ---------------------------------------------------------------------------

@patch("src.db.neo4j_client.Neo4jClient.run", side_effect=_mock_run)
@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_nutrients_for_trait_returns_list(mock_driver, mock_run):
    mock_driver.return_value = MagicMock()
    from src.graph.queries import find_nutrients_for_trait
    result = find_nutrients_for_trait("Folate metabolism")
    assert isinstance(result, list)
    assert len(result) >= 1


@patch("src.db.neo4j_client.Neo4jClient.run", side_effect=_mock_run)
@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_nutrients_for_trait_result_has_nutrient(mock_driver, mock_run):
    mock_driver.return_value = MagicMock()
    from src.graph.queries import find_nutrients_for_trait
    result = find_nutrients_for_trait("Folate metabolism")
    assert "nutrient" in result[0]


# ---------------------------------------------------------------------------
# find_graph_path (shortestPath)
# ---------------------------------------------------------------------------

@patch("src.db.neo4j_client.Neo4jClient.run", side_effect=_mock_run)
@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_graph_path_returns_list(mock_driver, mock_run):
    mock_driver.return_value = MagicMock()
    from src.graph.queries import find_graph_path
    result = find_graph_path("rs1801133", "Spinach")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_graph_summary
# ---------------------------------------------------------------------------

@patch("src.db.neo4j_client.Neo4jClient.run", side_effect=_mock_run)
@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_get_graph_summary_shape(mock_driver, mock_run):
    mock_driver.return_value = MagicMock()
    from src.graph.queries import get_graph_summary
    summary = get_graph_summary()
    assert "edge_count" in summary
    assert "node_count" in summary
    assert isinstance(summary["edge_count"], int)
    assert isinstance(summary["node_count"], int)


# ---------------------------------------------------------------------------
# DB connection is closed after each query
# ---------------------------------------------------------------------------

@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_paths_from_snp_closes_driver(mock_driver):
    mock_instance = MagicMock()
    mock_instance.session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_instance.session.return_value.__exit__ = MagicMock(return_value=False)
    mock_session = MagicMock()
    mock_session.run.return_value = iter([])
    mock_instance.session.return_value = mock_session
    mock_driver.return_value = mock_instance

    from src.graph.queries import find_paths_from_snp
    find_paths_from_snp("rs1801133")
    mock_instance.close.assert_called_once()


@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_foods_for_snp_closes_driver(mock_driver):
    mock_instance = MagicMock()
    mock_session = MagicMock()
    mock_session.run.return_value = iter([])
    mock_instance.session.return_value = mock_session
    mock_driver.return_value = mock_instance

    from src.graph.queries import find_foods_for_snp
    find_foods_for_snp("rs1801133")
    mock_instance.close.assert_called_once()


@patch("src.db.neo4j_client.GraphDatabase.driver")
def test_find_nutrients_for_trait_closes_driver(mock_driver):
    mock_instance = MagicMock()
    mock_session = MagicMock()
    mock_session.run.return_value = iter([])
    mock_instance.session.return_value = mock_session
    mock_driver.return_value = mock_instance

    from src.graph.queries import find_nutrients_for_trait
    find_nutrients_for_trait("Folate metabolism")
    mock_instance.close.assert_called_once()
