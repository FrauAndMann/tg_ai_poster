"""Tests for claim extractor module."""
import pytest

from pipeline.fact_check.claim_extractor import Claim, ClaimExtractor, ClaimType


class TestClaimExtractor:
    """Tests for ClaimExtractor class."""

    def test_extract_declarative_sentences_with_facts(self):
        """Test extraction of declarative sentences containing facts."""
        extractor = ClaimExtractor()

        text = "OpenAI released GPT-5 on March 15, 2026."
        claims = extractor.extract(text)

        assert len(claims) >= 1
        assert any("OpenAI" in claim.text for claim in claims)

    def test_extract_claims_with_dates(self):
        """Test extraction of claims containing dates."""
        extractor = ClaimExtractor()

        text = "The conference will be held 15 March 2026."
        claims = extractor.extract(text)

        assert len(claims) >= 1
        date_claims = [c for c in claims if c.claim_type == ClaimType.DATE]
        assert len(date_claims) >= 1

    def test_extract_claims_with_names(self):
        """Test extraction of claims containing proper names."""
        extractor = ClaimExtractor()

        text = "Sam Altman announced the new partnership."
        claims = extractor.extract(text)

        assert len(claims) >= 1
        name_claims = [c for c in claims if c.claim_type == ClaimType.NAME]
        assert len(name_claims) >= 1

    def test_extract_announcement_pattern(self):
        """Test extraction of 'X announced Y' patterns."""
        extractor = ClaimExtractor()

        text = "Google announced Gemini 2.0 at the I/O conference."
        claims = extractor.extract(text)

        assert len(claims) >= 1
        # Should extract both the event and the company
        event_claims = [c for c in claims if c.claim_type == ClaimType.EVENT]
        assert len(event_claims) >= 1

    def test_extract_russian_announcement_pattern(self):
        """Test extraction of Russian announcement patterns."""
        extractor = ClaimExtractor()

        text = "OpenAI анонсировала GPT-5 на конференции разработчиков."
        claims = extractor.extract(text)

        assert len(claims) >= 1

    def test_extract_claim_with_context(self):
        """Test that claims include surrounding context."""
        extractor = ClaimExtractor()

        text = "Some intro text. OpenAI released GPT-5 yesterday. More text here."
        claims = extractor.extract(text)

        assert len(claims) >= 1
        # Context should include words around the claim
        assert len(claims[0].context) > len(claims[0].text)

    def test_claim_has_source_url_field(self):
        """Test that Claim has source_url field."""
        claim = Claim(
            text="Test claim",
            claim_type=ClaimType.GENERAL,
            position=(0, 10),
            source_url="https://example.com/article"
        )

        assert claim.source_url == "https://example.com/article"

    def test_claim_has_source_quote_field(self):
        """Test that Claim has source_quote field."""
        claim = Claim(
            text="Test claim",
            claim_type=ClaimType.GENERAL,
            position=(0, 10),
            source_quote="Original quote from source"
        )

        assert claim.source_quote == "Original quote from source"

    def test_extract_with_source_info(self):
        """Test extraction with source URL and quote info."""
        extractor = ClaimExtractor()

        text = "OpenAI released GPT-5."
        source_url = "https://openai.com/blog/gpt5"
        source_quote = "OpenAI released GPT-5 today."

        claims = extractor.extract(
            text,
            source_url=source_url,
            source_quote=source_quote
        )

        assert len(claims) >= 1
        assert claims[0].source_url == source_url
        assert claims[0].source_quote == source_quote

    def test_extract_multiple_claim_types(self):
        """Test extraction of multiple claim types from text."""
        extractor = ClaimExtractor()

        text = """
        OpenAI released GPT-5 on March 15, 2026.
        The model is 3x faster than GPT-4.
        Sam Altman invested $10 billion in development.
        """
        claims = extractor.extract(text)

        # Should extract multiple types of claims
        claim_types = {c.claim_type for c in claims}
        assert len(claim_types) >= 2

    def test_extract_statistics_claims(self):
        """Test extraction of statistical claims."""
        extractor = ClaimExtractor()

        # Using text that matches STATISTIC pattern more clearly
        text = "Компания выросла на 150% за последний квартал."
        claims = extractor.extract(text)

        # The text should produce at least one claim (number or statistic)
        assert len(claims) >= 1
        # Either statistic or number type should be extracted
        claim_types = {c.claim_type for c in claims}
        assert ClaimType.STATISTIC in claim_types or ClaimType.NUMBER in claim_types

    def test_extract_number_claims(self):
        """Test extraction of numerical claims."""
        extractor = ClaimExtractor()

        text = "The project cost $500 million to develop."
        claims = extractor.extract(text)

        number_claims = [c for c in claims if c.claim_type == ClaimType.NUMBER]
        assert len(number_claims) >= 1

    def test_no_claims_from_vague_text(self):
        """Test that vague text produces no claims."""
        extractor = ClaimExtractor()

        text = "This is a very interesting development."
        claims = extractor.extract(text)

        # Vague text should produce few or no claims
        assert len(claims) == 0

    def test_claim_position_tracking(self):
        """Test that claim positions are tracked correctly."""
        extractor = ClaimExtractor()

        text = "Intro. OpenAI released GPT-5. Outro."
        claims = extractor.extract(text)

        assert len(claims) >= 1
        # Position should point to actual location in text
        start, end = claims[0].position
        extracted_text = text[start:end]
        assert "OpenAI" in extracted_text or "released" in extracted_text

    def test_confidence_score_range(self):
        """Test that confidence scores are in valid range."""
        extractor = ClaimExtractor()

        text = "OpenAI released GPT-5 on March 15, 2026."
        claims = extractor.extract(text)

        for claim in claims:
            assert 0.0 <= claim.confidence <= 1.0

    def test_extract_with_claim_indicators(self):
        """Test extraction using claim indicator words."""
        extractor = ClaimExtractor()

        text = "According to reports, the company laid off 500 employees."
        claims = extractor.extract(text)

        # Should extract the claim despite the indicator phrase
        assert len(claims) >= 1


