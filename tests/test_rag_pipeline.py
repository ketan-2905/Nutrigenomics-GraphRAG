import pytest
from unittest.mock import patch, MagicMock


def test_build_prompt():
    from src.rag.answer_generator import build_prompt
    evidence = ["rs1801133 LOCATED_IN MTHFR", "MTHFR AFFECTS Folate metabolism"]
    prompt = build_prompt("What foods support rs1801133?", evidence)
    assert "rs1801133" in prompt
    assert "MTHFR" in prompt
    assert "What foods support rs1801133?" in prompt


def test_generate_answer_no_api_key():
    with patch("src.rag.answer_generator.OPENAI_API_KEY", None):
        from src.rag.answer_generator import generate_answer
        result = generate_answer("What foods support rs1801133?", ["Evidence A", "Evidence B"])
        assert "answer" in result
        assert "evidence" in result
        assert len(result["evidence"]) == 2


def test_extract_snp_id():
    from src.rag.retriever import extract_snp_id
    assert extract_snp_id("What about rs1801133 and folate?") == "rs1801133"
    assert extract_snp_id("no snp here") is None


def test_extract_trait():
    from src.rag.retriever import extract_trait
    assert extract_trait("tell me about folate") == "Folate metabolism"
    assert extract_trait("glucose issues") == "Glucose metabolism"
    assert extract_trait("nothing relevant") is None


@patch("src.rag.retriever.vector_search", return_value=["Evidence A"])
@patch("src.rag.retriever.find_paths_from_snp", return_value=[{"node_ids": ["rs1801133", "MTHFR"], "rel_types": ["LOCATED_IN"]}])
@patch("src.rag.retriever.find_foods_for_snp", return_value=[{"food": "Spinach", "path_nodes": ["rs1801133", "MTHFR", "Folate metabolism", "Folate", "Spinach"]}])
@patch("src.rag.retriever.find_nutrients_for_trait", return_value=[{"nutrient": "Folate"}])
def test_hybrid_retrieve(mock_nutrients, mock_foods, mock_paths, mock_vector):
    from src.rag.retriever import hybrid_retrieve
    results = hybrid_retrieve("What foods support rs1801133 folate metabolism?")
    assert len(results) > 0
    assert any("Evidence A" in r for r in results)
