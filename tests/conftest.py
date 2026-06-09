"""Shared fixtures and test configuration for the nutrigenomics-graphrag test suite.

Unit tests do not need Docker services; all external I/O is mocked here.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Environment — disable all external services for unit tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _unit_env(request, monkeypatch):
    """Ensure no real Redis, Neo4j, or OpenAI calls escape in unit tests.

    Integration tests bypass this fixture so they can use real services.
    """
    if request.node.get_closest_marker("integration"):
        return
    monkeypatch.setenv("ENABLE_REDIS_CACHE", "false")
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "password123")
    monkeypatch.setenv("CHROMA_PATH", "./chroma_db_test")
    monkeypatch.setenv("CACHE_NAMESPACE", "test_ns")
    monkeypatch.setenv("DATASET_VERSION", "test")


# ---------------------------------------------------------------------------
# Shared sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_gwas_rows():
    return [
        {
            "SNPS": "rs1801133",
            "MAPPED_GENE": "MTHFR",
            "DISEASE/TRAIT": "Folate levels",
            "P-VALUE": "5e-8",
            "PUBMEDID": "12345678",
            "source_name": "GWAS Catalog",
            "source_url": "https://www.ebi.ac.uk/gwas/api/search/downloads/full",
            "retrieved_at": "2026-06-11T00:00:00+00:00",
        }
    ]


@pytest.fixture()
def sample_clinvar_rows():
    return [
        {
            "GeneSymbol": "MTHFR",
            "ClinicalSignificance": "Pathogenic",
            "PhenotypeList": "Homocystinuria",
            "ReviewStatus": "criteria provided",
            "RS# (dbSNP)": "1801133",
            "source_name": "NCBI ClinVar",
            "source_url": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz",
            "retrieved_at": "2026-06-11T00:00:00+00:00",
        }
    ]


@pytest.fixture()
def sample_usda_rows():
    return [
        {
            "fdc_id": 747447,
            "food_name": "spinach",
            "nutrient_name": "Folate, DFE",
            "amount": 194.0,
            "unit": "UG",
            "source_name": "USDA FoodData Central",
            "source_url": "https://fdc.nal.usda.gov/food-details/747447/nutrients",
            "retrieved_at": "2026-06-11T00:00:00+00:00",
        }
    ]


@pytest.fixture()
def sample_pubmed_rows():
    return [
        {
            "gene": "MTHFR",
            "query": "MTHFR folate homocysteine",
            "pmid": "12345678",
            "title": "MTHFR variants and folate status",
            "year": "2020",
            "source_name": "NCBI PubMed",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "retrieved_at": "2026-06-11T00:00:00+00:00",
        }
    ]


@pytest.fixture()
def sample_evidence():
    return [
        "rs1801133 is LOCATED_IN MTHFR gene.",
        "MTHFR AFFECTS Folate metabolism.",
        "Spinach CONTAINS Folate.",
    ]


# ---------------------------------------------------------------------------
# FastAPI TestClient fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def api_client():
    """TestClient with Neo4j, Redis, Chroma all mocked out."""
    with patch("src.db.neo4j_client.GraphDatabase.driver") as mock_driver, \
         patch("src.cache.redis_cache._get_redis", return_value=None), \
         patch("src.cache.redis_cache._get_semantic_cache", return_value=None):
        mock_driver.return_value = MagicMock()
        from fastapi.testclient import TestClient
        from src.api.main import app
        yield TestClient(app)