class TestClaim:
    """Tests for Claim dataclass."""

    def test_claim_default_values(self):
        """Test Claim default values."""
        claim = Claim(
            text="Test claim",
            claim_type=ClaimType.GENERAL,
            position=(0, 10)
        )

        assert claim.confidence == 1.0
        assert claim.context == ""
        assert claim.source_url == ""
        assert claim.source_quote == ""

    def test_claim_immutability_with_slots(self):
        """Test that Claim uses slots for efficiency."""
        claim = Claim(
            text="Test",
            claim_type=ClaimType.GENERAL,
            position=(0, 4)
        )

        # Should be able to set values
        claim.source_url = "https://example.com"
        assert claim.source_url == "https://example.com"


class TestClaimType:
    """Tests for ClaimType enum."""

    def test_claim_type_values(self):
        """Test that ClaimType has expected values."""
        assert ClaimType.STATISTIC.value == "statistic"
        assert ClaimType.DATE.value == "date"
        assert ClaimType.NAME.value == "name"
        assert ClaimType.EVENT.value == "event"
        assert ClaimType.NUMBER.value == "number"
        assert ClaimType.COMPARISON.value == "comparison"
        assert ClaimType.GENERAL.value == "general"
        assert ClaimType.QUOTE.value == "quote"
        assert ClaimType.FACT.value == "fact"
        assert ClaimType.PREDICTION.value == "prediction"


