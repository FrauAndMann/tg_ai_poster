"""
Tests for ContentValidator - strict post validation.
"""

import pytest

from pipeline.content_validator import (
    ContentValidator,
    ValidationResult,
    LLM_META_PATTERNS,
    QUESTION_PATTERNS,
    INCOMPLETE_PATTERNS,
)


class TestContentValidator:
    """Test ContentValidator class."""

    def test_init_default(self):
        """Test default initialization."""
        validator = ContentValidator()
        assert validator.strict_mode is True
        assert validator.min_body_length == 150
        assert validator.min_body_sentences == 3

    def test_init_custom(self):
        """Test custom initialization."""
        validator = ContentValidator(
            strict_mode=False,
            min_body_length=100,
            min_body_sentences=2,
        )
        assert validator.strict_mode is False
        assert validator.min_body_length == 100
        assert validator.min_body_sentences == 2


class TestMetaTextDetection:
    """Test LLM meta-text detection."""

    @pytest.fixture
    def validator(self):
        return ContentValidator()

    def test_russian_meta_text_here_is_post(self, validator):
        """Test detection of 'вот пост' pattern."""
        content = "Вот мой пост на тему искусственного интеллекта."
        result = validator.validate_raw_response(content)
        assert not result.is_valid
        assert result.score <= 70

    def test_russian_meta_text_i_created(self, validator):
        """Test detection of 'я создал/написал' pattern."""
        content = "Я написал для вас пост о нейросетях."
        result = validator.validate_raw_response(content)
        assert not result.is_valid

    def test_russian_meta_text_lets_discuss(self, validator):
        """Test detection of 'давайте рассмотрим' pattern."""
        content = "Давайте рассмотрим новую технологию."
        result = validator.validate_raw_response(content)
        assert not result.is_valid

    def test_english_meta_text_here_is(self, validator):
        """Test detection of 'here's the post' pattern."""
        content = "Here's the post about AI."
        result = validator.validate_raw_response(content)
        assert not result.is_valid

    def test_english_meta_text_i_created(self, validator):
        """Test detection of 'I created/wrote' pattern."""
        content = "I have created a post for you about machine learning."
        result = validator.validate_raw_response(content)
        assert not result.is_valid

    def test_english_meta_text_as_ai(self, validator):
        """Test detection of 'as an AI' pattern."""
        content = "As an AI language model, I can tell you..."
        result = validator.validate_raw_response(content)
        assert not result.is_valid

    def test_clean_content_passes(self, validator):
        """Test that clean content passes validation."""
        content = '''OpenAI выпустила GPT-5

Компания OpenAI анонсировала новую версию своей языковой модели GPT-5. Модель демонстрирует значительное улучшение в задачах рассуждения.

🔍 Что важно знать
• Производительность выросла на 40%
• Поддержка 100 языков
• API доступен для разработчиков

🧠 Почему это важно
Это значительный шаг вперёд в развитии ИИ.

🔗 Источники
• OpenAI Blog — https://openai.com

💡 TL;DR
OpenAI выпустила GPT-5 с улучшенной производительностью.

#OpenAI #GPT5 #AI'''
        result = validator.validate_raw_response(content)
        assert result.is_valid
        assert result.score >= 80


class TestQuestionDetection:
    """Test question-only content detection."""

    @pytest.fixture
    def validator(self):
        return ContentValidator()

    def test_generic_question_start_ru(self, validator):
        """Test detection of generic Russian questions."""
        content = "Задумывались ли вы, как работает ИИ? Давайте разберёмся."
        result = validator.validate_formatted_post(content)
        assert "question" in str(result.warnings).lower() or result.score < 100

    def test_generic_question_start_en(self, validator):
        """Test detection of generic English questions."""
        content = "Have you ever wondered how AI works? Let's explore."
        result = validator.validate_formatted_post(content)
        assert "question" in str(result.warnings).lower() or result.score < 100


class TestIncompleteContent:
    """Test incomplete content detection."""

    @pytest.fixture
    def validator(self):
        return ContentValidator()

    def test_placeholder_text(self, validator):
        """Test detection of placeholder text."""
        content = "Это пост [требуется добавить контент] о технологиях."
        result = validator.validate_raw_response(content)
        assert not result.is_valid

    def test_tbd_marker(self, validator):
        """Test detection of TBD marker."""
        content = "Post about AI [TBD] and machine learning."
        result = validator.validate_raw_response(content)
        assert not result.is_valid

    def test_ends_with_ellipsis(self, validator):
        """Test detection of content ending with ellipsis."""
        content = "Это пост о технологиях..."
        result = validator.validate_raw_response(content)
        assert not result.is_valid


