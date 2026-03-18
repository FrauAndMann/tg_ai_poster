"""Paragraph impact checker for detecting redundant content."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Set

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ParagraphReport:
    """Result of paragraph impact check."""

    paragraph_count: int = 0
    redundant_pairs: list[tuple[int, int]] = field(default_factory=list)
    passes_check: bool = True
    recommendations: list[str] = field(default_factory=list)


class ParagraphChecker:
    """
    Checks that each paragraph adds unique value.

    Compares key claims between paragraphs using word overlap similarity.
    Detects redundant paragraphs when similarity exceeds threshold.
    """

    # Stop words to filter out for better comparison
    STOP_WORDS: Set[str] = {
        # Russian stop words
        "и", "в", "на", "с", "то", "что", "это", "как", "по", "из",
        "за", "от", "до", "при", "о", "об", "но", "а", "или", "же",
        "был", "была", "были", "было", "быть", "есть", "который",
        "которая", "которые", "которого", "для", "не", "так", "также",
        # English stop words
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall",
        "can", "need", "dare", "ought", "used", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into",
        "through", "during", "before", "after", "above", "below",
        "between", "under", "again", "further", "then", "once",
        "this", "that", "these", "those", "and", "but", "or",
        "because", "if", "while", "although", "though", "so",
        "than", "too", "very", "just", "also", "only", "own",
    }

    def __init__(self, similarity_threshold: float = 0.7) -> None:
        """
        Initialize ParagraphChecker.

        Args:
            similarity_threshold: Maximum allowed similarity between paragraphs (0.0-1.0)
        """
        self.similarity_threshold = similarity_threshold

    def check(self, text: str) -> ParagraphReport:
        """
        Check paragraphs for redundancy.

        Args:
            text: Text to analyze (paragraphs separated by blank lines)

        Returns:
            ParagraphReport with findings
        """
        # Split text into paragraphs (by blank lines)
        paragraphs = self._extract_paragraphs(text)

        if len(paragraphs) < 2:
            return ParagraphReport(paragraph_count=len(paragraphs))

        redundant_pairs = []

        # Compare each pair of paragraphs
        for i in range(len(paragraphs)):
            for j in range(i + 1, len(paragraphs)):
                similarity = self._calculate_similarity(
                    paragraphs[i], paragraphs[j]
                )
                if similarity > self.similarity_threshold:
                    redundant_pairs.append((i, j))
                    logger.debug(
                        f"Redundant paragraphs found: {i} and {j} "
                        f"(similarity: {similarity:.2f})"
                    )

        passes_check = len(redundant_pairs) == 0

        recommendations = []
        if not passes_check:
            recommendations.append(
                f"Found {len(redundant_pairs)} redundant paragraph pair(s). "
                f"Consider merging or removing similar content."
            )
            for i, j in redundant_pairs[:3]:  # Limit to first 3 pairs
                recommendations.append(
                    f"Paragraphs {i + 1} and {j + 1} are similar"
                )

        return ParagraphReport(
            paragraph_count=len(paragraphs),
            redundant_pairs=redundant_pairs,
            passes_check=passes_check,
            recommendations=recommendations,
        )

    def _extract_paragraphs(self, text: str) -> list[str]:
        """
        Extract paragraphs from text.

        Args:
            text: Input text

        Returns:
            List of paragraph strings
        """
        # Split by blank lines (one or more empty lines)
        paragraphs = re.split(r'\n\s*\n', text.strip())
        # Filter out empty paragraphs and strip whitespace
        return [p.strip() for p in paragraphs if p.strip()]

    def _extract_key_claims(self, text: str) -> Set[str]:
        """
        Extract key claims/words from a paragraph.

        Filters out stop words and returns meaningful content words.

        Args:
            text: Paragraph text

        Returns:
            Set of significant words
        """
        # Normalize text: lowercase and split into words
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter out stop words and short words
        key_words = {
            word for word in words
            if word not in self.STOP_WORDS and len(word) > 1
        }

        return key_words

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two paragraphs using word overlap.

        Uses Jaccard similarity coefficient: intersection / union

        Args:
            text1: First paragraph
            text2: Second paragraph

        Returns:
            Similarity score (0.0 to 1.0)
        """
        words1 = self._extract_key_claims(text1)
        words2 = self._extract_key_claims(text2)

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0
