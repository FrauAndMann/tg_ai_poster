"""Information density scorer for measuring content quality."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DensityReport:
    """Result of density scoring."""

    density_score: float = 0.0
    facts_count: int = 0
    numbers_count: int = 0
    proper_nouns_count: int = 0
    dates_count: int = 0
    passes_threshold: bool = True
    recommendations: list[str] = field(default_factory=list)


class DensityScorer:
    """
    Calculates information density of content.

    Scores based on:
    - Specific facts (10 points each)
    - Numbers/metrics (8 points each)
    - Proper nouns (5 points each)
    - Specific dates (7 points each)
    """

    NUMBER_PATTERN = re.compile(
        r'\d+[.,]?\d*\s*(?:%|млн|млрд|тыс|million|billion|k)?|'
        r'\$[\d,]+|€[\d,]+|₽[\d,]+',
        re.IGNORECASE
    )

    DATE_PATTERN = re.compile(
        r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|'
        r'августа|сентября|октября|ноября|декабря)\s*(?:\d{4})?|'
        r'(?:January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+\d{1,2},?\s*\d{4}|'
        r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])',
        re.IGNORECASE
    )

    PROPER_NOUN_PATTERN = re.compile(
        r'\b(?:OpenAI|Google|Microsoft|Apple|Meta|Amazon|Anthropic|'
        r'DeepMind|Tesla|NVIDIA|GPT-[45]|Claude|Gemini|Llama|'
        r'ChatGPT)\b'
    )

    FACT_PATTERN = re.compile(
        r'(?:утверждает|сообщает|объявила|выпустила|анонсировала|'
        r'инвестировала|запустила|представила|по\s+данным|исследование|'
        r'according\s+to|announced|released|stated|reported|invested|'
        r'research|launched|presented)\b',
        re.IGNORECASE
    )

    def __init__(self, min_density: float = 15.0) -> None:
        self.min_density = min_density

    def score(self, text: str) -> DensityReport:
        """Calculate information density score."""
        word_count = len(text.split())
        if word_count == 0:
            return DensityReport()

        numbers = self.NUMBER_PATTERN.findall(text)
        dates = self.DATE_PATTERN.findall(text)
        proper_nouns = self.PROPER_NOUN_PATTERN.findall(text)
        facts = self.FACT_PATTERN.findall(text)

        numbers_count = len(set(numbers))
        dates_count = len(set(dates))
        proper_nouns_count = len(set(proper_nouns))
        facts_count = len(facts)

        raw_score = (
            facts_count * 10 +
            numbers_count * 8 +
            proper_nouns_count * 5 +
            dates_count * 7
        )

        density_score = (raw_score / word_count) * 100
        passes_threshold = density_score >= self.min_density

        recommendations = []
        if not passes_threshold:
            recommendations.append(
                f"Density score {density_score:.1f} below threshold {self.min_density}"
            )
            if numbers_count < 3:
                recommendations.append("Add more specific numbers and metrics")

        return DensityReport(
            density_score=round(density_score, 1),
            facts_count=facts_count,
            numbers_count=numbers_count,
            proper_nouns_count=proper_nouns_count,
            dates_count=dates_count,
            passes_threshold=passes_threshold,
            recommendations=recommendations,
        )
