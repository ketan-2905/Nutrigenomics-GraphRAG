import pytest
import pandas as pd
import gzip
from unittest.mock import patch, MagicMock

REQUIRED_PROVENANCE = ["source_name", "source_url", "retrieved_at"]

GWAS_SAMPLE = (
    "SNPS\tMAPPED_GENE\tDISEASE/TRAIT\tP-VALUE\tPUBMEDID\n"
    "rs1801133\tMTHFR\tFolate levels\t5e-8\t12345678\n"
)

CLINVAR_SAMPLE = (
    "Name\tGeneSymbol\tClinicalSignificance\tPhenotypeList\tReviewStatus\tRS# (dbSNP)\n"
    "NM_005957.4(MTHFR)\tMTHFR\tPathogenic\tHomocystinuria\tcriteria provided\t1801133\n"
)

USDA_MOCK = {
    "foods": [{
        "fdcId": 123,
        "description": "Spinach, raw",
        "foodNutrients": [
            {"nutrientName": "Folate, DFE", "value": 194.0, "unitName": "UG"},
        ],
    }]
}


def test_gwas_provenance_fields(tmp_path):
    raw = tmp_path / "gwas_catalog_full.tsv"
    raw.write_text(GWAS_SAMPLE)
    with patch("src.ingestion.load_gwas_catalog.RAW_FILE", str(raw)), \
         patch("src.ingestion.load_gwas_catalog.OUTPUT_FILE", str(tmp_path / "out.csv")):
        from src.ingestion.load_gwas_catalog import filter_gwas
        df = filter_gwas()

    for field in REQUIRED_PROVENANCE:
        assert field in df.columns, f"Missing provenance field: {field}"
    assert df["source_name"].iloc[0] == "GWAS Catalog"
    assert "ebi.ac.uk" in df["source_url"].iloc[0]


def test_clinvar_provenance_fields(tmp_path):
    raw = tmp_path / "variant_summary.txt.gz"
    with gzip.open(str(raw), "wt") as f:
        f.write(CLINVAR_SAMPLE)
    with patch("src.ingestion.load_clinvar.RAW_FILE", str(raw)), \
         patch("src.ingestion.load_clinvar.OUTPUT_FILE", str(tmp_path / "out.csv")):
        from src.ingestion.load_clinvar import filter_clinvar
        df = filter_clinvar()

    for field in REQUIRED_PROVENANCE:
        assert field in df.columns, f"Missing provenance field: {field}"
    assert df["source_name"].iloc[0] == "NCBI ClinVar"
    assert "clinical_significance" in df.columns or "ClinicalSignificance" in df.columns


def test_clinvar_includes_clinical_significance(tmp_path):
    raw = tmp_path / "variant_summary.txt.gz"
    with gzip.open(str(raw), "wt") as f:
        f.write(CLINVAR_SAMPLE)
    with patch("src.ingestion.load_clinvar.RAW_FILE", str(raw)), \
         patch("src.ingestion.load_clinvar.OUTPUT_FILE", str(tmp_path / "out.csv")):
        from src.ingestion.load_clinvar import filter_clinvar
        df = filter_clinvar()

    assert "ClinicalSignificance" in df.columns
    assert "ReviewStatus" in df.columns


def test_usda_provenance_fields(tmp_path):
    with patch("src.ingestion.load_fooddata.FDC_API_KEY", "test_key"), \
         patch("src.ingestion.load_fooddata.OUTPUT_FILE", str(tmp_path / "out.csv")), \
         patch("src.ingestion.load_fooddata.TARGET_FOODS", ["spinach"]), \
         patch("requests.get") as mock_get:

        mock_get.return_value.json.return_value = USDA_MOCK
        mock_get.return_value.raise_for_status = MagicMock()

        from src.ingestion.load_fooddata import fetch_all
        df = fetch_all()

    for field in REQUIRED_PROVENANCE:
        assert field in df.columns, f"Missing provenance field: {field}"
    assert "fdc_id" in df.columns
    assert "amount" in df.columns
    assert "unit" in df.columns
    assert df["source_name"].iloc[0] == "USDA FoodData Central"


