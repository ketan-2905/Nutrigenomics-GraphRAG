import json
import pytest
from unittest.mock import patch, MagicMock


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_redis_mock(stored: dict = None):
    store = stored or {}
    m = MagicMock()
    m.ping.return_value = True
    m.get.side_effect = lambda k: store.get(k)
    m.setex.side_effect = lambda k, ttl, v: store.update({k: v})
    m.keys.side_effect = lambda pattern: [k for k in store if k.startswith(pattern.rstrip("*"))]
    m.delete.side_effect = lambda *keys: [store.pop(k, None) for k in keys]
    return m, store


# ── exact cache ───────────────────────────────────────────────────────────────

def test_exact_cache_miss_returns_none():
    mock, _ = _make_redis_mock()
    with patch("src.cache.redis_cache._get_redis", return_value=mock), \
         patch("src.cache.redis_cache._cache_enabled", return_value=True):
        from src.cache.redis_cache import get_exact
        assert get_exact("what foods help with rs1801133?") is None


def test_exact_cache_roundtrip():
    mock, store = _make_redis_mock()
    answer = "Spinach may support folate metabolism."
    evidence = ["rs1801133 LOCATED_IN MTHFR", "Spinach CONTAINS Folate"]

    with patch("src.cache.redis_cache._get_redis", return_value=mock), \
         patch("src.cache.redis_cache._cache_enabled", return_value=True):
        from src.cache.redis_cache import set_exact, get_exact
        stored = set_exact("what foods help with rs1801133?", answer, evidence)
        assert stored is True

        result = get_exact("what foods help with rs1801133?")
        assert result is not None
        assert result["answer"] == answer
        assert result["answer_source"] == "exact_cache"
        assert result["cache_hit"] is True


def test_exact_cache_normalized_key():
    """Same question with different whitespace/case should hit the same key."""
    mock, store = _make_redis_mock()
    answer = "Spinach may support folate metabolism."
    evidence = ["MTHFR AFFECTS Folate metabolism"]

    with patch("src.cache.redis_cache._get_redis", return_value=mock), \
         patch("src.cache.redis_cache._cache_enabled", return_value=True):
        from src.cache.redis_cache import set_exact, get_exact
        set_exact("What foods help with rs1801133?", answer, evidence)
        result = get_exact("  what  foods  help  with  rs1801133?  ")
        assert result is not None


def test_exact_cache_does_not_cache_empty_evidence():
    mock, store = _make_redis_mock()
    with patch("src.cache.redis_cache._get_redis", return_value=mock), \
         patch("src.cache.redis_cache._cache_enabled", return_value=True):
        from src.cache.redis_cache import set_exact
        result = set_exact("some question?", "Some answer", [])
        assert result is False


def test_exact_cache_does_not_cache_error_answers():
    mock, store = _make_redis_mock()
    with patch("src.cache.redis_cache._get_redis", return_value=mock), \
         patch("src.cache.redis_cache._cache_enabled", return_value=True):
        from src.cache.redis_cache import set_exact
        result = set_exact(
            "some question?",
            "There is insufficient evidence to draw conclusions.",
            ["some evidence"],
        )
        assert result is False


def test_exact_cache_disabled():
    with patch("src.cache.redis_cache._cache_enabled", return_value=False):
        from src.cache.redis_cache import get_exact, set_exact
        assert get_exact("anything") is None
        assert set_exact("anything", "answer", ["ev"]) is False


def test_cache_clear():
    mock, store = _make_redis_mock({"myns:exact:v1:abc": '{"x":1}'})
    with patch("src.cache.redis_cache._get_redis", return_value=mock), \
         patch("src.cache.redis_cache.CACHE_NAMESPACE", "myns"):
        from src.cache.redis_cache import clear_cache
        result = clear_cache()
        assert result["cleared"] == 1


def test_cache_stats_redis_down():
    with patch("src.cache.redis_cache._get_redis", return_value=None):
        from src.cache.redis_cache import get_cache_stats
        stats = get_cache_stats()
        assert stats["redis_connected"] is False


def test_exact_cache_does_not_cache_unsafe_llm_error():
    mock, store = _make_redis_mock()
    with patch("src.cache.redis_cache._get_redis", return_value=mock), \
         patch("src.cache.redis_cache._cache_enabled", return_value=True):
        from src.cache.redis_cache import set_exact
        result = set_exact(
            "some question?",
            "LLM error: connection refused\n\nRetrieved evidence: something",
            ["some evidence"],
        )
        assert result is False


def test_exact_cache_does_not_cache_no_evidence_answer():
    mock, store = _make_redis_mock()
    with patch("src.cache.redis_cache._get_redis", return_value=mock), \
         patch("src.cache.redis_cache._cache_enabled", return_value=True):
        from src.cache.redis_cache import set_exact
        result = set_exact("some question?", "No evidence available.", [])
        assert result is False


def test_exact_key_includes_namespace_and_version():
    """Cache key must embed namespace and dataset_version so stale entries are isolated."""
    with patch("src.cache.redis_cache.CACHE_NAMESPACE", "myns"), \
         patch("src.cache.redis_cache.DATASET_VERSION", "v99"):
        from src.cache.redis_cache import _exact_key, _normalize
        key = _exact_key(_normalize("test question"))
        assert "myns" in key
        assert "v99" in key


def test_answer_source_exact_cache_on_hit():
    mock, store = _make_redis_mock()
    answer = "Spinach may help."
    evidence = ["MTHFR AFFECTS Folate metabolism"]

    with patch("src.cache.redis_cache._get_redis", return_value=mock), \
         patch("src.cache.redis_cache._cache_enabled", return_value=True):
        from src.cache.redis_cache import set_exact, get_exact
        set_exact("folate question?", answer, evidence)
        result = get_exact("folate question?")

    assert result["answer_source"] == "exact_cache"


def test_semantic_cache_fallback_when_redisvl_unavailable():
    """get_semantic must return None gracefully if redisvl is not available."""
    with patch("src.cache.redis_cache._cache_enabled", return_value=True), \
         patch("src.cache.redis_cache._semantic_cache_enabled", return_value=True), \
         patch("src.cache.redis_cache._get_semantic_cache", return_value=None):
        from src.cache.redis_cache import get_semantic
        result = get_semantic("What foods help folate?")
        assert result is None


def test_semantic_cache_set_skipped_when_unavailable():
    with patch("src.cache.redis_cache._cache_enabled", return_value=True), \
         patch("src.cache.redis_cache._semantic_cache_enabled", return_value=True), \
         patch("src.cache.redis_cache._get_semantic_cache", return_value=None):
        from src.cache.redis_cache import set_semantic
        result = set_semantic("any question?", "answer", ["evidence"])
        assert result is False


def test_answer_source_semantic_cache_on_hit():
    import json
    semantic_mock = MagicMock()
    payload = json.dumps({"answer": "Semantic answer", "evidence": ["ev1"]})
    semantic_mock.check.return_value = [{"response": payload}]

    with patch("src.cache.redis_cache._cache_enabled", return_value=True), \
         patch("src.cache.redis_cache._semantic_cache_enabled", return_value=True), \
         patch("src.cache.redis_cache._get_semantic_cache", return_value=semantic_mock):
        from src.cache.redis_cache import get_semantic
        result = get_semantic("What foods help folate?")

    assert result is not None
    assert result["answer_source"] == "semantic_cache"
    assert result["cache_hit"] is True
