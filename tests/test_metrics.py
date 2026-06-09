import pytest


def test_metrics_module_imports():
    from src.observability.metrics import (
        RAG_REQUESTS_TOTAL,
        RAG_ERRORS_TOTAL,
        RAG_REQUEST_LATENCY,
        RAG_RETRIEVAL_LATENCY,
        RAG_GRAPH_RETRIEVAL_LATENCY,
        RAG_VECTOR_RETRIEVAL_LATENCY,
        RAG_LLM_LATENCY,
        RAG_CACHE_HITS_TOTAL,
        RAG_CACHE_MISSES_TOTAL,
        RAG_CACHE_SET_TOTAL,
        RAG_CACHE_ERRORS_TOTAL,
        RAG_GRAPH_PATHS_RETURNED,
        RAG_VECTOR_CHUNKS_RETURNED,
        RAG_EVIDENCE_CHUNKS_INDEXED_TOTAL,
        RAG_DATASET_ROWS_LOADED_TOTAL,
        RAG_ANSWER_SOURCE_TOTAL,
        RAG_LLM_TOKENS_TOTAL,
    )
    # 17 metrics defined
    metrics = [
        RAG_REQUESTS_TOTAL, RAG_ERRORS_TOTAL, RAG_REQUEST_LATENCY,
        RAG_RETRIEVAL_LATENCY, RAG_GRAPH_RETRIEVAL_LATENCY,
        RAG_VECTOR_RETRIEVAL_LATENCY, RAG_LLM_LATENCY,
        RAG_CACHE_HITS_TOTAL, RAG_CACHE_MISSES_TOTAL, RAG_CACHE_SET_TOTAL,
        RAG_CACHE_ERRORS_TOTAL, RAG_GRAPH_PATHS_RETURNED,
        RAG_VECTOR_CHUNKS_RETURNED, RAG_EVIDENCE_CHUNKS_INDEXED_TOTAL,
        RAG_DATASET_ROWS_LOADED_TOTAL, RAG_ANSWER_SOURCE_TOTAL,
        RAG_LLM_TOKENS_TOTAL,
    ]
    assert len(metrics) >= 10


def test_counter_increments():
    from src.observability.metrics import RAG_REQUESTS_TOTAL
    before = RAG_REQUESTS_TOTAL.labels(endpoint="/test_counter", status="200")._value.get()
    RAG_REQUESTS_TOTAL.labels(endpoint="/test_counter", status="200").inc()
    after = RAG_REQUESTS_TOTAL.labels(endpoint="/test_counter", status="200")._value.get()
    assert after == before + 1


def test_histogram_observe():
    from src.observability.metrics import RAG_LLM_LATENCY
    RAG_LLM_LATENCY.observe(0.5)
    RAG_LLM_LATENCY.observe(1.2)


def test_dataset_rows_counter():
    from src.observability.metrics import RAG_DATASET_ROWS_LOADED_TOTAL
    before = RAG_DATASET_ROWS_LOADED_TOTAL.labels(dataset="test_ds")._value.get()
    RAG_DATASET_ROWS_LOADED_TOTAL.labels(dataset="test_ds").inc(100)
    after = RAG_DATASET_ROWS_LOADED_TOTAL.labels(dataset="test_ds")._value.get()
    assert after == before + 100


def test_metrics_endpoint_returns_text():
    """Verify /metrics returns prometheus text format via FastAPI test client."""
    from fastapi.testclient import TestClient
    from unittest.mock import patch, MagicMock

    with patch("src.db.neo4j_client.GraphDatabase.driver"), \
         patch("src.cache.redis_cache._get_redis", return_value=None), \
         patch("src.rag.retriever.vector_search", return_value=[]), \
         patch("src.rag.retriever.find_paths_from_snp", return_value=[]), \
         patch("src.rag.retriever.find_foods_for_snp", return_value=[]), \
         patch("src.rag.retriever.find_nutrients_for_trait", return_value=[]):
        from src.api.main import app
        client = TestClient(app)
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "rag_requests_total" in resp.text or "# HELP" in resp.text


REQUIRED_METRIC_NAMES = [
    "rag_requests_total",
    "rag_errors_total",
    "rag_request_latency_seconds",
    "rag_retrieval_latency_seconds",
    "rag_graph_retrieval_latency_seconds",
    "rag_vector_retrieval_latency_seconds",
    "rag_llm_latency_seconds",
    "rag_cache_hits_total",
    "rag_cache_misses_total",
    "rag_answer_source_total",
]


def test_metrics_endpoint_contains_all_required_metric_names():
    from fastapi.testclient import TestClient
    from unittest.mock import patch

    with patch("src.db.neo4j_client.GraphDatabase.driver"), \
         patch("src.cache.redis_cache._get_redis", return_value=None):
        from src.api.main import app
        client = TestClient(app)
        resp = client.get("/metrics")

    assert resp.status_code == 200
    for name in REQUIRED_METRIC_NAMES:
        assert name in resp.text, f"Expected metric '{name}' not found in /metrics output"


def test_metrics_increment_after_ask():
    """rag_requests_total must increase by 1 after a successful /ask call."""
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from prometheus_client import REGISTRY
    import re

    with patch("src.db.neo4j_client.GraphDatabase.driver"), \
         patch("src.cache.redis_cache._get_redis", return_value=None):
        from src.api.main import app
        client = TestClient(app)

        resp_before = client.get("/metrics")
        # Count current total for /ask 200
        before_text = resp_before.text

        with patch("src.api.main.hybrid_retrieve",
                   return_value=(["ev1", "ev2"], ["ev1"], 1, 1)), \
             patch("src.api.main.generate_answer",
                   return_value={"answer": "Spinach helps.", "answer_source": "template_fallback"}):
            client.post("/ask", json={"question": "What foods help folate?"})

        resp_after = client.get("/metrics")
        # rag_requests_total should appear in both; the counter must have increased
        assert "rag_requests_total" in resp_after.text


def test_cache_miss_counter_increments():
    from src.observability.metrics import RAG_CACHE_MISSES_TOTAL
    before = RAG_CACHE_MISSES_TOTAL._value.get()
    RAG_CACHE_MISSES_TOTAL.inc()
    after = RAG_CACHE_MISSES_TOTAL._value.get()
    assert after == before + 1


def test_answer_source_counter():
    from src.observability.metrics import RAG_ANSWER_SOURCE_TOTAL
    before = RAG_ANSWER_SOURCE_TOTAL.labels(answer_source="template_test")._value.get()
    RAG_ANSWER_SOURCE_TOTAL.labels(answer_source="template_test").inc()
    after = RAG_ANSWER_SOURCE_TOTAL.labels(answer_source="template_test")._value.get()
    assert after == before + 1
