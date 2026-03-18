"""Tests for flow checker - logical transitions between sections."""
import pytest
from pipeline.structure.flow_checker import FlowChecker, FlowReport, TransitionScore


def test_title_to_hook_relevance():
    """Test relevance score between title and hook (opening sentence)."""
    checker = FlowChecker()

    # Good transition: title relates to hook
    post = {
        "title": "OpenAI releases GPT-5 with 3x speed improvement",
        "hook": "OpenAI выпустила GPT-5 15 марта 2026 года.",
        "body": "Новая модель работает в 3 раза быстрее предыдущей версии.",
    }
    report = checker.check(post)

    assert report is not None
    assert "title_to_hook" in report.transitions
    assert report.transitions["title_to_hook"].score >= 7


def test_hook_to_body_facts():
    """Test that hook claims are supported by body facts."""
    checker = FlowChecker()

    # Hook claim is supported by body
    post = {
        "hook": "OpenAI выпустила GPT-5 15 марта 2026 года.",
        "body": """
        OpenAI выпустила GPT-5 15 марта 2026 года.
        Модель работает в 3 раза быстрее GPT-4.
        Компания инвестировала $10 миллиардов в разработку.
        """,
        "key_facts": ["GPT-5 выпущен 15 марта 2026", "3x быстрее GPT-4"],
    }
    report = checker.check(post)

    assert report is not None
    assert "hook_to_body" in report.transitions
    assert report.transitions["hook_to_body"].score >= 7


def test_body_to_analysis_insights_flow():
    """Test that body content leads to meaningful analysis insights."""
    checker = FlowChecker()

    # Body facts support analysis
    post = {
        "body": """
        OpenAI выпустила GPT-5 15 марта 2026 года.
        Модель работает в 3 раза быстрее GPT-4.
        Компания инвестировала $10 миллиардов в разработку.
        """,
        "analysis": """
        Ускорение в 3 раза делает GPT-5 лидером рынка.
        Инвестиции в $10 млрд показывают серьёзность намерений OpenAI.
        """,
    }
    report = checker.check(post)

    assert report is not None
    assert "body_to_analysis" in report.transitions
    assert report.transitions["body_to_analysis"].score >= 7


def test_tldr_quality():
    """Test TLDR summary accuracy (covers main points)."""
    checker = FlowChecker()

    # Good TLDR that summarizes key points
    post = {
        "body": """
        OpenAI выпустила GPT-5 15 марта 2026 года.
        Модель работает в 3 раза быстрее GPT-4.
        Компания инвестировала $10 миллиардов в разработку.
        """,
        "tldr": "OpenAI выпустила GPT-5 с 3-кратным приростом скорости.",
    }
    report = checker.check(post)

    assert report is not None
    assert "body_to_tldr" in report.transitions
    assert report.transitions["body_to_tldr"].score >= 7


def test_key_facts_to_analysis_transition():
    """Test that key facts logically lead to analysis thoughts."""
    checker = FlowChecker()

    # Key facts lead to analysis
    post = {
        "key_facts": [
            "GPT-5 работает в 3 раза быстрее",
            "Инвестиции: $10 млрд",
            "Дата релиза: 15 марта 2026",
        ],
        "analysis": """
        Ускорение в 3 раза означает серьёзный технологический прорыв.
        Инвестиции показывают долгосрочную стратегию OpenAI.
        """,
    }
    report = checker.check(post)

    assert report is not None
    assert "facts_to_analysis" in report.transitions
    assert report.transitions["facts_to_analysis"].score >= 7


def test_body_to_tldr_summary_accuracy():
    """Test that TLDR accurately summarizes body content."""
    checker = FlowChecker()

    # TLDR accurately reflects body content
    post = {
        "body": """
        Google анонсировала Gemini 2.0 на конференции I/O.
        Новая модель поддерживает мультимодальность.
        Цена осталась прежней - $20 в месяц.
        """,
        "tldr": "Google представила Gemini 2.0 с мультимодальностью.",
    }
    report = checker.check(post)

    assert report is not None
    assert "body_to_tldr" in report.transitions
    assert report.transitions["body_to_tldr"].score >= 6


def test_poor_transition_detected():
    """Test that poor transitions are detected with low scores."""
    checker = FlowChecker()

    # Poor transition: title doesn't relate to hook
    post = {
        "title": "AI Revolution Changes Everything",
        "hook": "Google купил стартап за $5 млн.",
        "body": "Это важное событие в индустрии.",
    }
    report = checker.check(post)

    assert report is not None
    assert "title_to_hook" in report.transitions
    # Poor relevance should get lower score
    assert report.transitions["title_to_hook"].score < 7


def test_average_score_calculation():
    """Test that average score is calculated correctly."""
    checker = FlowChecker()

    post = {
        "title": "OpenAI releases GPT-5",
        "hook": "OpenAI выпустила GPT-5 15 марта 2026 года.",
        "body": "Модель работает в 3 раза быстрее.",
        "analysis": "Это важный шаг для индустрии.",
        "tldr": "OpenAI выпустила быструю модель GPT-5.",
        "key_facts": ["GPT-5 выпущен"],
    }
    report = checker.check(post)

    assert report is not None
    assert report.average_score >= 0
    assert report.average_score <= 10
    assert len(report.transitions) <= 10  # Max 10 transitions


def test_passes_threshold():
    """Test that average score threshold (>=7) works correctly."""
    checker = FlowChecker()

    # High quality post should pass
    good_post = {
        "title": "OpenAI releases GPT-5 with major improvements",
        "hook": "OpenAI выпустила GPT-5 15 марта 2026 года.",
        "body": """
        OpenAI выпустила GPT-5 15 марта 2026 года.
        Модель работает в 3 раза быстрее GPT-4.
        """,
        "analysis": "Скорость выросла в 3 раза - значительное улучшение.",
        "tldr": "OpenAI выпустила GPT-5 с 3-кратным ускорением.",
        "key_facts": ["GPT-5 быстрее в 3 раза"],
    }
    report = checker.check(good_post)

    assert report.average_score >= 7
    assert report.passes_threshold is True


def test_empty_post_handling():
    """Test handling of empty or missing sections."""
    checker = FlowChecker()

    post = {}
    report = checker.check(post)

    assert report is not None
    # Should not crash, transitions may have low scores
    assert isinstance(report.transitions, dict)


def test_transition_score_dataclass():
    """Test TransitionScore dataclass structure."""
    score = TransitionScore(
        transition="title_to_hook",
        score=8.5,
        max_score=10,
        description="Title relates well to hook",
        issues=[],
    )

    assert score.transition == "title_to_hook"
    assert score.score == 8.5
    assert score.max_score == 10
    assert len(score.issues) == 0


def test_flow_report_dataclass():
    """Test FlowReport dataclass structure."""
    report = FlowReport(
        transitions={
            "title_to_hook": TransitionScore("title_to_hook", 8.0, 10, "Good", []),
        },
        average_score=8.0,
        passes_threshold=True,
    )

    assert report.average_score == 8.0
    assert report.passes_threshold is True
    assert len(report.transitions) == 1
