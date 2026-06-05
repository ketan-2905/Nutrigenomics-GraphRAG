import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
SEMANTIC_DISTANCE_THRESHOLD = float(os.getenv("SEMANTIC_CACHE_DISTANCE_THRESHOLD", "0.12"))
CACHE_NAMESPACE = os.getenv("CACHE_NAMESPACE", "nutrigenomics_graphrag")
DATASET_VERSION = os.getenv("DATASET_VERSION", "v1")


def _cache_enabled() -> bool:
    return os.getenv("ENABLE_REDIS_CACHE", "true").lower() == "true"


def _semantic_cache_enabled() -> bool:
    return os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() == "true"


_UNSAFE_PATTERNS = [
    "insufficient evidence",
    "llm api key not configured",
    "llm error",
    "cannot connect",
    "no evidence",
]


def _normalize(question: str) -> str:
    return re.sub(r"\s+", " ", question.lower().strip())


def _exact_key(normalized: str) -> str:
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return f"{CACHE_NAMESPACE}:exact:{DATASET_VERSION}:{digest}"


def _is_cacheable(answer: str, evidence: list) -> bool:
    if not evidence:
        return False
    answer_lower = answer.lower()
    for pattern in _UNSAFE_PATTERNS:
        if pattern in answer_lower:
            return False
    return True


def _get_redis():
    try:
        import redis as redis_lib
        client = redis_lib.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        return None


def _get_semantic_cache():
    if not _semantic_cache_enabled():
        return None
    try:
        from redisvl.extensions.cache.llm import SemanticCache
        cache = SemanticCache(
            name=f"{CACHE_NAMESPACE}:semantic:{DATASET_VERSION}",
            redis_url=REDIS_URL,
            distance_threshold=SEMANTIC_DISTANCE_THRESHOLD,
        )
        return cache
    except Exception:
        return None


def get_exact(question: str) -> Optional[dict]:
    if not _cache_enabled():
        return None
    client = _get_redis()
    if not client:
        return None
    try:
        key = _exact_key(_normalize(question))
        raw = client.get(key)
        if raw:
            data = json.loads(raw)
            data["answer_source"] = "exact_cache"
            data["cache_hit"] = True
            return data
    except Exception:
        pass
    return None


def set_exact(question: str, answer: str, evidence: list, extra: dict = None) -> bool:
    if not _cache_enabled():
        return False
    if not _is_cacheable(answer, evidence):
        return False
    client = _get_redis()
    if not client:
        return False
    try:
        key = _exact_key(_normalize(question))
        payload = {
            "answer": answer,
            "evidence": evidence,
            "dataset_version": DATASET_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **(extra or {}),
        }
        client.setex(key, CACHE_TTL_SECONDS, json.dumps(payload))
        return True
    except Exception:
        return False


def get_semantic(question: str) -> Optional[dict]:
    if not _cache_enabled() or not _semantic_cache_enabled():
        return None
    cache = _get_semantic_cache()
    if not cache:
        return None
    try:
        results = cache.check(prompt=question)
        if results:
            hit = results[0]
            response_str = hit.get("response", "{}")
            data = json.loads(response_str) if isinstance(response_str, str) else response_str
            data["answer_source"] = "semantic_cache"
            data["cache_hit"] = True
            return data
    except Exception:
        pass
    return None


def set_semantic(question: str, answer: str, evidence: list, extra: dict = None) -> bool:
    if not _cache_enabled() or not _semantic_cache_enabled():
        return False
    if not _is_cacheable(answer, evidence):
        return False
    cache = _get_semantic_cache()
    if not cache:
        return False
    try:
        payload = {
            "answer": answer,
            "evidence": evidence,
            "dataset_version": DATASET_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **(extra or {}),
        }
        cache.store(prompt=question, response=json.dumps(payload))
        return True
    except Exception:
        return False


def get_cache_stats() -> dict:
    stats = {
        "redis_connected": False,
        "semantic_cache_enabled": _semantic_cache_enabled(),
        "exact_cache_enabled": _cache_enabled(),
        "dataset_version": DATASET_VERSION,
        "ttl_seconds": CACHE_TTL_SECONDS,
    }
    client = _get_redis()
    if client:
        stats["redis_connected"] = True
        try:
            info = client.info("keyspace")
            stats["keyspace"] = info
        except Exception:
            pass
    return stats


def clear_cache(namespace: str = None) -> dict:
    client = _get_redis()
    if not client:
        return {"cleared": 0, "error": "Redis not connected"}
    ns = namespace or CACHE_NAMESPACE
    pattern = f"{ns}:*"
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
        return {"cleared": len(keys), "pattern": pattern}
    except Exception as e:
        return {"cleared": 0, "error": str(e)}
