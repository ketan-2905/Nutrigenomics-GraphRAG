import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from src.rag.retriever import hybrid_retrieve
from src.rag.answer_generator import generate_answer
from src.graph.queries import get_graph_summary, find_paths_from_snp, find_foods_for_snp, find_nutrients_for_trait
from src.cache import redis_cache
from src.observability.metrics import (
    RAG_REQUESTS_TOTAL,
    RAG_ERRORS_TOTAL,
    RAG_REQUEST_LATENCY,
    RAG_CACHE_HITS_TOTAL,
    RAG_CACHE_MISSES_TOTAL,
    RAG_CACHE_SET_TOTAL,
    RAG_ANSWER_SOURCE_TOTAL,
)

app = FastAPI(
    title="Nutrigenomics GraphRAG MVP",
    description="SNP → Gene → Trait → Nutrient → Food graph reasoning API",
    version="2.0.0",
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


class QueryRequest(BaseModel):
    question: str


@app.get("/")
def root():
    return {"status": "ok", "project": "Nutrigenomics GraphRAG MVP", "version": "2.0.0"}


@app.get("/health")
def health():
    try:
        summary = get_graph_summary()
        cache_stats = redis_cache.get_cache_stats()
        return {"status": "ok", "graph": summary, "cache": cache_stats}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@app.post("/ask")
def ask(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    t_start = time.perf_counter()
    question = request.question

    # 1. exact cache
    cached = redis_cache.get_exact(question)
    if cached:
        RAG_CACHE_HITS_TOTAL.labels(cache_type="exact").inc()
        RAG_REQUESTS_TOTAL.labels(endpoint="/ask", status="200").inc()
        RAG_ANSWER_SOURCE_TOTAL.labels(answer_source="exact_cache").inc()
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        return {
            "question": question,
            **cached,
            "graph_evidence": [],
            "vector_evidence": [],
            "cache_hit": True,
            "metrics": {"latency_ms": latency_ms, "graph_paths": 0, "vector_chunks": 0},
        }

    # 2. semantic cache
    cached = redis_cache.get_semantic(question)
    if cached:
        RAG_CACHE_HITS_TOTAL.labels(cache_type="semantic").inc()
        RAG_REQUESTS_TOTAL.labels(endpoint="/ask", status="200").inc()
        RAG_ANSWER_SOURCE_TOTAL.labels(answer_source="semantic_cache").inc()
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        return {
            "question": question,
            **cached,
            "graph_evidence": [],
            "vector_evidence": [],
            "cache_hit": True,
            "metrics": {"latency_ms": latency_ms, "graph_paths": 0, "vector_chunks": 0},
        }

    RAG_CACHE_MISSES_TOTAL.inc()

    try:
        # 3. hybrid retrieval
        evidence, vector_docs, graph_path_count, vector_chunk_count = hybrid_retrieve(question)

        # 4. generate answer
        result = generate_answer(question, evidence)
        answer = result["answer"]
        answer_source = result.get("answer_source", "llm")

        # 5. cache result
        extra = {"answer_source": answer_source}
        stored_exact = redis_cache.set_exact(question, answer, evidence, extra)
        if stored_exact:
            RAG_CACHE_SET_TOTAL.labels(cache_type="exact").inc()
        stored_sem = redis_cache.set_semantic(question, answer, evidence, extra)
        if stored_sem:
            RAG_CACHE_SET_TOTAL.labels(cache_type="semantic").inc()

        RAG_REQUESTS_TOTAL.labels(endpoint="/ask", status="200").inc()
        RAG_ANSWER_SOURCE_TOTAL.labels(answer_source=answer_source).inc()
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        RAG_REQUEST_LATENCY.labels(endpoint="/ask").observe(latency_ms / 1000)

        return {
            "question": question,
            "answer": answer,
            "evidence": evidence,
            "graph_evidence": [e for e in evidence if e not in vector_docs],
            "vector_evidence": vector_docs,
            "answer_source": answer_source,
            "cache_hit": False,
            "metrics": {
                "latency_ms": latency_ms,
                "graph_paths": graph_path_count,
                "vector_chunks": vector_chunk_count,
            },
        }

    except Exception as e:
        RAG_ERRORS_TOTAL.labels(endpoint="/ask").inc()
        RAG_REQUESTS_TOTAL.labels(endpoint="/ask", status="500").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/snp/{snp_id}/paths")
def snp_paths(snp_id: str):
    return {"snp_id": snp_id, "paths": find_paths_from_snp(snp_id)}


@app.get("/snp/{snp_id}/foods")
def snp_foods(snp_id: str):
    return {"snp_id": snp_id, "foods": find_foods_for_snp(snp_id)}


@app.get("/trait/{trait_name}/nutrients")
def trait_nutrients(trait_name: str):
    return {"trait": trait_name, "nutrients": find_nutrients_for_trait(trait_name)}


@app.get("/graph/summary")
def graph_summary():
    return get_graph_summary()


@app.get("/cache/stats")
def cache_stats():
    return redis_cache.get_cache_stats()


@app.post("/cache/clear")
def cache_clear():
    result = redis_cache.clear_cache()
    return result


@app.get("/data/sources")
def data_sources():
    import os, csv
    sources = []
    files = {
        "seed_edges": "data/seed/seed_edges.csv",
        "gwas_filtered": "data/processed/gwas_filtered.csv",
        "clinvar_filtered": "data/processed/clinvar_filtered.csv",
        "food_nutrients": "data/processed/food_nutrients.csv",
        "pubmed_evidence": "data/processed/pubmed_evidence.csv",
    }
    for name, path in files.items():
        if os.path.exists(path):
            try:
                with open(path) as f:
                    row_count = sum(1 for _ in f) - 1
                sources.append({"dataset": name, "path": path, "rows": row_count, "loaded": True})
            except Exception:
                sources.append({"dataset": name, "path": path, "rows": -1, "loaded": True})
        else:
            sources.append({"dataset": name, "path": path, "rows": 0, "loaded": False})
    return {"sources": sources}
