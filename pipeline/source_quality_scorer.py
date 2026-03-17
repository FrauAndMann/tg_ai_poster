"""
Source Quality Scorer - Scores source credibility and quality.

Analyzes source URLs for credibility, domain trust, and content quality indicators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class SourceTier(Enum):
    """Source trust tiers."""

    TIER_1 = 1.0  # Official docs, major outlets
    TIER_2 = 0.7  # Reputable tech blogs
    TIER_3 = 0.4  # Aggregators, news sites
    TIER_UNKNOWN = 0.5


class CredibilityLevel(Enum):
    """Credibility assessment levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


@dataclass(slots=True)
class SourceScore:
    """Credibility score for a source."""

    domain: str
    tier: SourceTier
    score: float
    age_days: Optional[float] = None
    content_snippet: Optional[str] = None
    is_aggregator: bool = False
    has_paywall: bool = False
    bias_indicators: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SourceQualityReport:
    """Complete source quality analysis."""

    total_sources: int
    credibility_scores: list[SourceScore]
    tier_distribution: dict[SourceTier, int] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    overall_credibility: float = 0.0


class SourceQualityScorer:
    """
    Scores source credibility and quality.

    Features:
    - Domain trust tiers
    - Age-based scoring
    - Bias detection
    - Credibility metrics
    """

    # Domain trust tiers configuration
    DOMAIN_TIERS = {
        # Tier 1: Official docs, major outlets
        "openai.com": SourceTier.TIER_1,
        "docs.anthropic.com": SourceTier.TIER_1,
        "deepmind.google": SourceTier.TIER_1,
        "arxiv.org": SourceTier.TIER_1,
        "nature.com": SourceTier.TIER_1,
        "science.org": SourceTier.TIER_1,
        # Tier 2: Reputable tech blogs
        "techcrunch.com": SourceTier.TIER_2,
        "wired.com": SourceTier.TIER_2,
        "theverge.com": SourceTier.TIER_2,
        "huggingface.co": SourceTier.TIER_2,
        "platform.openai.org": SourceTier.TIER_2,
        "github.blog": SourceTier.TIER_2,
        # Tier 3: Aggregators, news sites
        "reddit.com": SourceTier.TIER_3,
        "medium.com": SourceTier.TIER_3,
        "producthunt.com": SourceTier.TIER_3,
    }

    # Known credible sources
    CREDIBLE_SOURCES = {
        "arxiv.org",
        "nature.com",
        "science.org",
        "ieee.org",
        "acm.org",
        "tensorflow.org",
        "pytorch.org",
    }

    # Aggregator credibility modifiers
    AGGREGATOR_MODIFIERS = {
        "producthunt.com": 0.7,
        "medium.com": 0.5,
        "reddit.com": 0.3,
    }

    # Paywall domains
    PAYWALL_DOMAINS = {
        "ft.com",
        "wsj.com",
        "bloomberg.com",
    }

    def __init__(
        self,
        domain_trust_config: Optional[dict[str, Any]] = None,
        min_credibility: float = 0.5,
    ) -> None:
        self._domain_trust = domain_trust_config or self.DOMAIN_TIERS
        self._min_credibility = min_credibility
        self._min_source_age_days = 30

    def score_source(
        self,
        url: str,
        content_snippet: Optional[str] = None,
    ) -> SourceScore:
        """Score a single source for credibility."""
        domain = self._extract_domain(url)
        tier = self._get_tier(domain)
        age_days = self._get_domain_age(domain)
        is_aggregator = self._check_aggregator(domain)
        has_paywall = self._check_paywall(domain)

        # Base credibility from tier
        base_score = tier.value

        # Apply modifiers
        if is_aggregator:
            modifier = self.AGGREGATOR_MODIFIERS.get(domain, 1.0)
            base_score *= modifier

        if has_paywall:
            base_score -= 0.2

        # Detect bias indicators
        bias_indicators = self._detect_bias(content_snippet) if content_snippet else []

        issues = []
        suggestions = []

        if tier == SourceTier.TIER_3:
            issues.append(f"Source from tier 3 domain: {domain}")
            suggestions.append("Consider finding more authoritative sources")

        if bias_indicators:
            issues.extend(bias_indicators)
            suggestions.append("Review content for potential bias")

        return SourceScore(
            domain=domain,
            tier=tier,
            score=base_score,
            age_days=age_days,
            content_snippet=content_snippet,
            is_aggregator=is_aggregator,
            has_paywall=has_paywall,
            bias_indicators=bias_indicators,
            issues=issues,
            suggestions=suggestions,
        )

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            domain = domain.replace("www.", "")
            return domain
        except Exception:
            return url

    def _get_tier(self, domain: str) -> SourceTier:
        """Get trust tier for domain."""
        domain_lower = domain.lower()
        return self.DOMAIN_TIERS.get(domain_lower, SourceTier.TIER_UNKNOWN)

    def _get_domain_age(self, domain: str) -> Optional[float]:
        """Get domain age in days (simplified)."""
        # In production, would use whois lookup
        return None

    def _check_aggregator(self, domain: str) -> bool:
        """Check if domain is an aggregator."""
        aggregators = ["producthunt.com", "medium.com", "reddit.com"]
        return any(agg in domain.lower() for agg in aggregators)

    def _check_paywall(self, domain: str) -> bool:
        """Check if domain has paywall."""
        return domain.lower() in self.PAYWALL_DOMAINS

    def _detect_bias(self, content: str) -> list[str]:
        """Detect potential bias indicators."""
        bias_indicators = []

        # Sensational language patterns
        sensational_patterns = [
            r"shocking",
            r"incredible",
            r"unbelievable",
            r"mind-blowing",
            r"revolutionary",
            r"потрясающе",
            r"невероятно",
            r"прорывной",
        ]

        content_lower = content.lower()
        for pattern in sensational_patterns:
            if pattern in content_lower:
                bias_indicators.append(f"Sensational language: '{pattern}'")
                break

        # Vague sourcing
        vague_patterns = [
            "experts say",
            r"studies show",
            r"research indicates",
            r"people are saying",
            r"эксперты говорят",
        ]

        for pattern in vague_patterns:
            if pattern in content_lower:
                bias_indicators.append(f"Vague sourcing: '{pattern}'")
                break

        return bias_indicators

    def score_sources(self, urls: list[str]) -> SourceQualityReport:
        """Score multiple sources."""
        scores = [self.score_source(url) for url in urls]

        # Calculate tier distribution
        tier_distribution: dict[SourceTier, int] = {}
        for score in scores:
            tier_distribution[score.tier] = tier_distribution.get(score.tier, 0) + 1

        # Calculate overall credibility
        overall = sum(s.score for s in scores) / len(scores) if scores else 0.0

        # Generate recommendations
        recommendations = []
        avg_tier = overall / len(scores) if scores else 0

        if avg_tier < 0.5:
            recommendations.append("Consider adding more authoritative sources")

        tier_3_count = sum(1 for s in scores if s.tier == SourceTier.TIER_3)
        if tier_3_count > len(scores) * 0.5:
            recommendations.append("Reduce reliance on aggregators")

        return SourceQualityReport(
            total_sources=len(scores),
            credibility_scores=scores,
            tier_distribution=tier_distribution,
            recommendations=recommendations,
            overall_credibility=overall,
        )


# Configuration schema
SOURCE_QUALITY_SCORER_CONFIG_SCHEMA = {
    "source_quality": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable source quality scoring",
        },
        "min_credibility": {
            "type": "float",
            "default": 0.5,
            "description": "Minimum credibility score to publish",
        },
        "require_tier_1": {
            "type": "bool",
            "default": False,
            "description": "Require at least one tier 1 source",
        },
    }
}
