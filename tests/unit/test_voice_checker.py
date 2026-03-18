"""Tests for voice checker module."""
import pytest
from pipeline.style.voice_checker import VoiceChecker, VoiceCheckResult


def test_analytical_voice():
    """Test that analytical voice text gets high score."""
    checker = VoiceChecker()

    text = """
    Анализ данных показывает, что рынок ИИ вырос на 45% в 2025 году.
    Согласно исследованию OpenAI, GPT-5 работает в 3 раза быстрее предыдущей версии.
    Сравнение производительности демонстрирует значительное улучшение качества ответов.
    Ключевой фактор успеха - увеличение количества параметров до 1 триллиона.
    """
    result = checker.check(text)

    assert result.score >= 80, f"Expected score >= 80, got {result.score}"
    assert result.is_analytical is True
    assert result.is_promotional is False
    assert result.has_meta_language is False
    assert result.has_cringe_phrases is False
    assert result.is_direct is True
    assert result.grade in ("Excellent", "Good")


def test_promotional_voice():
    """Test that promotional language gets penalized."""
    checker = VoiceChecker()

    text = """
    Не упустите свою возможность! Это уникальное предложение!
    Революционный продукт изменит вашу жизнь!
    Только сегодня - эксклюзивный доступ!
    Закажите прямо сейчас и получите гарантированный результат!
    Подпишитесь на рассылку прямо сейчас!
    """
    result = checker.check(text)

    assert result.score <= 70, f"Expected score <= 70, got {result.score}"
    assert result.is_promotional is True
    assert result.is_analytical is False
    assert len(result.issues) > 0
    assert any("promotional" in issue.lower() for issue in result.issues)
    assert result.grade in ("Reject", "Acceptable")


def test_casual_tone():
    """Test that casual/informal tone is detected."""
    checker = VoiceChecker()

    text = """
    Ну, короче говоря, типа это как бы новая фича.
    В принципе, она работает, может быть даже нормально.
    По сути, это вроде бы полезная штука.
    Вобщем-то, стоит попробовать, пожалуй.
    Возможно, это поможет.
    """
    result = checker.check(text)

    assert result.score <= 85, f"Expected score <= 85, got {result.score}"
    assert result.is_direct is False
    assert len(result.issues) > 0
    # Should have suggestions about using more direct language
    assert any("direct" in s.lower() for s in result.suggestions)


def test_empty_text():
    """Test that empty text returns zero score."""
    checker = VoiceChecker()

    result = checker.check("")

    assert result.score == 100.0  # Empty text has no violations
    assert result.is_analytical is True
    assert result.is_promotional is False
    assert result.has_meta_language is False
    assert result.has_cringe_phrases is False


def test_meta_language_detection():
    """Test that meta-language is detected."""
    checker = VoiceChecker()

    text = """
    В этой статье мы рассмотрим новый продукт.
    В данном материале я расскажу о преимуществах.
    Сегодня мы поговорим о важных изменениях.
    Хочу отметить, что это важно.
    """
    result = checker.check(text)

    assert result.has_meta_language is True
    assert result.score < 85, f"Expected score < 85, got {result.score}"
    assert any("meta" in issue.lower() for issue in result.issues)


def test_cringe_phrases_detection():
    """Test that cringe phrases are detected."""
    checker = VoiceChecker()

    text = """
    Ни для кого не секрет, что технологии развиваются.
    Как известно, ИИ становится популярнее.
    Все мы знаем, что данные - это новая нефть.
    Друзья, вы наверняка слышали о ChatGPT.
    Само собой разумеется, это важно.
    """
    result = checker.check(text)

    assert result.has_cringe_phrases is True
    assert result.score <= 75, f"Expected score <= 75, got {result.score}"
    assert any("cringe" in issue.lower() for issue in result.issues)


def test_grade_property():
    """Test grade calculation based on score."""
    # Test Excellent (90+)
    result = VoiceCheckResult(score=95.0)
    assert result.grade == "Excellent"

    # Test Good (80-89)
    result = VoiceCheckResult(score=85.0)
    assert result.grade == "Good"

    # Test Acceptable (70-79)
    result = VoiceCheckResult(score=75.0)
    assert result.grade == "Acceptable"

    # Test Reject (<70)
    result = VoiceCheckResult(score=60.0)
    assert result.grade == "Reject"


def test_mixed_content():
    """Test text with both analytical and problematic elements."""
    checker = VoiceChecker()

    text = """
    Анализ показывает рост на 30%. Однако, не упустите возможность!
    Данные исследования подтверждают эффективность.
    Это революционный продукт, который изменит вашу жизнь.
    Сравнение с конкурентами демонстрирует преимущества.
    """
    result = checker.check(text)

    # Should have analytical elements but be penalized for promotional
    assert result.is_promotional is True
    # Score should be reduced due to promotional content
    assert result.score < 85


def test_english_text():
    """Test voice checking for English text."""
    checker = VoiceChecker()

    # Good analytical English text
    good_text = """
    Analysis shows that the market grew by 45% in 2025.
    According to research, the new model performs 3x faster.
    Data indicates significant improvement in response quality.
    The key factor is the increased parameter count.
    """
    result = checker.check(good_text)
    assert result.score >= 80

    # Promotional English text
    bad_text = """
    Don't miss out on this exclusive offer!
    This revolutionary product will change your life!
    Order now and get guaranteed results!
    Limited time only!
    Hurry up and buy now!
    """
    result = checker.check(bad_text)
    assert result.is_promotional is True
    assert result.score <= 70


def test_suggestions_are_provided():
    """Test that suggestions are provided for problematic content."""
    checker = VoiceChecker()

    text = "Не упустите возможность! Это революционный продукт!"
    result = checker.check(text)

    assert len(result.suggestions) > 0
    assert isinstance(result.suggestions, list)


def test_custom_threshold():
    """Test that custom pass threshold works."""
    checker = VoiceChecker(pass_threshold=80.0)

    assert checker.pass_threshold == 80.0


def test_default_threshold():
    """Test that default pass threshold is 70.0."""
    checker = VoiceChecker()

    assert checker.pass_threshold == 70.0


def test_voice_check_result_defaults():
    """Test VoiceCheckResult default values."""
    result = VoiceCheckResult()

    assert result.score == 0.0
    assert result.is_analytical is True
    assert result.is_promotional is False
    assert result.is_direct is True
    assert result.has_meta_language is False
    assert result.has_cringe_phrases is False
    assert result.issues == []
    assert result.suggestions == []


def test_checker_grade_property():
    """Test the grade property of VoiceChecker."""
    checker = VoiceChecker()

    assert isinstance(checker.grade, str)
    assert "VoiceChecker" in checker.grade
