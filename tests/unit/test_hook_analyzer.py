"""Tests for hook quality analyzer."""
import pytest
from pipeline.structure.hook_analyzer import HookAnalyzer, HookReport


def test_analyze_good_hook():
    """Test analysis of a strong hook."""
    analyzer = HookAnalyzer()

    hook = "OpenAI выпустила GPT-5 15 марта 2026 года."
    report = analyzer.analyze(hook)

    assert report.score >= 6
    assert "specific subject" in report.checks_passed


def test_analyze_weak_hook():
    """Test analysis of a weak hook."""
    analyzer = HookAnalyzer()

    hook = "Задумывались ли вы о будущем искусственного интеллекта?"
    report = analyzer.analyze(hook)

    assert report.score < 6
    assert report.passes_threshold is False


def test_specific_subject_detection():
    """Test detection of specific subjects in hooks."""
    analyzer = HookAnalyzer()

    # Test with company name
    hook1 = "Google представила новый продукт."
    report1 = analyzer.analyze(hook1)
    assert "specific subject" in report1.checks_passed

    # Test with product name
    hook2 = "Claude 3 показывает отличные результаты."
    report2 = analyzer.analyze(hook2)
    assert "specific subject" in report2.checks_passed

    # Test without specific subject
    hook3 = "Новая технология изменит мир."
    report3 = analyzer.analyze(hook3)
    assert "specific subject" not in report3.checks_passed


def test_concrete_event_detection():
    """Test detection of concrete events in hooks."""
    analyzer = HookAnalyzer()

    # Test with release event
    hook1 = "OpenAI выпустила новую модель."
    report1 = analyzer.analyze(hook1)
    assert "concrete event" in report1.checks_passed

    # Test with announcement event
    hook2 = "Microsoft announced a major update."
    report2 = analyzer.analyze(hook2)
    assert "concrete event" in report2.checks_passed

    # Test without concrete event
    hook3 = "OpenAI - это интересная компания."
    report3 = analyzer.analyze(hook3)
    assert "concrete event" not in report3.checks_passed


def test_cliche_detection():
    """Test detection of cliche opening phrases."""
    analyzer = HookAnalyzer()

    # Test with Russian cliche
    hook1 = "В современном мире технологии развиваются быстро."
    report1 = analyzer.analyze(hook1)
    assert "not a cliche" not in report1.checks_passed

    # Test with English cliche
    hook2 = "In today's world, AI is everywhere."
    report2 = analyzer.analyze(hook2)
    assert "not a cliche" not in report2.checks_passed

    # Test without cliche
    hook3 = "OpenAI выпустила GPT-5 вчера."
    report3 = analyzer.analyze(hook3)
    assert "not a cliche" in report3.checks_passed


def test_generic_question_detection():
    """Test detection of generic question patterns."""
    analyzer = HookAnalyzer()

    # Test Russian generic question
    hook1 = "Задумывались ли вы о будущем?"
    report1 = analyzer.analyze(hook1)
    assert "not a generic question" not in report1.checks_passed

    # Test English generic question
    hook2 = "Have you ever wondered about AI?"
    report2 = analyzer.analyze(hook2)
    assert "not a generic question" not in report2.checks_passed

    # Test normal statement
    hook3 = "OpenAI выпустила новую модель GPT-5."
    report3 = analyzer.analyze(hook3)
    assert "not a generic question" in report3.checks_passed


def test_active_voice_detection():
    """Test detection of active vs passive voice."""
    analyzer = HookAnalyzer()

    # Test with passive voice (Russian)
    hook1 = "Проект был запущен вчера."
    report1 = analyzer.analyze(hook1)
    assert "active voice" not in report1.checks_passed

    # Test with passive voice (English)
    hook2 = "The model was released yesterday."
    report2 = analyzer.analyze(hook2)
    assert "active voice" not in report2.checks_passed

    # Test with active voice
    hook3 = "OpenAI выпустила GPT-5."
    report3 = analyzer.analyze(hook3)
    assert "active voice" in report3.checks_passed


def test_concise_hook():
    """Test that hooks under 25 words get credit."""
    analyzer = HookAnalyzer()

    # Short hook
    hook1 = "OpenAI выпустила GPT-5."
    report1 = analyzer.analyze(hook1)
    assert "concise" in report1.checks_passed

    # Long hook (over 25 words)
    hook2 = "Это очень длинное предложение которое содержит более двадцати пяти слов и поэтому не должно получать балл за краткость потому что оно слишком длинное для хорошего хука."
    report2 = analyzer.analyze(hook2)
    assert "concise" not in report2.checks_passed


def test_hook_report_dataclass():
    """Test HookReport dataclass fields."""
    analyzer = HookAnalyzer()

    hook = "OpenAI выпустила GPT-5."
    report = analyzer.analyze(hook)

    assert isinstance(report.score, float)
    assert report.max_score == 10.0
    assert isinstance(report.checks_passed, list)
    assert isinstance(report.passes_threshold, bool)
    assert isinstance(report.suggestions, list)


def test_relevance_implied():
    """Test that hooks with content get relevance credit."""
    analyzer = HookAnalyzer()

    # Hook with content
    hook = "OpenAI выпустила GPT-5."
    report = analyzer.analyze(hook)
    assert "relevance implied" in report.checks_passed

    # Very short hook (less than 10 chars)
    hook2 = "Hi"
    report2 = analyzer.analyze(hook2)
    assert "relevance implied" not in report2.checks_passed


def test_suggestions_for_weak_hooks():
    """Test that weak hooks get improvement suggestions."""
    analyzer = HookAnalyzer()

    hook = "В современном мире это важно."
    report = analyzer.analyze(hook)

    assert len(report.suggestions) > 0
    assert report.passes_threshold is False
