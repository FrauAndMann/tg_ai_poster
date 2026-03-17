"""
Engagement Feedback Loop v2 - Pulls real metrics from Telegram API.

Tracks time-series engagement data and builds decay curves for quality signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = get_logger(__name__)


@dataclass(slots=True)
class EngagementSnapshot:
    """Engagement metrics at a point in time."""

    timestamp: datetime
    views: int
    forwards: int
    reactions: int
    comments: int
    engagement_rate: float = 1.0


@dataclass(slots=True)
class EngagementTimeSeries:
    """Time series of engagement data."""

    post_id: int
    snapshots: list[EngagementSnapshot] = field(default_factory=list)
    decay_rate: float = 1.0
    half_life_hours: float = 0.0
    peak_engagement: int = 0
    final_engagement: int = 0

    def add_snapshot(self, snapshot: EngagementSnapshot) -> None:
        self.snapshots.append(snapshot)
        if len(self.snapshots) > 1:
            self._calculate_decay()

    def _calculate_decay(self) -> None:
        """Calculate engagement decay rate."""
        if len(self.snapshots) < 2:
            return
        first = self.snapshots[0]
        last = self.snapshots[-1]
        hours_elapsed = (last.timestamp - first.timestamp).total_seconds() / 3600
        if hours_elapsed > 0:
            engagement_loss = first.engagement_rate - last.engagement_rate
            self.decay_rate = engagement_loss / hours_elapsed
            # Calculate half-life (time to 50% engagement)
            if engagement_loss > 0:
                self.half_life_hours = hours_elapsed * 0.69 / engagement_loss
        self.peak_engagement = max(s.views for s in self.snapshots)
        self.final_engagement = last.views

    @property
    def total_snapshots(self) -> int:
        return len(self.snapshots)


class EngagementFeedbackLoopV2:
    """
    Enhanced engagement tracking system.

    Features:
    - Pulls real metrics via Telethon API
    - Time-series data storage
    - Decay curve analysis
    - Quality signal extraction
    """

    def __init__(
        self,
        client: Optional["TelegramClient"] = None,
        update_interval_hours: float = 6.0,
        tracking_window_hours: int = 48,
    ) -> None:
        self.client = client
        self.update_interval = timedelta(hours=update_interval_hours)
        self.tracking_window = timedelta(hours=tracking_window_hours)
        self._time_series: dict[int, EngagementTimeSeries] = {}

    async def pull_engagement(
        self,
        post_id: int,
        message_id: int,
        channel_entity: Any = None,
    ) -> Optional[EngagementSnapshot]:
        """
        Pull engagement metrics for post via Telethon.

        Args:
            post_id: Database post ID
            message_id: Telegram message ID
            channel_entity: Channel entity for message lookup

        Returns:
            EngagementSnapshot or None
        """
        if not self.client:
            return None
        try:
            # Get message views and reactions
            messages = await self.client.get_messages(
                entity=channel_entity,
                ids=[message_id],
            )
            if not messages:
                return None
            msg = messages[0] if isinstance(messages, list) else messages
            views = getattr(msg, "views", 0) or 0
            forwards = getattr(msg, "forwards", 0) or 0
            reactions_data = getattr(msg, "reactions", None)
            reactions = 0
            if reactions_data:
                results = getattr(reactions_data, "results", [])
                reactions = sum(r.count for r in results) if results else 0

            # Calculate engagement rate
            engagement_rate = 1.0
            if views > 0:
                total_engagement = forwards + reactions
                engagement_rate = total_engagement / views

            snapshot = EngagementSnapshot(
                timestamp=datetime.now(),
                views=views,
                forwards=forwards,
                reactions=reactions,
                comments=0,  # Telegram doesn't expose easily
                engagement_rate=engagement_rate,
            )

            # Update time series
            if post_id not in self._time_series:
                self._time_series[post_id] = EngagementTimeSeries(post_id=post_id)
            self._time_series[post_id].add_snapshot(snapshot)

            return snapshot
        except Exception as e:
            logger.error("Failed to pull engagement: %s", e)
            return None

    async def track_all_posts(
        self,
        post_ids: list[int],
        message_ids: dict[int, int],
        channel_entity: Any = None,
    ) -> dict[int, EngagementTimeSeries]:
        """Track engagement for multiple posts."""
        results = {}
        for post_id in post_ids:
            message_id = message_ids.get(post_id)
            if message_id:
                snapshot = await self.pull_engagement(post_id, message_id, channel_entity)
                if snapshot and post_id in self._time_series:
                    results[post_id] = self._time_series[post_id]
        return results

    async def run_tracking_cycle(
        self,
        active_posts: dict[int, int],
        channel_entity: Any = None,
    ) -> dict[int, EngagementTimeSeries]:
        """Run full tracking cycle for all active posts.

        Args:
            active_posts: Dict of post_id -> telegram_message_id
            channel_entity: Channel entity for message lookup

        Returns:
            Dict of post_id -> EngagementTimeSeries
        """
        logger.info("Running engagement tracking cycle for %d posts", len(active_posts))
        now = datetime.now()

        for post_id, message_id in active_posts.items():
            if not message_id:
                continue

            # Get existing time series
            existing = self._time_series.get(post_id)
            if existing and existing.snapshots:
                # Check if tracking window expired
                if now - existing.snapshots[0].timestamp > self.tracking_window:
                    # Old data - reset tracking
                    del self._time_series[post_id]
                    existing = EngagementTimeSeries(post_id=post_id)
                    self._time_series[post_id] = existing
            else:
                existing = EngagementTimeSeries(post_id=post_id)
                self._time_series[post_id] = existing

            # Pull new engagement
            snapshot = await self.pull_engagement(post_id, message_id, channel_entity)
            if snapshot:
                existing.add_snapshot(snapshot)

        return self._time_series

    def get_decay_analysis(self, post_id: int) -> Optional[dict]:
        """Get decay analysis for a post."""
        ts = self._time_series.get(post_id)
        if not ts or len(ts.snapshots) < 2:
            return None
        return {
            "post_id": post_id,
            "snapshots_count": len(ts.snapshots),
            "decay_rate": ts.decay_rate,
            "half_life_hours": ts.half_life_hours,
            "peak_engagement": ts.peak_engagement,
            "final_engagement": ts.final_engagement,
            "engagement_trend": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "views": s.views,
                    "engagement_rate": s.engagement_rate,
                }
                for s in ts.snapshots
            ],
        }

    def get_quality_signals(
        self,
        min_engagement_rate: float = 0.01,
    ) -> list[int]:
        """Get posts with quality signals (good engagement decay)."""
        quality_posts = []
        for post_id, ts in self._time_series.items():
            if ts.decay_rate < min_engagement_rate:
                quality_posts.append(post_id)
        return quality_posts

    def get_top_performing(self, limit: int = 10) -> list[tuple[int, float]]:
        """Get top performing posts by engagement rate."""
        performance = [
            (post_id, ts.final_engagement / max(ts.peak_engagement, 1))
            for post_id, ts in self._time_series.items()
            if ts.peak_engagement > 0
        ]
        return sorted(performance, key=lambda x: x[1], reverse=True)[:limit]


# Configuration schema
ENGAGEMENT_FEEDBACK_V2_CONFIG_SCHEMA = {
    "engagement_tracking": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable engagement feedback loop v2",
        },
        "update_interval_hours": {
            "type": "float",
            "default": 6.0,
            "description": "Hours between engagement updates",
        },
        "tracking_window_hours": {
            "type": "int",
            "default": 48,
            "description": "Hours to track engagement after publishing",
        },
    }
}
