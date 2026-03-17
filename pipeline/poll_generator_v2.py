"""
Interactive Poll Generator v2 - LLM-powered poll generation.

Generates interesting, non-obvious polls that feed back
as data for persona engine.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter

logger = get_logger(__name__)


@dataclass(slots=True)
class PollOption:
    """A poll option."""

    text: str
    is_correct: bool = False


    votes: int = 0


@dataclass(slots=True)
class GeneratedPoll:
    """A generated poll with results."""

    question: str
    options: list[PollOption] = field(default_factory=list)
    trick_answer_index: int = 0  # Index of "trick" answer
    votes: dict[str, int] = field(default_factory=dict)  # option_text -> vote_count
    generated_at: datetime = field(default_factory=datetime.now)
    message_id: Optional[int] = None
    total_votes: int = 0


class PollGeneratorV2:
    """
    Advanced poll generator with LLM-powered creation.

    Features:
    - LLM analyzes post content for poll questions
    - Non-obvious "trick" answers
    - Discussion-sparking question design
    - Performance tracking
    """

    POLL_GENERATION_PROMPT = """Создай опрос на основе этого поста для Telegram-канала.

ПОСТ:
{post_content}

ТРЕбования к опросу:
1. Вопрос должен быть интересным и релевантным
2. 3-4 варианта ответа
3. Один ответ должен быть "хитрым" - правильный, но неочевидным
4. Один ответ должен быть "обманкой" - кажется правильным, но это распространенное заблуждение
5. Один ответ должен быть "трюком" - неожиданный инсайт

6. Вопрос должен побуждать к обсуждениям в комментариях

Верни JSON:
{{
    "question": "Вопрос?",
    "options": [
        {"text": "Вариант 1", "type": "trick"},
        {"text": "Вариант 2", "type": "decoy"},
        {"text": "Вариант 3", "type": "decoy"},
        {"text": "Вариант 4", "type": "decoy"}
    ],
    "trick_index": 0
}}"""

    def __init__(
        self,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
    ) -> None:
        """
        Initialize poll generator.

        Args:
            llm_adapter: LLM adapter for generation
        """
        self.llm = llm_adapter
        self._polls: dict[int, GeneratedPoll] = {}
        self._option_performance: dict[str, float] = {}  # option_text -> avg_engagement

    async def generate_poll(
        self,
        post_content: str,
        post_type: str = "analysis",
    ) -> Optional[GeneratedPoll]:
        """
        Generate a poll for a post.

        Args:
            post_content: Post content
            post_type: Type of post

        Returns:
            GeneratedPoll: Generated poll
        """
        if not self.llm:
            return self._generate_fallback_poll(post_content)
        try:
            prompt = self.POLL_GENERATION_PROMPT.format(post_content=post_content)
            response = await self.llm.generate(prompt)
            poll_data = self._parse_response(response.content)
            if poll_data:
                return self._create_poll_from_data(poll_data)
            return self._generate_fallback_poll(post_content)
        except Exception as e:
            logger.error("Poll generation failed: %s", e)
            return self._generate_fallback_poll(post_content)
    def _parse_response(self, content: str) -> Optional[dict]:
        """Parse LLM response."""
        import json
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, KeyError):
            return None
    def _create_poll_from_data(self, data: dict) -> GeneratedPoll:
        """Create poll from parsed data."""
        options = []
        for i in range(4):
            opt_text = data.get("options", [{}])[i].get("text", f"Вариант {i+1}")
            options.append(PollOption(text=opt_text))
        poll = GeneratedPoll(
            question=data.get("question", ""),
            options=options,
            trick_answer_index=data.get("trick_index", 0),
        )
        return poll
    def _generate_fallback_poll(self, post_content: str) -> GeneratedPoll:
        """Generate a fallback poll without LLM."""
        # Extract key terms from content
        words = post_content.split()[:20]
        key_terms = [w for w in words if len(w) > 5][:3]
        # Generic poll based on content
        if "AI" in post_content or "ML" in post_content or "нейро" in post_content:
            return GeneratedPoll(
                question="Как вы думаете, какой нейосет станет качество больше всего изменит индустрию?",
                options=[
                    PollOption("Генеративный AI", is_correct=True),
                    PollOption("Автономные агенты", is_correct=False),
                    PollOption("Мультимодальные модели", is_correct=False),
                    PollOption("Edge AI", is_correct=False),
                ],
                trick_answer_index=0,
            )
        else:
            return GeneratedPoll(
                question="Что вас интересует в технологиях больше всего?",
                options=[
                    PollOption("Новые продукты", is_correct=False),
                    PollOption("Исследования и статьи", is_correct=False),
                    PollOption("Практические кейсы", is_correct=False),
                    PollOption("Новости индустрии", is_correct=False),
                ],
                trick_answer_index=random.randint(0, 3),
            )
    def record_votes(
        self,
        poll_id: int,
        votes: dict[str, int],
    ) -> None:
        """Record poll votes for analysis."""
        if poll_id not in self._polls:
            return
        poll = self._polls[poll_id]
        poll.votes = votes
        poll.total_votes = sum(votes.values())
        # Analyze which options got most votes
        for option_text, vote_count in votes.items():
            if option_text not in self._option_performance:
                self._option_performance[option_text] = []
            self._option_performance[option_text].append(
                vote_count / poll.total_votes if poll.total_votes > 0 else 0.0
            )
    def get_best_poll_format(self) -> dict[str, Any]:
        """Analyze which poll formats perform best."""
        return {
            "total_polls": len(self._polls),
            "option_performance": dict(self._option_performance),
        }


# Configuration schema
POLL_GENERATOR_V2_CONFIG_SCHEMA = {
    "polls_v2": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable advanced poll generation",
        },
        "probability": {
            "type": "float",
            "default": 0.0,
            "min": 0.0,
            "max": 1.0,
            "description": "Probability of generating a poll for a post",
        },
    }
}
