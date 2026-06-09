import io
import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


# ── GWAS Catalog ──────────────────────────────────────────────────────────────

GWAS_SAMPLE = """SNPS\tMAPPED_GENE\tDISEASE/TRAIT\tP-VALUE\tPUBMEDID
rs1801133\tMTHFR\tFolate levels\t5e-8\t12345678
rs7903146\tTCF7L2\tType 2 diabetes\t1e-10\t87654321
rs99999\tUNKNOWN_GENE\tSome trait\t0.05\t11111111
"""


def test_gwas_filter_keeps_mvp_genes(tmp_path):
    raw = tmp_path / "gwas_catalog_full.tsv"
    raw.write_text(GWAS_SAMPLE)

    with patch("src.ingestion.load_gwas_catalog.RAW_FILE", str(raw)), \
         patch("src.ingestion.load_gwas_catalog.OUTPUT_FILE", str(tmp_path / "gwas_filtered.csv")):
        from src.ingestion.load_gwas_catalog import filter_gwas
        df = filter_gwas()

    assert len(df) == 2
    assert set(df["MAPPED_GENE"].tolist()) == {"MTHFR", "TCF7L2"}


def test_gwas_filter_has_provenance(tmp_path):
    raw = tmp_path / "gwas_catalog_full.tsv"
    raw.write_text(GWAS_SAMPLE)

    with patch("src.ingestion.load_gwas_catalog.RAW_FILE", str(raw)), \
         patch("src.ingestion.load_gwas_catalog.OUTPUT_FILE", str(tmp_path / "gwas_filtered.csv")):
        from src.ingestion.load_gwas_catalog import filter_gwas
        df = filter_gwas()

    assert "source_name" in df.columns
    assert "source_url" in df.columns
    assert "retrieved_at" in df.columns
    assert (df["source_name"] == "GWAS Catalog").all()


# ── ClinVar ───────────────────────────────────────────────────────────────────

CLINVAR_SAMPLE = """Name\tGeneSymbol\tClinicalSignificance\tPhenotypeList\tReviewStatus\tRS# (dbSNP)
NM_005957.4(MTHFR):c.665C>T\tMTHFR\tPathogenic\tHomocystinuria\tcriteria provided\t1801133
NM_000179.3(MSH6):c.3226C>T\tMSH6\tLikely pathogenic\tLynch syndrome\tcriteria provided\t267608234
"""

import gzip


def _make_gz(content: str, path: str):
    with gzip.open(path, "wt") as f:
        f.write(content)


def test_clinvar_filter_keeps_mvp_genes(tmp_path):
    raw = tmp_path / "variant_summary.txt.gz"
    _make_gz(CLINVAR_SAMPLE, str(raw))

    with patch("src.ingestion.load_clinvar.RAW_FILE", str(raw)), \
         patch("src.ingestion.load_clinvar.OUTPUT_FILE", str(tmp_path / "clinvar_filtered.csv")):
        from src.ingestion.load_clinvar import filter_clinvar
        df = filter_clinvar()

    assert len(df) == 1
    assert df.iloc[0]["GeneSymbol"] == "MTHFR"


def test_clinvar_filter_has_provenance(tmp_path):
    raw = tmp_path / "variant_summary.txt.gz"
    _make_gz(CLINVAR_SAMPLE, str(raw))

    with patch("src.ingestion.load_clinvar.RAW_FILE", str(raw)), \
         patch("src.ingestion.load_clinvar.OUTPUT_FILE", str(tmp_path / "clinvar_filtered.csv")):
        from src.ingestion.load_clinvar import filter_clinvar
        df = filter_clinvar()

    assert "source_name" in df.columns
    assert df.iloc[0]["source_name"] == "NCBI ClinVar"


def test_clinvar_extracts_significance(tmp_path):
    raw = tmp_path / "variant_summary.txt.gz"
    _make_gz(CLINVAR_SAMPLE, str(raw))

    with patch("src.ingestion.load_clinvar.RAW_FILE", str(raw)), \
         patch("src.ingestion.load_clinvar.OUTPUT_FILE", str(tmp_path / "clinvar_filtered.csv")):
        from src.ingestion.load_clinvar import filter_clinvar
        df = filter_clinvar()

    assert df.iloc[0]["ClinicalSignificance"] == "Pathogenic"


