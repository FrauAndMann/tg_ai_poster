"""Tests for TLDR quality checker."""
import pytest
from pipeline.structure.tldr_checker import TLDRChecker, TLDRReport


def test_good_tldr():
    """Test validation of a good TLDR."""
    checker = TLDRChecker()

    tldr = "OpenAI выпустила GPT-5 с 3-кратным приростом скорости."
    report = checker.check(tldr)

    assert report.passes_check is True
    assert report.sentence_count <= 2
    assert len(report.issues) == 0


def test_tldr_too_long():
    """Test that long TLDR is flagged."""
    checker = TLDRChecker()

    tldr = "OpenAI выпустила GPT-5. Модель работает быстрее. Цена осталась прежней."
    report = checker.check(tldr)

    assert report.sentence_count > 2
    assert report.passes_check is False
    assert any("too many sentences" in issue.lower() for issue in report.issues)


def test_tldr_has_main_subject():
    """Test TLDR without subject is flagged."""
    checker = TLDRChecker()

    tldr = "Выпущена новая модель с улучшенными характеристиками."
    report = checker.check(tldr)

    assert report.passes_check is False
    assert any("subject" in issue.lower() for issue in report.issues)


def test_tldr_has_event():
    """Test TLDR without event is flagged."""
    checker = TLDRChecker()

    tldr = "OpenAI - это интересная компания."
    report = checker.check(tldr)

    assert report.passes_check is False
    assert any("event" in issue.lower() for issue in report.issues)


def test_meta_language_detection():
    """Test that meta-language is detected."""
    checker = TLDRChecker()

    # Russian meta-language
    tldr_ru = "Этот пост обсуждает новый продукт OpenAI."
    report_ru = checker.check(tldr_ru)

    assert report_ru.passes_check is False
    assert any("meta" in issue.lower() for issue in report_ru.issues)

    # English meta-language
    tldr_en = "This article discusses the new OpenAI product."
    report_en = checker.check(tldr_en)

    assert report_en.passes_check is False
    assert any("meta" in issue.lower() for issue in report_en.issues)


def test_empty_tldr():
    """Test empty TLDR handling."""
    checker = TLDRChecker()

    tldr = ""
    report = checker.check(tldr)

    assert report.passes_check is False
    assert len(report.issues) > 0


def test_configurable_max_sentences():
    """Test that max_sentences is configurable."""
    checker = TLDRChecker(max_sentences=3)

    tldr = "OpenAI выпустила GPT-5. Модель работает быстрее. Цена осталась прежней."
    report = checker.check(tldr)

    assert report.sentence_count == 3
    # Should pass because we allowed 3 sentences
    assert not any("too many sentences" in issue.lower() for issue in report.issues)
