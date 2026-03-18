"""Tests for information density scorer."""
import pytest
from pipeline.anti_water.density_scorer import DensityScorer, DensityReport


def test_calculate_density_score():
    """Test density score calculation with concrete data."""
    scorer = DensityScorer()

    text = """
    OpenAI выпустила GPT-5 15 марта 2026 года.
    Модель работает в 3 раза быстрее GPT-4.
    Компания инвестировала $10 миллиардов в разработку.
    По данным исследования, 85% пользователей довольны.
    """
    report = scorer.score(text)

    assert report.facts_count >= 3
    assert report.numbers_count >= 4
    assert report.density_score > 10


def test_low_density_text():
    """Test that vague text has low density score."""
    scorer = DensityScorer()

    text = "Это очень важный продукт. Он значительно улучшает работу."
    report = scorer.score(text)

    assert report.density_score < 10
    assert report.passes_threshold is False


def test_detect_specific_dates():
    """Test detection of specific dates."""
    scorer = DensityScorer()

    text = "Событие произошло 15 марта 2025 года."
    report = scorer.score(text)

    assert report.dates_count >= 1


def test_detect_proper_nouns():
    """Test detection of proper nouns."""
    scorer = DensityScorer()

    text = "OpenAI и Google анонсировали партнёрство."
    report = scorer.score(text)

    assert report.proper_nouns_count >= 2
