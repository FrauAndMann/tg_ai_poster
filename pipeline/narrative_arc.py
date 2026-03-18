"""
Narrative Arc System - Plans multi-post story series.

Instead of standalone posts, implements a system that plans multi-post story
series with narrative continuity between chapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from core.constants import MAX_ARC_LENGTH
from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter
    from memory.database import Database

logger = get_logger(__name__)


class ArcStatus(str, Enum):
    """Status of a narrative arc."""

    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class ArcChapter:
    """A single chapter in a narrative arc."""

    chapter_number: int
    title: str
    topic: str
    key_points: list[str] = field(default_factory=list)
    scheduled_for: Optional[datetime] = None
    published_at: Optional[datetime] = None
    post_id: Optional[int] = None


@dataclass(slots=True)
class NarrativeArc:
    """A multi-post story series."""

    id: str
    title: str
    description: str
    total_chapters: int
    chapters: list[ArcChapter] = field(default_factory=list)
    status: ArcStatus = ArcStatus.PLANNING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    target_audience: str = "general"
    tone: str = "informative"  # informative, dramatic, analytical

    @property
    def current_chapter(self) -> int:
        """Get current chapter number."""
        for ch in self.chapters:
            if ch.published_at is None:
                return ch.chapter_number
        return len(self.chapters) + 1

    @property
    def next_chapter(self) -> Optional[ArcChapter]:
        """Get next unpublished chapter."""
        for ch in self.chapters:
            if ch.published_at is None:
                return ch
        return None

    @property
    def progress(self) -> float:
        """Get completion progress (0.0 to 1.0)."""
        if not self.chapters:
            return 0.0
        published = sum(1 for ch in self.chapters if ch.published_at)
        return published / len(self.chapters)


class NarrativeArcManager:
    """
    Manages narrative arc planning and execution.

    Features:
    - Story series planning
    - Chapter scheduling
    - Narrative continuity tracking
    - Automatic arc progression
    """

    # Arc planning prompt
    ARC_PLANNING_PROMPT = """Ты — редактор контента, планируешь серию постов на одну тему.

ТЕМА: {topic}
ОПИСАНИЕ: {description}
КОЛИЧЕСТВО ГЛАВ: {chapters}

Создай план серии постов. Для каждой главы:
1. Название главы (короткое, броское)
2. Основные тезисы (2-3 ключевых мысли)
3. Связь с предыдущей главой

ВАЖНО: Каждая глава должна логически следовать из предыдущей.