# ── USDA FoodData ─────────────────────────────────────────────────────────────

USDA_MOCK_RESPONSE = {
    "foods": [{
        "fdcId": 747447,
        "description": "Spinach, raw",
        "foodNutrients": [
            {"nutrientName": "Folate, DFE", "value": 194.0, "unitName": "UG"},
            {"nutrientName": "Magnesium, Mg", "value": 79.0, "unitName": "MG"},
        ]
    }]
}


def test_usda_loader_maps_food_to_nutrients(tmp_path):
    with patch("src.ingestion.load_fooddata.FDC_API_KEY", "test_key"), \
         patch("src.ingestion.load_fooddata.OUTPUT_FILE", str(tmp_path / "food_nutrients.csv")), \
         patch("src.ingestion.load_fooddata.TARGET_FOODS", ["spinach"]), \
         patch("requests.get") as mock_get:

        mock_get.return_value.json.return_value = USDA_MOCK_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        from src.ingestion.load_fooddata import fetch_all
        df = fetch_all()

    assert len(df) == 2
    assert set(df["nutrient_name"].tolist()) == {"Folate, DFE", "Magnesium, Mg"}
    assert (df["food_name"] == "spinach").all()


def test_usda_loader_has_provenance(tmp_path):
    with patch("src.ingestion.load_fooddata.FDC_API_KEY", "test_key"), \
         patch("src.ingestion.load_fooddata.OUTPUT_FILE", str(tmp_path / "food_nutrients.csv")), \
         patch("src.ingestion.load_fooddata.TARGET_FOODS", ["spinach"]), \
         patch("requests.get") as mock_get:

        mock_get.return_value.json.return_value = USDA_MOCK_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        from src.ingestion.load_fooddata import fetch_all
        df = fetch_all()

    assert "fdc_id" in df.columns
    assert "source_name" in df.columns
    assert "retrieved_at" in df.columns


def test_usda_loader_skips_without_api_key(tmp_path):
    with patch("src.ingestion.load_fooddata.FDC_API_KEY", None), \
         patch("src.ingestion.load_fooddata.OUTPUT_FILE", str(tmp_path / "food_nutrients.csv")):
        from src.ingestion.load_fooddata import fetch_all
        df = fetch_all()

    assert df.empty


# ── PubMed ────────────────────────────────────────────────────────────────────

ESEARCH_RESPONSE = {
    "esearchresult": {"idlist": ["12345678"]}
}

ESUMMARY_RESPONSE = {
    "result": {
        "uids": ["12345678"],
        "12345678": {
            "title": "MTHFR variants and folate status",
            "pubdate": "2020 Jan 15",
        },
    }
}


def test_pubmed_search_returns_pmids():
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = ESEARCH_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        from src.ingestion.load_pubmed_evidence import search_pubmed
        pmids = search_pubmed("MTHFR folate homocysteine")

    assert pmids == ["12345678"]


def test_pubmed_fetch_summary_extracts_fields():
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = ESUMMARY_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        from src.ingestion.load_pubmed_evidence import fetch_summary
        results = fetch_summary(["12345678"])

    assert len(results) == 1
    assert results[0]["pmid"] == "12345678"
    assert results[0]["title"] == "MTHFR variants and folate status"
    assert results[0]["year"] == "2020"


def test_pubmed_fetch_all_has_provenance(tmp_path):
    def _mock_get(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = MagicMock()
        if "esearch" in url:
            m.json.return_value = ESEARCH_RESPONSE
        else:
            m.json.return_value = ESUMMARY_RESPONSE
        return m

    with patch("requests.get", side_effect=_mock_get), \
         patch("src.ingestion.load_pubmed_evidence.OUTPUT_FILE", str(tmp_path / "pubmed.csv")), \
         patch("src.ingestion.load_pubmed_evidence.SEARCH_QUERIES", [("MTHFR", "MTHFR folate")]):
        from src.ingestion.load_pubmed_evidence import fetch_all_pubmed
        df = fetch_all_pubmed()

    assert not df.empty
    for field in ("pmid", "title", "year", "source_name", "source_url", "retrieved_at"):
        assert field in df.columns, f"Missing column: {field}"
    assert df.iloc[0]["source_name"] == "NCBI PubMed"
    assert "pubmed.ncbi.nlm.nih.gov" in df.iloc[0]["source_url"]
