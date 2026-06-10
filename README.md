# Nutrigenomics GraphRAG MVP

A production-style GraphRAG system connecting SNPs, genes, traits, biomarkers, nutrients, and foods using Neo4j, ChromaDB, Redis caching, Prometheus metrics, and Grafana dashboards.

## Problem Statement

Nutrigenomics research spans genetics, metabolism, nutrition, and disease risk — but this knowledge is fragmented across databases. This project builds a hybrid GraphRAG system that traverses a structured knowledge graph and performs semantic vector search to answer questions like:

- "What foods may support a person with MTHFR-related folate metabolism risk?"
- "What biomarkers should be monitored for rs1801133?"
- "Which nutrients are connected to glucose metabolism traits?"

This is a research/demo system — **not a medical diagnosis tool**.

## Architecture

```
Seed/Public Datasets (GWAS, ClinVar, USDA, PubMed)
        ↓
Data Cleaning + Filtering + Provenance tagging
        ↓
SNP/Gene/Trait/Condition/Nutrient/Food/Publication Nodes
        ↓
Neo4j Knowledge Graph
        ↓
Graph Evidence Text
        ↓
Chroma Vector Index
        ↓
User Query
        ↓
Redis Cache (exact + semantic) ──── hit → return cached answer
        ↓ miss
Graph Traversal + Semantic Search
        ↓
Evidence Context
        ↓
LLM / Fallback Generator
        ↓
Grounded Answer + Cache write
        ↓
Prometheus Metrics → Grafana Dashboard
```

## Tech Stack

| Layer           | Tool                                         |
| --------------- | -------------------------------------------- |
| Language        | Python 3.11+                                 |
| Graph DB        | Neo4j 5 (Docker)                             |
| Vector DB       | ChromaDB                                     |
| Embeddings      | sentence-transformers                        |
| Backend         | FastAPI                                      |
| UI              | Streamlit                                    |
| Data processing | pandas                                       |
| LLM             | OpenAI API (optional, fallback included)     |
| Cache           | Redis 7 (exact + semantic via RedisVL)       |
| Observability   | Prometheus + Grafana                         |

## Quick Start (Local)

### 1. Prerequisites

- Docker Desktop running
- Python 3.11+

### 2. Clone and set up environment

```bash
cd graph-rag
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env:
#   - Add OPENAI_API_KEY if you have one (optional — fallback template works without it)
#   - Add FDC_API_KEY for USDA food data (optional)
#   - Add NCBI_EMAIL + NCBI_API_KEY for PubMed (optional)
```

### 4. Start infrastructure

```bash
docker compose up -d neo4j redis
```

Neo4j browser: http://localhost:7474 (login: neo4j / password123)

### 5. Load seed data (always required)

```bash
python -m src.ingestion.load_seed_data
```

### 6. Load real public datasets (optional but recommended)

```bash
# GWAS Catalog — downloads ~100MB automatically
python -m src.ingestion.load_gwas_catalog

# ClinVar — downloads ~500MB automatically
python -m src.ingestion.load_clinvar

# USDA FoodData Central — requires FDC_API_KEY in .env
python -m src.ingestion.load_fooddata

# PubMed evidence — optional, requires NCBI_EMAIL in .env
python -m src.ingestion.load_pubmed_evidence
```

### 7. Build vector index

```bash
python -m src.rag.embed_chunks
```

### 8. Start API

```bash
uvicorn src.api.main:app --reload --port 8000
```

### 9. Start UI (new terminal)

```bash
streamlit run src/ui/app.py
```

## Full Docker Mode

```bash
docker compose up --build
```

This starts all services: Neo4j, Redis, API, Prometheus, Grafana.

After `docker compose up --build`, you still need to load data:

```bash
# In a new terminal:
docker compose exec api python -m src.ingestion.load_seed_data
docker compose exec api python -m src.rag.embed_chunks
```

## Service URLs

