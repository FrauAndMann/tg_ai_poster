"""
Structural Variation System - Varies post structure to prevent monotony.

Provides multiple alternative structures and templates for content variety.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class StructureType(Enum):
    """Types of post structures."""
    CLASSIC = "classic"  # Title -> Hook -> Body -> Key Facts -> Analysis -> Sources
    INVERTED = "inverted"  # Key Fact first -> Context -> Analysis
    STORY = "story"  # Narrative arc with personal angle
    BULLET_HEAVY = "bullet_heavy"  # More bullet points, less prose
    QUESTION_LED = "question_led"  # Opens with provocative question
    DATA_FIRST = "data_first"  # Statistics and numbers lead
    COMPARISON = "comparison"  # X vs Y structure
    TIMELINE = "timeline"  # Chronological progression


@dataclass(slots=True)
class StructureTemplate:
    """Template for post structure."""
    name: str
    structure_type: StructureType
    sections: list[str]
    hooks: list[str] = field(default_factory=list)
    transitions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StructureVariationReport:
    """Report on structure variation analysis."""
    current_structure: str
    suggested_alternatives: list[str]
    variety_score: float
    recommendations: list[str] = field(default_factory=list)


class StructureVariator:
    """
    Provides structural variety for posts.

    Features:
    - Multiple structure templates
    - Hook variation
    - Transition phrase rotation
    - Section reordering
    """

    TEMPLATES = {
        StructureType.CLASSIC: StructureTemplate(
            name="classic",
            structure_type=StructureType.CLASSIC,
            sections=["title", "hook", "body", "key_facts", "analysis", "sources", "tldr"],
            hooks=[
                "Что если",
                "Представьте",
                "Знаете ли вы, что",
                "Важное обновление",
                "Только что стало известно",
            ],
            transitions=[
                "Что это значит:",
                "Почему это важно:",
                "Ключевые моменты:",
                "В чём суть:",
            ],
        ),
        StructureType.INVERTED: StructureTemplate(
            name="inverted",
            structure_type=StructureType.INVERTED,
            sections=["key_fact_first", "context", "analysis", "implications", "sources"],
            hooks=[
                "Главный факт:",
                "Суть в одном предложении:",
                "Коротко:",
                "Важно:",
            ],
            transitions=[
                "Контекст:",
                "Что за этим стоит:",
                "Детали:",
            ],
        ),
        StructureType.STORY: StructureTemplate(
            name="story",
            structure_type=StructureType.STORY,
            sections=["scene_setter", "conflict", "resolution", "takeaway", "sources"],
            hooks=[
                "На прошлой неделе",
                "Вчера в",
                "Когда команда",
                "История началась с",
            ],
            transitions=[
                "И тут",
                "Но THEN",
                "Развитие событий:",
                "Чем всё закончилось:",
            ],
        ),
        StructureType.QUESTION_LED: StructureTemplate(
            name="question_led",
            structure_type=StructureType.QUESTION_LED,
            sections=["provocative_question", "context", "answer", "implications", "sources"],
            hooks=[
                "Почему",
                "Как",
                "Что будет, если",
                "Знали ли вы, что",
                "Когда последний раз",
            ],
            transitions=[
                "Ответ:",
                "Вот что мы знаем:",
                "Раскрываем детали:",
            ],
        ),
        StructureType.DATA_FIRST: StructureTemplate(
            name="data_first",
            structure_type=StructureType.DATA_FIRST,
            sections=["stat_lead", "context", "analysis", "what_it_means", "sources"],
            hooks=[
                "X% компаний уже",
                "$Y миллиардов —",
                "За последние N месяцев",
                "По данным исследования",
            ],
            transitions=[
                "Что за цифрами:",
                "Расшифровка:",
                "Сравнение с прошлым годом:",
            ],
        ),
    }

    # Transition phrase variations
    TRANSITION_PHRASES = {
        "to_analysis": [
            "Почему это важно:",
            "В чём значимость:",
            "Что это значит для индустрии:",
            "Ключевой инсайт:",
        ],
        "to_facts": [
            "Что нужно знать:",
            "Ключевые факты:",
            "Главное в цифрах:",
            "Суть изменений:",
        ],
        "to_sources": [
            "Подробнее:",
            "Источники:",
            "Читать далее:",
            "Материалы по теме:",
        ],
    }

    def __init__(self, seed: Optional[int] = None) -> None:
        """Initialize structure variator."""
        self._rng = random.Random(seed)
        self._used_structures: list[StructureType] = []
        self._max_history = 10

    def get_structure(self, post_type: str, avoid_recent: bool = True) -> StructureTemplate:
        """
        Get a structure template for a post type.

        Args:
            post_type: Type of post (news, analysis, tutorial, etc.)
            avoid_recent: Whether to avoid recently used structures

        Returns:
            StructureTemplate to use
        """
        # Map post types to preferred structures
        type_preferences = {
            "news": [StructureType.CLASSIC, StructureType.DATA_FIRST, StructureType.INVERTED],
            "analysis": [StructureType.QUESTION_LED, StructureType.CLASSIC, StructureType.STORY],
            "tutorial": [StructureType.BULLET_HEAVY, StructureType.CLASSIC],
            "deep_dive": [StructureType.STORY, StructureType.COMPARISON, StructureType.CLASSIC],
            "tool_roundup": [StructureType.BULLET_HEAVY, StructureType.COMPARISON],
            "breaking": [StructureType.INVERTED, StructureType.DATA_FIRST],
        }

        preferred = type_preferences.get(post_type, [StructureType.CLASSIC])

        if avoid_recent and self._used_structures:
            # Filter out recently used
            available = [s for s in preferred if s not in self._used_structures[-3:]]
            if not available:
                available = preferred

            # Pick randomly from available
            chosen = self._rng.choice(available)
        else:
            chosen = self._rng.choice(preferred)

        # Track usage
        self._used_structures.append(chosen)
        if len(self._used_structures) > self._max_history:
            self._used_structures.pop(0)

        return self.TEMPLATES[chosen]

    def get_hook(self, structure_type: StructureType) -> str:
        """Get a hook phrase for the structure."""
        template = self.TEMPLATES.get(structure_type, self.TEMPLATES[StructureType.CLASSIC])
        return self._rng.choice(template.hooks) if template.hooks else ""

    def get_transition(self, transition_type: str) -> str:
        """Get a transition phrase."""
        phrases = self.TRANSITION_PHRASES.get(transition_type, [])
        return self._rng.choice(phrases) if phrases else ""

    def analyze_variety(self, recent_posts: list[dict]) -> StructureVariationReport:
        """
        Analyze structural variety in recent posts.

        Args:
            recent_posts: List of recent post data

        Returns:
            StructureVariationReport with analysis
        """
        if not recent_posts:
            return StructureVariationReport(
                current_structure="unknown",
                suggested_alternatives=[s.value for s in StructureType],
                variety_score=1.0,
                recommendations=["No recent posts to analyze"],
            )

        # Count structure types used
        structure_counts: dict[str, int] = {}
        for post in recent_posts:
            structure = post.get("structure_type", "classic")
            structure_counts[structure] = structure_counts.get(structure, 0) + 1

        # Calculate variety score
        total = len(recent_posts)
        unique = len(structure_counts)
        variety_score = unique / min(total, len(StructureType))

        # Find overused and underused
        recommendations = []
        dominant = max(structure_counts.items(), key=lambda x: x[1])[0] if structure_counts else "classic"

        if structure_counts.get(dominant, 0) > total * 0.5:
            recommendations.append(
                f"Structure '{dominant}' used {structure_counts[dominant]}/{total} times. "
                "Consider more variety."
            )

        # Suggest alternatives
        unused = [s.value for s in StructureType if s.value not in structure_counts]
        if unused:
            recommendations.append(f"Try these unused structures: {', '.join(unused[:3])}")

        return StructureVariationReport(
            current_structure=dominant,
            suggested_alternatives=unused[:5] if unused else [s.value for s in StructureType],
            variety_score=variety_score,
            recommendations=recommendations,
        )


# Configuration schema
STRUCTURE_VARIATION_CONFIG_SCHEMA = {
    "structure_variation": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable structure variation",
        },
        "avoid_recent_count": {
            "type": "int",
            "default": 3,
            "description": "Number of recent structures to avoid repeating",
        },
        "preferred_by_type": {
            "type": "dict",
            "default": {},
            "description": "Override default structure preferences by post type",
        },
    }
}
