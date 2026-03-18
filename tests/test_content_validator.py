"""
Tests for ContentValidator - strict post validation.
"""

import pytest

from pipeline.content_validator import (
    ContentValidator,
    KeyFactsValidationResult,
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
        content = """OpenAI выпустила GPT-5

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

#OpenAI #GPT5 #AI"""
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
            "sources": [
                {"name": "OpenAI", "url": "https://openai.com", "confidence": 0.95}
            ],
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
        content = """🤖 OpenAI выпустила GPT-5

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

#OpenAI #GPT5 #AI"""
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
        content = """🤖 OpenAI выпустила GPT-5

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

#OpenAI #AI"""
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


class TestValidateKeyFacts:
    """Test validate_key_facts method."""

    @pytest.fixture
    def validator(self):
        return ContentValidator()

    def test_validate_key_facts_count(self, validator):
        """Test that key facts count must be 4-5."""
        # Too few facts
        few_facts = ["Fact 1", "Fact 2"]
        result = validator.validate_key_facts(few_facts)
        assert not result.is_valid
        assert "Too few key facts" in " ".join(result.issues)
        assert result.facts_count == 2

        # Too many facts
        many_facts = ["Fact 1", "Fact 2", "Fact 3", "Fact 4", "Fact 5", "Fact 6"]
        result = validator.validate_key_facts(many_facts)
        assert not result.is_valid
        assert "Too many key facts" in " ".join(result.issues)
        assert result.facts_count == 6

        # Valid count (4 facts)
        valid_4_facts = ["Fact 1", "Fact 2", "Fact 3", "Fact 4"]
        result = validator.validate_key_facts(valid_4_facts)
        assert result.facts_count == 4
        # Should not have count-related issues
        count_issues = [i for i in result.issues if "key facts" in i.lower()]
        assert len(count_issues) == 0

        # Valid count (5 facts)
        valid_5_facts = ["Fact 1", "Fact 2", "Fact 3", "Fact 4", "Fact 5"]
        result = validator.validate_key_facts(valid_5_facts)
        assert result.facts_count == 5
        # Should not have count-related issues
        count_issues = [i for i in result.issues if "key facts" in i.lower()]
        assert len(count_issues) == 0

    def test_validate_key_facts_structure(self, validator):
        """Test that each fact must be a single sentence."""
        # Compound fact with multiple sentences
        compound_facts = [
            "First fact. Second sentence.",  # Multiple sentences
            "Fact 2",
            "Fact 3",
            "Fact 4",
        ]
        result = validator.validate_key_facts(compound_facts)
        assert not result.is_valid
        assert any("multiple sentences" in i.lower() or "compound" in i.lower() for i in result.issues)

        # Non-string fact
        non_string_facts = ["Fact 1", 123, "Fact 3", "Fact 4"]
        result = validator.validate_key_facts(non_string_facts)
        assert not result.is_valid
        assert any("not a string" in i.lower() for i in result.issues)

        # Empty fact
        empty_facts = ["Fact 1", "", "Fact 3", "Fact 4"]
        result = validator.validate_key_facts(empty_facts)
        assert not result.is_valid
        assert any("empty" in i.lower() for i in result.issues)

    def test_validate_key_facts_independently_verifiable(self, validator):
        """Test that each fact must be independently verifiable (no overlapping facts)."""
        # Overlapping facts (high similarity - almost identical content)
        overlapping_facts = [
            "OpenAI released GPT-4 with 40% improvement in benchmarks",
            "OpenAI released GPT-4 with 40% improvement in benchmarks",  # Exact duplicate
            "The model supports 100 languages worldwide",
            "API is available for all developers",
        ]
        result = validator.validate_key_facts(overlapping_facts)
        assert not result.is_valid
        assert any("overlap" in i.lower() for i in result.issues)

        # Non-overlapping, independently verifiable facts
        good_facts = [
            "OpenAI released GPT-4 on March 14, 2023",
            "The model shows 40% improvement in benchmarks",
            "GPT-4 supports 100 languages worldwide",
            "API pricing starts at $0.03 per 1K tokens",
        ]
        result = validator.validate_key_facts(good_facts)
        # Should have no overlap issues (may have other issues like no metrics)
        overlap_issues = [i for i in result.issues if "overlap" in i.lower()]
        assert len(overlap_issues) == 0

    def test_validate_key_facts_format(self, validator):
        """Test that key facts use proper format (bullet points)."""
        # This test validates that the method accepts properly formatted facts
        # The actual formatting is done in the post formatter
        properly_formatted = [
            "OpenAI released GPT-4 on March 14, 2023",
            "The model shows 40% improvement in benchmarks",
            "GPT-4 supports 100 languages",
            "API pricing starts at $0.03 per 1K tokens",
        ]
        result = validator.validate_key_facts(properly_formatted)
        assert result.facts_count == 4
        # Check that result has proper structure
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'score')
        assert hasattr(result, 'issues')
        assert hasattr(result, 'facts_count')
        assert hasattr(result, 'has_metrics')

    def test_validate_key_facts_with_no_numbers(self, validator):
        """Test that facts without any metrics/numbers trigger a warning."""
        facts_no_numbers = [
            "OpenAI released a new model recently",
            "The model supports many languages",
            "API is available for developers",
            "The company is based in San Francisco",
        ]
        result = validator.validate_key_facts(facts_no_numbers)
        assert not result.is_valid
        assert not result.has_metrics
        assert any("metrics" in i.lower() or "numbers" in i.lower() for i in result.issues)

    def test_validate_key_facts_have_at_least_one_metric(self, validator):
        """Test that at least one fact has a metric/number."""
        facts_with_metric = [
            "OpenAI released GPT-4 with 40% improvement",
            "The model supports 100 languages",
            "API is available for developers",
            "The company is based in San Francisco",
        ]
        result = validator.validate_key_facts(facts_with_metric)
        assert result.has_metrics is True
        # Should not have the "no metrics" issue
        metric_issues = [i for i in result.issues if "metrics" in i.lower() or "numbers" in i.lower()]
        assert len(metric_issues) == 0


