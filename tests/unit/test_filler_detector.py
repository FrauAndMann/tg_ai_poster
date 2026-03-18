"""Tests for filler words detector."""
import pytest
from pipeline.anti_water.filler_detector import FillerDetector, FillerReport


def test_detect_russian_filler_words():
    """Test detection of Russian filler phrases."""
    detector = FillerDetector()

    text = "Стоит отметить, что этот продукт является революционным."
    report = detector.detect(text)

    assert report.filler_count >= 2
    assert report.water_percentage > 0
    assert any("стоит отметить" in f.lower() for f in report.filler_list)


def test_detect_english_filler_words():
    """Test detection of English filler phrases."""
    detector = FillerDetector()

    text = "It is worth noting that this is a game-changing solution."
    report = detector.detect(text)

    assert report.filler_count >= 2
    assert any("worth noting" in f.lower() for f in report.filler_list)


def test_water_percentage_calculation():
    """Test water percentage calculation."""
    detector = FillerDetector()

    # Text with some filler words - ~20-30% water content
    # "Стоит отметить" = 2 words, text has 9 total words = 22%
    text = "Стоит отметить, что компания OpenAI выпустила новую модель."
    report = detector.detect(text)

    assert report.water_percentage > 0
    assert report.water_percentage < 50


def test_text_passes_water_threshold():
    """Test that clean text passes the threshold."""
    detector = FillerDetector(max_water_percentage=15)

    text = "OpenAI выпустила GPT-5. Модель работает в 3 раза быстрее."
    report = detector.detect(text)

    assert report.passes_threshold is True
    assert report.water_percentage < 15
