"""
Hashtag Intelligence System - Smart hashtag selection based on performance.

Maintains historical performance database of hashtags, tracks impressions, engagement,
and post-click rate, and ranks hashtags for optimal selection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@dataclass(slots=True)
class HashtagStats:
    """Statistics for a single hashtag."""

    hashtag: str
    impressions: int = 0
    engagements: int = 0
    posts_count: int = 0
    first_used: Optional[datetime] = None
    last_used: Optional[datetime] = None
    trend_score: float = 0.0
    blacklisted: bool = False
    blacklist_reason: Optional[str] = None

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate."""
        if self.impressions == 0:
            return 0.0
        return self.engagements / self.impressions

    @property
    def is_performing(self) -> float:
        """Check if hashtag is performing well."""
        if self.blacklisted:
            return False
        if self.posts_count < 10:
            return True  # Not enough data
        return self.engagement_rate >= 0.05


class HashtagIntelligence:
    """
    Smart hashtag management system.

    Features:
    - Historical performance tracking
    - Engagement-based ranking
    - Trend score integration
    - Blacklist management
    - Topic relevance scoring
    """

    # Default AI/tech hashtags
    DEFAULT_HASHTAGS = [
        "#AI", "#ИИ", "#MachineLearning", "#ML", "#ArtificialIntelligence",
        "#LLM", "#GPT", "#NeuralNetworks", "#DeepLearning",
        "#TechNews", "#TechTrends", "#Innovation", "#Future",
        "#Automation", "#DataScience", "#NeuralNetwork", "#ChatGPT",
        "#Claude", "#OpenAI", "#Anthropic", "#TechCrunch",
    ]

    def __init__(
        self,
        blacklist_threshold: float = 0.1,
        min_impressions: int = 100,
        performance_window_days: int = 30,
    ) -> None:
        """
        Initialize hashtag intelligence system.

        Args:
            blacklist_threshold: Engagement rate below this = blacklist
            min_impressions: Minimum impressions before evaluation
            performance_window_days: Days to consider for performance
        """
        self.blacklist_threshold = blacklist_threshold
        self.min_impressions = min_impressions
        self.performance_window = timedelta(days=performance_window_days)

        self._hashtags: dict[str, HashtagStats] = {}
        self._blacklist: set[str] = set()

        # Initialize default hashtags
        for tag in self.DEFAULT_HASHTAGS:
            self._hashtags[tag.lower()] = HashtagStats(hashtag=tag)

    def record_usage(
        self,
        hashtag: str,
        impressions: int,
        engagements: int = 0,
    ) -> None:
        """
        Record hashtag usage with engagement data.

        Args:
            hashtag: Hashtag to record (with or without #)
            impressions: Post impressions/views
            engagements: Total engagements (reactions + shares + comments)
        """
        # Normalize hashtag
        tag = hashtag.lower().lstrip("#")
        if not tag:
            return

        full_tag = f"#{tag}" if not hashtag.startswith("#") else hashtag

        if tag not in self._hashtags:
            self._hashtags[tag] = HashtagStats(
                hashtag=full_tag,
                first_used=datetime.now(),
            )

        stats = self._hashtags[tag]
        stats.impressions += impressions
        stats.engagements += engagements
        stats.posts_count += 1
        stats.last_used = datetime.now()

        # Check if should be blacklisted
        if (
            stats.impressions >= self.min_impressions
            and stats.engagement_rate < self.blacklist_threshold
        ):
            self.blacklist(tag, f"Low engagement rate: {stats.engagement_rate:.2%}")

        logger.debug("Recorded hashtag %s: %d impressions, %d engagements", tag, impressions, engagements)

    def blacklist(self, hashtag: str, reason: str = "") -> None:
        """Add hashtag to blacklist."""
        tag = hashtag.lower().lstrip("#")
        self._blacklist.add(tag)

        if tag in self._hashtags:
            self._hashtags[tag].blacklisted = True
            self._hashtags[tag].blacklist_reason = reason

        logger.info("Blacklisted hashtag #%s: %s", tag, reason)

    def unblacklist(self, hashtag: str) -> None:
        """Remove hashtag from blacklist."""
        tag = hashtag.lower().lstrip("#")
        self._blacklist.discard(tag)

        if tag in self._hashtags:
            self._hashtags[tag].blacklisted = False
            self._hashtags[tag].blacklist_reason = None

    def is_blacklisted(self, hashtag: str) -> bool:
        """Check if hashtag is blacklisted."""
        tag = hashtag.lower().lstrip("#")
        return tag in self._blacklist

    def get_top_performers(self, limit: int = 20) -> list[HashtagStats]:
        """
        Get top performing hashtags.

        Args:
            limit: Maximum number to return

        Returns:
            List of top performing hashtags
        """
        candidates = [
            stats for stats in self._hashtags.values()
            if not stats.blacklisted and stats.posts_count > 0
        ]

        # Sort by engagement rate
        candidates.sort(key=lambda s: s.engagement_rate, reverse=True)

        return candidates[:limit]

    def select_hashtags(
        self,
        content: str,
        topic: str,
        count: int = 3,
        trending_tags: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Select optimal hashtags for content.

        Args:
            content: Post content
            topic: Post topic
            count: Number of hashtags to select
            trending_tags: Optional list of trending hashtags

        Returns:
            List of selected hashtags
        """
        # Get content keywords
        content_lower = content.lower()
        topic_lower = topic.lower()

        # Score all available hashtags
        scored: list[tuple[str, float]] = []

        for tag, stats in self._hashtags.items():
            if stats.blacklisted:
                continue

            score = self._calculate_tag_score(tag, stats, content_lower, topic_lower, trending_tags)
            scored.append((stats.hashtag, score))

        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)

        # Select top tags
        selected = []
        for tag, score in scored:
            if len(selected) >= count:
                break

            # Avoid duplicates (case-insensitive)
            if tag.lower() not in [t.lower() for t in selected]:
                selected.append(tag)

        # If not enough tags, add from trending
        if len(selected) < count and trending_tags:
            for tag in trending_tags:
                if len(selected) >= count:
                    break
                if not self.is_blacklisted(tag):
                    if tag.lower() not in [t.lower() for t in selected]:
                        selected.append(tag)

        return selected

    def _calculate_tag_score(
        self,
        tag: str,
        stats: HashtagStats,
        content: str,
        topic: str,
        trending_tags: Optional[list[str]],
    ) -> float:
        """Calculate score for a hashtag."""
        score = 1.0

        # Performance score
        if stats.posts_count >= self.min_impressions:
            score += stats.engagement_rate * 10  # Up to 1.0 bonus

        # Relevance score
        tag_clean = tag.lstrip("#").lower()
        if tag_clean in content or tag_clean in topic:
            score += 0.5

        # Recency bonus
        if stats.last_used:
            days_since = (datetime.now() - stats.last_used).days
            if days_since > 7:  # Good to reuse after a week
                score += 0.3
            elif days_since < 2:  # Penalize recent use
                score -= 0.5

        # Trending bonus
        if trending_tags:
            for t in trending_tags:
                if tag_clean in t.lower():
                    score += 0.5
                    break

        return score

    def get_stats_report(self) -> dict[str, Any]:
        """Get statistics report for all hashtags."""
        return {
            "total_hashtags": len(self._hashtags),
            "blacklisted_count": len(self._blacklist),
            "top_performers": [
                {
                    "hashtag": stats.hashtag,
                    "engagement_rate": f"{stats.engagement_rate:.2%}",
                    "impressions": stats.impressions,
                    "posts": stats.posts_count,
                }
                for stats in self.get_top_performers(10)
            ],
            "blacklisted": list(self._blacklist),
        }


# Configuration schema
HASHTAG_CONFIG_SCHEMA = {
    "hashtags": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable hashtag intelligence",
        },
        "blacklist_threshold": {
            "type": "float",
            "default": 0.1,
            "description": "Engagement rate threshold for blacklisting",
        },
        "min_impressions": {
            "type": "int",
            "default": 100,
            "description": "Minimum impressions before evaluation",
        },
    }
}
