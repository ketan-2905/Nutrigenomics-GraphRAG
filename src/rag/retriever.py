import os
import re
import time
import chromadb
from src.graph.queries import find_paths_from_snp, find_foods_for_snp, find_nutrients_for_trait
from src.observability.metrics import (
    RAG_GRAPH_RETRIEVAL_LATENCY,
    RAG_VECTOR_RETRIEVAL_LATENCY,
    RAG_RETRIEVAL_LATENCY,
    RAG_GRAPH_PATHS_RETURNED,
    RAG_VECTOR_CHUNKS_RETURNED,
)


def vector_search(query: str, k: int = 5) -> list[str]:
    t0 = time.perf_counter()
    try:
        chroma_path = os.getenv("CHROMA_PATH", "./chroma_db")
        client = chromadb.PersistentClient(path=chroma_path)
        try:
            collection = client.get_collection("graph_evidence")
        except Exception:
            return []
        results = collection.query(query_texts=[query], n_results=k)
        docs = results["documents"][0] if results["documents"] else []
    except Exception:
        docs = []
    finally:
        RAG_VECTOR_RETRIEVAL_LATENCY.observe(time.perf_counter() - t0)
    RAG_VECTOR_CHUNKS_RETURNED.observe(len(docs))
    return docs


def extract_snp_id(query: str):
    match = re.search(r"rs\d+", query, re.IGNORECASE)
    return match.group(0).lower() if match else None


def extract_trait(query: str):
    trait_keywords = {
        "folate": "Folate metabolism",
        "homocysteine": "High homocysteine",
        "cardiovascular": "Cardiovascular risk",
        "glucose": "Glucose metabolism",
        "diabetes": "Type 2 diabetes risk",
        "appetite": "Appetite regulation",
        "lipid": "Lipid metabolism",
        "caffeine": "Caffeine metabolism",
    }
    query_lower = query.lower()
    for keyword, trait in trait_keywords.items():
        if keyword in query_lower:
            return trait
    return None


def hybrid_retrieve(query: str) -> tuple[list[str], list[str], int, int]:
    """Returns (all_evidence, vector_docs, graph_path_count, vector_chunk_count)."""
    t0 = time.perf_counter()
    evidence = []
    vector_docs = []
    graph_path_count = 0

    try:
        vector_docs = vector_search(query)
    except Exception:
        vector_docs = []
    evidence.extend(vector_docs)

    t_graph = time.perf_counter()
    snp_id = extract_snp_id(query)
    if snp_id:
        try:
            graph_paths = find_paths_from_snp(snp_id)
            graph_path_count += len(graph_paths)
            if graph_paths:
                evidence.append(f"Graph paths found for {snp_id}: {len(graph_paths)} paths.")
            foods = find_foods_for_snp(snp_id)
            graph_path_count += len(foods)
            for f in foods[:5]:
                path_str = " -> ".join(f.get("path_nodes", []))
                evidence.append(f"Food connected to {snp_id}: {f['food']} via path {path_str}")
        except Exception:
            pass

    trait = extract_trait(query)
    if trait:
        try:
            nutrients = find_nutrients_for_trait(trait)
            graph_path_count += len(nutrients)
            for n in nutrients[:5]:
                evidence.append(f"Nutrient supporting {trait}: {n['nutrient']}")
        except Exception:
            pass

    RAG_GRAPH_RETRIEVAL_LATENCY.observe(time.perf_counter() - t_graph)
    RAG_RETRIEVAL_LATENCY.observe(time.perf_counter() - t0)
    RAG_GRAPH_PATHS_RETURNED.observe(graph_path_count)

    return evidence, vector_docs, graph_path_count, len(vector_docs)
