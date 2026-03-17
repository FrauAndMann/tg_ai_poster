"""
Analytics and Feedback Loop Module.

Tracks post performance, engagement metrics, and generates reports
for optimizing content strategy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from collections import defaultdict

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PostMetrics:
    """Metrics for a single published post."""
    post_id: int
    telegram_message_id: int
    published_at: datetime
    post_type: str
    source_count: int
    confidence_avg: float
    character_count: int
    has_media: bool = False

    # Engagement metrics (updated after 48h)
    views: int = 0
    reactions: int = 0
    forwards: int = 0
    replies: int = 0

    # Calculated
    engagement_score: float = 0.0
    engagement_collected_at: Optional[datetime] = None

    def calculate_engagement_score(self) -> float:
        """Calculate weighted engagement score."""
        self.engagement_score = (
            self.views * 0.01 +
            self.reactions * 1.0 +
            self.forwards * 2.0 +
            self.replies * 1.5
        )
        return self.engagement_score

    def to_dict(self) -> dict:
        return {
            "post_id": self.post_id,
            "telegram_message_id": self.telegram_message_id,
            "published_at": self.published_at.isoformat(),
            "post_type": self.post_type,
            "source_count": self.source_count,
            "confidence_avg": self.confidence_avg,
            "character_count": self.character_count,
            "has_media": self.has_media,
            "views": self.views,
            "reactions": self.reactions,
            "forwards": self.forwards,
            "replies": self.replies,
            "engagement_score": self.engagement_score,
            "engagement_collected_at": self.engagement_collected_at.isoformat() if self.engagement_collected_at else None,
        }


@dataclass
class AnalyticsReport:
    """Weekly analytics report."""
    period_start: datetime
    period_end: datetime
    total_posts: int
    posts_by_type: dict  # post_type -> count
    avg_views: float
    avg_engagement: float
    avg_confidence: float
    top_posts: list[PostMetrics]  # Top 5 by engagement
    best_post_type: str
    recommendations: list[str]

    def to_dict(self) -> dict:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_posts": self.total_posts,
            "posts_by_type": self.posts_by_type,
            "avg_views": self.avg_views,
            "avg_engagement": self.avg_engagement,
            "avg_confidence": self.avg_confidence,
            "top_posts": [p.to_dict() for p in self.top_posts],
            "best_post_type": self.best_post_type,
            "recommendations": self.recommendations,
        }


class AnalyticsEngine:
    """
    Engine for tracking and analyzing post performance.

    Implements Rules 41-45 from Phase 4.
    """

    POST_TYPE_ROTATION_CACHE_SIZE = 5  # Track last 5 post types

    def __init__(
        self,
        metrics_storage_path: Optional[Path] = None,
        engagement_update_hours: int = 48,
    ):
        """
        Initialize analytics engine.

        Args:
            metrics_storage_path: Path to store metrics data
            engagement_update_hours: Hours after publish to collect engagement
        """
        self.metrics_storage_path = metrics_storage_path or Path("data/analytics")
        self.engagement_update_hours = engagement_update_hours

        self._metrics: dict[int, PostMetrics] = {}
        self._post_type_history: list[str] = []  # Recent post types for rotation
        self._hashtag_cache: list[set] = []  # Track hashtags in recent posts

        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Ensure storage directory exists."""
        self.metrics_storage_path.mkdir(parents=True, exist_ok=True)

    def log_published_post(
        self,
        post_id: int,
        telegram_message_id: int,
        post_type: str,
        source_count: int,
        confidence_avg: float,
        character_count: int,
        hashtags: list[str],
        has_media: bool = False,
    ) -> None:
        """
        Rule 41: Log every published post with metrics.

        Args:
            post_id: Database post ID
            telegram_message_id: Telegram message ID
            post_type: Type of post
            source_count: Number of sources used
            confidence_avg: Average confidence score
            character_count: Post length in characters
            hashtags: List of hashtags used
            has_media: Whether post has media
        """
        metrics = PostMetrics(
            post_id=post_id,
            telegram_message_id=telegram_message_id,
            published_at=datetime.utcnow(),
            post_type=post_type,
            source_count=source_count,
            confidence_avg=confidence_avg,
            character_count=character_count,
            has_media=has_media,
        )

        self._metrics[post_id] = metrics

        # Update post type history for rotation
        self._post_type_history.append(post_type)
        if len(self._post_type_history) > self.POST_TYPE_ROTATION_CACHE_SIZE:
            self._post_type_history.pop(0)

        # Update hashtag cache
        self._hashtag_cache.append(set(hashtags))
        if len(self._hashtag_cache) > 3:
            self._hashtag_cache.pop(0)

        self._save_metrics()

        logger.info(
            f"Logged post {post_id}: type={post_type}, "
            f"sources={source_count}, confidence={confidence_avg:.0%}"
        )

    async def update_engagement_metrics(
        self,
        post_id: int,
        views: int,
        reactions: int,
        forwards: int,
        replies: int,
    ) -> Optional[PostMetrics]:
        """
        Rule 42-43: Update engagement metrics after 48 hours.

        Args:
            post_id: Post ID to update
            views: View count
            reactions: Reaction count
            forwards: Forward count
            replies: Reply count

        Returns:
            PostMetrics | None: Updated metrics or None if not found
        """
        if post_id not in self._metrics:
            logger.warning(f"Post {post_id} not found in metrics")
            return None

        metrics = self._metrics[post_id]
        metrics.views = views
        metrics.reactions = reactions
        metrics.forwards = forwards
        metrics.replies = replies
        metrics.engagement_collected_at = datetime.utcnow()
        metrics.calculate_engagement_score()

        self._save_metrics()

        logger.info(
            f"Updated engagement for post {post_id}: "
            f"views={views}, score={metrics.engagement_score:.1f}"
        )

        return metrics

    def generate_weekly_report(self, days: int = 7) -> AnalyticsReport:
        """
        Rule 44: Generate weekly analytics report.

        Args:
            days: Number of days to analyze

        Returns:
            AnalyticsReport: Generated report
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Filter metrics in period
        period_metrics = [
            m for m in self._metrics.values()
            if m.published_at >= cutoff
        ]

        if not period_metrics:
            return AnalyticsReport(
                period_start=cutoff,
                period_end=datetime.utcnow(),
                total_posts=0,
                posts_by_type={},
                avg_views=0,
                avg_engagement=0,
                avg_confidence=0,
                top_posts=[],
                best_post_type="",
                recommendations=["No posts in period"],
            )

        # Calculate aggregations
        posts_by_type = defaultdict(int)
        for m in period_metrics:
            posts_by_type[m.post_type] += 1

        avg_views = sum(m.views for m in period_metrics) / len(period_metrics)
        avg_engagement = sum(m.engagement_score for m in period_metrics) / len(period_metrics)
        avg_confidence = sum(m.confidence_avg for m in period_metrics) / len(period_metrics)

        # Top 5 posts by engagement
        top_posts = sorted(period_metrics, key=lambda m: m.engagement_score, reverse=True)[:5]

        # Best performing post type
        type_engagement = {}
        for post_type in posts_by_type:
            type_posts = [m for m in period_metrics if m.post_type == post_type]
            if type_posts:
                type_engagement[post_type] = sum(m.engagement_score for m in type_posts) / len(type_posts)

        best_post_type = max(type_engagement, key=type_engagement.get) if type_engagement else ""

        # Generate recommendations
        recommendations = self._generate_recommendations(
            posts_by_type, avg_engagement, avg_confidence, best_post_type
        )

        return AnalyticsReport(
            period_start=cutoff,
            period_end=datetime.utcnow(),
            total_posts=len(period_metrics),
            posts_by_type=dict(posts_by_type),
            avg_views=avg_views,
            avg_engagement=avg_engagement,
            avg_confidence=avg_confidence,
            top_posts=top_posts,
            best_post_type=best_post_type,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        posts_by_type: dict,
        avg_engagement: float,
        avg_confidence: float,
        best_post_type: str,
    ) -> list[str]:
        """Generate recommendations based on metrics."""
        recommendations = []

        # Rule 45: Recommend increasing high-performing post types
        if best_post_type:
            recommendations.append(
                f"Increase frequency of '{best_post_type}' posts - highest engagement"
            )

        # Check for underperforming post types
        for post_type, count in posts_by_type.items():
            if post_type != best_post_type and count >= 3:
                recommendations.append(
                    f"Consider reducing '{post_type}' posts - lower engagement"
                )

        # Confidence recommendations
        if avg_confidence < 0.7:
            recommendations.append(
                "Average confidence below 70% - improve source verification"
            )

        # Engagement recommendations
        if avg_engagement < 10:
            recommendations.append(
                "Low engagement - review content quality and posting times"
            )

        return recommendations[:5]  # Max 5 recommendations

    def check_post_type_rotation(self, proposed_type: str) -> bool:
        """
        Rule 37: Check if post type would violate rotation rule.

        Args:
            proposed_type: Proposed post type

        Returns:
            bool: True if rotation is valid (no two same type consecutively)
        """
        if not self._post_type_history:
            return True

        # Check last post type
        last_type = self._post_type_history[-1] if self._post_type_history else None
        if last_type == proposed_type:
            logger.warning(f"Post type rotation violation: {proposed_type} same as last post")
            return False

        return True

    def check_hashtag_duplicates(self, proposed_hashtags: list) -> bool:
        """
        Rule 19: Check for duplicate hashtags in recent posts.

        Args:
            proposed_hashtags: Proposed hashtags

        Returns:
            bool: True if no duplicates in 3 consecutive posts
        """
        proposed_set = set(h.lower().lstrip('#') for h in proposed_hashtags)

        for recent_set in self._hashtag_cache[-3:] if self._hashtag_cache else []:
            overlap = proposed_set & recent_set
            if len(overlap) > 2:  # Allow up to 2 overlapping hashtags
                logger.warning(f"Hashtag overlap with recent post: {overlap}")
                return False

        return True

    def get_post_type_weights(self) -> dict:
        """
        Rule 45: Get weights for post type frequency based on performance.

        Returns:
            dict: post_type -> weight (higher = more frequent)
        """
        if not self._metrics:
            return {
                "breaking": 1.0,
                "deep_dive": 1.0,
                "tool_roundup": 1.0,
                "analysis": 1.0,
            }

        # Calculate average engagement by type
        type_engagement = defaultdict(list)
        for m in self._metrics.values():
            type_engagement[m.post_type].append(m.engagement_score)

        weights = {}
        for post_type, scores in type_engagement.items():
            avg = sum(scores) / len(scores)
            # Normalize weights (baseline 1.0, increase for high performers)
            weights[post_type] = 1.0 + (avg / 50)  # Scale factor

        # Ensure all types have weights
        for post_type in ["breaking", "deep_dive", "tool_roundup", "analysis"]:
            if post_type not in weights:
                weights[post_type] = 1.0

        return weights

    def _save_metrics(self) -> None:
        """Save metrics to storage."""
        try:
            data_file = self.metrics_storage_path / "metrics.json"
            data = {
                str(k): v.to_dict() for k, v in self._metrics.items()
            }
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def _load_metrics(self) -> None:
        """Load metrics from storage."""
        try:
            data_file = self.metrics_storage_path / "metrics.json"
            if data_file.exists():
                with open(data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    v["published_at"] = datetime.fromisoformat(v["published_at"])
                    if v.get("engagement_collected_at"):
                        v["engagement_collected_at"] = datetime.fromisoformat(v["engagement_collected_at"])
                    self._metrics[int(k)] = PostMetrics(**v)
        except Exception as e:
            logger.warning(f"Failed to load metrics: {e}")


class WeeklyReporter:
    """
    Weekly report generator and sender.

    Generates weekly performance reports and sends them
    to the channel admin via Telegram.
    """

    def __init__(
        self,
        analytics_engine: AnalyticsEngine,
    ):
        self.engine = analytics_engine

    async def generate_report(self, days: int = 7) -> AnalyticsReport:
        """
        Generate weekly analytics report.

        Args:
            days: Number of days to analyze

        Returns:
            AnalyticsReport: Generated report
        """
        return self.engine.generate_weekly_report(days)

    async def send_report_to_admin(
        self,
        report: AnalyticsReport,
        admin_user_id: int
    ) -> bool:
        """
        Send report to admin via Telegram.

        Args:
            report: Generated report
            admin_user_id: Admin's Telegram user ID

        Returns:
            bool: True if sent successfully
        """
        # Format report message
        lines = [
            "📊 **Weekly Report**",
            f"📅 Period: {report.period_start.strftime('%Y-%m-%d')} - {report.period_end.strftime('%Y-%m-%d')}",
            "",
            f"📝 Total posts: {report.total_posts}",
            f"👀 Average views: {report.avg_views:.0f}",
            f"💫 Average engagement: {report.avg_engagement:.1f}",
            f"🎯 Average confidence: {report.avg_confidence:.1%}",
            "",
            f"📈 Best post type: {report.best_post_type or 'N/A'}",
            "",
            "**Top Posts:**",
        ]

        for i, post in enumerate(report.top_posts[:5], 1):
            lines.append(f"  {i}. ID {post.post_id}: {post.engagement_score:.1f} engagement")

        if report.recommendations:
            lines.append("")
            lines.append("**Recommendations:**")
            for rec in report.recommendations:
                lines.append(f"  • {rec}")

        message = "\n".join(lines)
        logger.info(f"Weekly report generated:\n{message}")

        # Note: Actual sending would be done via Telegram API
        # This is a placeholder for integration
        return True

    def get_top_posts(self, limit: int = 5) -> list[PostMetrics]:
        """Get top posts by engagement."""
        return sorted(
            self.engine._metrics.values(),
            key=lambda m: m.engagement_score,
            reverse=True
        )[:limit]
