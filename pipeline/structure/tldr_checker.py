"""TLDR quality checker for validating summaries."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TLDRReport:
    """Result of TLDR validation."""

    passes_check: bool = True
    sentence_count: int = 0
    issues: list[str] = field(default_factory=list)


class TLDRChecker:
    """
    Validates TLDR quality.

    Rules:
    - Maximum 2 sentences (configurable)
    - Contains main subject (proper noun or company name)
    - Contains main event/outcome (action verbs or metrics)
    - No meta-language ("этот пост", "this post discusses")
    """

    # Meta-language patterns to detect
    META_LANGUAGE_PATTERNS = [
        # Russian meta-language
        r"\bэтот\s+пост\b",
        r"\bв\s+этом\s+посте\b",
        r"\bстатья\s+обсуждает\b",
        r"\bэта\s+статья\b",
        r"\bв\s+этой\s+статье\b",
        r"\bданный\s+пост\b",
        r"\bданная\s+статья\b",
        # English meta-language
        r"\bthis\s+post\b",
        r"\bthis\s+article\b",
        r"\bthe\s+following\b",
        r"\bthis\s+piece\s+discusses\b",
        r"\bthe\s+article\s+discusses\b",
    ]

    # Common company/product names (proper nouns)
    SUBJECT_PATTERNS = [
        # Major tech companies
        r"\b(?:OpenAI|Google|Microsoft|Apple|Meta|Amazon|Anthropic|Tesla|NVIDIA)\b",
        # AI products
        r"\b(?:GPT-[45]|Claude|Gemini|ChatGPT|Llama|Copilot|Midjourney)\b",
        # Russian companies
        r"\b(?:Яндекс|Yandex|Сбер|Sber|ВК|VK|Тинькофф|Tinkoff)\b",
        # Capitalized words (potential proper nouns) - at least 3 chars
        r"\b[A-Z][a-z]{2,}\b",
        # Russian capitalized words
        r"\b[А-Я][а-я]{2,}\b",
    ]

    # Action verbs and metrics indicating main event/outcome
    EVENT_PATTERNS = [
        # Russian action verbs
        r"\b(?:выпустил|анонсировал|запустил|представил|объявил|опубликовал|разработал)\b",
        r"\b(?:выпустила|анонсировала|запустила|представила|объявила)\b",
        # English action verbs
        r"\b(?:released|announced|launched|unveiled|published|developed|shipped)\b",
        # Metrics/improvements
        r"\b\d+[xх]\b",  # 3x speedup
        r"\b\d+%\b",  # 50% increase
        r"\b(?:увелич|уменьш|вырос|снизил|improved|increased|reduced)\b",
        r"\$(?:\d+\.?\d*[мк]?\s*)?(?:млн|млрд|million|billion)?\b",  # money amounts
    ]

    def __init__(self, max_sentences: int = 2) -> None:
        """Initialize TLDR checker.

        Args:
            max_sentences: Maximum allowed sentences (default: 2)
        """
        self.max_sentences = max_sentences
        self._meta_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.META_LANGUAGE_PATTERNS
        ]
        self._subject_patterns = [
            re.compile(p) for p in self.SUBJECT_PATTERNS
        ]
        self._event_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.EVENT_PATTERNS
        ]

    def check(self, tldr: str) -> TLDRReport:
        """Validate TLDR quality.

        Args:
            tldr: The TLDR text to validate

        Returns:
            TLDRReport with validation results
        """
        issues = []

        # Handle empty TLDR
        if not tldr or not tldr.strip():
            return TLDRReport(
                passes_check=False,
                sentence_count=0,
                issues=["TLDR is empty"],
            )

        tldr = tldr.strip()

        # Count sentences
        sentences = [s.strip() for s in re.split(r'[.!?]+', tldr) if s.strip()]
        sentence_count = len(sentences)

        if sentence_count > self.max_sentences:
            issues.append(
                f"TLDR has too many sentences ({sentence_count}), max is {self.max_sentences}"
            )

        # Check for meta-language
        has_meta_language = False
        for pattern in self._meta_patterns:
            if pattern.search(tldr):
                has_meta_language = True
                break

        if has_meta_language:
            issues.append("TLDR contains meta-language (self-referential phrases)")

        # Check for main subject
        has_subject = False
        for pattern in self._subject_patterns:
            if pattern.search(tldr):
                has_subject = True
                break

        if not has_subject:
            issues.append("TLDR missing main subject (company/product name)")

        # Check for main event/outcome
        has_event = False
        for pattern in self._event_patterns:
            if pattern.search(tldr):
                has_event = True
                break

        if not has_event:
            issues.append("TLDR missing main event/outcome")

        passes_check = len(issues) == 0

        return TLDRReport(
            passes_check=passes_check,
            sentence_count=sentence_count,
            issues=issues,
        )
