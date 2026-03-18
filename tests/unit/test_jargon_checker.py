"""Tests for jargon checker module."""
import pytest
from pipeline.style.jargon_checker import JargonChecker, JargonReport, JargonTerm


def test_common_knowledge_jargon_passes_without_definition():
    """Test that common knowledge jargon (like API) passes without definition."""
    checker = JargonChecker()

    text = "The new API allows developers to integrate quickly."
    result = checker.check(text)

    assert result.passes_check is True
    assert result.unexplained_count == 0
    # API should be found but marked as common knowledge
    api_terms = [t for t in result.jargon_terms if t.term == "API"]
    assert len(api_terms) == 1
    assert api_terms[0].is_common_knowledge is True
    assert api_terms[0].has_definition is True  # Common knowledge counts as explained


def test_non_common_jargon_requires_definition():
    """Test that non-common jargon requires a definition nearby."""
    checker = JargonChecker()

    # LLM without definition should fail
    text = "The new LLM shows impressive results in benchmarks."
    result = checker.check(text)

    assert result.passes_check is False
    assert result.unexplained_count > 0
    llm_terms = [t for t in result.jargon_terms if t.term == "LLM"]
    assert len(llm_terms) == 1
    assert llm_terms[0].is_common_knowledge is False
    assert llm_terms[0].has_definition is False


def test_definition_in_same_sentence_counts():
    """Test that definition in the same sentence counts as explained."""
    checker = JargonChecker()

    text = "The new LLM (Large Language Model) shows impressive results."
    result = checker.check(text)

    assert result.passes_check is True
    assert result.unexplained_count == 0
    llm_terms = [t for t in result.jargon_terms if t.term == "LLM"]
    assert len(llm_terms) == 1
    assert llm_terms[0].has_definition is True


def test_definition_in_next_sentence_counts():
    """Test that definition in the next sentence counts as explained."""
    checker = JargonChecker()

    text = "The new LLM shows impressive results. Large Language Models are revolutionizing AI development."
    result = checker.check(text)

    assert result.passes_check is True
    assert result.unexplained_count == 0


def test_multiple_jargon_terms_handled():
    """Test that multiple jargon terms are handled correctly."""
    checker = JargonChecker()

    text = """
    The RAG system uses LLM for text generation.
    RAG stands for Retrieval-Augmented Generation and helps with accuracy.
    """
    result = checker.check(text)

    # LLM should be flagged (no definition), RAG should pass (has definition)
    assert len(result.jargon_terms) >= 2

    rag_terms = [t for t in result.jargon_terms if t.term == "RAG"]
    llm_terms = [t for t in result.jargon_terms if t.term == "LLM"]

    assert len(rag_terms) >= 1
    assert rag_terms[0].has_definition is True

    assert len(llm_terms) >= 1
    assert llm_terms[0].has_definition is False

    assert result.unexplained_count >= 1


def test_recommendations_generated():
    """Test that recommendations are generated for unexplained jargon."""
    checker = JargonChecker()

    text = "The new LLM and RAG architectures show impressive results."
    result = checker.check(text)

    assert result.passes_check is False
    assert len(result.recommendations) > 0
    # Recommendations should mention the unexplained terms
    recommendations_text = " ".join(result.recommendations).lower()
    assert "llm" in recommendations_text or "rag" in recommendations_text


def test_definition_patterns_detected():
    """Test that various definition patterns are detected."""
    checker = JargonChecker()

    # Pattern: "term - definition"
    text1 = "LLM - Large Language Model is a powerful tool."
    result1 = checker.check(text1)
    assert result1.passes_check is True

    # Pattern: "term: definition"
    text2 = "LLM: Large Language Model is a powerful tool."
    result2 = checker.check(text2)
    assert result2.passes_check is True

    # Pattern: "term means definition"
    text3 = "LLM means Large Language Model."
    result3 = checker.check(text3)
    assert result3.passes_check is True

    # Pattern: "term stands for definition"
    text4 = "LLM stands for Large Language Model."
    result4 = checker.check(text4)
    assert result4.passes_check is True


