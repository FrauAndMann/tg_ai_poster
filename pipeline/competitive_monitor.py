"""
Competitive Intelligence Monitor - Tracks competitor channels.

Monitors competitor Telegram channels and analyzes content formats and topics.
Generates weekly competitive landscape reports and identifies content gaps.
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
class CompetitorPost:
    """Post from a competitor channel."""

    channel_name: str
    channel_id: str
    content: str
    published_at: datetime
    post_type: str = ""
    topic: str = ""
    engagement: int = 0
    source_url: Optional[str] = None
    hashtags: list[str] = field(default_factory=list)
    media_type: str = ""  # text, image, video
    detected_at: datetime = field(default_factory=datetime.now)


    analyzed_at: Optional[datetime] = None


@dataclass(slots=True)
class CompetitiveInsight:
    """Insight from competitor analysis."""

    category: str
    topic: str
    frequency: int = 0
    engagement_avg: float = 0.0
    format_types: list[str] = field(default_factory=list)
    gap_analysis: str = ""
    opportunity_score: float = 0.0
    detected_at: datetime = field(default_factory=datetime.now)


class CompetitiveMonitor:
    """
    Monitors competitor channels and generates insights.

    Features:
    - Channel tracking
    - Content format analysis
    - Topic gap identification
    - Weekly landscape reports
    """

    def __init__(
        self,
        channels: Optional[list[str]] = None,
        analysis_interval_days: int = 7,
    min_posts_for_gap: int = 5,
    ) -> None:
        """
        Initialize competitive monitor.

        Args:
            channels: List of competitor channel IDs/usernames
            analysis_interval_days: Days between analyses
            min_posts_for_gap: Minimum posts to identify gaps
        """
        self.channels = channels or []
        self.analysis_interval = timedelta(days=analysis_interval_days)
        self.min_posts_for_gap = min_posts_for_gap

        self._posts: dict[str, list[CompetitorPost]] = {}
        self._insights: list[CompetitiveInsight] = []
        self._last_analysis: Optional[datetime] = None

    def track_post(
        self,
        channel_name: str,
        content: str,
        published_at: Optional[datetime] = None,
        topic: str = "",
        post_type: str = "",
        engagement: int = 0,
        hashtags: Optional[list[str]] = None,
        source_url: Optional[str] = None,
        media_type: str = "",
    ) -> None:
        """Track a post from a competitor."""
        post = CompetitorPost(
            channel_name=channel_name,
            content=content,
            published_at=published_at or datetime.now(),
            topic=topic,
            post_type=post_type,
            engagement=engagement,
            hashtags=hashtags or [],
            source_url=source_url,
            media_type=media_type,
        )

        if channel_name not in self._posts:
            self._posts[channel_name] = []
        self._posts[channel_name].append(post)

        logger.debug("Tracked post from %s", channel_name)

    def analyze_posts(self, channel_name: str) -> CompetitiveInsight:
        """Analyze posts from a competitor channel."""
        posts = self._posts.get(channel_name, [])
        if len(posts) < 5:
            return CompetitiveInsight(
                category="insufficient_data",
                topic="",
                frequency=len(posts),
            )

        # Analyze content patterns
        all_content = " ".join(p.content for p in posts)
        topics = [p.topic for p in posts if p.topic]
        formats = self._detect_formats(all_content)
        [tag for p in posts for tag in p.hashtags]

        # Calculate averages
        avg_engagement = sum(p.engagement for p in posts) / len(posts)
        topic_counts = {}
        for topic in topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Most common format
        primary_format = max(formats, key=formats.get)
        formats[0] if formats else None

        # Generate insight
        insight = CompetitiveInsight(
            category="content_analysis",
            topic=max(topic_counts.keys(), key=lambda k: topic_counts[k]) if topic_counts else "various",
            frequency=len(posts),
            engagement_avg=avg_engagement,
            format_types=primary_format,
            gap_analysis=f"Competitor focuses on {primary_format} format",
        )
        self._insights.append(insight)
        self._last_analysis = datetime.now()
        logger.info("Analyzed %d posts from %s", channel_name)
        return insight

    def _detect_formats(self, content: str) -> list[str]:
        """Detect content format patterns."""
        formats = []

        # Check for list format
        if re.search(r"^\d+\.\s", content, re.MULTILINE):
            formats.append("list")
        if re.search(r"^•\s", content, re.MULTILINE):
            formats.append("bullets")
        if re.search(r">.*$", content, re.MULTILINE):
            formats.append("blockquote")
        if re.search(r"```", content):
            formats.append("code")
        if re.search(r"\[.*\]\(.*\)", content):
            formats.append("link")

        if re.search(r"#\w+", content):
            formats.append("hashtags")
        if len(content) < 500:
            formats.append("short")
        elif len(content) > 1500:
            formats.append("long")

        return formats if formats else ["text_only"]
    def identify_content_gaps(
        self,
        our_topics: list[str],
        timeframe_days: int = 14,
    ) -> list[CompetitiveInsight]:
        """
        Identify topics competitors cover that we haven't.

        Args:
            our_topics: List of topics we've covered
            timeframe_days: Days to look back

        Returns:
            List of gap insights
        """
        gaps = []
        cutoff = datetime.now() - timedelta(days=timeframe_days)
        recent_our_topics = set(our_topics)
        competitor_topics = set()
        for post in self._posts.values():
            for p in post:
                if p.topic and p.published_at >= cutoff:
                    competitor_topics.add(p.topic)

        # Find gaps
        for our_topic in recent_our_topics:
            if our_topic not in competitor_topics:
                gap = CompetitiveInsight(
                    category="topic_gap",
                    topic=our_topic,
                    frequency=0,
                    gap_analysis=f"Competitor has not covered: {our_topic}",
                    opportunity_score=0.8,  # High opportunity
                )
                gaps.append(gap)

        return gaps
    def generate_weekly_report(self) -> dict[str, Any]:
        """Generate weekly competitive landscape report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "channels_monitored": len(self.channels),
            "total_posts_tracked": sum(len(posts) for posts in self._posts.values()),
            "insights": [
                {
                    "category": insight.category,
                    "topic": insight.topic,
                    "frequency": insight.frequency,
                    "engagement_avg": insight.engagement_avg,
                    "format_types": insight.format_types,
                    "gap_analysis": insight.gap_analysis,
                    "opportunity_score": insight.opportunity_score,
                }
                for insight in self._insights
            ],
            "top_hashtags": self._get_top_hashtags(),
            "content_gaps": [
                gap.to_dict() for gap in self.identify_content_gaps([], 14)
            ],
        }
        return report
    def _get_top_hashtags(self) -> list[str]:
        """Get most used hashtags."""
        hashtag_counts = {}
        for posts in self._posts.values():
            for post in posts:
                for tag in post.hashtags:
                    hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
        sorted_hashtags = sorted(
            hashtag_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [tag for tag, _ in sorted_hashtags[:10]]
    def get_opportunities(self) -> list[str]:
        """Get list of content opportunities."""
        opportunities = []
        for insight in self._insights:
            if insight.opportunity_score >= 0.5:
                opportunities.append(insight.topic)
        return opportunities


# Configuration schema
COMPETITIVE_MONITOR_CONFIG_SCHEMA = {
    "competitive": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable competitive monitoring",
        },
        "channels": {
            "type": "list",
            "description": "List of competitor channel usernames/IDs",
        },
        "analysis_interval_days": {
            "type": "int",
            "default": 7,
            "description": "Days between competitive analyses",
        },
    }
}
