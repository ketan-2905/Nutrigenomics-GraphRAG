import os
import subprocess
import pandas as pd
from datetime import datetime, timezone
from src.db.neo4j_client import Neo4jClient
from src.observability.metrics import RAG_DATASET_ROWS_LOADED_TOTAL

MVP_GENES = {
    "MTHFR", "TCF7L2", "FTO", "APOE", "APOA5", "CYP1A2", "ADH1B",
    "FADS1", "FUT2", "MCM6", "IL6", "HFE", "SLC30A8", "MC4R",
}

CLINVAR_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
RAW_FILE = "data/raw/variant_summary.txt.gz"
OUTPUT_FILE = "data/processed/clinvar_filtered.csv"
KEEP_COLS = ["Name", "GeneSymbol", "ClinicalSignificance", "PhenotypeList", "ReviewStatus", "RS# (dbSNP)"]
SOURCE_NAME = "NCBI ClinVar"
SOURCE_URL = CLINVAR_URL


def download_clinvar():
    os.makedirs("data/raw", exist_ok=True)
    print(f"Downloading ClinVar from {CLINVAR_URL} ...")
    subprocess.run(
        ["curl", "-L", "-o", RAW_FILE, CLINVAR_URL],
        check=True,
    )
    print(f"Saved to {RAW_FILE}")


def filter_clinvar() -> pd.DataFrame:
    if not os.path.exists(RAW_FILE):
        download_clinvar()

    retrieved_at = datetime.now(timezone.utc).isoformat()
    chunks = []
    for chunk in pd.read_csv(
        RAW_FILE, sep="\t", compression="gzip", low_memory=False, chunksize=50_000
    ):
        filtered = chunk[chunk["GeneSymbol"].astype(str).isin(MVP_GENES)].copy()
        if not filtered.empty:
            chunks.append(filtered)

    df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    df = df[[c for c in KEEP_COLS if c in df.columns]]
    df["source_name"] = SOURCE_NAME
    df["source_url"] = SOURCE_URL
    df["retrieved_at"] = retrieved_at

    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Filtered {len(df)} ClinVar rows -> {OUTPUT_FILE}")
    return df


def load_clinvar_to_graph():
    if not os.path.exists(OUTPUT_FILE):
        filter_clinvar()

    df = pd.read_csv(OUTPUT_FILE)
    db = Neo4jClient()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    count = 0

    for _, row in df.iterrows():
        gene = str(row.get("GeneSymbol", "")).strip()
        phenotype = str(row.get("PhenotypeList", "")).strip()
        significance = str(row.get("ClinicalSignificance", "")).strip()
        review_status = str(row.get("ReviewStatus", "")).strip()
        rs_id = str(row.get("RS# (dbSNP)", "")).strip()

        if not gene or gene == "nan":
            continue

        db.run("MERGE (g:Gene {id:$gene})", {"gene": gene})

        if phenotype and phenotype != "nan":
            db.run("MERGE (c:Condition {id:$phenotype})", {"phenotype": phenotype})
            db.run("""
            MATCH (g:Gene {id:$gene}) MATCH (c:Condition {id:$phenotype})
            MERGE (g)-[r:RELATED {type:'HAS_CLINVAR_CONDITION'}]->(c)
            SET r.clinical_significance=$sig, r.review_status=$review_status,
                r.source_name=$source_name, r.source_url=$source_url,
                r.retrieved_at=$retrieved_at, r.evidence_level='ClinVar'
            """, {"gene": gene, "phenotype": phenotype, "sig": significance,
                  "review_status": review_status, "source_name": SOURCE_NAME,
                  "source_url": SOURCE_URL, "retrieved_at": retrieved_at})

        if rs_id and rs_id != "nan" and rs_id != "-1":
            snp_id = f"rs{rs_id}" if not rs_id.startswith("rs") else rs_id
            db.run("MERGE (s:SNP {id:$snp})", {"snp": snp_id})
            if phenotype and phenotype != "nan":
                db.run("""
                MATCH (s:SNP {id:$snp}) MATCH (c:Condition {id:$phenotype})
                MERGE (s)-[r:RELATED {type:'HAS_CLINVAR_CONDITION'}]->(c)
                SET r.clinical_significance=$sig, r.review_status=$review_status,
                    r.source_name=$source_name, r.retrieved_at=$retrieved_at,
                    r.evidence_level='ClinVar'
                """, {"snp": snp_id, "phenotype": phenotype, "sig": significance,
                      "review_status": review_status, "source_name": SOURCE_NAME,
                      "retrieved_at": retrieved_at})
        count += 1

    db.close()
    RAG_DATASET_ROWS_LOADED_TOTAL.labels(dataset="clinvar").inc(count)
    print(f"Loaded {count} ClinVar rows into graph.")


if __name__ == "__main__":
    filter_clinvar()
    load_clinvar_to_graph()