def test_usda_includes_fdc_id(tmp_path):
    with patch("src.ingestion.load_fooddata.FDC_API_KEY", "test_key"), \
         patch("src.ingestion.load_fooddata.OUTPUT_FILE", str(tmp_path / "out.csv")), \
         patch("src.ingestion.load_fooddata.TARGET_FOODS", ["spinach"]), \
         patch("requests.get") as mock_get:

        mock_get.return_value.json.return_value = USDA_MOCK
        mock_get.return_value.raise_for_status = MagicMock()

        from src.ingestion.load_fooddata import fetch_all
        df = fetch_all()

    assert int(df["fdc_id"].iloc[0]) == 123


# ── PubMed provenance ─────────────────────────────────────────────────────────

ESEARCH_RESP = {"esearchresult": {"idlist": ["12345678"]}}
ESUMMARY_RESP = {
    "result": {
        "uids": ["12345678"],
        "12345678": {"title": "MTHFR and folate", "pubdate": "2020 Jan"},
    }
}


def test_pubmed_provenance_fields(tmp_path):
    def _mock_get(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = ESEARCH_RESP if "esearch" in url else ESUMMARY_RESP
        return m

    with patch("requests.get", side_effect=_mock_get), \
         patch("src.ingestion.load_pubmed_evidence.OUTPUT_FILE", str(tmp_path / "pub.csv")), \
         patch("src.ingestion.load_pubmed_evidence.SEARCH_QUERIES", [("MTHFR", "MTHFR folate")]):
        from src.ingestion.load_pubmed_evidence import fetch_all_pubmed
        df = fetch_all_pubmed()

    for field in REQUIRED_PROVENANCE:
        assert field in df.columns, f"Missing provenance field: {field}"
    assert df["source_name"].iloc[0] == "NCBI PubMed"
    assert "pubmed.ncbi.nlm.nih.gov" in df["source_url"].iloc[0]


def test_pubmed_includes_pmid_title_year(tmp_path):
    def _mock_get(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = ESEARCH_RESP if "esearch" in url else ESUMMARY_RESP
        return m

    with patch("requests.get", side_effect=_mock_get), \
         patch("src.ingestion.load_pubmed_evidence.OUTPUT_FILE", str(tmp_path / "pub.csv")), \
         patch("src.ingestion.load_pubmed_evidence.SEARCH_QUERIES", [("MTHFR", "MTHFR folate")]):
        from src.ingestion.load_pubmed_evidence import fetch_all_pubmed
        df = fetch_all_pubmed()

    assert "pmid" in df.columns
    assert "title" in df.columns
    assert "year" in df.columns
    assert df["pmid"].iloc[0] == "12345678"
    assert df["year"].iloc[0] == "2020"


# ── GWAS has p_value and pmid ─────────────────────────────────────────────────

def test_gwas_has_p_value_and_pmid(tmp_path):
    raw = tmp_path / "gwas_catalog_full.tsv"
    raw.write_text(
        "SNPS\tMAPPED_GENE\tDISEASE/TRAIT\tP-VALUE\tPUBMEDID\n"
        "rs1801133\tMTHFR\tFolate levels\t5e-8\t12345678\n"
    )
    with patch("src.ingestion.load_gwas_catalog.RAW_FILE", str(raw)), \
         patch("src.ingestion.load_gwas_catalog.OUTPUT_FILE", str(tmp_path / "out.csv")):
        from src.ingestion.load_gwas_catalog import filter_gwas
        df = filter_gwas()

    assert "P-VALUE" in df.columns or "p_value" in df.columns
    assert "PUBMEDID" in df.columns or "pmid" in df.columns
