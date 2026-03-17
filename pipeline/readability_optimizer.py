"""
Readability Optimizer - Optimizes content for readability and engagement.

Analyzes and improves text readability using various metrics and guidelines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ReadabilityMetrics:
    """Readability metrics for text."""

    flesch_kincaid_grade: float = 0.0
    avg_sentence_length: float = 0.0
    avg_word_length: float = 0.0
    avg_syllables_per_word: float = 0.0
    paragraph_count: int = 0
    avg_paragraph_length: float = 0.0
    passive_voice_ratio: float = 0.0
    complex_word_ratio: float = 0.0


@dataclass(slots=True)
class ReadabilityReport:
    """Complete readability analysis report."""

    metrics: ReadabilityMetrics
    overall_score: float = 0.0
    grade_level: str = "unknown"
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    optimized_excerpts: list[dict[str, str]] = field(default_factory=list)


class ReadabilityOptimizer:
    """
    Analyzes and optimizes text readability.

    Features:
    - Multiple readability metrics
    - Issue detection
    - Optimization suggestions
    - Grade level estimation
    """

    # Russian stop words for syllable counting
    VOWELS_RU = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"
    VOWELS_EN = "aeiouyAEIOUY"

    # Grade level mappings
    GRADE_LEVELS = {
        (0, 6): "elementary",
        (6, 8): "middle_school",
        (8, 10): "high_school",
        (10, 12): "college",
        (12, 14): "graduate",
        (14, 100): "professional",
    }

    # Complex word patterns
    COMPLEX_PATTERNS = [
        r"\b\w{12,}\b",  # Very long words
        r"\b[а-яё]*tion\b",  # Technical suffixes
        r"\b\w*ization\b",
    ]

    def __init__(
        self,
        target_grade_level: str = "high_school",
        max_sentence_length: int = 25,
        max_paragraph_sentences: int = 5,
    ) -> None:
        self.target_grade = target_grade_level
        self.max_sentence_length = max_sentence_length
        self.max_paragraph_sentences = max_paragraph_sentences

    def analyze(self, text: str) -> ReadabilityReport:
        """
        Analyze text readability.

        Args:
            text: Text to analyze

        Returns:
            ReadabilityReport with findings
        """
        metrics = self._calculate_metrics(text)
        issues = self._detect_issues(text, metrics)
        suggestions = self._generate_suggestions(issues, metrics)
        overall_score = self._calculate_score(metrics, issues)
        grade_level = self._estimate_grade_level(metrics)

        return ReadabilityReport(
            metrics=metrics,
            overall_score=overall_score,
            grade_level=grade_level,
            issues=issues,
            suggestions=suggestions,
        )

    def _calculate_metrics(self, text: str) -> ReadabilityMetrics:
        """Calculate all readability metrics."""
        # Split into sentences
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        # Split into words
        words = re.findall(r"\b[а-яёa-z]+\b", text.lower())

        if not sentences or not words:
            return ReadabilityMetrics()

        # Calculate metrics
        total_words = len(words)
        total_sentences = len(sentences)
        total_syllables = sum(self._count_syllables(w) for w in words)

        avg_sentence_length = total_words / total_sentences
        avg_word_length = sum(len(w) for w in words) / total_words
        avg_syllables = total_syllables / total_words

        avg_paragraph_length = total_sentences / len(paragraphs) if paragraphs else 0

        # Calculate passive voice ratio (simplified)
        passive_count = self._count_passive_constructions(text)
        passive_ratio = passive_count / total_sentences if total_sentences > 0 else 0

        # Calculate complex word ratio
        complex_count = sum(1 for w in words if self._is_complex_word(w))
        complex_ratio = complex_count / total_words

        # Estimate Flesch-Kincaid (adapted for mixed content)
        fk_grade = self._estimate_fk_grade(
            avg_sentence_length,
            avg_syllables,
        )

        return ReadabilityMetrics(
            flesch_kincaid_grade=fk_grade,
            avg_sentence_length=avg_sentence_length,
            avg_word_length=avg_word_length,
            avg_syllables_per_word=avg_syllables,
            paragraph_count=len(paragraphs),
            avg_paragraph_length=avg_paragraph_length,
            passive_voice_ratio=passive_ratio,
            complex_word_ratio=complex_ratio,
        )

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word."""
        if not word:
            return 0

        # Check if Russian or English
        is_russian = any(c in "аеёиоуыэюя" for c in word.lower())

        if is_russian:
            # Russian: count vowel groups
            count = sum(1 for c in word if c.lower() in self.VOWELS_RU)
        else:
            # English syllable estimation
            count = sum(1 for c in word if c.lower() in self.VOWELS_EN)
            # Adjust for silent e
            if word.endswith("e"):
                count = max(1, count - 1)

        return max(1, count)

    def _count_passive_constructions(self, text: str) -> int:
        """Count passive voice constructions."""
        passive_patterns = [
            r"\bбыл[аи]?\s+\w+ен[а-я]*\b",  # Russian passive
            r"\bбыло\s+\w+ен[оа]\b",
            r"\bwas\s+\w+ed\b",  # English passive
            r"\bwere\s+\w+ed\b",
            r"\bis\s+being\s+\w+ed\b",
            r"\bhas\s+been\s+\w+ed\b",
        ]

        count = 0
        for pattern in passive_patterns:
            count += len(re.findall(pattern, text.lower()))

        return count

    def _is_complex_word(self, word: str) -> bool:
        """Check if word is complex."""
        if len(word) > 10:
            return True

        for pattern in self.COMPLEX_PATTERNS:
            if re.search(pattern, word, re.IGNORECASE):
                return True

        return False

    def _estimate_fk_grade(
        self,
        avg_sentence_length: float,
        avg_syllables: float,
    ) -> float:
        """Estimate Flesch-Kincaid grade level."""
        # Simplified formula
        return 0.39 * avg_sentence_length + 11.8 * avg_syllables - 15.59

    def _detect_issues(self, text: str, metrics: ReadabilityMetrics) -> list[str]:
        """Detect readability issues."""
        issues = []

        if metrics.avg_sentence_length > self.max_sentence_length:
            issues.append(
                f"Sentences too long (avg {metrics.avg_sentence_length:.1f} words, "
                f"max {self.max_sentence_length})"
            )

        if metrics.avg_paragraph_length > self.max_paragraph_sentences:
            issues.append(
                f"Paragraphs too long (avg {metrics.avg_paragraph_length:.1f} sentences, "
                f"max {self.max_paragraph_sentences})"
            )

        if metrics.passive_voice_ratio > 0.3:
            issues.append(f"Too much passive voice ({metrics.passive_voice_ratio:.0%})")

        if metrics.complex_word_ratio > 0.2:
            issues.append(f"Too many complex words ({metrics.complex_word_ratio:.0%})")

        if metrics.avg_word_length > 6:
            issues.append(
                f"Words too long on average ({metrics.avg_word_length:.1f} chars)"
            )

        # Check for wall of text
        sentences = re.split(r"[.!?]+", text)
        long_runs = 0
        current_run = 0

        for sentence in sentences:
            word_count = len(sentence.split())
            if word_count > 20:
                current_run += 1
                if current_run > 2:
                    long_runs += 1
            else:
                current_run = 0

        if long_runs > 0:
            issues.append(f"Found {long_runs} sections with consecutive long sentences")

        return issues

    def _generate_suggestions(
        self,
        issues: list[str],
        metrics: ReadabilityMetrics,
    ) -> list[str]:
        """Generate optimization suggestions."""
        suggestions = []

        for issue in issues:
            if "Sentences too long" in issue:
                suggestions.append(
                    "Break long sentences into shorter ones. "
                    "Aim for 15-20 words per sentence."
                )
            elif "Paragraphs too long" in issue:
                suggestions.append(
                    "Split long paragraphs. Each paragraph should cover one idea."
                )
            elif "passive voice" in issue:
                suggestions.append(
                    "Convert passive constructions to active voice. "
                    "Instead of 'was created', use 'created'."
                )
            elif "complex words" in issue:
                suggestions.append(
                    "Replace complex terms with simpler alternatives, "
                    "or explain them on first use."
                )
            elif "Words too long" in issue:
                suggestions.append("Use shorter, simpler words where possible.")
            elif "consecutive long" in issue:
                suggestions.append(
                    "Vary sentence length. Follow long sentences with short ones."
                )

        # General suggestions based on grade level
        if metrics.flesch_kincaid_grade > 12:
            suggestions.append(
                "Content may be too technical. Consider adding explanations "
                "for complex terms."
            )

        return suggestions

    def _calculate_score(
        self,
        metrics: ReadabilityMetrics,
        issues: list[str],
    ) -> float:
        """Calculate overall readability score."""
        score = 100.0

        # Deduct for issues
        score -= len(issues) * 10

        # Adjust for grade level match
        grade_penalty = abs(metrics.flesch_kincaid_grade - 10) * 2
        score -= grade_penalty

        # Adjust for passive voice
        score -= metrics.passive_voice_ratio * 20

        return max(0.0, min(100.0, score))

    def _estimate_grade_level(self, metrics: ReadabilityMetrics) -> str:
        """Estimate reading grade level."""
        grade = metrics.flesch_kincaid_grade

        for (low, high), level in self.GRADE_LEVELS.items():
            if low <= grade < high:
                return level

        return "professional"

    def optimize_sentence(self, sentence: str) -> str:
        """Optimize a single sentence for readability."""
        # Remove redundant words
        optimizations = [
            (r"\bдля того чтобы\b", "чтобы"),
            (r"\bдля того, чтобы\b", "чтобы"),
            (r"\bпо причине того, что\b", "потому что"),
            (r"\bin order to\b", "to"),
            (r"\bdue to the fact that\b", "because"),
            (r"\bat this point in time\b", "now"),
            (r"\bin the event that\b", "if"),
        ]

        optimized = sentence
        for pattern, replacement in optimizations:
            optimized = re.sub(pattern, replacement, optimized, flags=re.IGNORECASE)

        return optimized


# Configuration schema
READABILITY_CONFIG_SCHEMA = {
    "readability": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable readability optimization",
        },
        "target_grade_level": {
            "type": "str",
            "default": "high_school",
            "description": "Target reading grade level",
        },
        "max_sentence_length": {
            "type": "int",
            "default": 25,
            "description": "Maximum recommended sentence length",
        },
        "min_readability_score": {
            "type": "int",
            "default": 60,
            "description": "Minimum readability score required",
        },
    }
}
