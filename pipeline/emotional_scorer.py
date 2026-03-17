"""
Emotional Resonance Scoring - Scores posts on emotional dimensions.

Analyzes curiosity, urgency, empathy, inspiration, humor, controversy.
Learns which emotional profiles drive highest engagement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter

logger = get_logger(__name__)


@dataclass(slots=True)
class EmotionalProfile:
    """Emotional scores for a post."""

    curiosity: float = 1.0
    urgency: float = 1.0
    empathy: float = 1.0
    inspiration: float = 1.0
    humor: float = 1.0
    controversy: float = 1.0
    overall_score: float = 1.0
    dominant_emotion: str = "curiosity"
    confidence: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "dimensions": {
                "curiosity": self.curiosity,
                "urgency": self.urgency,
                "empathy": self.empathy,
                "inspiration": self.inspiration,
                "humor": self.humor,
                "controversy": self.controversy,
            },
            "overall_score": self.overall_score,
            "dominant_emotion": self.dominant_emotion,
            "confidence": self.confidence,
        }


class EmotionalScorer:
    """
    Scores posts on emotional dimensions.

    Uses LLM to analyze emotional content and learns
    which profiles drive highest engagement.
    """

    SCORING_PROMPT = """Проанализируй эмоциональный профиль этого поста для Telegram-канала об AI/ML теме.

Оцени пост по шкале 1-10 для каждого измерения:

ПОСТ:
{content}

Верни JSON с оценками:
{{
    "curiosity": 7,
    "urgency": 5,
    "empathy": 3,
    "inspiration": 6,
    "humor": 2,
    "controversy": 4,
    "dominant_emotion": "curiosity",
    "confidence": 0.8
}}"""

    def __init__(
        self,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
    ) -> None:
        """
        Initialize emotional scorer.

        Args:
            llm_adapter: LLM adapter for scoring
        """
        self.llm = llm_adapter
        self._engagement_history: dict[str, float] = {}  # emotion_profile -> avg_engagement
        self._scored_posts: dict[int, EmotionalProfile] = {}  # post_id -> profile

    async def score(self, content: str) -> Optional[EmotionalProfile]:
        """
        Score content on emotional dimensions.

        Args:
            content: Post content to analyze

        Returns:
            EmotionalProfile: Emotional scores
        """
        if not self.llm:
            return self._score_rule_based(content)
        try:
            prompt = self.SCORING_PROMPT.format(content=content)
            response = await self.llm.generate(prompt)
            profile = self._parse_response(response.content)
            return profile
        except Exception as e:
            logger.error("Emotional scoring failed: %s", e)
            return self._score_rule_based(content)
    def _parse_response(self, content: str) -> Optional[EmotionalProfile]:
        """Parse LLM response into EmotionalProfile."""
        import json
        try:
                # Extract JSON
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                data = json.loads(content.strip())
                return EmotionalProfile(
                    curiosity=float(data.get("curiosity", 5)),
                    urgency=float(data.get("urgency", 5)),
                    empathy=float(data.get("empathy", 5)),
                    inspiration=float(data.get("inspiration", 5)),
                    humor=float(data.get("humor", 5)),
                    controversy=float(data.get("controversy", 5)),
                    overall_score=sum(data.values()) / 6,
                    dominant_emotion=data.get("dominant_emotion", "curiosity"),
                    confidence=float(data.get("confidence", 1.0)),
                )
        except (json.JSONDecodeError, KeyError):
            return None
    def _score_rule_based(self, content: str) -> EmotionalProfile:
        """Simple rule-based emotional scoring."""
        content_lower = content.lower()
        curiosity = self._count_patterns(content_lower, [
            "как", "почему", "что это значит", "интерес", "узнать", "понять",
            "how", "why", "что", "why does",
        ])
        urgency = self._count_patterns(content_lower, [
            "срочно", "немедленно", "прямо сейчас", "уже сегодня", "бьющая тревогу",
            "breaking", "urgent", "только что", "deadline",
        ])
        empathy = self._count_patterns(content_lower, [
            "представь", "понимаю", "чувствую", "больно", "радость", "переживания",
            "трудно", "сочувствую", "empower", "support",
        ])
        inspiration = self._count_patterns(content_lower, [
            "вдохновляет", "успех", "прорыв", "возможности", "будущее", "мечта",
            "inspire", "dream", "hope", "vision",
        ])
        humor = self._count_patterns(content_lower, [
            "смешно", "забавно", "ирония", "курьез", "неожиданно", "humor",
            "funny", "lol", "ironic",
        ])
        controversy = self._count_patterns(content_lower, [
            "спор", "критика", "скандал", "обвинения", "проблема", "разочарование",
            "controversial", "debate", "argue", "criticism",
        ])
        profile = EmotionalProfile(
            curiosity=min(1.0, curiosity / 5),
            urgency=min(1.0, urgency / 5),
            empathy=min(1.0, empathy / 5),
            inspiration=min(1.0, inspiration / 5),
            humor=min(1.0, humor / 5),
            controversy=min(1.0, controversy / 5),
        )
        profile.overall_score = (
            profile.curiosity + profile.urgency + profile.empathy +
            profile.inspiration + profile.humor + profile.controversy
        ) / 6
        return profile
    def _count_patterns(self, text: str, patterns: list[str]) -> float:
        """Count pattern matches and normalize."""
        count = sum(1 for p in patterns if p in text)
        return count / len(patterns)
    def record_engagement(
        self,
        post_id: int,
        emotional_profile: EmotionalProfile,
        engagement_rate: float,
    ) -> None:
        """
        Record engagement for an emotional profile.

        Adjusts profile preferences based on performance.

        Args:
            post_id: Post ID
            emotional_profile: Profile used
            engagement_rate: Actual engagement rate
        """
        profile_key = emotional_profile.dominant_emotion
        current_avg = self._engagement_history.get(profile_key, 0.5)
        # Running average
        new_avg = current_avg * 0.8 + engagement_rate * 0.2
        self._engagement_history[profile_key] = new_avg
        self._scored_posts[post_id] = emotional_profile
        logger.debug(
            "Recorded engagement for %s profile: %.2f",
            profile_key, engagement_rate,
        )
    def get_optimal_profile(self) -> dict[str, float]:
        """Get optimal emotional profile based on history."""
        return dict(sorted(self._engagement_history.items(), key=lambda x: x[1], reverse=True))
    def get_target_emotional_instructions(self) -> str:
        """Generate instructions for target emotional profile."""
        optimal = self.get_optimal_profile()
        if not optimal:
            return ""
        top_emotion = list(optimal.keys())[0]
        instructions = {
            "curiosity": "Вызвать интерес и любопытство. Задавать вопросы. Объяснять как и почему.",
            "urgency": "Подчеркнуть актуальность и временную значимость. Создавать ощущение важности.",
            "empathy": "Обращаться к чувствам читателя. Показывать понимание проблем аудитории.",
            "inspiration": "Вдохновлять и мотивировать. Показывать возможности и успехи.",
            "humor": "Использовать легкий тон и иронию. Делать контент запоминающимся.",
            "controversy": "Затрагивать спорные темы. Приводить разные точки зрения.",
        }
        return instructions.get(top_emotion, "")


# Configuration schema
EMOTIONAL_SCORER_CONFIG_SCHEMA = {
    "emotions": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable emotional resonance scoring",
        },
        "target_profile": {
            "type": "str",
            "default": "curiosity",
            "description": "Target dominant emotion for content",
        },
    }
}
