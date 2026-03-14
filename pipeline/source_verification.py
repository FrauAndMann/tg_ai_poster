"""
Source verification module for validating news sources.

Verifies credibility, cross-references multiple sources, and filters
low-quality or unreliable information.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from core.logger import get_logger
from llm.base import BaseLLMAdapter
from pipeline.source_collector import Article

logger = get_logger(__name__)


# Domain trust levels for source verification
TRUSTED_DOMAINS = {
    # Highest trust - major tech publications
    "techcrunch.com": 95,
    "theverge.com": 95,
    "arstechnica.com": 90,
    "wired.com": 90,
    "venturebeat.com": 85,
    
    # Academic and scientific
    "nature.com": 98,
    "science.org": 98,
    "arxiv.org": 95,
    "sciencedirect.com": 95,
    "springer.com": 90,
    
    # Official company blogs
    "openai.com": 95,
    "anthropic.com": 95,
    "deepmind.google": 95,
    "ai.googleblog.com": 95,
    "blog.google": 90,
    "meta.com": 85,
    "facebook.com": 80,
    "microsoft.com": 85,
    "azure.microsoft.com": 85,
    
    # Code and models
    "github.com": 90,
    "huggingface.co": 90,
    "paperswithcode.com": 88,
    
    # Wire services
    "reuters.com": 95,
    "bloomberg.com": 90,
    "wsj.com": 88,
    "ft.com": 88,
    
    # Industry
    "deeplearning.ai": 85,
    "oreilly.com": 85,
    "mit.edu": 95,
    "stanford.edu": 95,
    
    # Regional tech
    "vc.ru": 75,
    "forbes.ru": 70,
    "incrussia.ru": 70,
    
    # Community
    "reddit.com": 60,
    "news.ycombinator.com": 70,
    "producthunt.com": 65,
}

# Minimum trust score for a source to be considered reliable
MIN_TRUST_SCORE = 60


@dataclass
class VerifiedSource:
    """
    A verified source with credibility information.
    
    Attributes:
        article: Original article
        trust_score: Credibility score (0-100)
        is_primary: Whether this is the primary/authoritative source
        verification_notes: Notes about verification
    """
    article: Article
    trust_score: float
    is_primary: bool = False
    verification_notes: str = ""
    
    def to_dict(self) -> dict:
        return {
            "title": self.article.title,
            "url": self.article.url,
            "source": self.article.source,
            "trust_score": self.trust_score,
            "is_primary": self.is_primary,
            "notes": self.verification_notes,
        }


@dataclass
class VerificationResult:
    """
    Result of source verification.
    
    Attributes:
        verified: Whether sources pass verification
        credibility_score: Overall credibility (0-100)
        sources: List of verified sources
        primary_source: The most authoritative source
        cross_reference_count: Number of independent sources
        inconsistencies: Any conflicting information found
        recommendation: publish/needs_review/reject
        reasoning: Explanation of the verdict
    """
    verified: bool
    credibility_score: float
    sources: list[VerifiedSource] = field(default_factory=list)
    primary_source: Optional[VerifiedSource] = None
    cross_reference_count: int = 0
    inconsistencies: list[str] = field(default_factory=list)
    recommendation: str = "needs_review"
    reasoning: str = ""
    
    def to_dict(self) -> dict:
        return {
            "verified": self.verified,
            "credibility_score": self.credibility_score,
            "sources": [s.to_dict() for s in self.sources],
            "primary_source": self.primary_source.to_dict() if self.primary_source else None,
            "cross_reference_count": self.cross_reference_count,
            "inconsistencies": self.inconsistencies,
            "recommendation": self.recommendation,
            "reasoning": self.reasoning,
        }


class SourceVerifier:
    """
    Verifies source credibility and cross-references information.
    
    Ensures news comes from reliable sources and is confirmed by
    multiple independent outlets before publication.
    """
    
    def __init__(
        self,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        min_sources: int = 2,
        min_trust_score: float = MIN_TRUST_SCORE,
        min_credibility: float = 70.0,
        trusted_domains: Optional[dict[str, float]] = None,
    ) -> None:
        """
        Initialize source verifier.
        
        Args:
            llm_adapter: Optional LLM for AI-assisted verification
            min_sources: Minimum number of sources required
            min_trust_score: Minimum trust score for a single source
            min_credibility: Minimum overall credibility score
            trusted_domains: Custom trusted domains with scores
        """
        self.llm = llm_adapter
        self.min_sources = min_sources
        self.min_trust_score = min_trust_score
        self.min_credibility = min_credibility
        self.trusted_domains = trusted_domains or TRUSTED_DOMAINS
        
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""
    
    def _get_trust_score(self, url: str) -> float:
        """Get trust score for a URL based on its domain."""
        domain = self._extract_domain(url)
        
        # Check exact match
        if domain in self.trusted_domains:
            return self.trusted_domains[domain]
        
        # Check parent domain (e.g., blog.openai.com -> openai.com)
        parts = domain.split(".")
        if len(parts) > 2:
            parent_domain = ".".join(parts[-2:])
            if parent_domain in self.trusted_domains:
                return self.trusted_domains[parent_domain] * 0.9  # Slightly lower for subdomains
        
        # Unknown domain - low trust
        return 40.0
    
    def _check_content_similarity(
        self, 
        articles: list[Article],
    ) -> list[tuple[int, int, float]]:
        """
        Check similarity between articles to find cross-references.
        
        Returns list of (idx1, idx2, similarity) tuples.
        """
        similarities = []
        
        # Simple word overlap similarity
        for i, a1 in enumerate(articles):
            words1 = set(a1.title.lower().split() + a1.summary.lower().split())
            words1 = {w for w in words1 if len(w) > 3}  # Filter short words
            
            for j, a2 in enumerate(articles[i+1:], i+1):
                words2 = set(a2.title.lower().split() + a2.summary.lower().split())
                words2 = {w for w in words2 if len(w) > 3}
                
                if not words1 or not words2:
                    continue
                
                intersection = len(words1 & words2)
                union = len(words1 | words2)
                
                if union > 0:
                    similarity = intersection / union
                    similarities.append((i, j, similarity))
        
        return similarities
    
    def verify_sources(
        self,
        articles: list[Article],
        topic: Optional[str] = None,
    ) -> VerificationResult:
        """
        Verify a list of articles as sources.
        
        Args:
            articles: Articles to verify
            topic: Optional topic for context
            
        Returns:
            VerificationResult with verification details
        """
        if not articles:
            return VerificationResult(
                verified=False,
                credibility_score=0,
                recommendation="reject",
                reasoning="No sources provided",
            )
        
        # Score each source
        verified_sources = []
        
        for article in articles:
            trust_score = self._get_trust_score(article.url)
            
            vs = VerifiedSource(
                article=article,
                trust_score=trust_score,
                verification_notes=self._get_source_notes(article, trust_score),
            )
            verified_sources.append(vs)
        
        # Sort by trust score
        verified_sources.sort(key=lambda x: x.trust_score, reverse=True)
        
        # Mark primary source (highest trust)
        if verified_sources:
            verified_sources[0].is_primary = True
        
        # Calculate cross-references
        similarities = self._check_content_similarity(articles)
        
        # Count independent confirmations (similarity > 0.3 means same topic)
        cross_ref_count = len([s for s in similarities if s[2] > 0.3]) + 1
        
        # Calculate overall credibility
        if not verified_sources:
            credibility_score = 0
        else:
            # Weighted average, with bonus for multiple sources
            base_score = sum(vs.trust_score for vs in verified_sources) / len(verified_sources)
            
            # Bonus for cross-references
            cross_ref_bonus = min(cross_ref_count * 5, 15)
            
            # Penalty for only low-trust sources
            high_trust_count = len([vs for vs in verified_sources if vs.trust_score >= 70])
            if high_trust_count == 0:
                base_score *= 0.7
            
            credibility_score = min(100, base_score + cross_ref_bonus)
        
        # Determine recommendation
        if credibility_score >= self.min_credibility and len(verified_sources) >= self.min_sources:
            recommendation = "publish"
            verified = True
            reasoning = f"Verified with {len(verified_sources)} sources, credibility {credibility_score:.0f}%"
        elif credibility_score >= 60 and len(verified_sources) >= 1:
            recommendation = "needs_review"
            verified = True  # Allow with caution
            reasoning = f"Limited verification: {len(verified_sources)} source(s), credibility {credibility_score:.0f}%"
        else:
            recommendation = "reject"
            verified = False
            reasoning = f"Insufficient verification: {len(verified_sources)} source(s), credibility {credibility_score:.0f}%"
        
        return VerificationResult(
            verified=verified,
            credibility_score=credibility_score,
            sources=verified_sources,
            primary_source=verified_sources[0] if verified_sources else None,
            cross_reference_count=cross_ref_count,
            recommendation=recommendation,
            reasoning=reasoning,
        )
    
    def _get_source_notes(self, article: Article, trust_score: float) -> str:
        """Generate notes about a source's credibility."""
        domain = self._extract_domain(article.url)
        
        if trust_score >= 90:
            return f"Highly trusted source: {domain}"
        elif trust_score >= 70:
            return f"Reliable source: {domain}"
        elif trust_score >= 60:
            return f"Moderate trust: {domain}"
        else:
            return f"Low trust source: {domain} - verify independently"
    
    async def verify_with_ai(
        self,
        articles: list[Article],
        topic: str,
    ) -> VerificationResult:
        """
        Verify sources using LLM for deeper analysis.
        
        Args:
            articles: Articles to verify
            topic: Topic being covered
            
        Returns:
            VerificationResult with AI-assisted verification
        """
        # First do rule-based verification
        base_result = self.verify_sources(articles, topic)
        
        if not self.llm:
            return base_result
        
        try:
            # Build prompt for AI verification
            sources_text = "\n".join([
                f"- {a.title}\n  URL: {a.url}\n  Source: {a.source}\n  Summary: {a.summary[:200]}..."
                for a in articles[:5]
            ])
            
            prompt = f"""Verify these sources for a news post about: {topic}

SOURCES:
{sources_text}

Verify:
1. Are these credible sources?
2. Do they confirm the same information?
3. Any inconsistencies?

Respond in JSON:
{{
  "verified": true/false,
  "credibility_score": 0-100,
  "primary_source": "most authoritative source name",
  "cross_reference_count": number of independent confirmations,
  "inconsistencies": ["any conflicting info"],
  "recommendation": "publish/needs_review/reject",
  "reasoning": "brief explanation"
}}"""
            
            response = await self.llm.generate(prompt)
            response_text = response.content.strip()
            
            # Parse JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            
            ai_result = json.loads(response_text.strip())
            
            # Combine results
            combined_score = (base_result.credibility_score + ai_result.get("credibility_score", 50)) / 2
            
            return VerificationResult(
                verified=ai_result.get("verified", base_result.verified) and base_result.verified,
                credibility_score=combined_score,
                sources=base_result.sources,
                primary_source=base_result.primary_source,
                cross_reference_count=max(
                    base_result.cross_reference_count,
                    ai_result.get("cross_reference_count", 0)
                ),
                inconsistencies=ai_result.get("inconsistencies", []),
                recommendation=ai_result.get("recommendation", base_result.recommendation),
                reasoning=ai_result.get("reasoning", base_result.reasoning),
            )
            
        except Exception as e:
            logger.error(f"AI verification failed: {e}")
            return base_result
    
    def get_source_context_for_post(
        self,
        verified_sources: list[VerifiedSource],
    ) -> str:
        """
        Format verified sources for inclusion in post generation.
        
        Args:
            verified_sources: List of verified sources
            
        Returns:
            str: Formatted source context for LLM prompt
        """
        if not verified_sources:
            return "No verified sources available."
        
        parts = ["VERIFIED SOURCES (use ONLY these facts):\n"]
        
        for i, vs in enumerate(verified_sources[:3], 1):
            parts.append(f"\n[Source {i}] {vs.article.source} (trust: {vs.trust_score:.0f}%)")
            parts.append(f"Title: {vs.article.title}")
            parts.append(f"URL: {vs.article.url}")
            if vs.article.summary:
                parts.append(f"Summary: {vs.article.summary}")
            if vs.is_primary:
                parts.append("(PRIMARY SOURCE)")
        
        parts.append("\n\nIMPORTANT: Use only facts from these sources. Include source URLs in your post.")
        
        return "\n".join(parts)