Верни JSON:
{{
    "chapters": [
        {
            "number": 1,
            "title": "Название главы",
            "key_points": ["Тезис 1", "Тезис 2", "Тезис 3"],
            "connection_to_previous": null
        }
    ]
}}"""

    def __init__(
        self,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
        db: Optional["Database"] = None,
        max_arc_length: int = MAX_ARC_LENGTH,
    ) -> None:
        """
        Initialize narrative arc manager.

        Args:
            llm_adapter: LLM adapter for planning
            db: Database for persistence
            max_arc_length: Maximum chapters per arc
        """
        self.llm = llm_adapter
        self.db = db
        self.max_arc_length = max_arc_length
        self._arcs: dict[str, NarrativeArc] = {}

    async def create_arc(
        self,
        topic: str,
        description: str,
        chapters: int = 5,
        target_audience: str = "general",
        tone: str = "informative",
    ) -> Optional[NarrativeArc]:
        """
        Create a new narrative arc.

        Args:
            topic: Main topic for the series
            description: Description of the story
            chapters: Number of chapters
            target_audience: Target audience
            tone: Content tone

        Returns:
            NarrativeArc: Created arc or None if failed
        """
        if chapters > self.max_arc_length:
            logger.warning(
                "Chapter count %d exceeds max %d", chapters, self.max_arc_length
            )
            chapters = self.max_arc_length

        import uuid

        arc_id = str(uuid.uuid4())[:8]

        arc = NarrativeArc(
            id=arc_id,
            title=topic,
            description=description,
            total_chapters=chapters,
            status=ArcStatus.PLANNING,
            target_audience=target_audience,
            tone=tone,
        )

        # Plan chapters if LLM available
        if self.llm:
            try:
                plan = await self._plan_chapters(arc)
                if plan:
                    arc.chapters = plan
                    logger.info("Planned %d chapters for arc %s", len(plan), arc_id)
            except Exception as e:
                logger.error("Failed to plan chapters: %s", e)
                # Create basic chapter structure
                arc.chapters = self._create_basic_chapters(chapters, topic)

        self._arcs[arc_id] = arc
        logger.info("Created narrative arc: %s (%d chapters)", arc_id, chapters)
        return arc

    async def _plan_chapters(self, arc: NarrativeArc) -> list[ArcChapter]:
        """Use LLM to plan chapters."""
        prompt = self.ARC_PLANNING_PROMPT.format(
            topic=arc.title,
            description=arc.description,
            chapters=arc.total_chapters,
        )

        response = await self.llm.generate(prompt)
        data = self._parse_chapter_plan(response.content)

        chapters = []
        for ch_data in data.get("chapters", []):
            chapters.append(
                ArcChapter(
                    chapter_number=ch_data.get("number", len(chapters) + 1),
                    title=ch_data.get("title", f"Chapter {len(chapters) + 1}"),
                    topic=arc.title,
                    key_points=ch_data.get("key_points", []),
                )
            )

        return chapters

    def _parse_chapter_plan(self, content: str) -> dict:
        """Parse chapter plan from LLM response."""
        import json

        try:
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, KeyError):
            return {"chapters": []}

    def _create_basic_chapters(self, count: int, topic: str) -> list[ArcChapter]:
        """Create basic chapter structure without LLM."""
        return [
            ArcChapter(
                chapter_number=i + 1,
                title=f"Часть {i + 1}: {topic}",
                topic=topic,
                key_points=[],
            )
            for i in range(count)
        ]

    def get_active_arc(self) -> Optional[NarrativeArc]:
        """Get the currently active narrative arc."""
        for arc in self._arcs.values():
            if arc.status == ArcStatus.ACTIVE:
                return arc
        return None

    def start_arc(self, arc_id: str) -> bool:
        """Start a narrative arc."""
        arc = self._arcs.get(arc_id)
        if not arc:
            return False

        arc.status = ArcStatus.ACTIVE
        arc.started_at = datetime.now()
        logger.info("Started narrative arc: %s", arc_id)
        return True

    def complete_arc(self, arc_id: str) -> bool:
        """Mark an arc as completed."""
        arc = self._arcs.get(arc_id)
        if not arc:
            return False

        arc.status = ArcStatus.COMPLETED
        arc.completed_at = datetime.now()
        logger.info("Completed narrative arc: %s", arc_id)
        return True

    def record_chapter_publication(
        self,
        arc_id: str,
        chapter_number: int,
        post_id: int,
    ) -> bool:
        """Record that a chapter was published."""
        arc = self._arcs.get(arc_id)
        if not arc:
            return False

        for chapter in arc.chapters:
            if chapter.chapter_number == chapter_number:
                chapter.published_at = datetime.now()
                chapter.post_id = post_id
                logger.info("Chapter %d of arc %s published", chapter_number, arc_id)

                # Check if arc is complete
                if arc.progress >= 1.0:
                    self.complete_arc(arc_id)

                return True

        return False

    def get_next_chapter_context(self, arc_id: str) -> Optional[dict[str, Any]]:
        """Get context for generating the next chapter."""
        arc = self._arcs.get(arc_id)
        if not arc or arc.status != ArcStatus.ACTIVE:
            return None

        next_chapter = arc.next_chapter
        if not next_chapter:
            return None

        # Build context from previous chapters
        previous_chapters = [
            {"title": ch.title, "key_points": ch.key_points}
            for ch in arc.chapters
            if ch.published_at and ch.chapter_number < next_chapter.chapter_number
        ]

        return {
            "arc_title": arc.title,
            "arc_description": arc.description,
            "current_chapter": next_chapter.chapter_number,
            "total_chapters": arc.total_chapters,
            "chapter_title": next_chapter.title,
            "key_points": next_chapter.key_points,
            "previous_chapters": previous_chapters,
            "tone": arc.tone,
            "target_audience": arc.target_audience,
        }


# Configuration schema
NARRATIVE_ARC_CONFIG_SCHEMA = {
    "storytelling": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable narrative arc system",
        },
        "max_arc_length": {
            "type": "int",
            "default": 10,
            "min": 2,
            "max": 30,
            "description": "Maximum chapters per arc",
        },
    }
}
