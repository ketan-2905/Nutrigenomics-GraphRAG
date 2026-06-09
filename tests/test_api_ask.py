import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _get_client():
    with patch("src.db.neo4j_client.GraphDatabase.driver"), \
         patch("src.cache.redis_cache._get_redis", return_value=None), \
         patch("src.cache.redis_cache._get_semantic_cache", return_value=None):
        from src.api.main import app
        return TestClient(app)


def test_root():
    client = _get_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ask_returns_required_fields():
    client = _get_client()
    with patch("src.api.main.hybrid_retrieve",
               return_value=(["Evidence A", "Evidence B"], ["Evidence A"], 1, 1)), \
         patch("src.api.main.generate_answer",
               return_value={"answer": "Spinach may support folate.", "answer_source": "template_fallback"}):
        resp = client.post("/ask", json={"question": "What foods support rs1801133?"})

    assert resp.status_code == 200
    data = resp.json()
    assert "question" in data
    assert "answer" in data
    assert "evidence" in data
    assert "graph_evidence" in data
    assert "vector_evidence" in data
    assert "answer_source" in data
    assert "cache_hit" in data
    assert "metrics" in data
    assert "latency_ms" in data["metrics"]
    assert "graph_paths" in data["metrics"]
    assert "vector_chunks" in data["metrics"]


def test_ask_empty_question_returns_400():
    client = _get_client()
    resp = client.post("/ask", json={"question": "  "})
    assert resp.status_code == 400


def test_ask_cache_hit_returns_cached_result():
    cached = {
        "answer": "Cached answer",
        "evidence": ["Evidence A"],
        "answer_source": "exact_cache",
        "cache_hit": True,
    }
    client = _get_client()
    with patch("src.api.main.redis_cache.get_exact", return_value=cached):
        resp = client.post("/ask", json={"question": "What foods support rs1801133?"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["cache_hit"] is True
    assert data["answer_source"] == "exact_cache"


def test_graph_and_vector_evidence_separated():
    client = _get_client()
    vector_docs = ["Vector doc 1"]
    graph_docs = ["Graph doc 2"]
    all_evidence = vector_docs + graph_docs

    with patch("src.api.main.hybrid_retrieve",
               return_value=(all_evidence, vector_docs, 2, 1)), \
         patch("src.api.main.generate_answer",
               return_value={"answer": "Answer", "answer_source": "llm"}):
        resp = client.post("/ask", json={"question": "What nutrients help glucose metabolism?"})

    data = resp.json()
    assert "Vector doc 1" in data["vector_evidence"]
    assert "Graph doc 2" in data["graph_evidence"]


def test_health_endpoint():
    client = _get_client()
    with patch("src.api.main.get_graph_summary", return_value={"edge_count": 35, "node_count": 30}):
        resp = client.get("/health")
    assert resp.status_code == 200


def test_cache_stats_endpoint():
    client = _get_client()
    resp = client.get("/cache/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "redis_connected" in data


def test_data_sources_endpoint(tmp_path):
    client = _get_client()
    resp = client.get("/data/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "sources" in data
    assert isinstance(data["sources"], list)


def test_graph_summary_endpoint():
    client = _get_client()
    with patch("src.api.main.get_graph_summary", return_value={"edge_count": 35, "node_count": 30}):
        resp = client.get("/graph/summary")
    assert resp.status_code == 200
    assert "edge_count" in resp.json()
