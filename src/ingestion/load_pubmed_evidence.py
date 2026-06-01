import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone
from src.db.neo4j_client import Neo4jClient
from src.observability.metrics import RAG_DATASET_ROWS_LOADED_TOTAL

NCBI_EMAIL = os.getenv("NCBI_EMAIL", "")
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
PUBMED_MAX_RESULTS = int(os.getenv("PUBMED_MAX_RESULTS", "5"))
OUTPUT_FILE = "data/processed/pubmed_evidence.csv"

SEARCH_QUERIES = [
    ("MTHFR", "MTHFR folate homocysteine"),
    ("TCF7L2", "TCF7L2 glucose metabolism diabetes"),
    ("APOE", "APOE lipid metabolism cardiovascular"),
    ("CYP1A2", "CYP1A2 caffeine metabolism"),
    ("FTO", "FTO obesity appetite regulation"),
    ("MTHFR", "MTHFR cardiovascular risk folate"),
]

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
SOURCE_NAME = "NCBI PubMed"
SOURCE_URL_TEMPLATE = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def _ncbi_params(extra: dict) -> dict:
    params = {"retmode": "json", **extra}
    if NCBI_EMAIL:
        params["email"] = NCBI_EMAIL
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    return params


def search_pubmed(query: str) -> list[str]:
    params = _ncbi_params({
        "db": "pubmed",
        "term": query,
        "retmax": PUBMED_MAX_RESULTS,
        "sort": "relevance",
    })
    resp = requests.get(ESEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("esearchresult", {}).get("idlist", [])


def fetch_summary(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    params = _ncbi_params({
        "db": "pubmed",
        "id": ",".join(pmids),
    })
    resp = requests.get(ESUMMARY_URL, params=params, timeout=15)
    resp.raise_for_status()
    result = resp.json().get("result", {})
    uids = result.get("uids", [])
    summaries = []
    for uid in uids:
        doc = result.get(uid, {})
        summaries.append({
            "pmid": uid,
            "title": doc.get("title", ""),
            "year": doc.get("pubdate", "")[:4],
        })
    return summaries


def fetch_all_pubmed() -> pd.DataFrame:
    rows = []
    retrieved_at = datetime.now(timezone.utc).isoformat()

    for gene, query in SEARCH_QUERIES:
        print(f"  Searching PubMed: {query}")
        try:
            pmids = search_pubmed(query)
            summaries = fetch_summary(pmids)
            for s in summaries:
                rows.append({
                    "gene": gene,
                    "query": query,
                    "pmid": s["pmid"],
                    "title": s["title"],
                    "year": s["year"],
                    "source_name": SOURCE_NAME,
                    "source_url": SOURCE_URL_TEMPLATE.format(pmid=s["pmid"]),
                    "retrieved_at": retrieved_at,
                })
        except Exception as e:
            print(f"  Warning: PubMed query failed for '{query}': {e}")
        # polite rate limit: 3 requests/sec without API key, 10/sec with
        time.sleep(0.4 if NCBI_API_KEY else 1.0)

    df = pd.DataFrame(rows)
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved {len(df)} PubMed records -> {OUTPUT_FILE}")
    return df


def load_pubmed_to_graph():
    if not os.path.exists(OUTPUT_FILE):
        df = fetch_all_pubmed()
        if df.empty:
            return
    else:
        df = pd.read_csv(OUTPUT_FILE)

    db = Neo4jClient()
    count = 0

    for _, row in df.iterrows():
        gene = str(row.get("gene", "")).strip()
        pmid = str(row.get("pmid", "")).strip()
        title = str(row.get("title", "")).strip()
        year = str(row.get("year", "")).strip()
        source_url = str(row.get("source_url", "")).strip()

        if not pmid or pmid == "nan":
            continue

        db.run("""
        MERGE (p:Publication {pmid:$pmid})
        SET p.title=$title, p.year=$year, p.source_name=$source_name, p.source_url=$source_url
        """, {"pmid": pmid, "title": title, "year": year,
              "source_name": SOURCE_NAME, "source_url": source_url})

        if gene and gene != "nan":
            db.run("MERGE (g:Gene {id:$gene})", {"gene": gene})
            db.run("""
            MATCH (g:Gene {id:$gene}) MATCH (p:Publication {pmid:$pmid})
            MERGE (g)-[:RELATED {type:'HAS_PUBLICATION_EVIDENCE'}]->(p)
            """, {"gene": gene, "pmid": pmid})
        count += 1

    db.close()
    RAG_DATASET_ROWS_LOADED_TOTAL.labels(dataset="pubmed").inc(count)
    print(f"Loaded {count} PubMed records into graph.")


if __name__ == "__main__":
    fetch_all_pubmed()
    load_pubmed_to_graph()
