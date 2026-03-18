"""Tests for source mapper module."""
import pytest

from pipeline.fact_check.claim_extractor import Claim, ClaimType
from pipeline.fact_check.source_mapper import (
    ClaimSource,
    SourceMapper,
    SourceMappingResult,
)


class TestClaimSource:
    """Tests for ClaimSource dataclass."""

    def test_claim_source_creation(self):
        """Test creating a ClaimSource instance."""
        mapping = ClaimSource(
            claim_text="OpenAI released GPT-5",
            source_url="https://openai.com/blog/gpt5",
            source_quote="OpenAI released GPT-5 today",
            confidence=0.95,
        )

        assert mapping.claim_text == "OpenAI released GPT-5"
        assert mapping.source_url == "https://openai.com/blog/gpt5"
        assert mapping.source_quote == "OpenAI released GPT-5 today"
        assert mapping.confidence == 0.95

    def test_claim_source_confidence_validation_low(self):
        """Test that confidence below 0.0 raises error."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            ClaimSource(
                claim_text="Test claim",
                source_url="https://example.com",
                source_quote="Quote",
                confidence=-0.1,
            )

    def test_claim_source_confidence_validation_high(self):
        """Test that confidence above 1.0 raises error."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            ClaimSource(
                claim_text="Test claim",
                source_url="https://example.com",
                source_quote="Quote",
                confidence=1.5,
            )

    def test_claim_source_confidence_boundary_values(self):
        """Test confidence at boundary values 0.0 and 1.0."""
        # Min boundary
        mapping_min = ClaimSource(
            claim_text="Test",
            source_url="https://example.com",
            source_quote="Quote",
            confidence=0.0,
        )
        assert mapping_min.confidence == 0.0

        # Max boundary
        mapping_max = ClaimSource(
            claim_text="Test",
            source_url="https://example.com",
            source_quote="Quote",
            confidence=1.0,
        )
        assert mapping_max.confidence == 1.0


class TestSourceMappingResult:
    """Tests for SourceMappingResult dataclass."""

    def test_default_values(self):
        """Test default values for SourceMappingResult."""
        result = SourceMappingResult()

        assert result.mapped_claims == []
        assert result.unmapped_claims == []
        assert result.footnotes == []
        assert result.passes_validation is True
        assert result.coverage_ratio == 1.0
        assert result.warnings == []

    def test_with_values(self):
        """Test SourceMappingResult with values."""
        mapping = ClaimSource(
            claim_text="Test",
            source_url="https://example.com",
            source_quote="Quote",
            confidence=0.9,
        )

        result = SourceMappingResult(
            mapped_claims=[mapping],
            unmapped_claims=[],
            footnotes=["[1] https://example.com"],
            passes_validation=True,
            coverage_ratio=1.0,
            warnings=[],
        )

        assert len(result.mapped_claims) == 1
        assert result.passes_validation is True