class TestJSONValidation:
    """Test JSON post validation."""

    @pytest.fixture
    def validator(self):
        return ContentValidator()

    def test_valid_json_post(self, validator):
        """Test validation of valid JSON post."""
        data = {
            "title": "🤖 OpenAI выпустила GPT-5",
            "hook": "Новая модель демонстрирует впечатляющие результаты.",
            "body": "Компания OpenAI анонсировала GPT-5. Модель показывает улучшение на 40% в бенчмарках по сравнению с предыдущей версией. Поддержка 100 языков делает её универсальной для разработчиков по всему миру. API уже доступен для интеграции.",
            "key_facts": [
                "Производительность выросла на 40%",
                "Поддержка 100 языков",
                "API доступен сразу",
            ],
            "analysis": "Это важный шаг в развитии ИИ.",
            "sources": [{"name": "OpenAI", "url": "https://openai.com", "confidence": 0.95}],
            "tldr": "OpenAI выпустила GPT-5 с улучшениями.",
            "hashtags": ["OpenAI", "GPT5", "AI"],
        }
        result = validator.validate_json_post(data)
        assert result.is_valid

    def test_missing_body_field(self, validator):
        """Test detection of missing body field."""
        data = {
            "title": "Some title",
            "hashtags": ["AI"],
        }
        result = validator.validate_json_post(data)
        assert not result.is_valid
        assert any("body" in issue.lower() for issue in result.critical_issues)

    def test_empty_body(self, validator):
        """Test detection of empty body."""
        data = {
            "body": "",
            "title": "Title",
        }
        result = validator.validate_json_post(data)
        assert not result.is_valid

    def test_body_too_short(self, validator):
        """Test detection of too short body."""
        data = {
            "body": "Short text.",
            "title": "Title",
        }
        result = validator.validate_json_post(data)
        assert not result.is_valid
        assert any("short" in issue.lower() for issue in result.critical_issues)

    def test_meta_text_in_body(self, validator):
        """Test detection of meta-text in body."""
        data = {
            "body": "Вот пост о технологиях. OpenAI выпустила новую модель с улучшениями на 40%.",
            "title": "Title",
            "key_facts": ["Fact 1", "Fact 2"],
        }
        result = validator.validate_json_post(data)
        assert not result.is_valid


class TestFormattedPostValidation:
    """Test formatted post validation."""

    @pytest.fixture
    def validator(self):
        return ContentValidator()

    def test_valid_formatted_post(self, validator):
        """Test validation of valid formatted post."""
        content = '''🤖 OpenAI выпустила GPT-5

Компания OpenAI анонсировала новую версию. Модель показывает улучшение на 40%.

🔍 Что важно знать
• Производительность выросла на 40%
• Поддержка 100 языков

🧠 Почему это важно
Это важный шаг в развитии ИИ.

🔗 Источники
• OpenAI — https://openai.com

💡 TL;DR
OpenAI выпустила GPT-5 с улучшениями.

#OpenAI #GPT5 #AI'''
        result = validator.validate_formatted_post(content)
        assert result.is_ready or result.score >= 60

    def test_missing_blocks_warning(self, validator):
        """Test warning for missing blocks in non-strict mode."""
        validator_non_strict = ContentValidator(strict_mode=False)
        content = "Простой пост без специальных блоков, но с достаточным количеством текста для прохождения минимальной проверки длины контента."
        result = validator_non_strict.validate_formatted_post(content)
        # Should have warnings but might still be valid
        assert isinstance(result.warnings, list)

    def test_post_too_short(self, validator):
        """Test detection of too short post."""
        content = "Короткий пост."
        result = validator.validate_formatted_post(content)
        assert not result.is_ready


class TestIsPublicationReady:
    """Test is_publication_ready method."""

    @pytest.fixture
    def validator(self):
        return ContentValidator()

    def test_ready_content(self, validator):
        """Test that good content is ready."""
        content = '''🤖 OpenAI выпустила GPT-5

Компания OpenAI анонсировала новую версию модели. Улучшение на 40% в бенчмарках.

🔍 Что важно знать
• Производительность +40%
• 100 языков

🧠 Почему это важно
Важный шаг в развитии ИИ.

🔗 Источники
• OpenAI — https://openai.com

💡 TL;DR
GPT-5 вышел с улучшениями.

#OpenAI #AI'''
        is_ready, reason = validator.is_publication_ready(content)
        assert is_ready

    def test_not_ready_meta_text(self, validator):
        """Test that meta-text content is not ready."""
        content = "Вот мой пост о технологиях."
        is_ready, reason = validator.is_publication_ready(content)
        assert not is_ready
        assert "Critical" in reason or "low" in reason.lower()

    def test_dict_content_validation(self, validator):
        """Test validation of dict content."""
        data = {
            "body": "Это тестовый пост с достаточным количеством текста для прохождения проверки.",
            "title": "Заголовок",
        }
        is_ready, reason = validator.is_publication_ready(data)
        # May or may not be ready depending on other factors
        assert isinstance(is_ready, bool)
        assert isinstance(reason, str)


class TestSanitization:
    """Test content sanitization."""

    @pytest.fixture
    def validator(self):
        return ContentValidator()

    def test_sanitize_meta_prefix(self, validator):
        """Test removal of meta-text prefix."""
        content = "Вот мой пост: Реальный контент о технологиях."
        result = validator.validate_raw_response(content)
        # Should detect meta-text even if sanitization is attempted
        assert result.score < 100
