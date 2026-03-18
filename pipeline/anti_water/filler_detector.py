"""Filler words detector for measuring 'water' content."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FillerReport:
    """Result of filler detection."""

    filler_count: int = 0
    water_percentage: float = 0.0
    filler_list: list[str] = field(default_factory=list)
    passes_threshold: bool = True
    recommendations: list[str] = field(default_factory=list)


class FillerDetector:
    """
    Detects filler words and calculates water percentage.

    Uses dictionaries of Russian/English filler phrases and
    calculates the percentage of "water" content.
    """

    # Built-in filler patterns
    DEFAULT_FILLER_PATTERNS = [
        # Russian fillers
        r"\bстоит\s+отметить\b",
        r"\bнельзя\s+не\s+сказать\b",
        r"\bбезусловно\b",
        r"\bнесомненно\b",
        r"\bкрайне\s+\w+\b",
        r"\bвесьма\s+\w+\b",
        r"\bочень\s+\w+\b",
        r"\bданный\s+\w+\b",
        r"\bявляется\s+\w+\b",
        r"\bв\s+современном\s+мире\b",
        # English fillers
        r"\bit\s+is\s+worth\s+noting\b",
        r"\bneedless\s+to\s+say\b",
        r"\bobviously\b",
        r"\bvery\s+\w+\b",
        r"\bextremely\s+\w+\b",
        r"\bin\s+today'?s?\s+world\b",
        r"\bgame-changing\b",
        r"\brevolutionary\b",
    ]

    def __init__(
        self,
        max_water_percentage: float = 15.0,
    ) -> None:
        self.max_water_percentage = max_water_percentage
        self._patterns: list[re.Pattern] = [
            re.compile(p, re.IGNORECASE) for p in self.DEFAULT_FILLER_PATTERNS
        ]

    def detect(self, text: str) -> FillerReport:
        """
        Detect filler words and calculate water percentage.

        Args:
            text: Text to analyze

        Returns:
            FillerReport with findings
        """
        filler_list = []
        total_matches = 0

        for pattern in self._patterns:
            for match in pattern.finditer(text):
                filler_list.append(match.group())
                total_matches += 1

        # Calculate water percentage
        words = text.split()
        word_count = len(words)

        # Count filler words (each match can be multiple words)
        filler_word_count = sum(len(f.split()) for f in filler_list)

        water_percentage = (
            (filler_word_count / word_count * 100) if word_count > 0 else 0
        )

        passes_threshold = water_percentage <= self.max_water_percentage

        # Generate recommendations
        recommendations = []
        if not passes_threshold:
            recommendations.append(
                f"Water content {water_percentage:.1f}% exceeds "
                f"threshold {self.max_water_percentage}%"
            )
            recommendations.append(
                f"Remove or rephrase: {', '.join(filler_list[:5])}"
            )

        return FillerReport(
            filler_count=total_matches,
            water_percentage=round(water_percentage, 1),
            filler_list=filler_list,
            passes_threshold=passes_threshold,
            recommendations=recommendations,
        )
