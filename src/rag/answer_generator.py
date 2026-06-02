import time
from src.config import OPENAI_API_KEY, LLM_MODEL
from src.rag.prompts import ANSWER_TEMPLATE, SYSTEM_PROMPT
from src.observability.metrics import RAG_LLM_LATENCY, RAG_LLM_TOKENS_TOTAL


def build_prompt(question: str, evidence: list[str]) -> str:
    context = "\n".join([f"- {item}" for item in evidence]) if evidence else "No evidence retrieved."
    return ANSWER_TEMPLATE.format(context=context, question=question)


def generate_answer(question: str, evidence: list[str]) -> dict:
    prompt = build_prompt(question, evidence)

    if not OPENAI_API_KEY:
        answer = _template_answer(question, evidence)
        return {
            "answer": answer,
            "evidence": evidence,
            "answer_source": "template_fallback",
        }

    t0 = time.perf_counter()
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        RAG_LLM_LATENCY.observe(time.perf_counter() - t0)

        usage = getattr(response, "usage", None)
        if usage:
            RAG_LLM_TOKENS_TOTAL.labels(type="prompt").inc(getattr(usage, "prompt_tokens", 0))
            RAG_LLM_TOKENS_TOTAL.labels(type="completion").inc(getattr(usage, "completion_tokens", 0))

        return {
            "answer": response.choices[0].message.content,
            "evidence": evidence,
            "answer_source": "llm",
        }
    except Exception as e:
        RAG_LLM_LATENCY.observe(time.perf_counter() - t0)
        return {
            "answer": f"LLM error: {e}\n\nRetrieved evidence:\n" + "\n".join(evidence),
            "evidence": evidence,
            "answer_source": "template_fallback",
        }


def _template_answer(question: str, evidence: list[str]) -> str:
    evidence_text = "\n".join([f"- {e}" for e in evidence]) if evidence else "No evidence available."
    return (
        f"**Nutrigenomics GraphRAG Answer** (template mode — no LLM API key configured)\n\n"
        f"**Question:** {question}\n\n"
        f"**Retrieved Evidence:**\n{evidence_text}\n\n"
        f"**Note:** This is educational output only. Configure OPENAI_API_KEY for full LLM-generated answers. "
        f"This is not medical advice. Consult a qualified healthcare professional for personalized guidance."
    )
