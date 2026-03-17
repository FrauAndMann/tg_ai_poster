"""
SEO & Discoverability Optimizer - Optimizes posts for Telegram search.

Analyzes posts for search discoverability, optimizes titles with keywords,
and identifies related channels for mentions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter

logger = get_logger(__name__)


@dataclass(slots=True)
class SEOScore:
    """SEO score breakdown for a post."""

    keyword_presence: float = 1.0
    title_optimization: float = 1.0
    hashtag_relevance: float = 1.0
    source_quality: float = 1.0
    related_channels: list[str] = field(default_factory=list)
    overall_score: float = 1.0
    recommendations: list[str] = field(default_factory=list)


class SEOOptimizer:
    """
    Optimizes posts for Telegram search discoverability.

    Features:
    - Keyword extraction and optimization
    - Title enhancement for search
    - Related channels identification
    - SEO rubric scoring
    """

    # High-value AI/tech keywords
    HIGH_VALUE_KEYWORDS = [
        "AI",
        "ИИ",
        "ML",
        "machine learning",
        "GPT",
        "neural network",
        "deep learning",
        "LLM",
        "ChatGPT",
        "Claude",
        "transformer",
        "автоматизация",
        "нейросеть",
        "генеративный",
        "AI agents",
        "computer vision",
        "NLP",
        "reinforcement learning",
    ]

    # Related AI/tech channels (for mention strategy)
    RELATED_CHANNELS = [
        "@ai_news",
        "@ml_daily",
        "@techcrunch",
        "@theverge",
        "@wired",
        "@deeplearning",
        "@openai",
    ]

    def __init__(
        self,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
    ) -> None:
        """
        Initialize SEO optimizer.

        Args:
            llm_adapter: LLM for optimization suggestions
        """
        self.llm = llm_adapter

    def optimize_title(self, title: str, keywords: list[str]) -> str:
        """
        Optimize title with keywords.

        Args:
            title: Original title
            keywords: Keywords to include

        Returns:
            Optimized title
        """
        # Check if title already contains keywords
        title_lower = title.lower()
        for kw in keywords:
            if kw.lower() in title_lower:
                return title  # Already optimized
        # Add primary keyword at beginning if not too long
        primary_kw = keywords[0] if keywords else ""
        if len(title) + len(primary_kw) + 2 < 120:
            return f"{primary_kw}: {title}"
        return title

    def extract_keywords(self, content: str, topic: str) -> list[str]:
        """Extract relevant keywords from content."""
        keywords = []
        content_lower = content.lower()
        topic_lower = topic.lower()
        # Check high-value keywords
        for kw in self.HIGH_VALUE_KEYWORDS:
            if kw.lower() in content_lower or kw.lower() in topic_lower:
                keywords.append(kw)
        # Extract technical terms (capitalized words)
        caps = re.findall(r"\b[A-Z][a-z]{2,}\b", content)
        for cap in caps[:5]:
            if cap.lower() not in [kw.lower() for kw in keywords]:
                keywords.append(cap)
        return list(set(keywords))[:5]  # Unique, top 5

    def find_related_channels(self, content: str, topic: str) -> list[str]:
        """Find channels related to the content."""
        related = []
        content_lower = content.lower()
        for channel in self.RELATED_CHANNELS:
            # Simple relevance check
            channel_topic = channel.lstrip("@").lower()
            if channel_topic in content_lower or any(
                word in content_lower for word in channel_topic.split("_")
            ):
                related.append(channel)
        return related[:2]  # Max 2 channels

    def score_seo(
        self,
        title: str,
        content: str,
        hashtags: list[str],
        sources: list[str],
        topic: str,
    ) -> SEOScore:
        """
        Score post for SEO optimization.

        Args:
            title: Post title
            content: Post content
            hashtags: Hashtags
            sources: Source URLs
            topic: Post topic

        Returns:
            SEOScore: SEO analysis results
        """
        # Extract keywords
        keywords = self.extract_keywords(content, topic)
        # Score keyword presence
        keyword_score = len(keywords) / 5  # 0-1
        # Score title optimization
        title_lower = title.lower()
        title_kw_count = sum(1 for kw in keywords if kw.lower() in title_lower)
        title_score = min(title_kw_count / len(keywords), 1.0) if keywords else 0.5
        # Score hashtag relevance
        hashtag_score = 0.5
        for tag in hashtags:
            tag_clean = tag.lstrip("#").lower()
            for kw in keywords:
                if kw.lower() in tag_clean:
                    hashtag_score += 0.1
        hashtag_score = min(hashtag_score, 1.0)
        # Score source quality
        source_score = 0.7
        if len(sources) >= 2:
            source_score = 0.9
        if any("arxiv" in " ".join(sources).lower()):
            source_score += 0.1
        # Find related channels
        related = self.find_related_channels(content, topic)
        # Overall score
        overall = (keyword_score + title_score + hashtag_score + source_score) / 4
        # Generate recommendations
        recommendations = []
        if title_kw_count < len(keywords) * 0.5:
            recommendations.append("Include more keywords in title")
        if not hashtags:
            recommendations.append("Add relevant hashtags")
        if len(sources) < 2:
            recommendations.append("Add more sources for credibility")
        if not related:
            recommendations.append("Consider mentioning related channels")
        return SEOScore(
            keyword_presence=keyword_score,
            title_optimization=title_score,
            hashtag_relevance=hashtag_score,
            source_quality=source_score,
            related_channels=related,
            overall_score=overall,
            recommendations=recommendations,
        )


# Configuration schema
SEO_OPTIMIZER_CONFIG_SCHEMA = {
    "seo": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable SEO optimization",
        },
        "min_keywords": {
            "type": "int",
            "default": 3,
            "description": "Minimum keywords in post",
        },
        "min_score": {
            "type": "int",
            "default": 60,
            "description": "Minimum SEO score for publication",
        },
    }
}
