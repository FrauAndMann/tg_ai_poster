"""
Content Recycling System - Intelligently recycles evergreen posts.

Identifies high-engagement posts older than a threshold and schedules them
for republication with AI-rewritten content while preserving core facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from core.constants import (
    RECYCLING_MIN_AGE_DAYS,
    RECYCLING_MIN_ENGAGEMENT_SCORE,
    RECYCLING_CONTENT_REWRITE_THRESHOLD,
)
from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter
    from memory.post_store import PostStore

logger = get_logger(__name__)


@dataclass(slots=True)
class RecyclablePost:
    """Represents a post candidate for recycling."""

    post_id: int
    original_content: str
    engagement_score: float
    published_at: datetime
    topic: str
    source_urls: list[str] = field(default_factory=list)
    post_type: str = "analysis"

    @property
    def age_days(self) -> int:
        """Calculate age of the post in days."""
        return (datetime.now() - self.published_at).days


@dataclass(slots=True)
class RecycledContent:
    """Result of content recycling."""

    original_post_id: int
    new_content: str
    rewrite_ratio: float  # Percentage of content that was rewritten
    preserved_facts: list[str] = field(default_factory=list)
    new_angle: str = ""
    confidence: float = 0.0


class ContentRecycler:
    """
    Intelligent content recycling system.

    Identifies evergreen posts with high engagement and creates
    fresh versions with updated statistics and new angles.
    """

    # System prompt for content rewriting
    REWRITE_PROMPT = """Ты — опытный редактор технического канала. Твоя задача — переписать пост,
сохранив все ключевые факты, но с новым углом подачи и обновлённой статистикой.

ПРАВИЛА:
1. Сохрани ВСЕ технические факты и цифры
2. Измени вступление (hook) полностью
3. Перепиши минимум 40% текста новыми словами
4. Добавь актуальный контекст (если применимо)
5. Измени структуру абзацев
6. Сохрани тональность: экспертная, но доступная

ОРИГИНАЛЬНЫЙ ПОСТ:
{original_content}

ТЕМА: {topic}
ТИП ПОСТА: {post_type}

