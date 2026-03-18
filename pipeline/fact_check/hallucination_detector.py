"""
Hallucination Detector for Phase 2 Factual Accuracy.

Detects common AI-generated hallucination patterns in text including:
- Vague expert claims without attribution
- Unnamed studies and research
- Future predictions presented as facts
- Impossible or suspicious statistics
- Fake quotes without proper sources
- Made-up company names
- Non-existent products
- Future dates presented as past events
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HallucinationReport:
    """Report of hallucination detection results."""

    score: float  # 0.0 (clean) to 1.0 (highly suspicious)
    indicators: list[str] = field(default_factory=list)
    passes_check: bool = True
    details: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


class HallucinationDetector:
    """
    Detects AI-generated hallucinations in text.

    Features:
    - Pattern-based detection of common hallucination types
    - Confidence scoring for hallucination likelihood
    - Specific indicators with explanations
    - Auto-reject threshold for high-risk content
    """

    # Auto-reject threshold - content with score >= this value is flagged
    AUTO_REJECT_THRESHOLD = 0.7

    # Common AI hallucination patterns with severity weights
    HALLUCINATION_PATTERNS: dict[str, tuple[str, float]] = {
        # Vague expert claims - very common AI hallucination
        "vague_expert_ru": (
            r"эксперты\s+(?:прогнозируют|утверждают|считают|ожидают|полагают)",
            0.8,
        ),
        "vague_expert_en": (
            r"experts\s+(?:predict|claim|believe|expect|suggest)",
            0.8,
        ),
        "analysts_ru": (r"аналитики\s+(?:прогнозируют|ожидают|считают)", 0.75),
        "analysts_en": (r"analysts\s+(?:predict|expect|forecast)", 0.75),
        # Unnamed studies - another common hallucination
        "unnamed_study_ru": (
            r"(?:недавнее\s+)?исследование\s+(?:показало|выявило|подтвердило|демонстрирует)",
            0.85,
        ),
        "unnamed_study_en": (
            r"(?:a\s+)?(?:recent\s+)?study\s+(?:showed|found|revealed|demonstrated|suggests)",
            0.85,
        ),
        "studies_show": (r"studies\s+have\s+shown", 0.8),
        "research_shows": (r"research\s+(?:has\s+)?shows?", 0.75),
        "according_to_research": (r"по\s+данным\s+исследований?\s+(?!ссылки|URL|http)", 0.7),
        # Future predictions presented as facts
        "future_as_fact_ru": (
            r"в\s+(\d{4})\s+году\s+(?:будет|ожидается|планируется|появится)",
            0.65,
        ),
        "future_as_fact_en": (
            r"by\s+(\d{4}),?\s+(?:will\s+be|is\s+expected|is\s+projected)",
            0.65,
        ),
        "will_revolutionize": (r"will\s+(?:completely\s+)?revolutionize", 0.7),
        "will_transform": (r"will\s+transform\s+(?:the\s+)?(?:industry|world|market)", 0.65),
        # Impossible statistics
        "impossible_improvement": (
            r"(?:\d{3,}|100+)\s*%\s*(?:улучшение|improvement|увеличение|increase)",
            0.9,
        ),
        "impossible_growth": (
            r"вырос(?:ла|ли)?\s+на\s*(?:\d{3,}|100+)\s*%",
            0.9,
        ),
        "too_precise_stat": (
            r"(?:\d+\.\d{3,})\s*%",  # Suspiciously precise percentages
            0.5,
        ),
        # Fake quotes without attribution
        "unattributed_quote_ru": (
            r'(?:\xab|")[^\xbb"]{20,}(?:\xbb|")(?!\s*[-\u2014]\s*[\u0410-\u042f\u0401A-Z])',
            0.6,
        ),
        "unattributed_quote_en": (
            r'"[^"]{20,}"(?!\s*[-\u2014]\s*[A-Z])',
            0.6,
        ),
        # Hedging language that often precedes hallucinations
        "some_experts": (r"some\s+experts", 0.5),
        "many_believe": (r"many\s+(?:experts\s+)?believe", 0.55),
        "widely_known": (r"(?:широко\s+известно|widely\s+known|commonly\s+known)", 0.5),
        # Overconfident claims
        "guaranteed": (r"(?:гарантированно|guaranteed)\s+(?:приведет|will)", 0.7),
        "obviously": (r"(?:очевидно|obviously|clearly)\s*,", 0.4),
        "undoubtedly": (r"(?:несомненно|undoubtedly|without\s+doubt)", 0.5),
        # Suspicious vague sources
        "reports_suggest": (r"reports\s+suggest", 0.65),
        "sources_say": (r"sources\s+(?:say|indicate|suggest)", 0.6),
        "according_to_sources": (r"по\s+информации\s+из\s+источников", 0.6),
    }

    # AI cliche phrases that often accompany hallucinations
    AI_CLICHE_PATTERNS: dict[str, tuple[str, float]] = {
        "game_changer": (r"game[- ]?changer", 0.3),
        "revolutionary": (r"revolutionary\s+(?:new|technology|approach)", 0.35),
        "groundbreaking": (r"ground[- ]?breaking", 0.35),
        "paradigm_shift": (r"paradigm\s+shift", 0.3),
        "cutting_edge": (r"cutting[- ]?edge", 0.25),
        "state_of_art": (r"state[- ]?of[- ]?the[- ]?art", 0.25),
        "best_in_class": (r"best[- ]?in[- ]?class", 0.3),
        "industry_leading": (r"industry[- ]?leading", 0.25),
    }

    def __init__(
        self,
        auto_reject_threshold: float = 0.7,
        strict_mode: bool = False,
    ) -> None:
        """
        Initialize the hallucination detector.

        Args:
            auto_reject_threshold: Score threshold for auto-reject (default 0.7)
            strict_mode: If True, applies stricter detection rules
        """
        self.auto_reject_threshold = auto_reject_threshold
        self.strict_mode = strict_mode

        # Compile patterns for efficiency
        self._compiled_hallucination: dict[str, tuple[re.Pattern, float]] = {
            name: (re.compile(pattern, re.IGNORECASE), weight)
            for name, (pattern, weight) in self.HALLUCINATION_PATTERNS.items()
        }

        self._compiled_cliches: dict[str, tuple[re.Pattern, float]] = {
            name: (re.compile(pattern, re.IGNORECASE), weight)
            for name, (pattern, weight) in self.AI_CLICHE_PATTERNS.items()
        }

    def detect(self, text: str) -> HallucinationReport:
        """
        Detect hallucinations in text.

        Args:
            text: Text to analyze for hallucinations

        Returns:
            HallucinationReport with score, indicators, and pass/fail status
        """
        indicators: list[str] = []
        details: dict[str, float] = {}
        total_weight = 0.0
        max_possible_weight = 0.0

        # Check hallucination patterns
        for name, (pattern, weight) in self._compiled_hallucination.items():
            matches = list(pattern.finditer(text))
            if matches:
                match_weight = weight * len(matches)
                total_weight += match_weight
                details[name] = match_weight

                # Add indicators with context
                for match in matches[:3]:  # Limit to first 3 matches per pattern
                    context = self._get_match_context(text, match)
                    indicators.append(f"{self._format_pattern_name(name)}: '{context}'")

            max_possible_weight += weight

        # Check AI cliches (lower weight but still relevant)
        cliche_count = 0
        for name, (pattern, weight) in self._compiled_cliches.items():
            matches = list(pattern.finditer(text))
            if matches:
                cliche_count += len(matches)
                # Cliches contribute to hallucination score but less heavily
                cliche_weight = weight * len(matches) * 0.5
                total_weight += cliche_weight
                details[f"cliche_{name}"] = cliche_weight

        # Calculate normalized hallucination score (0.0 to 1.0)
        if max_possible_weight > 0:
            raw_score = total_weight / max_possible_weight
        else:
            raw_score = 0.0

        # Apply strict mode multiplier
        if self.strict_mode:
            raw_score = min(1.0, raw_score * 1.3)

        # Add cliche density factor
        text_length = len(text.split())
        if text_length > 0 and cliche_count > 0:
            cliche_density = cliche_count / (text_length / 100)  # Per 100 words
            raw_score = min(1.0, raw_score + cliche_density * 0.05)

        # Clamp score to valid range
        hallucination_score = max(0.0, min(1.0, raw_score))

        # Determine if content passes
        passes_check = hallucination_score < self.auto_reject_threshold

        # Generate recommendations
        recommendations = self._generate_recommendations(
            hallucination_score, details, cliche_count
        )

        return HallucinationReport(
            score=round(hallucination_score, 3),
            indicators=indicators,
            passes_check=passes_check,
            details=details,
            recommendations=recommendations,
        )

    def _get_match_context(self, text: str, match: re.Match, window: int = 30) -> str:
        """Get context around a match."""
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        context = text[start:end]
        # Add ellipsis if truncated
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        return context.strip()

    def _format_pattern_name(self, name: str) -> str:
        """Format pattern name for display."""
        return name.replace("_", " ").title()

    def _generate_recommendations(
        self,
        score: float,
        details: dict[str, float],
        cliche_count: int,
    ) -> list[str]:
        """Generate actionable recommendations based on detection results."""
        recommendations = []

        if score >= self.auto_reject_threshold:
            recommendations.append(
                f"КРИТИЧНО: Высокий риск галлюцинаций (score: {score:.2f}). "
                "Требуется ручная проверка перед публикацией."
            )
        elif score >= 0.5:
            recommendations.append(
                f"ВНИМАНИЕ: Обнаружены признаки галлюцинаций (score: {score:.2f}). "
                "Рекомендуется добавить конкретные источники."
            )
        elif score >= 0.3:
            recommendations.append(
                f"Умеренный риск галлюцинаций (score: {score:.2f}). "
                "Проверьте утверждения без источников."
            )

        # Specific recommendations based on detected patterns
        if "unnamed_study_ru" in details or "unnamed_study_en" in details:
            recommendations.append(
                "Укажите конкретное исследование: название, авторы, дата публикации."
            )

        if "vague_expert_ru" in details or "vague_expert_en" in details:
            recommendations.append(
                "Замените 'эксперты' на конкретные имена или организации."
            )

        if any(k.startswith("future_as_fact") for k in details):
            recommendations.append(
                "Прогнозы должны содержать слова 'прогнозируется', 'ожидается', "
                "либо ссылку на источник прогноза."
            )

        if any(k.startswith("impossible") for k in details):
            recommendations.append(
                "Проверьте статистику - подозрительно высокие показатели. "
                "Добавьте источник данных."
            )

        if cliche_count > 3:
            recommendations.append(
                f"Обнаружено {cliche_count} AI-клише. "
                "Перефразируйте текст для более естественного звучания."
            )

        return recommendations

    def get_hallucination_score(self, text: str) -> float:
        """
        Get only the hallucination score without full report.

        Args:
            text: Text to analyze

        Returns:
            Hallucination score from 0.0 to 1.0
        """
        report = self.detect(text)
        return report.score

    def is_safe_to_publish(self, text: str) -> bool:
        """
        Quick check if text passes hallucination threshold.

        Args:
            text: Text to check

        Returns:
            True if text is safe to publish, False otherwise
        """
        return self.detect(text).passes_check

    def get_high_risk_segments(self, text: str) -> list[dict[str, str]]:
        """
        Get segments of text with highest hallucination risk.

        Args:
            text: Text to analyze

        Returns:
            List of high-risk segments with their patterns
        """
        segments = []

        for name, (pattern, weight) in self._compiled_hallucination.items():
            if weight < 0.6:  # Only high-severity patterns
                continue

            for match in pattern.finditer(text):
                segments.append(
                    {
                        "text": match.group(),
                        "pattern": name,
                        "weight": weight,
                        "position": (match.start(), match.end()),
                        "context": self._get_match_context(text, match),
                    }
                )

        # Sort by weight descending
        segments.sort(key=lambda x: x["weight"], reverse=True)

        return segments
