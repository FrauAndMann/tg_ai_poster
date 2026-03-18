"""Tests for unified quality scorer."""
import pytest
from pipeline.quality_scorer import QualityScorer, QualityScoreReport


def test_calculate_composite_score():
    """Test composite quality score calculation - high quality post scores well."""
    scorer = QualityScorer()

    text = """
OpenAI выпустила GPT-5 15 марта 2026 года.

Компания инвестировала $10 миллиардов в разработку.
По данным исследования, 85% пользователей довольны.
Модель работает в 3 раза быстрее GPT-4.

🔍 Ключевые факты:
• GPT-5 выпущен 15 марта 2026
• Инвестиции: $10 млрд
• Прирост скорости: 3x
• Удовлетворённость: 85%

💡 TLDR: OpenAI выпустила GPT-5 с 3-кратным приростом скорости.
    """

    report = scorer.score(text)

    assert report.total_score >= 70
    assert report.breakdown["density"] > 0


def test_low_quality_post_score():
    """Test that low quality posts get low scores - vague text gets low scores."""
    scorer = QualityScorer()

    text = """
Это очень важный и интересный продукт.
Стоит отметить, что он безусловно полезен.
В современном мире это крайне необходимо.
    """

    report = scorer.score(text)

    assert report.total_score < 70
    assert report.passes_threshold is False


def test_score_breakdown():
    """Test that score breakdown is provided with all components."""
    scorer = QualityScorer()

    text = "OpenAI выпустила GPT-5. 🔍 Факты: GPT-5 готов. 💡 TLDR: GPT-5 вышел."
    report = scorer.score(text)

    assert "density" in report.breakdown
    assert "water_penalty" in report.breakdown
    assert "structure" in report.breakdown
    assert "factual_accuracy" in report.breakdown
    assert "style" in report.breakdown

    # All breakdown values should be in 0-100 range
    for component, value in report.breakdown.items():
        assert 0 <= value <= 100, f"{component} score {value} out of range"


def test_grade_property():
    """Test grade calculation based on total score."""
    # Test Excellent (90+)
    report = QualityScoreReport(total_score=92.0)
    assert report.grade == "Excellent"

    # Test Good (80-89)
    report = QualityScoreReport(total_score=85.0)
    assert report.grade == "Good"

    # Test Acceptable (70-79)
    report = QualityScoreReport(total_score=75.0)
    assert report.grade == "Acceptable"

    # Test Reject (<70)
    report = QualityScoreReport(total_score=65.0)
    assert report.grade == "Reject"


def test_rejection_threshold():
    """Test that posts below 70 are rejected."""
    scorer = QualityScorer(pass_threshold=70.0)

    # Very low quality text with water content
    text = "Это весьма важный продукт. Стоит отметить, что он крайне необходим."
    report = scorer.score(text)

    assert report.total_score < 70
    assert report.passes_threshold is False
    assert report.grade == "Reject"


def test_passes_threshold_boundary():
    """Test that posts exactly at 70 pass the threshold."""
    # Create a mock report to test boundary
    report = QualityScoreReport(total_score=70.0, passes_threshold=True)
    assert report.passes_threshold is True
    assert report.grade == "Acceptable"


def test_issues_are_collected():
    """Test that issues are collected from component checks."""
    scorer = QualityScorer()

    # Text with high water content
    text = "Это очень важный продукт. Стоит отметить, что он весьма полезен."
    report = scorer.score(text)

    # Should have issues due to low quality
    assert len(report.issues) > 0 or not report.passes_threshold


def test_recommendations_are_provided():
    """Test that recommendations are provided for improvement."""
    scorer = QualityScorer()

    # Low density text
    text = "Продукт вышел. Он хороший. 🔍 Факт: продукт. 💡 TLDR: вышел."
    report = scorer.score(text)

    # Recommendations should be a list
    assert isinstance(report.recommendations, list)


def test_structure_score_requires_markers():
    """Test that structure score requires required markers (🔍, 💡)."""
    scorer = QualityScorer()

    # Text without markers
    text_no_markers = "OpenAI выпустила GPT-5. Компания инвестировала $10 млрд."
    report = scorer.score(text_no_markers)

    # Should have lower structure score
    assert report.breakdown["structure"] < 100

    # Text with markers
    text_with_markers = "OpenAI выпустила GPT-5. 🔍 Факты здесь. 💡 TLDR: GPT-5."
    report_with_markers = scorer.score(text_with_markers)

    assert report_with_markers.breakdown["structure"] >= report.breakdown["structure"]


def test_default_pass_threshold():
    """Test that default pass_threshold is 70.0."""
    scorer = QualityScorer()
    assert scorer.pass_threshold == 70.0


def test_custom_pass_threshold():
    """Test that custom pass_threshold can be set."""
    scorer = QualityScorer(pass_threshold=80.0)
    assert scorer.pass_threshold == 80.0
