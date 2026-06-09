"""API contract tests — verify response shapes without real Neo4j/Redis/OpenAI."""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit

REQUIRED_ASK_FIELDS = {
    "question", "answer", "evidence", "graph_evidence",
    "vector_evidence", "answer_source", "cache_hit", "metrics",
}
REQUIRED_METRICS_FIELDS = {"latency_ms", "graph_paths", "vector_chunks"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patched_client():
    """Return a TestClient with all external deps mocked."""
    with patch("src.db.neo4j_client.GraphDatabase.driver"), \
         patch("src.cache.redis_cache._get_redis", return_value=None), \
         patch("src.cache.redis_cache._get_semantic_cache", return_value=None):
        from fastapi.testclient import TestClient
        from src.api.main import app
        return TestClient(app)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health_returns_200():
    client = _patched_client()
    with patch("src.api.main.get_graph_summary", return_value={"edge_count": 35, "node_count": 30}):
        resp = client.get("/health")
    assert resp.status_code == 200


def test_health_status_field():
    client = _patched_client()
    with patch("src.api.main.get_graph_summary", return_value={"edge_count": 35, "node_count": 30}):
        data = client.get("/health").json()
    assert "status" in data


def test_health_degraded_on_error():
    client = _patched_client()
    with patch("src.api.main.get_graph_summary", side_effect=Exception("Neo4j down")):
        data = client.get("/health").json()
    assert data["status"] == "degraded"


# ---------------------------------------------------------------------------
# GET /data/sources
# ---------------------------------------------------------------------------

def test_data_sources_returns_200():
    client = _patched_client()
    resp = client.get("/data/sources")
    assert resp.status_code == 200


def test_data_sources_shape():
    client = _patched_client()
    data = client.get("/data/sources").json()
    assert "sources" in data
    assert isinstance(data["sources"], list)
    for entry in data["sources"]:
        assert "dataset" in entry
        assert "path" in entry
        assert "loaded" in entry


# ---------------------------------------------------------------------------
# GET /graph/summary
# ---------------------------------------------------------------------------

def test_graph_summary_returns_200():
    client = _patched_client()
    with patch("src.api.main.get_graph_summary", return_value={"edge_count": 35, "node_count": 30}):
        resp = client.get("/graph/summary")
    assert resp.status_code == 200


def test_graph_summary_shape():
    client = _patched_client()
    with patch("src.api.main.get_graph_summary", return_value={"edge_count": 35, "node_count": 30}):
        data = client.get("/graph/summary").json()
    assert "edge_count" in data
    assert "node_count" in data


# ---------------------------------------------------------------------------
# POST /ask — required response shape
# ---------------------------------------------------------------------------

def _ask(client, question="What foods support rs1801133?"):
    evidence = ["rs1801133 in MTHFR", "Spinach contains Folate"]
    with patch("src.api.main.hybrid_retrieve",
               return_value=(evidence, [evidence[0]], 2, 1)), \
         patch("src.api.main.generate_answer",
               return_value={"answer": "Spinach may help.", "answer_source": "template_fallback"}):
        return client.post("/ask", json={"question": question})


def test_ask_returns_200():
    client = _patched_client()
    assert _ask(client).status_code == 200


def test_ask_has_all_required_fields():
    client = _patched_client()
    data = _ask(client).json()
    missing = REQUIRED_ASK_FIELDS - set(data.keys())
    assert not missing, f"Missing fields in /ask response: {missing}"


def test_ask_metrics_has_all_subfields():
    client = _patched_client()
    data = _ask(client).json()
    missing = REQUIRED_METRICS_FIELDS - set(data["metrics"].keys())
    assert not missing, f"Missing subfields in metrics: {missing}"


def test_ask_evidence_is_list():
    client = _patched_client()
    data = _ask(client).json()
    assert isinstance(data["evidence"], list)
    assert isinstance(data["graph_evidence"], list)
    assert isinstance(data["vector_evidence"], list)


def test_ask_cache_hit_false_on_fresh_request():
    client = _patched_client()
    data = _ask(client).json()
    assert data["cache_hit"] is False


def test_ask_question_echoed_back():
    client = _patched_client()
    data = _ask(client, question="Tell me about MTHFR").json()
    assert data["question"] == "Tell me about MTHFR"


def test_ask_empty_question_returns_400():
    client = _patched_client()
    resp = client.post("/ask", json={"question": "  "})
    assert resp.status_code == 400


def test_ask_cache_hit_exact():
    cached = {
        "answer": "Cached answer",
        "evidence": ["Evidence A"],
        "answer_source": "exact_cache",
        "cache_hit": True,
    }
    client = _patched_client()
    with patch("src.api.main.redis_cache.get_exact", return_value=cached):
        data = client.post("/ask", json={"question": "What foods support rs1801133?"}).json()
    assert data["cache_hit"] is True
    assert data["answer_source"] == "exact_cache"


def test_ask_cache_hit_semantic():
    cached = {
        "answer": "Semantic cached answer",
        "evidence": ["Evidence B"],
        "answer_source": "semantic_cache",
        "cache_hit": True,
    }
    client = _patched_client()
    with patch("src.api.main.redis_cache.get_exact", return_value=None), \
         patch("src.api.main.redis_cache.get_semantic", return_value=cached):
        data = client.post("/ask", json={"question": "rs1801133 folate?"}).json()
    assert data["cache_hit"] is True
    assert data["answer_source"] == "semantic_cache"


def test_ask_graph_and_vector_evidence_separated():
    client = _patched_client()
    vector_docs = ["Vector doc 1"]
    graph_docs = ["Graph doc 2"]
    all_evidence = vector_docs + graph_docs
    with patch("src.api.main.hybrid_retrieve",
               return_value=(all_evidence, vector_docs, 2, 1)), \
         patch("src.api.main.generate_answer",
               return_value={"answer": "Answer", "answer_source": "llm"}):
        data = client.post("/ask", json={"question": "What nutrients help glucose?"}).json()
    assert "Vector doc 1" in data["vector_evidence"]
    assert "Graph doc 2" in data["graph_evidence"]


def test_ask_latency_ms_is_integer():
    client = _patched_client()
    data = _ask(client).json()
    assert isinstance(data["metrics"]["latency_ms"], int)