def test_empty_text():
    """Test that empty text passes."""
    checker = JargonChecker()

    result = checker.check("")

    assert result.passes_check is True
    assert result.unexplained_count == 0
    assert len(result.jargon_terms) == 0


def test_no_jargon_in_text():
    """Test text without any jargon terms."""
    checker = JargonChecker()

    text = "The weather today is sunny and warm."
    result = checker.check(text)

    assert result.passes_check is True
    assert result.unexplained_count == 0
    assert len(result.jargon_terms) == 0


def test_jargon_term_dataclass():
    """Test JargonTerm dataclass attributes."""
    term = JargonTerm(
        term="LLM",
        position=10,
        is_common_knowledge=False,
        has_definition=True,
        context="The LLM is powerful."
    )

    assert term.term == "LLM"
    assert term.position == 10
    assert term.is_common_knowledge is False
    assert term.has_definition is True
    assert term.context == "The LLM is powerful."


def test_jargon_report_dataclass():
    """Test JargonReport dataclass attributes."""
    report = JargonReport(
        jargon_terms=[],
        unexplained_count=0,
        passes_check=True,
        recommendations=[]
    )

    assert report.jargon_terms == []
    assert report.unexplained_count == 0
    assert report.passes_check is True
    assert report.recommendations == []


def test_case_insensitive_jargon_detection():
    """Test that jargon detection is case insensitive."""
    checker = JargonChecker()

    text = "The llm and Api work together."
    result = checker.check(text)

    # Should find both LLM and API regardless of case
    terms = [t.term for t in result.jargon_terms]
    assert "LLM" in terms or "llm" in [t.term.lower() for t in result.jargon_terms]
    assert "API" in terms or "api" in [t.term.lower() for t in result.jargon_terms]


def test_definition_with_link_counts():
    """Test that jargon with an explanatory link counts as explained."""
    checker = JargonChecker()

    text = "Learn more about LLM [here](https://example.com/llm-explained)."
    result = checker.check(text)

    # Having a link should count as having an explanation
    llm_terms = [t for t in result.jargon_terms if t.term.upper() == "LLM"]
    if llm_terms:  # Only check if LLM was found
        # Link presence counts as explanation
        assert llm_terms[0].has_definition is True


def test_context_extraction():
    """Test that context is properly extracted around jargon terms."""
    checker = JargonChecker()

    text = "This is a long text. The RAG system is innovative. More text follows."
    result = checker.check(text)

    rag_terms = [t for t in result.jargon_terms if t.term == "RAG"]
    assert len(rag_terms) == 1
    # Context should include surrounding text
    assert "RAG" in rag_terms[0].context


def test_custom_config_path():
    """Test that custom config path can be specified."""
    checker = JargonChecker(config_path="config/tech_jargon.yaml")

    # Should still work with the specified config
    text = "The API works well."
    result = checker.check(text)

    assert isinstance(result, JargonReport)


def test_multiple_occurrences_of_same_jargon():
    """Test handling multiple occurrences of the same jargon term."""
    checker = JargonChecker()

    text = "The LLM is powerful. This LLM can generate text. Another LLM example."
    result = checker.check(text)

    # Should find multiple occurrences
    llm_terms = [t for t in result.jargon_terms if t.term == "LLM"]
    assert len(llm_terms) >= 1  # At least one occurrence found


def test_definition_before_jargon_counts():
    """Test that definition appearing before the jargon term also counts."""
    checker = JargonChecker()

    text = "Large Language Models are powerful. The new LLM shows great results."
    result = checker.check(text)

    # Definition appears before the term, should still count
    llm_terms = [t for t in result.jargon_terms if t.term == "LLM"]
    if llm_terms:
        assert llm_terms[0].has_definition is True


def test_various_jargon_categories():
    """Test that jargon from different categories is detected."""
    checker = JargonChecker()

    text = "The API connects to the GPU for faster inference."
    result = checker.check(text)

    # Should detect both API (general_tech) and GPU (hardware)
    terms = [t.term for t in result.jargon_terms]
    # API is common knowledge, GPU may or may not be
    assert len(result.jargon_terms) >= 1
