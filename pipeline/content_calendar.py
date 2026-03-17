"""
Content Calendar & Strategic Planner - Intelligent scheduling system.

Plans content themes, avoids repetition, and maintains editorial calendar
with strategic content spacing and variety optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from memory.database import PostStore

logger = get_logger(__name__)


class ContentType(Enum):
    """Content type categories."""

    NEWS = "news"
    ANALYSIS = "analysis"
    TUTORIAL = "tutorial"
    OPINION = "opinion"
    TOOL_REVIEW = "tool_review"
    TREND = "trend"
    BREAKING = "breaking"
    DEEP_DIVE = "deep_dive"


@dataclass(slots=True)
class CalendarSlot:
    """A scheduled content slot in the calendar."""

    date: datetime
    content_type: ContentType
    topic_hint: str = ""
    post_id: Optional[int] = None
    status: str = "empty"  # empty, planned, scheduled, published
    priority: int = 5  # 1-10, 1 = highest


@dataclass(slots=True)
class ContentPlan:
    """Weekly content plan."""

    week_start: datetime
    slots: list[CalendarSlot] = field(default_factory=list)
    theme: str = ""
    goals: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TopicGap:
    """Identified gap in content coverage."""

    topic: str
    last_covered: Optional[datetime]
    suggested_priority: int
    reason: str


class ContentCalendar:
    """
    Strategic content planning and scheduling system.

    Features:
    - Theme-based weekly planning
    - Content variety optimization
    - Topic gap detection
    - Repetition avoidance
    - Strategic spacing
    """

    # Minimum days between same content type
    CONTENT_TYPE_SPACING = {
        ContentType.NEWS: 1,
        ContentType.ANALYSIS: 3,
        ContentType.TUTORIAL: 5,
        ContentType.OPINION: 4,
        ContentType.TOOL_REVIEW: 3,
        ContentType.TREND: 2,
        ContentType.BREAKING: 0,  # Can post anytime
        ContentType.DEEP_DIVE: 7,
    }

    # Target content mix (percentage)
    TARGET_MIX = {
        ContentType.NEWS: 30,
        ContentType.ANALYSIS: 25,
        ContentType.TUTORIAL: 10,
        ContentType.OPINION: 10,
        ContentType.TOOL_REVIEW: 10,
        ContentType.TREND: 10,
        ContentType.BREAKING: 5,
        ContentType.DEEP_DIVE: 5,
    }

    def __init__(
        self,
        post_store: Optional["PostStore"] = None,
        planning_window_days: int = 14,
        min_posts_per_week: int = 7,
    ) -> None:
        self.post_store = post_store
        self.planning_window = timedelta(days=planning_window_days)
        self.min_posts_per_week = min_posts_per_week
        self._calendar: dict[str, CalendarSlot] = {}  # date_key -> slot

    def plan_week(self, week_start: Optional[datetime] = None) -> ContentPlan:
        """
        Create a content plan for the week.

        Args:
            week_start: Start of the week (defaults to next Monday)

        Returns:
            ContentPlan with scheduled slots
        """
        if week_start is None:
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            week_start = today + timedelta(days=days_until_monday)
            week_start = week_start.replace(hour=9, minute=0, second=0, microsecond=0)

        plan = ContentPlan(
            week_start=week_start,
            theme=self._determine_weekly_theme(week_start),
        )

        # Generate slots for each day
        for day_offset in range(7):
            slot_date = week_start + timedelta(days=day_offset)
            content_type = self._suggest_content_type(slot_date, plan.slots)

            slot = CalendarSlot(
                date=slot_date,
                content_type=content_type,
                topic_hint=self._suggest_topic(content_type, plan),
                priority=self._calculate_priority(content_type, slot_date),
            )
            plan.slots.append(slot)
            self._calendar[slot_date.strftime("%Y-%m-%d")] = slot

        logger.info("Created content plan for week starting %s", week_start.date())
        return plan

    def _determine_weekly_theme(self, week_start: datetime) -> str:
        """Determine a theme for the week."""
        # Simple rotation of themes
        themes = [
            "AI Tools & Automation",
            "Machine Learning Advances",
            "Industry News & Updates",
            "Practical Tutorials",
            "Research & Analysis",
            "Future Trends",
            "Community & Opinions",
        ]
        week_number = week_start.isocalendar()[1]
        return themes[week_number % len(themes)]

    def _suggest_content_type(
        self,
        date: datetime,
        existing_slots: list[CalendarSlot],
    ) -> ContentType:
        """Suggest content type for a date based on spacing rules."""
        # Check what types we've used recently
        [s.content_type for s in existing_slots]

        # Find best type that respects spacing rules
        candidates = []
        for content_type, min_spacing in self.CONTENT_TYPE_SPACING.items():
            # Check if this type was used too recently
            days_since_last = self._days_since_type(content_type, existing_slots)
            if days_since_last >= min_spacing:
                candidates.append((content_type, days_since_last))

        if not candidates:
            # Default to news if no spacing rules satisfied
            return ContentType.NEWS

        # Prioritize by target mix and freshness
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _days_since_type(
        self,
        content_type: ContentType,
        slots: list[CalendarSlot],
    ) -> int:
        """Calculate days since last post of this type."""
        for slot in reversed(slots):
            if slot.content_type == content_type:
                return (datetime.now() - slot.date).days
        return 999  # Never used

    def _suggest_topic(self, content_type: ContentType, plan: ContentPlan) -> str:
        """Suggest a topic based on content type and weekly theme."""
        topic_hints = {
            ContentType.NEWS: f"Latest news in {plan.theme}",
            ContentType.ANALYSIS: f"Deep analysis of {plan.theme}",
            ContentType.TUTORIAL: f"How-to guide for {plan.theme}",
            ContentType.OPINION: f"Thoughts on {plan.theme}",
            ContentType.TOOL_REVIEW: f"Tool review related to {plan.theme}",
            ContentType.TREND: f"Emerging trends in {plan.theme}",
            ContentType.BREAKING: "Breaking news (check sources)",
            ContentType.DEEP_DIVE: f"Comprehensive deep dive into {plan.theme}",
        }
        return topic_hints.get(content_type, f"Content about {plan.theme}")

    def _calculate_priority(self, content_type: ContentType, date: datetime) -> int:
        """Calculate posting priority."""
        # Breaking news is always high priority
        if content_type == ContentType.BREAKING:
            return 1

        # Mid-week posts get higher priority
        if date.weekday() in [1, 2, 3]:  # Tuesday, Wednesday, Thursday
            return 3

        return 5

    def find_topic_gaps(
        self, topics: list[str], days_threshold: int = 14
    ) -> list[TopicGap]:
        """
        Find topics that haven't been covered recently.

        Args:
            topics: List of topics to check
            days_threshold: Days without coverage to consider a gap

        Returns:
            List of TopicGap objects
        """
        gaps = []
        now = datetime.now()

        for topic in topics:
            last_covered = self._find_last_coverage(topic)

            if last_covered is None:
                gaps.append(
                    TopicGap(
                        topic=topic,
                        last_covered=None,
                        suggested_priority=2,
                        reason="Never covered",
                    )
                )
            elif (now - last_covered).days >= days_threshold:
                gaps.append(
                    TopicGap(
                        topic=topic,
                        last_covered=last_covered,
                        suggested_priority=min(10, (now - last_covered).days // 2),
                        reason=f"Not covered for {(now - last_covered).days} days",
                    )
                )

        return sorted(gaps, key=lambda g: g.suggested_priority)

    def _find_last_coverage(self, topic: str) -> Optional[datetime]:
        """Find when a topic was last covered."""
        if not self.post_store:
            return None

        # This would query the post store for topic coverage
        # Simplified implementation
        return None

    def mark_slot_scheduled(self, date: datetime, post_id: int) -> None:
        """Mark a calendar slot as scheduled with a post."""
        date_key = date.strftime("%Y-%m-%d")
        if date_key in self._calendar:
            self._calendar[date_key].post_id = post_id
            self._calendar[date_key].status = "scheduled"
            logger.debug("Marked slot %s as scheduled with post %d", date_key, post_id)

    def mark_slot_published(self, date: datetime) -> None:
        """Mark a calendar slot as published."""
        date_key = date.strftime("%Y-%m-%d")
        if date_key in self._calendar:
            self._calendar[date_key].status = "published"
            logger.debug("Marked slot %s as published", date_key)

    def get_upcoming_slots(self, days: int = 7) -> list[CalendarSlot]:
        """Get upcoming calendar slots."""
        now = datetime.now()
        end_date = now + timedelta(days=days)

        slots = []
        for date_key, slot in self._calendar.items():
            slot_date = datetime.strptime(date_key, "%Y-%m-%d")
            if now <= slot_date <= end_date:
                slots.append(slot)

        return sorted(slots, key=lambda s: s.date)

    def get_content_mix_analysis(self) -> dict[str, Any]:
        """Analyze current content mix vs target."""
        type_counts: dict[ContentType, int] = {}

        for slot in self._calendar.values():
            if slot.status == "published":
                type_counts[slot.content_type] = (
                    type_counts.get(slot.content_type, 0) + 1
                )

        total = sum(type_counts.values()) or 1

        analysis = {
            "current_mix": {},
            "target_mix": {},
            "gaps": [],
        }

        for content_type in ContentType:
            current_pct = (type_counts.get(content_type, 0) / total) * 100
            target_pct = self.TARGET_MIX.get(content_type, 0)

            analysis["current_mix"][content_type.value] = current_pct
            analysis["target_mix"][content_type.value] = target_pct

            if target_pct > 0 and current_pct < target_pct * 0.7:
                analysis["gaps"].append(
                    {
                        "type": content_type.value,
                        "current": current_pct,
                        "target": target_pct,
                        "shortfall": target_pct - current_pct,
                    }
                )

        return analysis


# Configuration schema
CONTENT_CALENDAR_CONFIG_SCHEMA = {
    "content_calendar": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable content calendar system",
        },
        "planning_window_days": {
            "type": "int",
            "default": 14,
            "description": "Days to look ahead for planning",
        },
        "min_posts_per_week": {
            "type": "int",
            "default": 7,
            "description": "Minimum posts per week target",
        },
        "auto_theme_selection": {
            "type": "bool",
            "default": True,
            "description": "Automatically select weekly themes",
        },
    }
}
