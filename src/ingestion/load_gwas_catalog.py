import io
import os
import zipfile
import pandas as pd
import requests
from datetime import datetime, timezone
from src.db.neo4j_client import Neo4jClient
from src.observability.metrics import RAG_DATASET_ROWS_LOADED_TOTAL

MVP_GENES = {
    "MTHFR", "TCF7L2", "FTO", "APOE", "APOA5", "CYP1A2", "ADH1B",
    "FADS1", "FUT2", "MCM6", "IL6", "HFE", "SLC30A8", "MC4R",
}

GWAS_CATALOG_URL = os.getenv(
    "GWAS_CATALOG_URL",
    "https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest/gwas-catalog-associations-full.zip",
)
GWAS_MAX_ROWS = int(os.getenv("GWAS_MAX_ROWS", "5000"))
RAW_FILE = "data/raw/gwas_catalog_associations.zip"
OUTPUT_FILE = "data/processed/gwas_filtered.csv"
SOURCE_NAME = "GWAS Catalog"


def download_gwas():
    os.makedirs("data/raw", exist_ok=True)
    url = GWAS_CATALOG_URL
    print(f"Downloading GWAS Catalog from {url} ...")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(RAW_FILE, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
    print(f"Saved to {RAW_FILE}")


def filter_gwas() -> pd.DataFrame:
    if not os.path.exists(RAW_FILE):
        download_gwas()

    print("Extracting and filtering GWAS associations...")
    with zipfile.ZipFile(RAW_FILE) as zf:
        tsv_names = [n for n in zf.namelist() if n.endswith(".tsv")]
        if not tsv_names:
            raise RuntimeError(f"No TSV found inside {RAW_FILE}: {zf.namelist()}")
        tsv_name = tsv_names[0]
        with zf.open(tsv_name) as f:
            df = pd.read_csv(
                io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                sep="\t",
                low_memory=False,
                nrows=GWAS_MAX_ROWS,
            )

    keep_cols = ["SNPS", "MAPPED_GENE", "DISEASE/TRAIT", "P-VALUE", "PUBMEDID", "STUDY ACCESSION"]
    df = df[[c for c in keep_cols if c in df.columns]]
    df = df[df["MAPPED_GENE"].astype(str).isin(MVP_GENES)].copy()
    df["source_name"] = SOURCE_NAME
    df["source_url"] = GWAS_CATALOG_URL
    df["retrieved_at"] = datetime.now(timezone.utc).isoformat()

    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Filtered {len(df)} GWAS rows -> {OUTPUT_FILE}")
    return df


def load_gwas_to_graph():
    if not os.path.exists(OUTPUT_FILE):
        filter_gwas()

    df = pd.read_csv(OUTPUT_FILE)
    db = Neo4jClient()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    count = 0

    for _, row in df.iterrows():
        snp = str(row.get("SNPS", "")).strip()
        gene = str(row.get("MAPPED_GENE", "")).strip()
        trait = str(row.get("DISEASE/TRAIT", "")).strip()
        p_value = str(row.get("P-VALUE", "")).strip()
        pmid = str(row.get("PUBMEDID", "")).strip()

        if not snp or not gene or not trait or snp == "nan":
            continue

        db.run("MERGE (s:SNP {id:$snp})", {"snp": snp})
        db.run("MERGE (g:Gene {id:$gene})", {"gene": gene})
        db.run("MERGE (t:Trait {id:$trait})", {"trait": trait})

        db.run("""
        MATCH (s:SNP {id:$snp}) MATCH (g:Gene {id:$gene})
        MERGE (s)-[r:RELATED {type:'LOCATED_IN'}]->(g)
        SET r.source_name=$source_name, r.source_url=$source_url, r.retrieved_at=$retrieved_at,
            r.evidence_level='GWAS'
        """, {"snp": snp, "gene": gene, "source_name": SOURCE_NAME,
              "source_url": GWAS_CATALOG_URL, "retrieved_at": retrieved_at})

        db.run("""
        MATCH (s:SNP {id:$snp}) MATCH (t:Trait {id:$trait})
        MERGE (s)-[r:RELATED {type:'ASSOCIATED_WITH'}]->(t)
        SET r.p_value=$p_value, r.source_name=$source_name, r.source_url=$source_url,
            r.retrieved_at=$retrieved_at, r.evidence_level='GWAS'
        """, {"snp": snp, "trait": trait, "p_value": p_value,
              "source_name": SOURCE_NAME, "source_url": GWAS_CATALOG_URL, "retrieved_at": retrieved_at})

        if pmid and pmid != "nan":
            db.run("MERGE (p:Publication {pmid:$pmid})", {"pmid": pmid})
            db.run("""
            MATCH (t:Trait {id:$trait}) MATCH (p:Publication {pmid:$pmid})
            MERGE (t)-[:RELATED {type:'SUPPORTED_BY'}]->(p)
            """, {"trait": trait, "pmid": pmid})

        count += 1

    db.close()
    RAG_DATASET_ROWS_LOADED_TOTAL.labels(dataset="gwas").inc(count)
    print(f"Loaded {count} GWAS rows into graph.")


if __name__ == "__main__":
    filter_gwas()
    load_gwas_to_graph()
