"""
Poll generation for interactive posts.

Generates polls for topics that suit them (opinions, preferences, quizzes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from llm import BaseLLMAdapter
from pipeline.source_collector import Article
from core.logger import get_logger

logger = get_logger(__name__)


class PollType(str, Enum):
    """Types of polls."""

    OPINION = "opinion"
    QUIZ = "quiz"
    PREFERENCE = "preference"


@dataclass
class PollData:
    """Generated poll data."""

    question: str
    options: list[str]
    allows_multiple_answers: bool
    correct_option: int | None  # Index of correct answer (0-based)
    post_id: Optional[int] = None  # Associated post if published
    created_at: Optional[str] = None


class PollGenerator:
    """Generate polls for interactive posts."""

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        channel_topic: str,
    ):
        self.llm = llm_adapter
        self.channel_topic = channel_topic

    def should_generate_poll(self, article: Article) -> bool:
        """Determine if article is suitable for poll generation."""
        poll_keywords = [
            "opinion",
            "prefer",
            "survey",
            "quiz",
            "vote",
            "think",
            "best",
            "worst",
            "top",
            "favorite",
            "choose",
        ]

        # Check if content suggests poll-worthy content
        text_lower = (article.title + " " + article.summary).lower()
        return any(kw in text_lower for kw in poll_keywords)

    def _build_prompt(
        self, topic: str, context_summary: str, poll_type: PollType
    ) -> str:
        """Build prompt for poll generation."""
        return f"""You are an expert content writer for a Telegram channel about {self.channel_topic}.

Generate a poll (quiz/opinion/preference) for the channel subscribers.

Guidelines:
1. Question should be engaging and relevant to the AI/tech audience
2. Options should be:
   - Clear and distinct (no overlap)
   - 4 options total
   - Reasonable length (not too long)
3. For quiz type: one option should be clearly correct
4. Consider the poll type: {poll_type.value}

Topic: {topic}
Context: {context_summary}

Return JSON only:
{{
    "question": "...",
    "options": ["...", "...", "...", "..."],
    "correct_option": <0-based index or null>
}}
"""

    async def generate(
        self, article: Article, poll_type: PollType = PollType.OPINION
    ) -> Optional[PollData]:
        """Generate a poll from an article."""
        if not self.should_generate_poll(article):
            logger.debug(f"Article not suitable for poll: {article.title}")
            return None

        context_summary = f"{article.title}\n\n{article.summary}"
        prompt = self._build_prompt(
            topic=article.title, context_summary=context_summary, poll_type=poll_type
        )

        try:
            response = await self.llm.generate(
                prompt=prompt, response_format={"type": "json"}
            )
            data = json.loads(response)

            return PollData(
                question=data["question"],
                options=data["options"],
                allows_multiple_answers=False,
                correct_option=data.get("correct_option"),
            )

        except Exception as e:
            logger.error(f"Failed to generate poll: {e}")
            return None