class TestSourceMapper:
    """Tests for SourceMapper class."""

    def test_claim_source_mapping(self):
        """Test mapping claims to sources."""
        mapper = SourceMapper()

        text = "OpenAI released GPT-5 on March 15, 2026."
        source_url = "https://openai.com/blog/gpt5"
        source_quote = "OpenAI released GPT-5 today"

        result = mapper.map_claims_to_sources(
            text=text,
            source_url=source_url,
            source_quote=source_quote,
        )

        assert isinstance(result, SourceMappingResult)
        assert len(result.mapped_claims) >= 1
        assert result.passes_validation is True
        assert result.coverage_ratio == 1.0

    def test_empty_text(self):
        """Test mapping with empty text."""
        mapper = SourceMapper()

        result = mapper.map_claims_to_sources(
            text="",
            source_url="https://example.com",
            source_quote="",
        )

        assert isinstance(result, SourceMappingResult)
        assert len(result.mapped_claims) == 0
        assert len(result.unmapped_claims) == 0
        assert result.passes_validation is True
        assert result.coverage_ratio == 1.0

    def test_mapping_with_existing_mappings(self):
        """Test mapping with pre-existing claim-source mappings."""
        mapper = SourceMapper()

        # Create claims directly to test existing mapping functionality
        claims = [
            Claim(
                text="150%",
                claim_type=ClaimType.STATISTIC,
                position=(0, 4),
                source_required=True,
                source_url="",
            ),
        ]

        existing_mapping = ClaimSource(
            claim_text="150%",
            source_url="https://example.com/report",
            source_quote="The company grew by 150%",
            confidence=0.9,
        )

        result = mapper.map_extracted_claims(
            claims=claims,
            existing_mappings=[existing_mapping],
        )

        # Should map the statistic claim to the existing source
        assert len(result.mapped_claims) == 1
        assert result.passes_validation is True

    def test_mapping_with_unmapped_claims(self):
        """Test mapping when some claims cannot be mapped."""
        mapper = SourceMapper()

        # Create claims manually without source info
        claims = [
            Claim(
                text="Some claim without source",
                claim_type=ClaimType.FACT,
                position=(0, 24),
                source_required=True,
                source_url="",  # No source
            ),
        ]

        result = mapper.map_extracted_claims(claims)

        assert len(result.unmapped_claims) == 1
        assert result.passes_validation is False
        assert result.coverage_ratio == 0.0
        assert len(result.warnings) == 1

    def test_mapping_with_partial_coverage(self):
        """Test mapping with partial source coverage."""
        mapper = SourceMapper()

        claims = [
            Claim(
                text="Claim with source",
                claim_type=ClaimType.FACT,
                position=(0, 17),
                source_required=True,
                source_url="https://example.com/1",
            ),
            Claim(
                text="Claim without source",
                claim_type=ClaimType.FACT,
                position=(18, 38),
                source_required=True,
                source_url="",
            ),
        ]

        result = mapper.map_extracted_claims(claims)

        assert len(result.mapped_claims) == 1
        assert len(result.unmapped_claims) == 1
        assert result.passes_validation is False
        assert result.coverage_ratio == 0.5

    def test_footnote_generation_numbered(self):
        """Test footnote generation with numbered format."""
        mapper = SourceMapper()

        mappings = [
            ClaimSource(
                claim_text="Claim 1",
                source_url="https://example.com/1",
                source_quote="Quote 1",
                confidence=0.9,
            ),
            ClaimSource(
                claim_text="Claim 2",
                source_url="https://example.com/2",
                source_quote="Quote 2",
                confidence=0.8,
            ),
        ]

        footnotes = mapper.generate_footnotes(mappings, format_style="numbered")

        assert len(footnotes) == 2
        assert footnotes[0] == '[1] "Quote 1" - https://example.com/1'
        assert footnotes[1] == '[2] "Quote 2" - https://example.com/2'

    def test_footnote_generation_bracket(self):
        """Test footnote generation with bracket format."""
        mapper = SourceMapper()

        mappings = [
            ClaimSource(
                claim_text="Claim 1",
                source_url="https://example.com/1",
                source_quote="Quote 1",
                confidence=0.9,
            ),
        ]

        footnotes = mapper.generate_footnotes(mappings, format_style="bracket")

        assert len(footnotes) == 1
        assert "¹" in footnotes[0]
        assert "https://example.com/1" in footnotes[0]

    def test_footnote_generation_simple(self):
        """Test footnote generation with simple format."""
        mapper = SourceMapper()

        mappings = [
            ClaimSource(
                claim_text="Claim 1",
                source_url="https://example.com/1",
                source_quote="Quote 1",
                confidence=0.9,
            ),
        ]

        footnotes = mapper.generate_footnotes(mappings, format_style="simple")

        assert len(footnotes) == 1
        assert footnotes[0] == "https://example.com/1"

    def test_footnote_without_quote(self):
        """Test footnote generation without quote."""
        mapper = SourceMapper()

        mappings = [
            ClaimSource(
                claim_text="Claim 1",
                source_url="https://example.com/1",
                source_quote="",  # No quote
                confidence=0.9,
            ),
        ]

        footnotes = mapper.generate_footnotes(mappings, format_style="numbered")

        assert footnotes[0] == "[1] https://example.com/1"

    def test_footnotes_deduplicate_urls(self):
        """Test that duplicate URLs are deduplicated in footnotes."""
        mapper = SourceMapper()

        mappings = [
            ClaimSource(
                claim_text="Claim 1",
                source_url="https://example.com/same",
                source_quote="Quote 1",
                confidence=0.9,
            ),
            ClaimSource(
                claim_text="Claim 2",
                source_url="https://example.com/same",  # Same URL
                source_quote="Quote 2",
                confidence=0.8,
            ),
        ]

        footnotes = mapper.generate_footnotes(mappings)

        assert len(footnotes) == 1  # Only one footnote for duplicate URL

    def test_validate_source_coverage(self):
        """Test quick source coverage validation."""
        mapper = SourceMapper()

        text = "OpenAI released GPT-5."
        source_url = "https://openai.com/blog/gpt5"

        passes, ratio, warnings = mapper.validate_source_coverage(text, source_url)

        assert isinstance(passes, bool)
        assert isinstance(ratio, float)
        assert isinstance(warnings, list)
        assert 0.0 <= ratio <= 1.0

    def test_validate_source_coverage_no_source(self):
        """Test validation when no source is provided."""
        mapper = SourceMapper()

        # Use text that will generate source_required claims
        text = "The company grew by 150% last quarter."

        passes, ratio, warnings = mapper.validate_source_coverage(text, "")

        # Without a source URL, the claims won't have sources
        assert passes is False
        assert ratio < 1.0
        assert len(warnings) > 0

    def test_add_source_to_claim(self):
        """Test creating a new claim-source mapping."""
        mapper = SourceMapper()

        mapping = mapper.add_source_to_claim(
            claim_text="OpenAI released GPT-5",
            source_url="https://openai.com/blog/gpt5",
            source_quote="OpenAI released GPT-5 today",
            confidence=0.95,
        )

        assert isinstance(mapping, ClaimSource)
        assert mapping.claim_text == "OpenAI released GPT-5"
        assert mapping.confidence == 0.95

    def test_get_footnotes_text(self):
        """Test generating complete footnotes section."""
        mapper = SourceMapper()

        mappings = [
            ClaimSource(
                claim_text="Claim 1",
                source_url="https://example.com/1",
                source_quote="Quote 1",
                confidence=0.9,
            ),
        ]

        footnotes_text = mapper.get_footnotes_text(mappings)

        assert "Источники:" in footnotes_text
        assert "https://example.com/1" in footnotes_text

    def test_get_footnotes_text_empty(self):
        """Test footnotes section with no mappings."""
        mapper = SourceMapper()

        footnotes_text = mapper.get_footnotes_text([])

        assert footnotes_text == ""

    def test_get_footnotes_text_custom_header(self):
        """Test footnotes section with custom header."""
        mapper = SourceMapper()

        mappings = [
            ClaimSource(
                claim_text="Claim 1",
                source_url="https://example.com/1",
                source_quote="Quote 1",
                confidence=0.9,
            ),
        ]

        footnotes_text = mapper.get_footnotes_text(mappings, header="Sources:")

        assert "Sources:" in footnotes_text

    def test_filter_high_confidence_mappings(self):
        """Test filtering mappings by confidence."""
        mapper = SourceMapper(min_confidence=0.7)

        mappings = [
            ClaimSource(
                claim_text="Claim 1",
                source_url="https://example.com/1",
                source_quote="Quote 1",
                confidence=0.9,
            ),
            ClaimSource(
                claim_text="Claim 2",
                source_url="https://example.com/2",
                source_quote="Quote 2",
                confidence=0.5,  # Below threshold
            ),
            ClaimSource(
                claim_text="Claim 3",
                source_url="https://example.com/3",
                source_quote="Quote 3",
                confidence=0.8,
            ),
        ]

        filtered = mapper.filter_high_confidence_mappings(mappings)

        assert len(filtered) == 2
        assert all(m.confidence >= 0.7 for m in filtered)

    def test_filter_high_confidence_mappings_custom_threshold(self):
        """Test filtering with custom confidence threshold."""
        mapper = SourceMapper()

        mappings = [
            ClaimSource(
                claim_text="Claim 1",
                source_url="https://example.com/1",
                source_quote="Quote 1",
                confidence=0.9,
            ),
            ClaimSource(
                claim_text="Claim 2",
                source_url="https://example.com/2",
                source_quote="Quote 2",
                confidence=0.6,
            ),
        ]

        filtered = mapper.filter_high_confidence_mappings(mappings, min_confidence=0.8)

        assert len(filtered) == 1
        assert filtered[0].confidence == 0.9

    def test_claims_not_requiring_sources(self):
        """Test that claims with source_required=False are ignored."""
        mapper = SourceMapper()

        claims = [
            Claim(
                text="Some name",
                claim_type=ClaimType.NAME,
                position=(0, 9),
                source_required=False,  # Doesn't require source
            ),
        ]

        result = mapper.map_extracted_claims(claims)

        # Claims not requiring sources should not affect validation
        assert len(result.mapped_claims) == 0
        assert len(result.unmapped_claims) == 0
        assert result.passes_validation is True

    def test_map_claims_with_claim_context_as_quote(self):
        """Test that claim context is used as quote when no quote provided."""
        mapper = SourceMapper()

        claims = [
            Claim(
                text="Some claim",
                claim_type=ClaimType.FACT,
                position=(0, 10),
                source_required=True,
                source_url="https://example.com",
                source_quote="",  # No explicit quote
                context="Context around the claim",
            ),
        ]

        result = mapper.map_extracted_claims(claims)

        assert len(result.mapped_claims) == 1
        assert result.mapped_claims[0].source_quote == "Context around the claim"


