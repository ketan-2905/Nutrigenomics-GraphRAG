"""Unit tests for the hybrid retriever — Chroma and Neo4j are fully mocked."""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GRAPH_PATHS = [
    {"node_ids": ["rs1801133", "MTHFR", "Folate metabolism"], "rel_types": ["LOCATED_IN", "AFFECTS"]}
]
_FOODS = [
    {"food": "Spinach", "path_nodes": ["rs1801133", "MTHFR", "Folate metabolism", "Folate", "Spinach"]}
]
_NUTRIENTS = [
    {"nutrient": "Folate", "path_nodes": ["Folate", "Folate metabolism"]}
]


# ---------------------------------------------------------------------------
# SNP extraction
# ---------------------------------------------------------------------------

def test_extract_snp_id_found():
    from src.rag.retriever import extract_snp_id
    assert extract_snp_id("What about rs1801133 and folate?") == "rs1801133"


def test_extract_snp_id_case_insensitive():
    from src.rag.retriever import extract_snp_id
    assert extract_snp_id("Tell me about RS1801133") == "rs1801133"


def test_extract_snp_id_not_found():
    from src.rag.retriever import extract_snp_id
    assert extract_snp_id("no snp here") is None


def test_extract_snp_id_partial_match():
    from src.rag.retriever import extract_snp_id
    result = extract_snp_id("rs1801133 and rs7903146 both matter")
    assert result is not None
    assert result.startswith("rs")


# ---------------------------------------------------------------------------
# Trait extraction
# ---------------------------------------------------------------------------

def test_extract_trait_folate():
    from src.rag.retriever import extract_trait
    assert extract_trait("question about folate levels") == "Folate metabolism"


def test_extract_trait_glucose():
    from src.rag.retriever import extract_trait
    assert extract_trait("glucose issues") == "Glucose metabolism"


def test_extract_trait_not_found():
    from src.rag.retriever import extract_trait
    assert extract_trait("nothing relevant") is None


# ---------------------------------------------------------------------------
# hybrid_retrieve — returns both graph and vector evidence
# ---------------------------------------------------------------------------

@patch("src.rag.retriever.vector_search", return_value=["Vector doc 1", "Vector doc 2"])
@patch("src.rag.retriever.find_paths_from_snp", return_value=_GRAPH_PATHS)
@patch("src.rag.retriever.find_foods_for_snp", return_value=_FOODS)
@patch("src.rag.retriever.find_nutrients_for_trait", return_value=_NUTRIENTS)
def test_hybrid_retrieve_returns_both_graph_and_vector(mock_nuts, mock_foods, mock_paths, mock_vec):
    from src.rag.retriever import hybrid_retrieve
    evidence, vector_docs, graph_path_count, vector_chunk_count = hybrid_retrieve(
        "What foods support rs1801133 folate metabolism?"
    )
    assert len(vector_docs) == 2
    assert graph_path_count > 0
    assert any("Vector doc" in e for e in evidence)
    assert any("rs1801133" in e for e in evidence)


@patch("src.rag.retriever.vector_search", return_value=["VecDoc"])
@patch("src.rag.retriever.find_paths_from_snp", return_value=[])
@patch("src.rag.retriever.find_foods_for_snp", return_value=[])
@patch("src.rag.retriever.find_nutrients_for_trait", return_value=[])
def test_hybrid_retrieve_without_snp_uses_vector_only(mock_nuts, mock_foods, mock_paths, mock_vec):
    from src.rag.retriever import hybrid_retrieve
    evidence, vector_docs, graph_path_count, vector_chunk_count = hybrid_retrieve(
        "What is a healthy diet?"
    )
    assert "VecDoc" in evidence
    assert vector_chunk_count == 1


@patch("src.rag.retriever.vector_search", return_value=["VecDoc"])
@patch("src.rag.retriever.find_paths_from_snp", side_effect=Exception("Neo4j timeout"))
@patch("src.rag.retriever.find_foods_for_snp", side_effect=Exception("Neo4j timeout"))
@patch("src.rag.retriever.find_nutrients_for_trait", return_value=[])
def test_hybrid_retrieve_survives_graph_failure(mock_nuts, mock_foods, mock_paths, mock_vec):
    from src.rag.retriever import hybrid_retrieve
    evidence, vector_docs, graph_path_count, vector_chunk_count = hybrid_retrieve(
        "What foods support rs1801133?"
    )
    assert "VecDoc" in evidence


@patch("src.rag.retriever.vector_search", side_effect=Exception("Chroma unavailable"))
@patch("src.rag.retriever.find_paths_from_snp", return_value=_GRAPH_PATHS)
@patch("src.rag.retriever.find_foods_for_snp", return_value=_FOODS)
@patch("src.rag.retriever.find_nutrients_for_trait", return_value=[])
def test_hybrid_retrieve_survives_vector_failure(mock_nuts, mock_foods, mock_paths, mock_vec):
    from src.rag.retriever import hybrid_retrieve
    evidence, vector_docs, graph_path_count, vector_chunk_count = hybrid_retrieve(
        "What foods support rs1801133?"
    )
    assert isinstance(evidence, list)


# ---------------------------------------------------------------------------
# Return value is structured and serializable
# ---------------------------------------------------------------------------

@patch("src.rag.retriever.vector_search", return_value=["VecDoc"])
@patch("src.rag.retriever.find_paths_from_snp", return_value=_GRAPH_PATHS)
@patch("src.rag.retriever.find_foods_for_snp", return_value=_FOODS)
@patch("src.rag.retriever.find_nutrients_for_trait", return_value=_NUTRIENTS)
def test_hybrid_retrieve_output_is_serializable(mock_nuts, mock_foods, mock_paths, mock_vec):
    import json
    from src.rag.retriever import hybrid_retrieve
    evidence, vector_docs, graph_path_count, vector_chunk_count = hybrid_retrieve(
        "rs1801133 folate metabolism"
    )
    # All evidence items must be strings (JSON-serializable)
    json.dumps(evidence)
    assert all(isinstance(e, str) for e in evidence)
    assert isinstance(graph_path_count, int)
    assert isinstance(vector_chunk_count, int)