| Service         | URL                         |
| --------------- | --------------------------- |
| FastAPI         | http://localhost:8000       |
| API Docs        | http://localhost:8000/docs  |
| Metrics         | http://localhost:8000/metrics |
| Streamlit UI    | http://localhost:8501       |
| Neo4j Browser   | http://localhost:7474       |
| Prometheus      | http://localhost:9090       |
| Grafana         | http://localhost:3000 (admin/admin) |
| Redis           | localhost:6379              |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/health` | Graph + cache stats |
| POST | `/ask` | Ask a question (GraphRAG) |
| GET | `/snp/{snp_id}/paths` | Graph paths from SNP |
| GET | `/snp/{snp_id}/foods` | Foods connected to SNP |
| GET | `/trait/{trait_name}/nutrients` | Nutrients for a trait |
| GET | `/graph/summary` | Node/edge counts |
| GET | `/cache/stats` | Redis cache statistics |
| POST | `/cache/clear` | Clear Redis cache |
| GET | `/data/sources` | Dataset loading status |
| GET | `/metrics` | Prometheus metrics |

### /ask response format

```json
{
  "question": "...",
  "answer": "...",
  "evidence": [],
  "graph_evidence": [],
  "vector_evidence": [],
  "answer_source": "llm|template_fallback|exact_cache|semantic_cache",
  "cache_hit": false,
  "metrics": {
    "latency_ms": 0,
    "graph_paths": 0,
    "vector_chunks": 0
  }
}
```

## Demo Questions

```
1. What foods may support rs1801133 related folate metabolism risk?
2. Which nutrients are connected to glucose metabolism?
3. What is the graph path between MTHFR and cardiovascular risk?
4. Which biomarkers are connected to folate metabolism?
5. Which foods contain nutrients linked with lipid metabolism?
6. What does CYP1A2 affect and what food is connected to it?
```

## Graph Schema

| Node      | Example           |
| --------- | ----------------- |
| SNP       | rs1801133         |
| Gene      | MTHFR             |
| Trait     | Folate metabolism |
| Condition | Homocystinuria    |
| Nutrient  | Folate            |
| Food      | Spinach           |
| Publication | PMID 12345678   |

| Relationship             | Example                        |
| ------------------------ | ------------------------------ |
| LOCATED_IN               | SNP → Gene                     |
| AFFECTS                  | Gene → Trait                   |
| ASSOCIATED_WITH          | SNP → Trait (GWAS, p-value)    |
| HAS_CLINVAR_CONDITION    | Gene/SNP → Condition           |
| RELATED_TO               | Trait → Biomarker              |
| INCREASES_RISK_OF        | Biomarker → Disease risk       |
| SUPPORTS                 | Nutrient → Trait               |
| CONTAINS                 | Food → Nutrient (USDA data)    |
| SUPPORTED_BY             | Trait → Publication            |
| HAS_PUBLICATION_EVIDENCE | Gene → Publication             |

## Data Provenance

Every real-data edge includes:

| Field               | Description                          |
| ------------------- | ------------------------------------ |
| `source_name`       | GWAS Catalog / NCBI ClinVar / USDA  |
| `source_url`        | Direct URL to source                 |
| `retrieved_at`      | ISO 8601 timestamp of ingestion      |
| `evidence_level`    | GWAS / ClinVar / USDA / Seed        |
| `p_value`           | GWAS statistical association p-value |
| `clinical_significance` | ClinVar classification           |
| `review_status`     | ClinVar review quality              |
| `fdc_id`            | USDA FoodData Central food ID       |
| `amount` / `unit`   | Nutrient quantity from USDA         |

## Prometheus Metrics (17 custom metrics)

| Metric | Type | Description |
|--------|------|-------------|
| `rag_requests_total` | Counter | Total /ask requests |
| `rag_errors_total` | Counter | Total errors |
| `rag_request_latency_seconds` | Histogram | End-to-end latency |
| `rag_retrieval_latency_seconds` | Histogram | Hybrid retrieval latency |
| `rag_graph_retrieval_latency_seconds` | Histogram | Neo4j traversal latency |
| `rag_vector_retrieval_latency_seconds` | Histogram | ChromaDB search latency |
| `rag_llm_latency_seconds` | Histogram | LLM generation latency |
| `rag_cache_hits_total` | Counter | Cache hits by type |
| `rag_cache_misses_total` | Counter | Cache misses |
| `rag_cache_set_total` | Counter | Cache writes |
| `rag_cache_errors_total` | Counter | Cache errors |
| `rag_graph_paths_returned` | Histogram | Graph paths per request |
| `rag_vector_chunks_returned` | Histogram | Vector chunks per request |
| `rag_evidence_chunks_indexed_total` | Gauge | Indexed chunk count |
| `rag_dataset_rows_loaded_total` | Counter | Rows loaded per dataset |
| `rag_answer_source_total` | Counter | Answers by source |
| `rag_llm_tokens_total` | Counter | LLM tokens used |

## Testing

### Unit Tests (no Docker or internet required)

```bash
pytest -m "not integration"
```

113 unit tests covering:
- API contract (`/health`, `/data/sources`, `/graph/summary`, `/ask` response shape)
- Redis exact + semantic cache set/get, normalization, unstorable answer filtering
- Prometheus metrics — 10+ custom metric names verified in `/metrics` output
- GWAS, ClinVar, USDA, PubMed data loaders with fixture data
- Data provenance fields (`source_name`, `source_url`, `retrieved_at`, `evidence_level`) for all loaders
- RAG hybrid retriever — SNP extraction, trait extraction, graph + vector evidence, resilience to failures
- Answer generator — template fallback, prompt safety rules, LLM mock path
- Graph query functions — dispatch, return shapes, driver connection closed

**All external services are fully mocked.** No internet, no Neo4j, no Redis, no OpenAI needed.

### Integration Tests (requires Neo4j + Redis via Docker)

```bash
docker compose up -d neo4j redis
python -m src.ingestion.load_seed_data
python -m src.rag.embed_chunks

