"""Integration tests for the full seed pipeline.

These tests require Docker services (Neo4j + Redis) to be running.
They are skipped automatically when services are unreachable.

Run with:
    pytest -m integration
"""
import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Service availability guards
# ---------------------------------------------------------------------------

def _neo4j_available():
    try:
        from neo4j import GraphDatabase
        import os
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USERNAME", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "password123"),
            ),
        )
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


def _redis_available():
    try:
        import redis
        import os
        client = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=2,
        )
        client.ping()
        return True
    except Exception:
        return False


neo4j_required = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j not reachable — start with: docker compose up -d neo4j",
)
redis_required = pytest.mark.skipif(
    not _redis_available(),
    reason="Redis not reachable — start with: docker compose up -d redis",
)
all_services_required = pytest.mark.skipif(
    not (_neo4j_available() and _redis_available()),
    reason="Neo4j and/or Redis not reachable — start with: docker compose up -d neo4j redis",
)


# ---------------------------------------------------------------------------
# Neo4j connectivity
# ---------------------------------------------------------------------------

@neo4j_required
def test_neo4j_is_reachable():
    from src.db.neo4j_client import Neo4jClient
    db = Neo4jClient()
    result = db.run("RETURN 1 AS n")
    db.close()
    assert result[0]["n"] == 1


# ---------------------------------------------------------------------------
# Redis connectivity
# ---------------------------------------------------------------------------

@redis_required
def test_redis_is_reachable():
    import redis
    import os
    client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    assert client.ping()


# ---------------------------------------------------------------------------
# Seed data loading
# ---------------------------------------------------------------------------

@neo4j_required
def test_seed_data_loads():
    from src.ingestion.load_seed_data import load_seed_data
    load_seed_data()


@neo4j_required
def test_graph_has_at_least_30_edges_after_seed():
    from src.ingestion.load_seed_data import load_seed_data
    from src.graph.queries import get_graph_summary
    load_seed_data()
    summary = get_graph_summary()
    assert summary["edge_count"] >= 30, (
        f"Expected ≥30 edges after seed load but got {summary['edge_count']}"
    )


# ---------------------------------------------------------------------------
# Chroma vector index
# ---------------------------------------------------------------------------

@neo4j_required
def test_chroma_vector_index_builds(tmp_path):
    import os
    os.environ["CHROMA_PATH"] = str(tmp_path / "chroma_test")

    from src.ingestion.load_seed_data import load_seed_data
    load_seed_data()

    from src.rag.embed_chunks import build_vector_index
    build_vector_index()

    import chromadb
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma_test"))
    try:
        collection = client.get_collection("graph_evidence")
        count = collection.count()
        assert count > 0, "Chroma collection is empty after embed_all()"
    except Exception as e:
        pytest.fail(f"Chroma collection not found: {e}")


# ---------------------------------------------------------------------------
# /ask end-to-end with seed data
# ---------------------------------------------------------------------------

@all_services_required
def test_ask_end_to_end_with_seed_data():
    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)
    resp = client.post(
        "/ask",
        json={"question": "What foods may support rs1801133 related folate metabolism risk?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "evidence" in data


# ---------------------------------------------------------------------------
# /metrics
# ---------------------------------------------------------------------------

@neo4j_required
def test_metrics_endpoint_accessible():
    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "rag_requests_total" in resp.text or "# HELP" in resp.text


# ---------------------------------------------------------------------------
# Redis cache hit on repeated /ask
# ---------------------------------------------------------------------------

@all_services_required
def test_repeated_ask_shows_cache_hit():
    import os
    os.environ["ENABLE_REDIS_CACHE"] = "true"

    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.cache import redis_cache

    # Clear any stale cache entries before the test
    redis_cache.clear_cache()

    client = TestClient(app)
    question = "What foods help rs1801133 folate metabolism?"

    resp1 = client.post("/ask", json={"question": question})
    assert resp1.status_code == 200
    assert resp1.json()["cache_hit"] is False

    resp2 = client.post("/ask", json={"question": question})
    assert resp2.status_code == 200
    # Second call should hit the exact cache
    assert resp2.json()["cache_hit"] is True
