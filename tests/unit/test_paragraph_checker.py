"""Tests for paragraph impact checker."""
import pytest
from pipeline.anti_water.paragraph_checker import ParagraphChecker, ParagraphReport


def test_detect_redundant_paragraphs():
    """Test detection of redundant paragraphs."""
    checker = ParagraphChecker()

    # These paragraphs are intentionally very similar (almost identical)
    text = """
OpenAI выпустила новую модель GPT-5 с улучшенной производительностью.
Модель работает значительно быстрее.

OpenAI представила новую модель GPT-5 с улучшенной производительностью.
Новая модель GPT-5 работает значительно быстрее.
    """
    report = checker.check(text)

    assert len(report.redundant_pairs) > 0


def test_each_paragraph_has_unique_claim():
    """Test that unique paragraphs pass."""
    checker = ParagraphChecker()

    text = """
OpenAI выпустила GPT-5 15 марта 2026 года.

Google анонсировала Gemini 2.0 на конференции I/O.

Microsoft интегрировала Copilot в Windows 12.
    """
    report = checker.check(text)

    assert report.passes_check is True
    assert len(report.redundant_pairs) == 0


def test_extract_key_claims():
    """Test extraction of key claims from paragraphs."""
    checker = ParagraphChecker()

    text = """
OpenAI выпустила GPT-5 с улучшенной производительностью.

Google представила новый сервис для разработчиков.
    """
    report = checker.check(text)

    # Verify claims were extracted (2 paragraphs)
    assert report.paragraph_count == 2
    # Each paragraph should have different key words
    assert report.passes_check is True


def test_single_paragraph():
    """Test that single paragraph always passes."""
    checker = ParagraphChecker()

    text = "OpenAI выпустила GPT-5."
    report = checker.check(text)

    assert report.passes_check is True
    assert report.paragraph_count == 1
    assert len(report.redundant_pairs) == 0


def test_custom_similarity_threshold():
    """Test custom similarity threshold."""
    # With stricter threshold
    checker = ParagraphChecker(similarity_threshold=0.9)

    text = """
OpenAI выпустила GPT-5.

Google выпустила Gemini.
    """
    report = checker.check(text)

    # These should not be redundant at 0.9 threshold
    assert report.passes_check is True


def test_empty_text():
    """Test handling of empty text."""
    checker = ParagraphChecker()

    report = checker.check("")

    assert report.passes_check is True
    assert report.paragraph_count == 0


def test_stop_words_filtered():
    """Test that stop words are filtered in comparison."""
    checker = ParagraphChecker()

    # These paragraphs have many common stop words but different content
    text = """
OpenAI выпустила новую модель GPT-5.

Google представила свой новый продукт Gemini.
    """
    report = checker.check(text)

    # Should pass because content is different despite stop words
    assert report.passes_check is True
    assert len(report.redundant_pairs) == 0


def test_recommendations_for_redundant_content():
    """Test that recommendations are generated for redundant paragraphs."""
    checker = ParagraphChecker()

    text = """
OpenAI выпустила новую модель GPT-5.
Это важное событие в мире технологий.

OpenAI выпустила новую модель GPT-5.
Это важное событие в мире технологий.
    """
    report = checker.check(text)

    assert report.passes_check is False
    assert len(report.recommendations) > 0
    assert "redundant" in report.recommendations[0].lower()
