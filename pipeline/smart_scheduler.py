"""
Smart Scheduler - Intelligent posting time optimization.

Analyzes engagement metrics to determine optimal posting times,
adapts schedule based on audience activity patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from memory.post_store import PostStore

logger = get_logger(__name__)


@dataclass(slots=True)
class TimeSlot:
    """Represents a potential posting time slot."""
    hour: int
    weekday: int  # 0 = Monday, 6 = Sunday
    engagement_score: float = 0.0
    post_count: int = 0
    avg_views: float = 0.0
    avg_reactions: float = 0.0
    confidence: float = 0.0  # Based on sample size


@dataclass(slots=True)
class SmartSchedule:
    """Optimized posting schedule."""
    recommended_times: list[str]  # HH:MM format
    best_hours: list[int]  # Hours with highest engagement
    worst_hours: list[int]  # Hours to avoid
    confidence: float  # Overall confidence in recommendations
    insights: list[str]  # Human-readable insights


class SmartScheduler:
    """
    Analyzes engagement data to optimize posting times.

    Features:
    - Learns from historical engagement data
    - Identifies best hours for each day of week
    - Adapts to audience behavior patterns
    - Provides actionable insights
    """

    # Default best times if no data available (Russian audience)
    DEFAULT_PEAK_HOURS = [9, 12, 18, 19, 20, 21]
    DEFAULT_AVOID_HOURS = [1, 2, 3, 4, 5, 6, 23, 0]

    # Minimum posts needed for reliable analysis
    MIN_SAMPLES_FOR_ANALYSIS = 10

    def __init__(self, post_store: Optional[PostStore] = None):
        """
        Initialize smart scheduler.

        Args:
            post_store: Post store for fetching engagement data
        """
        self.post_store = post_store
        self._time_slots: dict[tuple[int, int], TimeSlot] = {}

    async def analyze_engagement_patterns(self, days_back: int = 30) -> dict[tuple[int, int], TimeSlot]:
        """
        Analyze historical engagement to find optimal posting times.

        Args:
            days_back: Number of days to analyze

        Returns:
            Dict mapping (hour, weekday) to TimeSlot
        """
        if not self.post_store:
            logger.warning("No post store available for analysis")
            return {}

        try:
            # Get posts with engagement data
            posts = await self.post_store.get_recent(
                limit=100,
                status="published",
            )

            if len(posts) < self.MIN_SAMPLES_FOR_ANALYSIS:
                logger.info(f"Only {len(posts)} posts, need {self.MIN_SAMPLES_FOR_ANALYSIS} for analysis")
                return {}

            # Initialize time slots
            time_slots: dict[tuple[int, int], TimeSlot] = {}

            for post in posts:
                if not post.published_at:
                    continue

                hour = post.published_at.hour
                weekday = post.published_at.weekday()
                key = (hour, weekday)

                if key not in time_slots:
                    time_slots[key] = TimeSlot(
                        hour=hour,
                        weekday=weekday,
                    )

                slot = time_slots[key]
                slot.post_count += 1
                slot.avg_views = self._update_average(
                    slot.avg_views, slot.post_count, post.views or 0
                )
                slot.avg_reactions = self._update_average(
                    slot.avg_reactions, slot.post_count, post.reactions or 0
                )

            # Calculate engagement scores
            max_views = max((s.avg_views for s in time_slots.values()), default=1)
            max_reactions = max((s.avg_reactions for s in time_slots.values()), default=1)

            for slot in time_slots.values():
                # Normalized engagement score (views + reactions)
                views_score = slot.avg_views / max_views if max_views > 0 else 0
                reactions_score = slot.avg_reactions / max_reactions if max_reactions > 0 else 0

                # Weighted combination (views more important)
                slot.engagement_score = (views_score * 0.6 + reactions_score * 0.4) * 100

                # Confidence based on sample size
                slot.confidence = min(1.0, slot.post_count / 10)

            self._time_slots = time_slots
            return time_slots

        except Exception as e:
            logger.error(f"Failed to analyze engagement: {e}")
            return {}

    def _update_average(self, current_avg: float, count: int, new_value: float) -> float:
        """Update running average with new value."""
        return (current_avg * (count - 1) + new_value) / count

    def get_best_times(self, top_n: int = 5) -> list[TimeSlot]:
        """
        Get top N best posting times based on engagement.

        Args:
            top_n: Number of best times to return

        Returns:
            List of best TimeSlots
        """
        if not self._time_slots:
            # Return defaults
            return [
                TimeSlot(hour=h, weekday=-1, engagement_score=70, confidence=0)
                for h in self.DEFAULT_PEAK_HOURS[:top_n]
            ]

        sorted_slots = sorted(
            self._time_slots.values(),
            key=lambda s: s.engagement_score * s.confidence,
            reverse=True
        )

        return sorted_slots[:top_n]

    def get_worst_times(self, top_n: int = 5) -> list[TimeSlot]:
        """
        Get worst posting times to avoid.

        Args:
            top_n: Number of worst times to return

        Returns:
            List of worst TimeSlots
        """
        if not self._time_slots:
            return [
                TimeSlot(hour=h, weekday=-1, engagement_score=20, confidence=0)
                for h in self.DEFAULT_AVOID_HOURS[:top_n]
            ]

        sorted_slots = sorted(
            self._time_slots.values(),
            key=lambda s: s.engagement_score
        )

        return sorted_slots[:top_n]

    async def get_optimized_schedule(
        self,
        posts_per_day: int = 3,
        current_times: Optional[list[str]] = None,
    ) -> SmartSchedule:
        """
        Get optimized posting schedule.

        Args:
            posts_per_day: Target posts per day
            current_times: Current schedule times (HH:MM)

        Returns:
            SmartSchedule with recommendations
        """
        # Analyze if not done yet
        if not self._time_slots:
            await self.analyze_engagement_patterns()

        best_times = self.get_best_times(posts_per_day * 2)  # Get extra options
        worst_times = self.get_worst_times(3)

        # Select best unique hours
        recommended_hours = []
        seen_hours = set()
        for slot in best_times:
            if slot.hour not in seen_hours:
                recommended_hours.append(slot.hour)
                seen_hours.add(slot.hour)
            if len(recommended_hours) >= posts_per_day:
                break

        # If not enough data, use defaults
        if len(recommended_hours) < posts_per_day:
            for h in self.DEFAULT_PEAK_HOURS:
                if h not in seen_hours:
                    recommended_hours.append(h)
                    seen_hours.add(h)
                if len(recommended_hours) >= posts_per_day:
                    break

        # Convert to HH:MM format
        recommended_times = [f"{h:02d}:00" for h in sorted(recommended_hours)]

        # Generate insights
        insights = []

        if best_times and best_times[0].confidence > 0.5:
            best = best_times[0]
            insights.append(f"Лучшее время: {best.hour:02d}:00 (engagement: {best.engagement_score:.0f})")

        if worst_times:
            worst = worst_times[0]
            insights.append(f"Избегайте: {worst.hour:02d}:00")

        # Compare with current schedule
        if current_times:
            current_hours = [int(t.split(":")[0]) for t in current_times if ":" in t]
            overlap = len(set(current_hours) & set(recommended_hours))
            if overlap < len(current_hours) // 2:
                insights.append("Текущее расписание можно оптимизировать")

        # Calculate overall confidence
        confidence = sum(s.confidence for s in best_times[:posts_per_day]) / posts_per_day
        confidence = min(1.0, confidence)

        return SmartSchedule(
            recommended_times=recommended_times,
            best_hours=sorted(recommended_hours),
            worst_hours=[s.hour for s in worst_times],
            confidence=confidence,
            insights=insights,
        )

    def get_day_of_week_analysis(self) -> dict[int, dict]:
        """
        Analyze engagement by day of week.

        Returns:
            Dict mapping weekday to stats
        """
        if not self._time_slots:
            return {}

        day_stats: dict[int, dict] = {}

        for (hour, weekday), slot in self._time_slots.items():
            if weekday not in day_stats:
                day_stats[weekday] = {
                    "total_posts": 0,
                    "avg_engagement": 0,
                    "best_hour": None,
                    "slots": [],
                }

            day_stats[weekday]["total_posts"] += slot.post_count
            day_stats[weekday]["slots"].append(slot)

        # Calculate averages and find best hours
        for weekday, stats in day_stats.items():
            if stats["slots"]:
                best_slot = max(stats["slots"], key=lambda s: s.engagement_score)
                stats["best_hour"] = best_slot.hour
                stats["avg_engagement"] = sum(
                    s.engagement_score for s in stats["slots"]
                ) / len(stats["slots"])

        return day_stats

    def get_recommendation_summary(self) -> str:
        """
        Get human-readable summary of recommendations.

        Returns:
            Summary string
        """
        if not self._time_slots:
            return "Недостаточно данных для анализа. Используйте стандартное расписание."

        best = self.get_best_times(3)
        worst = self.get_worst_times(2)

        lines = ["📊 Анализ времени публикаций:"]

        if best:
            lines.append("\n✅ Лучшее время:")
            for slot in best:
                confidence_str = f" (уверенность: {slot.confidence:.0%})" if slot.confidence < 1 else ""
                lines.append(f"  • {slot.hour:02d}:00 - score: {slot.engagement_score:.0f}{confidence_str}")

        if worst:
            lines.append("\n❌ Избегайте:")
            for slot in worst:
                lines.append(f"  • {slot.hour:02d}:00")

        return "\n".join(lines)


# Singleton
_scheduler_instance: Optional[SmartScheduler] = None


def get_smart_scheduler(post_store: Optional[PostStore] = None) -> SmartScheduler:
    """Get or create smart scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None or (post_store and _scheduler_instance.post_store != post_store):
        _scheduler_instance = SmartScheduler(post_store)
    return _scheduler_instance
