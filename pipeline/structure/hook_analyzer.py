"""Hook quality analyzer for evaluating opening sentences."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HookReport:
    """Result of hook analysis."""

    score: float = 0.0
    max_score: float = 10.0
    checks_passed: list[str] = field(default_factory=list)
    passes_threshold: bool = True
    suggestions: list[str] = field(default_factory=list)


class HookAnalyzer:
    """
    Analyzes opening sentences (hooks) for quality.

    Scoring criteria (0-10):
    - Specific subject mentioned (+2)
    - Concrete event/news (+2)
    - Relevance implied (+2)
    - Not a generic question (+1)
    - Not a cliche (+1)
    - Under 25 words (+1)
    - Active voice (+1)
    """

    GENERIC_QUESTION_PATTERNS = [
        r"^задумывались\s+ли\s+вы",
        r"^знали\s+ли\s+вы",
        r"^have\s+you\s+ever\s+wondered",
        r"^did\s+you\s+know",
    ]

    CLICHE_OPENINGS = [
        "в современном мире",
        "сегодня мы рассмотрим",
        "in today's world",
        "let's explore",
    ]

    def __init__(self, min_score: float = 6.0) -> None:
        self.min_score = min_score
        self._question_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.GENERIC_QUESTION_PATTERNS
        ]

    def analyze(self, text: str) -> HookReport:
        """Analyze hook quality."""
        score = 0.0
        checks_passed = []
        suggestions = []

        first_sentence = text.split(".")[0].strip()
        first_sentence_lower = first_sentence.lower()

        # Check 1: Specific subject
        if self._has_specific_subject(first_sentence):
            score += 2
            checks_passed.append("specific subject")
        else:
            suggestions.append("Include a specific company, product, or person")

        # Check 2: Concrete event
        if self._has_concrete_event(first_sentence):
            score += 2
            checks_passed.append("concrete event")
        else:
            suggestions.append("Mention a specific event or announcement")

        # Check 3: Relevance
        if len(first_sentence) > 10:
            score += 2
            checks_passed.append("relevance implied")

        # Check 4: Not generic question
        is_generic_question = any(
            p.search(first_sentence) for p in self._question_patterns
        )
        if not is_generic_question and "?" not in first_sentence[:20]:
            score += 1
            checks_passed.append("not a generic question")
        else:
            suggestions.append("Avoid generic questions as hooks")

        # Check 5: Not cliche
        is_cliche = any(c in first_sentence_lower for c in self.CLICHE_OPENINGS)
        if not is_cliche:
            score += 1
            checks_passed.append("not a cliche")
        else:
            suggestions.append("Avoid cliche opening phrases")

        # Check 6: Concise
        word_count = len(first_sentence.split())
        if word_count <= 25:
            score += 1
            checks_passed.append("concise")

        # Check 7: Active voice
        if not re.search(r'\b(был[аи]?|was|were)\b', first_sentence_lower):
            score += 1
            checks_passed.append("active voice")

        passes_threshold = score >= self.min_score

        return HookReport(
            score=score,
            max_score=10.0,
            checks_passed=checks_passed,
            passes_threshold=passes_threshold,
            suggestions=suggestions,
        )

    def _has_specific_subject(self, text: str) -> bool:
        patterns = [
            r'\b(?:OpenAI|Google|Microsoft|Apple|Meta|Amazon)\b',
            r'\b(?:GPT-[45]|Claude|Gemini|ChatGPT)\b',
        ]
        return any(re.search(p, text) for p in patterns)

    def _has_concrete_event(self, text: str) -> bool:
        event_patterns = [
            r'(?:выпустил|анонс|запустил|представил)',
            r'(?:released|announced|launched)',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in event_patterns)
