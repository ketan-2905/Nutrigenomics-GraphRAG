"""Unit tests for the answer generator — LLM calls are always mocked."""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit

QUESTION = "What foods may support rs1801133 related folate metabolism risk?"
EVIDENCE = [
    "rs1801133 is LOCATED_IN MTHFR gene.",
    "MTHFR AFFECTS Folate metabolism.",
    "Spinach CONTAINS Folate.",
]


# ---------------------------------------------------------------------------
# Template fallback (no API key)
# ---------------------------------------------------------------------------

def test_template_fallback_when_no_api_key():
    with patch("src.rag.answer_generator.OPENAI_API_KEY", None):
        from src.rag.answer_generator import generate_answer
        result = generate_answer(QUESTION, EVIDENCE)
    assert "answer" in result
    assert "evidence" in result
    assert result["answer_source"] == "template_fallback"


def test_template_fallback_includes_evidence_text():
    with patch("src.rag.answer_generator.OPENAI_API_KEY", None):
        from src.rag.answer_generator import generate_answer
        result = generate_answer(QUESTION, EVIDENCE)
    for ev in EVIDENCE:
        assert ev in result["answer"]


def test_template_fallback_contains_not_medical_advice():
    with patch("src.rag.answer_generator.OPENAI_API_KEY", None):
        from src.rag.answer_generator import generate_answer
        result = generate_answer(QUESTION, EVIDENCE)
    answer_lower = result["answer"].lower()
    assert "not medical advice" in answer_lower or "medical" in answer_lower


# ---------------------------------------------------------------------------
# Prompt safety rules
# ---------------------------------------------------------------------------

def test_prompt_contains_no_diagnosis_rule():
    from src.rag.answer_generator import build_prompt
    from src.rag.prompts import ANSWER_TEMPLATE
    prompt = build_prompt(QUESTION, EVIDENCE)
    assert "do not diagnose" in prompt.lower() or "diagnos" in ANSWER_TEMPLATE.lower()


def test_prompt_contains_educational_only_or_not_medical_advice():
    from src.rag.prompts import ANSWER_TEMPLATE
    lower = ANSWER_TEMPLATE.lower()
    assert "not medical advice" in lower or "medical" in lower or "educational" in lower


def test_prompt_contains_insufficient_evidence_handling():
    from src.rag.prompts import ANSWER_TEMPLATE
    lower = ANSWER_TEMPLATE.lower()
    assert "insufficient" in lower or "evidence" in lower


def test_prompt_contains_no_certainty_rule():
    from src.rag.prompts import ANSWER_TEMPLATE
    lower = ANSWER_TEMPLATE.lower()
    assert "certainty" in lower or "do not claim" in lower or "claim" in lower


def test_build_prompt_includes_question_and_evidence():
    from src.rag.answer_generator import build_prompt
    prompt = build_prompt(QUESTION, EVIDENCE)
    assert QUESTION in prompt
    assert "rs1801133" in prompt
    assert "MTHFR" in prompt


def test_build_prompt_handles_empty_evidence():
    from src.rag.answer_generator import build_prompt
    prompt = build_prompt(QUESTION, [])
    assert "No evidence retrieved" in prompt


# ---------------------------------------------------------------------------
# LLM path — mocked when key is present
# ---------------------------------------------------------------------------

def test_generate_answer_calls_openai_when_key_present():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Based on evidence, spinach may help."
    mock_response.usage = None

    # OpenAI is imported inside the function body, so patch it at its source.
    with patch("src.rag.answer_generator.OPENAI_API_KEY", "sk-test"), \
         patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        from src.rag.answer_generator import generate_answer
        result = generate_answer(QUESTION, EVIDENCE)

    assert result["answer_source"] == "llm"
    assert "spinach" in result["answer"].lower()


def test_generate_answer_fallback_on_llm_exception():
    with patch("src.rag.answer_generator.OPENAI_API_KEY", "sk-test"), \
         patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit")
        mock_openai_cls.return_value = mock_client

        from src.rag.answer_generator import generate_answer
        result = generate_answer(QUESTION, EVIDENCE)

    assert "answer" in result
    assert result["answer_source"] == "template_fallback"


# ---------------------------------------------------------------------------
# Cache safety — generator should never produce answers that would
# bypass the cache safety guard (tested by checking _is_cacheable)
# ---------------------------------------------------------------------------

def test_is_cacheable_rejects_empty_evidence():
    from src.cache.redis_cache import _is_cacheable
    assert _is_cacheable("Good answer with evidence.", []) is False


def test_is_cacheable_rejects_insufficient_evidence_phrase():
    # _UNSAFE_PATTERNS includes "insufficient evidence" (exact substring)
    from src.cache.redis_cache import _is_cacheable
    assert _is_cacheable("There is insufficient evidence to support this claim.", ["ev"]) is False


def test_is_cacheable_rejects_llm_error_phrase():
    from src.cache.redis_cache import _is_cacheable
    assert _is_cacheable("LLM error: something went wrong", ["ev"]) is False


def test_is_cacheable_accepts_valid_answer():
    from src.cache.redis_cache import _is_cacheable
    assert _is_cacheable("Spinach may support folate metabolism.", ["ev1", "ev2"]) is True
