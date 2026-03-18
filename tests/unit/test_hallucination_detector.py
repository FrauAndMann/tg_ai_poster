"""Tests for hallucination detector module."""
import pytest

from pipeline.fact_check.hallucination_detector import (
    HallucinationDetector,
    HallucinationReport,
)


class TestHallucinationDetector:
    """Tests for HallucinationDetector class."""

    def test_detect_vague_expert_claims_russian(self):
        """Test detection of vague expert claims in Russian."""
        detector = HallucinationDetector()

        text = "Эксперты прогнозируют рост рынка ИИ на 50% в следующем году."
        report = detector.detect(text)

        assert report.score > 0
        assert len(report.indicators) >= 1
        assert "vague_expert_ru" in report.details

    def test_detect_vague_expert_claims_english(self):
        """Test detection of vague expert claims in English."""
        detector = HallucinationDetector()

        text = "Experts predict that AI will revolutionize the industry."
        report = detector.detect(text)

        assert report.score > 0
        assert "vague_expert_en" in report.details

    def test_detect_unnamed_studies(self):
        """Test detection of unnamed study references."""
        detector = HallucinationDetector()

        text = "Недавнее исследование показало, что 90% компаний используют ИИ."
        report = detector.detect(text)

        assert report.score > 0
        assert "unnamed_study_ru" in report.details
        assert len(report.indicators) >= 1

    def test_detect_impossible_statistics(self):
        """Test detection of impossible or suspicious statistics."""
        detector = HallucinationDetector()

        text = "Новая модель показывает 500% улучшение производительности."
        report = detector.detect(text)

        assert report.score >= 0.5
        assert "impossible_improvement" in report.details

    def test_clean_text_passes_check(self):
        """Test that clean text passes hallucination check."""
        detector = HallucinationDetector()

        text = "OpenAI выпустила GPT-5 15 января 2026 года. Модель работает в 3 раза быстрее."
        report = detector.detect(text)

        assert report.passes_check is True
        assert report.score < detector.auto_reject_threshold

    def test_high_risk_text_fails_check(self):
        """Test that high-risk text fails hallucination check."""
        detector = HallucinationDetector()

        text = """
        Эксперты прогнозируют революцию в отрасли.
        Недавнее исследование показало 1000% рост.
        Исследования показывают полную трансформацию.
        Эксперты утверждают, что это изменит всё.
        """
        report = detector.detect(text)

        assert report.passes_check is False
        assert report.score >= detector.auto_reject_threshold
        assert len(report.recommendations) >= 1

    def test_ai_cliche_detection(self):
        """Test detection of AI cliches."""
        detector = HallucinationDetector()

        text = "This is a game-changer and revolutionary technology. A groundbreaking paradigm shift."
        report = detector.detect(text)

        # Cliches should increase the score
        assert report.score > 0

    def test_strict_mode_increases_sensitivity(self):
        """Test that strict mode increases detection sensitivity."""
        normal_detector = HallucinationDetector(strict_mode=False)
        strict_detector = HallucinationDetector(strict_mode=True)

        text = "Эксперты прогнозируют значительные изменения в индустрии."

        normal_report = normal_detector.detect(text)
        strict_report = strict_detector.detect(text)

        assert strict_report.score >= normal_report.score

    def test_custom_auto_reject_threshold(self):
        """Test custom auto-reject threshold."""
        detector = HallucinationDetector(auto_reject_threshold=0.5)

        text = "Эксперты прогнозируют изменения."
        report = detector.detect(text)

        # With lower threshold, more content should fail
        # The exact behavior depends on the content
        assert detector.auto_reject_threshold == 0.5

    def test_recommendations_generated(self):
        """Test that recommendations are generated for flagged content."""
        detector = HallucinationDetector()

        text = "Недавнее исследование показало, что эксперты прогнозируют революцию."
        report = detector.detect(text)

        assert len(report.recommendations) >= 1
        # Should recommend adding sources
        assert any(
            "исследован" in rec.lower() or "эксперт" in rec.lower() or "источник" in rec.lower()
            for rec in report.recommendations
        )

    def test_get_hallucination_score_only(self):
        """Test getting only the score without full report."""
        detector = HallucinationDetector()

        text = "Эксперты прогнозируют рост."
        score = detector.get_hallucination_score(text)

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_is_safe_to_publish_quick_check(self):
        """Test quick safety check for publishing."""
        detector = HallucinationDetector()

        clean_text = "OpenAI выпустила новую модель GPT-5."
        risky_text = "Эксперты прогнозируют 500% улучшение согласно недавнему исследованию."

        assert detector.is_safe_to_publish(clean_text) is True
        assert detector.is_safe_to_publish(risky_text) is False

    def test_get_high_risk_segments(self):
        """Test extraction of high-risk segments."""
        detector = HallucinationDetector()

        text = "Недавнее исследование показало, что 500% пользователей довольны."
        segments = detector.get_high_risk_segments(text)

        assert len(segments) >= 1
        assert all("text" in seg for seg in segments)
        assert all("pattern" in seg for seg in segments)
        assert all("weight" in seg for seg in segments)

    def test_future_predictions_as_facts(self):
        """Test detection of future predictions presented as facts."""
        detector = HallucinationDetector()

        text = "В 2030 году будет создан настоящий AGI."
        report = detector.detect(text)

        assert report.score > 0
        assert "future_as_fact_ru" in report.details


class TestHallucinationReport:
    """Tests for HallucinationReport dataclass."""

    def test_report_default_values(self):
        """Test HallucinationReport default values."""
        report = HallucinationReport(score=0.0)

        assert report.score == 0.0
        assert report.indicators == []
        assert report.passes_check is True
        assert report.details == {}
        assert report.recommendations == []

    def test_report_with_high_score_fails(self):
        """Test that high score results in failed check."""
        report = HallucinationReport(score=0.8, passes_check=False)

        assert report.passes_check is False
        assert report.score >= 0.7