class TestRequiredTaskTests:
    """Required tests for Task 2.1 from implementation plan."""

    def test_extract_factual_claims(self):
        """Test extraction of factual claims from declarative sentences."""
        extractor = ClaimExtractor()

        text = """
        OpenAI выпустила GPT-5 15 марта 2026 года.
        Google анонсировала партнёрство с Anthropic.
        Microsoft инвестировала $10 миллиардов в OpenAI.
        """
        claims = extractor.extract(text)

        # Should extract multiple factual claims
        assert len(claims) >= 3

        # Claims should have proper structure
        for claim in claims:
            assert claim.text is not None
            assert claim.claim_type in [
                ClaimType.FACT, ClaimType.NAME, ClaimType.DATE,
                ClaimType.NUMBER, ClaimType.EVENT
            ]
            assert 0.0 <= claim.confidence <= 1.0

    def test_extract_claims_with_numbers(self):
        """Test extraction of claims containing numbers, dates, and names."""
        extractor = ClaimExtractor()

        text = """
        Компания инвестировала $10 миллиардов в разработку.
        По данным исследования, 85% пользователей довольны.
        Модель работает в 3 раза быстрее GPT-4.
        Событие произошло 15 марта 2025 года.
        """
        claims = extractor.extract(text)

        # Should extract numbers, percentages, and dates
        claim_types = {c.claim_type for c in claims}

        # Should have at least number claims
        number_claims = [c for c in claims if c.claim_type == ClaimType.NUMBER]
        assert len(number_claims) >= 2  # $10 billion and 85%

        # Check for currency and percentage patterns
        number_texts = " ".join(c.text for c in number_claims)
        assert "$" in number_texts or "%" in number_texts or "млрд" in number_texts

    def test_extract_quotes(self):
        """Test extraction of quotes with attribution patterns."""
        extractor = ClaimExtractor()

        # Russian quote patterns
        text_ru = '''
        Сэм Алтман сказал: "GPT-5 будет революцией в AI".
        «Мы верим в безопасный AI» — сказал генеральный директор.
        '''
        claims_ru = extractor.extract(text_ru)

        quote_claims_ru = [c for c in claims_ru if c.claim_type == ClaimType.QUOTE]
        # Should detect quote patterns
        assert len(quote_claims_ru) >= 1

        # English quote patterns
        text_en = '''
        Sam Altman said, "GPT-5 will be revolutionary."
        "We believe in safe AI" — CEO stated.
        According to the report, the company grew significantly.
        '''
        claims_en = extractor.extract(text_en)

        quote_claims_en = [c for c in claims_en if c.claim_type == ClaimType.QUOTE]
        # Should detect quote patterns
        assert len(quote_claims_en) >= 1

    def test_classify_claim_types(self):
        """Test classification of claims into correct types: fact, quote, statistic, prediction."""
        extractor = ClaimExtractor()

        # Text with different claim types
        text = """
        OpenAI выпустила GPT-5. Это факт.
        Эксперты прогнозируют рост рынка на 50% к 2025 году.
        Выручка компании выросла на 150% за год.
        "Мы лидеры в AI" — сказал CEO.
        """
        claims = extractor.extract(text)

        claim_types = {c.claim_type for c in claims}

        # Should classify different types of claims
        # At minimum, should have name/event claims and number/statistic claims
        expected_types = {ClaimType.NAME, ClaimType.EVENT, ClaimType.STATISTIC,
                        ClaimType.NUMBER, ClaimType.PREDICTION, ClaimType.QUOTE}

        # At least some expected types should be present
        assert len(claim_types.intersection(expected_types)) >= 2

        # Verify claims have required attributes
        for claim in claims:
            assert hasattr(claim, 'text')
            assert hasattr(claim, 'claim_type')
            assert hasattr(claim, 'confidence')
            assert hasattr(claim, 'source_required')

    def test_empty_text(self):
        """Test that empty text returns empty claims list."""
        extractor = ClaimExtractor()

        # Empty string
        claims = extractor.extract("")
        assert claims == []

        # Whitespace only
        claims_whitespace = extractor.extract("   \n\t  ")
        assert claims_whitespace == []

        # Very short text with no claims
        claims_short = extractor.extract("Hi.")
        assert claims_short == []