class TestValidateKeyFactsTLDR:
    """Test TLDR validation within validate_key_facts."""

    @pytest.fixture
    def validator(self):
        return ContentValidator()

    def test_tldr_max_2_sentences(self, validator):
        """Test that TLDR must be max 2 sentences."""
        good_facts = [
            "OpenAI released GPT-4 with 40% improvement",
            "The model supports 100 languages",
            "API is available for developers",
            "The company is based in San Francisco",
        ]

        # TLDR with 3 sentences (too many)
        long_tldr = "OpenAI released GPT-4. The model is improved. It supports many languages."
        result = validator.validate_key_facts(good_facts, tldr=long_tldr)
        assert not result.tldr_valid
        assert result.tldr_sentence_count == 3
        assert any("too many sentences" in i.lower() for i in result.issues)

    def test_tldr_meaningful_without_full_post(self, validator):
        """Test that TLDR is meaningful without reading full post."""
        good_facts = [
            "OpenAI released GPT-4 with 40% improvement",
            "The model supports 100 languages",
            "API is available for developers",
            "The company is based in San Francisco",
        ]

        # TLDR with meta-language (not self-contained)
        meta_tldr = "This post discusses the new GPT-4 release from OpenAI."
        result = validator.validate_key_facts(good_facts, tldr=meta_tldr)
        assert not result.tldr_valid
        assert any("meta" in i.lower() or "self-referential" in i.lower() for i in result.issues)

    def test_tldr_self_contained(self, validator):
        """Test that TLDR passes self-contained check."""
        good_facts = [
            "OpenAI released GPT-4 with 40% improvement",
            "The model supports 100 languages",
            "API is available for developers",
            "The company is based in San Francisco",
        ]

        # Good TLDR (self-contained)
        good_tldr = "OpenAI released GPT-4 with 40% improvement and 100 language support."
        result = validator.validate_key_facts(good_facts, tldr=good_tldr)
        assert result.tldr_valid
        assert result.tldr_sentence_count == 1

    def test_tldr_too_short(self, validator):
        """Test that TLDR is not too short."""
        good_facts = [
            "OpenAI released GPT-4 with 40% improvement",
            "The model supports 100 languages",
            "API is available for developers",
            "The company is based in San Francisco",
        ]

        # TLDR too short
        short_tldr = "GPT-4 released."
        result = validator.validate_key_facts(good_facts, tldr=short_tldr)
        assert not result.tldr_valid
        assert any("too short" in i.lower() for i in result.issues)


class TestKeyFactsValidationResult:
    """Test KeyFactsValidationResult dataclass."""

    def test_result_to_dict(self):
        """Test that KeyFactsValidationResult can be converted to dict."""
        result = KeyFactsValidationResult(
            is_valid=True,
            score=95.0,
            issues=[],
            facts_count=4,
            has_metrics=True,
            tldr_valid=True,
            tldr_sentence_count=1,
        )
        result_dict = result.to_dict()

        assert result_dict["is_valid"] is True
        assert result_dict["score"] == 95.0
        assert result_dict["facts_count"] == 4
        assert result_dict["has_metrics"] is True
        assert result_dict["tldr_valid"] is True
        assert result_dict["tldr_sentence_count"] == 1

    def test_result_default_values(self):
        """Test KeyFactsValidationResult default values."""
        result = KeyFactsValidationResult(is_valid=True, score=100.0)

        assert result.issues == []
        assert result.facts_count == 0
        assert result.has_metrics is False
        assert result.tldr_valid is True
        assert result.tldr_sentence_count == 0
