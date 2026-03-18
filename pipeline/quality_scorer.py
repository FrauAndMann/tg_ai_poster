"""Unified quality scorer for content evaluation."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logger import get_logger
from pipeline.anti_water import FillerDetector, DensityScorer

logger = get_logger(__name__)


@dataclass
class QualityScoreReport:
    """Comprehensive quality score report."""

    total_score: float = 0.0
    passes_threshold: bool = True
    breakdown: dict[str, float] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def grade(self) -> str:
        """Get letter grade for score.

        Returns:
            "Excellent" (90+), "Good" (80-89), "Acceptable" (70-79), "Reject" (<70)
        """
        if self.total_score >= 90:
            return "Excellent"
        elif self.total_score >= 80:
            return "Good"
        elif self.total_score >= 70:
            return "Acceptable"
        else:
            return "Reject"


class QualityScorer:
    """
    Unified quality scoring system.

    Combines multiple quality checks into a single 0-100 score:
    - Density score (20%)
    - Water penalty (20%)
    - Structure score (20%)
    - Factual accuracy (25%)
    - Style score (15%)
    """

    # Required structure markers
    REQUIRED_MARKERS = [
        ("\U0001F50D", "Key Facts"),  # 🔍
        ("\U0001F4A1", "TLDR"),       # 💡
    ]

    def __init__(self, pass_threshold: float = 70.0) -> None:
        """
        Initialize the quality scorer.

        Args:
            pass_threshold: Minimum score to pass (default: 70.0)
        """
        self.pass_threshold = pass_threshold
        self._filler_detector = FillerDetector()
        self._density_scorer = DensityScorer()

    def score(self, text: str) -> QualityScoreReport:
        """
        Calculate comprehensive quality score.

        Args:
            text: Text content to evaluate

        Returns:
            QualityScoreReport with total score, breakdown, and recommendations
        """
        breakdown: dict[str, float] = {}
        issues: list[str] = []
        recommendations: list[str] = []

        # 1. Density score (weighted 20%)
        density_report = self._density_scorer.score(text)
        # Normalize density score to 0-100 (density scores are typically low)
        density_normalized = min(100.0, density_report.density_score * 5)
        breakdown["density"] = density_normalized

        if not density_report.passes_threshold:
            issues.append("Low information density")
            recommendations.extend(density_report.recommendations)

        # 2. Water penalty (weighted 20%)
        filler_report = self._filler_detector.detect(text)
        # Water score: start at 100, penalize for water percentage
        # Each percentage point of water reduces score by 3 points
        water_score = max(0.0, 100.0 - filler_report.water_percentage * 3)
        breakdown["water_penalty"] = water_score

        if not filler_report.passes_threshold:
            issues.append(f"High water content: {filler_report.water_percentage}%")
            recommendations.extend(filler_report.recommendations)

        # 3. Structure score (20%)
        structure_score = 100.0
        for marker, name in self.REQUIRED_MARKERS:
            if marker not in text:
                structure_score -= 25
        breakdown["structure"] = max(0.0, structure_score)

        if structure_score < 100:
            missing = [name for marker, name in self.REQUIRED_MARKERS if marker not in text]
            if missing:
                issues.append(f"Missing structure markers: {', '.join(missing)}")

        # 4. Factual accuracy (25%)
        factual_score = self._calculate_factual_score(text)
        breakdown["factual_accuracy"] = factual_score

        # 5. Style score (15%)
        style_score = self._calculate_style_score(text)
        breakdown["style"] = style_score

        # Calculate weighted total
        total_score = (
            breakdown["density"] * 0.20 +
            breakdown["water_penalty"] * 0.20 +
            breakdown["structure"] * 0.20 +
            breakdown["factual_accuracy"] * 0.25 +
            breakdown["style"] * 0.15
        )

        passes_threshold = total_score >= self.pass_threshold

        # Add general recommendations if not passing
        if not passes_threshold:
            if breakdown["density"] < 50:
                recommendations.append("Add more specific facts, numbers, and dates")
            if breakdown["water_penalty"] < 70:
                recommendations.append("Remove filler words and vague phrases")
            if breakdown["structure"] < 75:
                recommendations.append("Add required structure markers (🔍, 💡)")

        return QualityScoreReport(
            total_score=round(total_score, 1),
            passes_threshold=passes_threshold,
            breakdown=breakdown,
            issues=issues,
            recommendations=recommendations[:5],  # Limit to top 5 recommendations
        )

    def _calculate_factual_score(self, text: str) -> float:
        """
        Calculate factual accuracy score.

        Based on presence of:
        - Numbers (dates, metrics, amounts)
        - Proper nouns (companies, products)
        - Factual indicators
        """
        score = 70.0  # Base score

        # Bonus for numbers
        if re.search(r'\d+', text):
            score += 5
        # Bonus for year (4-digit number)
        if re.search(r'\d{4}', text):
            score += 5
        # Bonus for percentage
        if re.search(r'\d+%', text):
            score += 5
        # Bonus for currency
        if re.search(r'[$€₽]', text):
            score += 5
        # Bonus for multiple numbers (indicating data)
        numbers = re.findall(r'\d+', text)
        if len(numbers) >= 3:
            score += 5
        # Bonus for proper nouns (tech companies)
        if re.search(r'\b(?:OpenAI|Google|Microsoft|Apple|Meta|Amazon)\b', text, re.IGNORECASE):
            score += 5

        return min(100.0, score)

    def _calculate_style_score(self, text: str) -> float:
        """
        Calculate style score.

        Based on:
        - Text length (not too short, not too long)
        - Sentence variety
        - Active voice usage
        """
        score = 80.0  # Base score

        word_count = len(text.split())

        # Penalize very short text
        if word_count < 20:
            score -= 20
        elif word_count < 50:
            score -= 10
        # Bonus for reasonable length
        elif 100 <= word_count <= 500:
            score += 10

        # Bonus for bullet points (structured content)
        if '\u2022' in text or '-' in text:  # • or -
            score += 5

        # Check for passive voice indicators (Russian and English)
        passive_patterns = [
            r'\bбыл[аои]?\b',  # Russian: был, была, было, были
            r'\bбыть\b',       # Russian: быть
            r'\bwas\b',        # English: was
            r'\bwere\b',       # English: were
            r'\bbeen\b',       # English: been
        ]

        passive_count = sum(
            len(re.findall(p, text, re.IGNORECASE))
            for p in passive_patterns
        )

        if passive_count > 2:
            score -= 5

        return min(100.0, max(0.0, score))