ВАЖНО: Верни результат в JSON формате:
{{
    "new_content": "полный текст нового поста",
    "rewrite_ratio": 0.45,
    "preserved_facts": ["факт 1", "факт 2"],
    "new_angle": "описание нового угла подачи"
}}
"""

    def __init__(
        self,
        post_store: "PostStore",
        llm_adapter: Optional["BaseLLMAdapter"] = None,
        min_age_days: int = RECYCLING_MIN_AGE_DAYS,
        min_engagement_score: float = RECYCLING_MIN_ENGAGEMENT_SCORE,
        min_rewrite_ratio: float = RECYCLING_CONTENT_REWRITE_THRESHOLD,
        max_candidates: int = 10,
    ) -> None:
        """
        Initialize content recycler.

        Args:
            post_store: Post storage for fetching historical posts
            llm_adapter: LLM adapter for content rewriting
            min_age_days: Minimum age in days for recycling eligibility
            min_engagement_score: Minimum engagement score threshold
            min_rewrite_ratio: Minimum content that must be rewritten
            max_candidates: Maximum number of candidates to process per run
        """
        self.post_store = post_store
        self.llm = llm_adapter
        self.min_age_days = min_age_days
        self.min_engagement_score = min_engagement_score
        self.min_rewrite_ratio = min_rewrite_ratio
        self.max_candidates = max_candidates

    async def find_recyclable_posts(self) -> list[RecyclablePost]:
        """
        Find posts eligible for recycling.

        Criteria:
        - Age >= min_age_days
        - Engagement score >= min_engagement_score
        - Not already recycled recently

        Returns:
            List of RecyclablePost candidates sorted by engagement
        """
        logger.info(
            "Searching for recyclable posts: age>=%ddays, engagement>=%.2f",
            self.min_age_days,
            self.min_engagement_score,
        )

        try:
            # Get high-engagement posts from database
            # This assumes post_store has a method to query by criteria
            posts = await self._fetch_eligible_posts()

            candidates = []
            for post in posts:
                recyclable = RecyclablePost(
                    post_id=post["id"],
                    original_content=post["content"],
                    engagement_score=post.get("engagement_score", 0.0),
                    published_at=post["published_at"],
                    topic=post.get("topic", ""),
                    source_urls=post.get("source_urls", []),
                    post_type=post.get("post_type", "analysis"),
                )
                candidates.append(recyclable)

            # Sort by engagement score (highest first)
            candidates.sort(key=lambda x: x.engagement_score, reverse=True)

            # Limit candidates
            candidates = candidates[: self.max_candidates]

            logger.info("Found %d recyclable post candidates", len(candidates))
            return candidates

        except Exception as e:
            logger.error("Failed to find recyclable posts: %s", e)
            return []

    async def _fetch_eligible_posts(self) -> list[dict]:
        """Fetch posts that meet recycling criteria from database."""
        # This would query the post_store for posts matching criteria
        # Implementation depends on PostStore interface
        datetime.now() - timedelta(days=self.min_age_days)

        # Placeholder - actual implementation would use post_store
        return []

    async def recycle_post(self, post: RecyclablePost) -> Optional[RecycledContent]:
        """
        Recycle a single post with AI rewriting.

        Args:
            post: Post to recycle

        Returns:
            RecycledContent if successful, None otherwise
        """
        if not self.llm:
            logger.warning("No LLM adapter configured for content recycling")
            return None

        try:
            prompt = self.REWRITE_PROMPT.format(
                original_content=post.original_content,
                topic=post.topic,
                post_type=post.post_type,
            )

            response = await self.llm.generate(prompt)
            result = self._parse_recycle_response(response.content)

            if result and result.rewrite_ratio >= self.min_rewrite_ratio:
                logger.info(
                    "Successfully recycled post %d: %.0f%% rewritten",
                    post.post_id,
                    result.rewrite_ratio * 100,
                )
                return result
            else:
                logger.warning(
                    "Recycled content doesn't meet rewrite threshold: %.0f%% < %.0f%%",
                    (result.rewrite_ratio * 100) if result else 0,
                    self.min_rewrite_ratio * 100,
                )
                return None

        except Exception as e:
            logger.error("Failed to recycle post %d: %s", post.post_id, e)
            return None

    def _parse_recycle_response(self, response: str) -> Optional[RecycledContent]:
        """Parse LLM response into RecycledContent."""
        import json

        try:
            # Extract JSON from response
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response.strip())

            return RecycledContent(
                original_post_id=0,  # Will be set by caller
                new_content=data.get("new_content", ""),
                rewrite_ratio=float(data.get("rewrite_ratio", 0.0)),
                preserved_facts=data.get("preserved_facts", []),
                new_angle=data.get("new_angle", ""),
                confidence=0.8,
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Failed to parse recycle response: %s", e)
            return None

    async def run_recycling_cycle(self) -> list[RecycledContent]:
        """
        Run a complete recycling cycle.

        Finds candidates, recycles them, and returns successful results.

        Returns:
            List of successfully recycled content
        """
        logger.info("Starting content recycling cycle")

        candidates = await self.find_recyclable_posts()
        if not candidates:
            logger.info("No recyclable posts found")
            return []

        results = []
        for candidate in candidates:
            recycled = await self.recycle_post(candidate)
            if recycled:
                recycled.original_post_id = candidate.post_id
                results.append(recycled)

        logger.info(
            "Recycling cycle complete: %d/%d posts recycled",
            len(results),
            len(candidates),
        )
        return results


# Configuration schema for config.yaml
RECYCLING_CONFIG_SCHEMA = {
    "recycling": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable content recycling feature",
        },
        "min_age_days": {
            "type": "int",
            "default": 30,
            "min": 14,
            "max": 365,
            "description": "Minimum age in days before post can be recycled",
        },
        "min_engagement_score": {
            "type": "float",
            "default": 0.7,
            "min": 0.0,
            "max": 1.0,
            "description": "Minimum engagement score for recycling eligibility",
        },
        "min_rewrite_ratio": {
            "type": "float",
            "default": 0.4,
            "min": 0.3,
            "max": 0.8,
            "description": "Minimum percentage of content that must be rewritten",
        },
        "max_candidates_per_run": {
            "type": "int",
            "default": 5,
            "min": 1,
            "max": 20,
            "description": "Maximum candidates to process per recycling cycle",
        },
        "schedule_hours": {
            "type": "int",
            "default": 168,  # Weekly
            "min": 24,
            "max": 720,
            "description": "Hours between recycling cycles",
        },
    }
}
