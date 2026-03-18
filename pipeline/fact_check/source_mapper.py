"""
Source Mapper for Phase 2 Factual Accuracy.

Maps claims to their sources and generates footnotes for posts.
Ensures all claims requiring sources have proper attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger
from pipeline.fact_check.claim_extractor import Claim, ClaimExtractor, ClaimType

logger = get_logger(__name__)


@dataclass(slots=True)
class ClaimSource:
    """Maps a claim to its source information."""

    claim_text: str
    source_url: str
    source_quote: str  # Exact quote from source
    confidence: float  # 0.0 to 1.0

    def __post_init__(self) -> None:
        """Validate confidence range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class SourceMappingResult:
    """Result of source mapping operation."""

    mapped_claims: list[ClaimSource] = field(default_factory=list)
    unmapped_claims: list[Claim] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)
    passes_validation: bool = True
    coverage_ratio: float = 1.0
    warnings: list[str] = field(default_factory=list)


class SourceMapper:
    """
    Maps claims to sources and generates footnotes.

    Features:
    - Validates that all source_required claims have mappings
    - Generates formatted footnotes for posts
    - Calculates source coverage ratio
    - Provides warnings for missing sources
    """

    # Minimum confidence threshold for auto-mapping
    MIN_CONFIDENCE_THRESHOLD = 0.5

    def __init__(
        self,
        claim_extractor: Optional[ClaimExtractor] = None,
        min_confidence: float = MIN_CONFIDENCE_THRESHOLD,
    ) -> None:
        """
        Initialize the source mapper.

        Args:
            claim_extractor: Optional ClaimExtractor instance for extracting claims
            min_confidence: Minimum confidence threshold for source mappings
        """
        self.claim_extractor = claim_extractor or ClaimExtractor()
        self.min_confidence = min_confidence

    def map_claims_to_sources(
        self,
        text: str,
        source_url: str = "",
        source_quote: str = "",
        existing_mappings: Optional[list[ClaimSource]] = None,
    ) -> SourceMappingResult:
        """
        Map claims in text to their sources.

        Args:
            text: Text containing claims to map
            source_url: Primary source URL for all claims
            source_quote: Primary source quote for reference
            existing_mappings: Pre-existing claim-to-source mappings

        Returns:
            SourceMappingResult with mapped claims, unmapped claims, and footnotes
        """
        # Extract claims from text
        claims = self.claim_extractor.extract(text, source_url=source_url, source_quote=source_quote)

        return self.map_extracted_claims(claims, existing_mappings)

    def map_extracted_claims(
        self,
        claims: list[Claim],
        existing_mappings: Optional[list[ClaimSource]] = None,
    ) -> SourceMappingResult:
        """
        Map already-extracted claims to sources.

        Args:
            claims: List of Claim objects to map
            existing_mappings: Pre-existing claim-to-source mappings

        Returns:
            SourceMappingResult with mapped claims, unmapped claims, and footnotes
        """
        existing_mappings = existing_mappings or []

        mapped_claims: list[ClaimSource] = []
        unmapped_claims: list[Claim] = []
        warnings: list[str] = []

        # Create lookup for existing mappings
        existing_lookup = {m.claim_text.lower(): m for m in existing_mappings}

        for claim in claims:
            # Check if this claim requires a source
            if not claim.source_required:
                continue

            # Check for existing mapping
            existing = existing_lookup.get(claim.text.lower())

            if existing:
                # Use existing mapping
                mapped_claims.append(existing)
            elif claim.source_url:
                # Create mapping from claim's source info
                mapping = ClaimSource(
                    claim_text=claim.text,
                    source_url=claim.source_url,
                    source_quote=claim.source_quote or claim.context,
                    confidence=claim.confidence,
                )
                mapped_claims.append(mapping)
            else:
                # No source available - add to unmapped
                unmapped_claims.append(claim)
                warnings.append(
                    f"Claim requires source but has no mapping: '{claim.text[:50]}...'"
                )

        # Calculate coverage ratio
        total_source_required = len(mapped_claims) + len(unmapped_claims)
        if total_source_required > 0:
            coverage_ratio = len(mapped_claims) / total_source_required
        else:
            coverage_ratio = 1.0  # No claims requiring sources

        # Determine if validation passes
        passes_validation = len(unmapped_claims) == 0

        # Generate footnotes
        footnotes = self.generate_footnotes(mapped_claims)

        return SourceMappingResult(
            mapped_claims=mapped_claims,
            unmapped_claims=unmapped_claims,
            footnotes=footnotes,
            passes_validation=passes_validation,
            coverage_ratio=round(coverage_ratio, 2),
            warnings=warnings,
        )

    def generate_footnotes(
        self,
        mappings: list[ClaimSource],
        format_style: str = "numbered",
    ) -> list[str]:
        """
        Generate formatted footnotes from claim-source mappings.

        Args:
            mappings: List of ClaimSource mappings
            format_style: Footnote format style ('numbered', 'bracket', 'simple')

        Returns:
            List of formatted footnote strings
        """
        footnotes = []
        seen_urls: set[str] = set()

        for i, mapping in enumerate(mappings, 1):
            # Skip duplicate URLs
            if mapping.source_url in seen_urls:
                continue
            seen_urls.add(mapping.source_url)

            if format_style == "numbered":
                footnote = self._format_numbered_footnote(i, mapping)
            elif format_style == "bracket":
                footnote = self._format_bracket_footnote(i, mapping)
            else:
                footnote = self._format_simple_footnote(mapping)

            footnotes.append(footnote)

        return footnotes

    def _format_numbered_footnote(self, index: int, mapping: ClaimSource) -> str:
        """Format footnote with numbered style: [1] Source"""
        if mapping.source_quote:
            return f"[{index}] \"{mapping.source_quote}\" - {mapping.source_url}"
        return f"[{index}] {mapping.source_url}"

    def _format_bracket_footnote(self, index: int, mapping: ClaimSource) -> str:
        """Format footnote with bracket style: ¹ Source"""
        superscripts = "¹²³⁴⁵⁶⁷⁸⁹"
        superscript = superscripts[(index - 1) % len(superscripts)]

        if mapping.source_quote:
            return f"{superscript} \"{mapping.source_quote}\" - {mapping.source_url}"
        return f"{superscript} {mapping.source_url}"

    def _format_simple_footnote(self, mapping: ClaimSource) -> str:
        """Format footnote with simple style: Source URL only"""
        return mapping.source_url

    def validate_source_coverage(
        self,
        text: str,
        source_url: str = "",
    ) -> tuple[bool, float, list[str]]:
        """
        Quick validation of source coverage for text.

        Args:
            text: Text to validate
            source_url: Source URL to check against

        Returns:
            Tuple of (passes_validation, coverage_ratio, warnings)
        """
        result = self.map_claims_to_sources(text, source_url=source_url)
        return result.passes_validation, result.coverage_ratio, result.warnings

    def add_source_to_claim(
        self,
        claim_text: str,
        source_url: str,
        source_quote: str,
        confidence: float = 1.0,
    ) -> ClaimSource:
        """
        Create a new claim-source mapping.

        Args:
            claim_text: The claim text
            source_url: Source URL
            source_quote: Exact quote from source
            confidence: Confidence in the mapping

        Returns:
            New ClaimSource instance
        """
        return ClaimSource(
            claim_text=claim_text,
            source_url=source_url,
            source_quote=source_quote,
            confidence=confidence,
        )

    def get_footnotes_text(
        self,
        mappings: list[ClaimSource],
        header: str = "Источники:",
        format_style: str = "numbered",
    ) -> str:
        """
        Generate complete footnotes section as text.

        Args:
            mappings: List of ClaimSource mappings
            header: Header text for footnotes section
            format_style: Footnote format style

        Returns:
            Formatted footnotes section text
        """
        footnotes = self.generate_footnotes(mappings, format_style)

        if not footnotes:
            return ""

        return f"\n\n{header}\n" + "\n".join(footnotes)

    def filter_high_confidence_mappings(
        self,
        mappings: list[ClaimSource],
        min_confidence: Optional[float] = None,
    ) -> list[ClaimSource]:
        """
        Filter mappings by confidence threshold.

        Args:
            mappings: List of mappings to filter
            min_confidence: Minimum confidence (uses instance default if not provided)

        Returns:
            Filtered list of high-confidence mappings
        """
        threshold = min_confidence or self.min_confidence
        return [m for m in mappings if m.confidence >= threshold]
