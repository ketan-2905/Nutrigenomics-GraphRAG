from prometheus_client import Counter, Histogram, Gauge

RAG_REQUESTS_TOTAL = Counter(
    "rag_requests_total",
    "Total number of RAG /ask requests",
    ["endpoint", "status"],
)

RAG_ERRORS_TOTAL = Counter(
    "rag_errors_total",
    "Total number of RAG errors",
    ["endpoint"],
)

RAG_REQUEST_LATENCY = Histogram(
    "rag_request_latency_seconds",
    "End-to-end /ask request latency in seconds",
    ["endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

RAG_RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_latency_seconds",
    "Total hybrid retrieval latency in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

RAG_GRAPH_RETRIEVAL_LATENCY = Histogram(
    "rag_graph_retrieval_latency_seconds",
    "Neo4j graph traversal latency in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

RAG_VECTOR_RETRIEVAL_LATENCY = Histogram(
    "rag_vector_retrieval_latency_seconds",
    "ChromaDB vector search latency in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

RAG_LLM_LATENCY = Histogram(
    "rag_llm_latency_seconds",
    "LLM generation latency in seconds",
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

RAG_CACHE_HITS_TOTAL = Counter(
    "rag_cache_hits_total",
    "Total cache hits",
    ["cache_type"],
)

RAG_CACHE_MISSES_TOTAL = Counter(
    "rag_cache_misses_total",
    "Total cache misses",
)

RAG_CACHE_SET_TOTAL = Counter(
    "rag_cache_set_total",
    "Total cache set operations",
    ["cache_type"],
)

RAG_CACHE_ERRORS_TOTAL = Counter(
    "rag_cache_errors_total",
    "Total cache errors",
)

RAG_GRAPH_PATHS_RETURNED = Histogram(
    "rag_graph_paths_returned",
    "Number of graph paths returned per request",
    buckets=[0, 1, 2, 5, 10, 20, 50],
)

RAG_VECTOR_CHUNKS_RETURNED = Histogram(
    "rag_vector_chunks_returned",
    "Number of vector chunks returned per request",
    buckets=[0, 1, 2, 5, 10, 20],
)

RAG_EVIDENCE_CHUNKS_INDEXED_TOTAL = Gauge(
    "rag_evidence_chunks_indexed_total",
    "Total number of evidence chunks currently indexed in ChromaDB",
)

RAG_DATASET_ROWS_LOADED_TOTAL = Counter(
    "rag_dataset_rows_loaded_total",
    "Total number of dataset rows loaded into the graph",
    ["dataset"],
)

RAG_ANSWER_SOURCE_TOTAL = Counter(
    "rag_answer_source_total",
    "Count of answers by source",
    ["answer_source"],
)

RAG_LLM_TOKENS_TOTAL = Counter(
    "rag_llm_tokens_total",
    "Total LLM tokens used",
    ["type"],  # prompt / completion
)
