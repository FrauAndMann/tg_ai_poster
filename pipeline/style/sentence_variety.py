"""Sentence variety analyzer for evaluating text rhythm and structure."""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SentenceVarietyReport:
    """Result of sentence variety analysis."""

    variety_score: float = 0.0  # 0-100 scale
    sentence_count: int = 0
    short_sentence_count: int = 0
    long_sentence_count: int = 0
    repetitive_patterns: list[str] = field(default_factory=list)
    length_distribution: dict[str, int] = field(default_factory=dict)
    rhythm_issues: list[str] = field(default_factory=list)
    passes_threshold: bool = True
    suggestions: list[str] = field(default_factory=list)


class SentenceVarietyAnalyzer:
    """
    Analyzes sentence variety and rhythm in text.

    Scoring criteria (0-100):
    - Sentence length distribution (0-40 points)
    - Absence of repetitive patterns (0-30 points)
    - Good rhythm and flow (0-30 points)

    A score of 70+ is considered good variety.
    """

    # Thresholds for sentence classification (in words)
    SHORT_SENTENCE_THRESHOLD = 8
    LONG_SENTENCE_THRESHOLD = 25
    REPETITION_THRESHOLD = 3  # Same pattern appears N times

    # Ideal distribution percentages
    IDEAL_SHORT_RATIO = 0.30  # 30% short sentences
    IDEAL_LONG_RATIO = 0.20  # 20% long sentences
    IDEAL_MEDIUM_RATIO = 0.50  # 50% medium sentences

    def __init__(self, min_score: float = 70.0) -> None:
        """
        Initialize the sentence variety analyzer.

        Args:
            min_score: Minimum acceptable variety score (0-100)
        """
        self.min_score = min_score

    def analyze(self, text: str) -> SentenceVarietyReport:
        """
        Analyze sentence variety in the given text.

        Args:
            text: Text to analyze for sentence variety

        Returns:
            SentenceVarietyReport with analysis results
        """
        if not text or not text.strip():
            return self._empty_report()

        sentences = self._split_sentences(text)

        if not sentences:
            return self._empty_report()

        sentence_lengths = [len(s.split()) for s in sentences]
        sentence_count = len(sentences)

        # Classify sentences by length
        short_count = sum(1 for l in sentence_lengths if l <= self.SHORT_SENTENCE_THRESHOLD)
        long_count = sum(1 for l in sentence_lengths if l >= self.LONG_SENTENCE_THRESHOLD)
        medium_count = sentence_count - short_count - long_count

        # Build length distribution
        length_distribution = {
            "short": short_count,
            "medium": medium_count,
            "long": long_count,
        }

        # Detect repetitive patterns
        repetitive_patterns = self._detect_repetitive_patterns(sentences)

        # Detect rhythm issues
        rhythm_issues = self._detect_rhythm_issues(sentence_lengths)

        # Calculate variety score (0-100)
        variety_score = self._calculate_variety_score(
            sentence_count=sentence_count,
            short_count=short_count,
            long_count=long_count,
            medium_count=medium_count,
            repetitive_patterns=repetitive_patterns,
            rhythm_issues=rhythm_issues,
            sentence_lengths=sentence_lengths,
        )

        # Generate suggestions
        suggestions = self._generate_suggestions(
            short_count=short_count,
            long_count=long_count,
            medium_count=medium_count,
            sentence_count=sentence_count,
            repetitive_patterns=repetitive_patterns,
            rhythm_issues=rhythm_issues,
        )

        passes_threshold = variety_score >= self.min_score

        return SentenceVarietyReport(
            variety_score=round(variety_score, 1),
            sentence_count=sentence_count,
            short_sentence_count=short_count,
            long_sentence_count=long_count,
            repetitive_patterns=repetitive_patterns,
            length_distribution=length_distribution,
            rhythm_issues=rhythm_issues,
            passes_threshold=passes_threshold,
            suggestions=suggestions,
        )

    def score(self, text: str) -> float:
        """
        Get the variety score for text (0-100).

        Args:
            text: Text to score

        Returns:
            Variety score from 0 to 100
        """
        report = self.analyze(text)
        return report.variety_score

    def _empty_report(self) -> SentenceVarietyReport:
        """Return an empty report for empty text."""
        return SentenceVarietyReport(
            variety_score=0.0,
            sentence_count=0,
            short_sentence_count=0,
            long_sentence_count=0,
            repetitive_patterns=[],
            length_distribution={"short": 0, "medium": 0, "long": 0},
            rhythm_issues=["Text is empty"],
            passes_threshold=False,
            suggestions=["Provide text to analyze"],
        )

    def _split_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences.

        Handles both Russian and English sentence delimiters.
        """
        # Pattern for sentence splitting:
        # - Splits on . ! ? followed by whitespace
        # - Works with or without capital letter after (more permissive)
        pattern = r'(?<=[.!?])\s+'

        # Split and clean sentences
        raw_sentences = re.split(pattern, text.strip())

        sentences = []
        for s in raw_sentences:
            s = s.strip()
            # Remove trailing punctuation for cleaner analysis
            s = s.rstrip('.!?')
            if s and len(s.split()) >= 2:  # Minimum 2 words to be a sentence
                sentences.append(s)

        return sentences

    def _detect_repetitive_patterns(self, sentences: list[str]) -> list[str]:
        """
        Detect repetitive sentence structures or patterns.

        Returns list of detected repetitive patterns.
        """
        patterns_found = []

        # Check for repetitive sentence beginnings at different granularities
        for num_words in [2, 3]:  # Check first 2 words and first 3 words
            beginnings = []
            for s in sentences:
                words = s.split()[:num_words]
                if len(words) >= num_words:
                    beginnings.append(" ".join(words).lower())

            # Count occurrences of each beginning pattern
            pattern_counts: dict[str, int] = {}
            for b in beginnings:
                # Normalize pattern (remove punctuation, lowercase)
                normalized = re.sub(r'[^\w\s]', '', b).strip()
                if normalized:
                    pattern_counts[normalized] = pattern_counts.get(normalized, 0) + 1

            # Find patterns that repeat too often (threshold = 3)
            for pattern, count in pattern_counts.items():
                if count >= self.REPETITION_THRESHOLD:
                    patterns_found.append(f"Repetitive start: '{pattern}...' (appears {count} times)")
                    break  # Only report once per granularity

        # Check for repetitive sentence structures (same word count patterns)
        word_counts = [len(s.split()) for s in sentences]
        if len(word_counts) >= 4:
            # Check for 4+ consecutive sentences with same length (+/- 2 words)
            for i in range(len(word_counts) - 3):
                segment = word_counts[i:i+4]
                if max(segment) - min(segment) <= 2:
                    patterns_found.append(
                        f"Monotonous length: 4+ sentences with {segment[0]} (+/- 2) words"
                    )
                    break

        return patterns_found

    def _detect_rhythm_issues(self, sentence_lengths: list[int]) -> list[str]:
        """
        Detect rhythm and flow issues in sentence lengths.

        Returns list of detected rhythm issues.
        """
        issues = []

        if len(sentence_lengths) < 3:
            return issues

        # Check for all sentences being the same length
        if len(set(sentence_lengths)) == 1:
            issues.append(f"All sentences have the same length ({sentence_lengths[0]} words)")

        # Check for low variance (monotonous rhythm)
        if len(sentence_lengths) >= 3:
            try:
                stdev = statistics.stdev(sentence_lengths)
                mean = statistics.mean(sentence_lengths)
                # Coefficient of variation
                cv = (stdev / mean) * 100 if mean > 0 else 0

                if cv < 15:
                    issues.append("Low length variance: sentences are too uniform")
            except statistics.StatisticsError:
                pass

        # Check for abrupt length changes (poor flow)
        for i in range(len(sentence_lengths) - 1):
            diff = abs(sentence_lengths[i+1] - sentence_lengths[i])
            if diff > 20:  # Very abrupt change
                issues.append(
                    f"Abrupt length change: {sentence_lengths[i]} to {sentence_lengths[i+1]} words"
                )
                break  # Only report once

        # Check for run-on sentences (consecutive very long sentences - 25+ words)
        consecutive_long = 0
        for length in sentence_lengths:
            if length >= self.LONG_SENTENCE_THRESHOLD:
                consecutive_long += 1
                if consecutive_long >= 2:
                    issues.append(f"Multiple consecutive very long sentences ({self.LONG_SENTENCE_THRESHOLD}+ words)")
                    break
            else:
                consecutive_long = 0

        return issues

    def _calculate_variety_score(
        self,
        sentence_count: int,
        short_count: int,
        long_count: int,
        medium_count: int,
        repetitive_patterns: list[str],
        rhythm_issues: list[str],
        sentence_lengths: list[int],
    ) -> float:
        """
        Calculate the overall variety score (0-100).

        Components:
        - Length distribution (0-40 points)
        - Pattern variety (0-30 points)
        - Rhythm quality (0-30 points)
        """
        score = 0.0

        # 1. Length distribution score (0-40 points)
        if sentence_count > 0:
            short_ratio = short_count / sentence_count
            long_ratio = long_count / sentence_count
            medium_ratio = medium_count / sentence_count

            # Calculate how close to ideal distribution
            short_score = max(0, 10 - abs(short_ratio - self.IDEAL_SHORT_RATIO) * 30)
            long_score = max(0, 10 - abs(long_ratio - self.IDEAL_LONG_RATIO) * 30)
            medium_score = max(0, 20 - abs(medium_ratio - self.IDEAL_MEDIUM_RATIO) * 30)

            length_score = short_score + long_score + medium_score
            score += length_score

        # 2. Pattern variety score (0-30 points)
        # Start with full points, deduct for repetitive patterns
        pattern_score = 30.0
        for pattern in repetitive_patterns:
            pattern_score -= 10  # -10 for each repetitive pattern
        score += max(0, pattern_score)

        # 3. Rhythm quality score (0-30 points)
        # Start with full points, deduct for rhythm issues
        rhythm_score = 30.0
        for issue in rhythm_issues:
            rhythm_score -= 8  # -8 for each rhythm issue
        score += max(0, rhythm_score)

        return min(100.0, max(0.0, score))

    def _generate_suggestions(
        self,
        short_count: int,
        long_count: int,
        medium_count: int,
        sentence_count: int,
        repetitive_patterns: list[str],
        rhythm_issues: list[str],
    ) -> list[str]:
        """Generate improvement suggestions based on analysis."""
        suggestions = []

        if sentence_count == 0:
            return ["Add more content to analyze"]

        # Length distribution suggestions
        short_ratio = short_count / sentence_count
        long_ratio = long_count / sentence_count
        medium_ratio = medium_count / sentence_count

        if short_ratio > 0.5:
            suggestions.append(
                f"Too many short sentences ({short_ratio:.0%}). "
                "Combine some for better flow."
            )
        elif short_ratio < 0.1:
            suggestions.append(
                "Add some short, punchy sentences for emphasis."
            )

        if long_ratio > 0.4:
            suggestions.append(
                f"Too many long sentences ({long_ratio:.0%}). "
                "Break some into shorter ones."
            )
        elif long_ratio < 0.05 and sentence_count > 5:
            suggestions.append(
                "Consider adding a longer, detailed sentence for depth."
            )

        if medium_ratio > 0.7:
            suggestions.append(
                "Sentences are too uniform in length. Vary short, medium, and long."
            )

        # Repetitive pattern suggestions
        for pattern in repetitive_patterns:
            if "Repetitive start" in pattern:
                suggestions.append(
                    "Vary your sentence openings to maintain reader interest."
                )
            elif "Monotonous length" in pattern:
                suggestions.append(
                    "Mix up sentence lengths to create better rhythm."
                )

        # Rhythm suggestions
        for issue in rhythm_issues:
            if "same length" in issue:
                suggestions.append(
                    "Vary sentence lengths significantly for better engagement."
                )
            elif "Low length variance" in issue:
                suggestions.append(
                    "Create more contrast between short and long sentences."
                )
            elif "Abrupt length change" in issue:
                suggestions.append(
                    "Smooth the transition between very different sentence lengths."
                )
            elif "consecutive very long" in issue:
                suggestions.append(
                    "Break up long sentences or add short ones between them."
                )

        # Deduplicate suggestions
        return list(dict.fromkeys(suggestions))