class TestSourceMapperIntegration:
    """Integration tests for SourceMapper with ClaimExtractor."""

    def test_full_mapping_workflow(self):
        """Test complete workflow from text to mapped claims."""
        mapper = SourceMapper()

        text = """
        OpenAI announced GPT-5 on March 15, 2026.
        The model is 3x faster than GPT-4.
        Sam Altman invested $10 billion in development.
        """
        source_url = "https://openai.com/blog/gpt5"
        source_quote = "OpenAI announces GPT-5 with significant improvements."

        result = mapper.map_claims_to_sources(
            text=text,
            source_url=source_url,
            source_quote=source_quote,
        )

        assert isinstance(result, SourceMappingResult)
        assert len(result.mapped_claims) >= 1
        assert result.coverage_ratio == 1.0
        assert len(result.footnotes) >= 1

        # Check that footnotes contain the source URL
        assert any(source_url in fn for fn in result.footnotes)

    def test_russian_text_mapping(self):
        """Test mapping with Russian text."""
        mapper = SourceMapper()

        text = "OpenAI анонсировала GPT-5 15 марта 2026 года."
        source_url = "https://openai.com/blog/gpt5"

        result = mapper.map_claims_to_sources(
            text=text,
            source_url=source_url,
        )

        assert isinstance(result, SourceMappingResult)
        assert len(result.mapped_claims) >= 1

    def test_multiple_sources(self):
        """Test mapping claims from multiple sources."""
        mapper = SourceMapper()

        # Create claims directly with multiple sources
        claims = [
            Claim(
                text="First claim",
                claim_type=ClaimType.FACT,
                position=(0, 11),
                source_required=True,
                source_url="https://source1.com",
            ),
            Claim(
                text="Second claim",
                claim_type=ClaimType.FACT,
                position=(12, 24),
                source_required=True,
                source_url="https://source2.com",
            ),
        ]

        result = mapper.map_extracted_claims(claims)

        # Should have multiple mapped sources
        assert len(result.mapped_claims) == 2
        assert result.passes_validation is True
        assert len(result.footnotes) == 2