pytest -m integration
```

Integration tests verify:
1. Neo4j is reachable
2. Redis is reachable
3. Seed data loads successfully
4. Graph has ≥30 relationships after seed load
5. Chroma vector index builds and is non-empty
6. `/ask` returns answer + evidence end-to-end
7. `/metrics` returns Prometheus output
8. Repeated `/ask` call shows `cache_hit: true` (Redis cache verified)

**Tests skip automatically with a clear message when Docker services are unavailable.**

### Smoke Test (full stack)

```bash
./scripts/smoke_test.sh
```

Starts Neo4j + Redis, loads data, starts API, then exercises `/health`, `/ask`, and `/metrics`.

### Full Docker Test

```bash
docker compose up --build
```

After containers start, load data:

```bash
docker compose exec api python -m src.ingestion.load_seed_data
docker compose exec api python -m src.rag.embed_chunks
```

Then verify:
- FastAPI: http://localhost:8000
- Metrics: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Neo4j: http://localhost:7474

### Real dataset loaders

Data loaders use trusted public sources:
- GWAS Catalog (EBI) — no key required
- NCBI ClinVar — no key required
- USDA FoodData Central — requires `FDC_API_KEY`
- NCBI PubMed — rate-limited, `NCBI_API_KEY` recommended

OpenAI key is **optional** — a template fallback generates grounded answers from evidence without any LLM call.

## Limitations

- Seed data is manually curated (~35 edges)
- Real data loaders require downloading large files (GWAS ~100MB, ClinVar ~500MB)
- Not a medical diagnosis system
- LLM answers require OpenAI API key (fallback template provided)
- SemanticCache requires RedisVL (falls back to exact cache gracefully if unavailable)

## Future Improvements

1. PubMed full-text retrieval
2. Full GWAS Catalog ingestion (beyond 5000 rows)
3. User genotype file upload
4. Personalized SNP report PDF
5. Graph visualization (Neo4j Bloom or D3.js)
6. Evaluation metrics for retrieval quality (RAGAS)
7. Multi-hop graph reasoning
8. Biomarker report integration

## Resume Description

Built a production-style Nutrigenomics GraphRAG MVP combining Neo4j knowledge graphs, ChromaDB vector search, Redis semantic caching (RedisVL), and LLM-based answer generation to connect SNPs, genes, traits, biomarkers, nutrients, and foods from GWAS Catalog, ClinVar, and USDA FoodData Central. Implemented hybrid graph + vector retrieval with full data provenance, Prometheus metrics, Grafana dashboards, and a FastAPI backend with Streamlit UI.
