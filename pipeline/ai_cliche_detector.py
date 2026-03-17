"""
AI Cliche Detector - Advanced detection of AI-generated content patterns.

Detects subtle AI writing patterns, cliches, and tells that make content
feel artificial. Provides scoring and suggestions for humanization.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ClicheMatch:
    """A detected cliche or AI pattern."""

    text: str
    category: str
    position: tuple[int, int]  # (start, end)
    severity: str  # low, medium, high
    suggestion: str = ""
    context: str = ""


@dataclass(slots=True)
class ClicheReport:
    """Complete cliche analysis report."""

    total_matches: int = 0
    high_severity_count: int = 0
    medium_severity_count: int = 0
    low_severity_count: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    matches: list[ClicheMatch] = field(default_factory=list)
    ai_probability_score: float = 0.0
    humanization_suggestions: list[str] = field(default_factory=list)


class AIClicheDetector:
    """
    Advanced AI-generated content pattern detector.

    Features:
    - Multi-category pattern detection
    - Severity-based scoring
    - Context-aware analysis
    - Humanization suggestions
    - Continuous pattern learning
    """

    # Extended AI cliche patterns with severity
    AI_PATTERNS = {
        "transition_cliches": {
            "patterns": [
                r"\bоднако\s+стоит\s+отметить\b",
                r"\bтем\s+не\s+менее\b",
                r"\bв\s+то\s+же\s+время\b",
                r"\bс\s+другой\s+стороны\b",
                r"\bболее\s+того\b",
                r"\bкроме\s+того\b",
                r"\bважно\s+подчеркнуть\b",
                r"\bследует\s+упомянуть\b",
                r"\bнельзя\s+не\s+сказать\b",
                r"\bworth\s+noting\b",
                r"\bimportant\s+to\s+mention\b",
                r"\bit\s+is\s+worth\s+noting\b",
                r"\bneedless\s+to\s+say\b",
                r"\binterestingly\b",
                r"\bnotably\b",
                r"\bsignificantly\b",
            ],
            "severity": "medium",
            "suggestion": "Используй более естественные переходы или убери лишнее",
        },
        "hollow_intensifiers": {
            "patterns": [
                r"\bочень\s+\w+\b",
                r"\bкрайне\s+\w+\b",
                r"\bвесьма\s+\w+\b",
                r"\bисключительно\s+\w+\b",
                r"\bпо-настоящему\s+\w+\b",
                r"\bвпечатляюще\s+\w+\b",
                r"\bincredibly\s+\w+\b",
                r"\bextremely\s+\w+\b",
                r"\bremarkably\s+\w+\b",
                r"\bexceptionally\s+\w+\b",
                r"\btruly\s+\w+\b",
                r"\babsolutely\s+\w+\b",
            ],
            "severity": "low",
            "suggestion": "Замените на конкретные данные или уберите",
        },
        "empty_openings": {
            "patterns": [
                r"^в\s+современном\s+мире\b",
                r"^сегодня\s+мы\s+рассмотрим\b",
                r"^в\s+этой\s+статье\b",
                r"^данная\s+статья\b",
                r"^в\s+данном\s+материале\b",
                r"^хочется\s+начать\s+с\s+того\b",
                r"^прежде\s+всего\b",
                r"^in\s+today\'?s?\s+world\b",
                r"^in\s+this\s+(article|post|piece)\b",
                r"^let\'?s?\s+(explore|dive|look|examine)\b",
                r"^first\s+and\s+foremost\b",
            ],
            "severity": "high",
            "suggestion": "Начните с факта, истории или конкретного заявления",
        },
        "redundant_phrases": {
            "patterns": [
                r"\bплан\s+по\s+плану\b",
                r"\bпериод\s+времени\b",
                r"\bв\s+конечном\s+итоге\b",
                r"\bв\s+общем\s+и\s+целом\b",
                r"\bпо\s+сути\s+дела\b",
                r"\bс\s+самого\s+начала\b",
                r"\bдо\s+сих\s+пор\b",
                r"\bкак\s+минимум\b",
                r"\bпо\s+возможности\b",
                r"\bпо\s+мере\s+необходимости\b",
            ],
            "severity": "medium",
            "suggestion": "Упростите фразу или уберите лишнее",
        },
        "ai_sentence_structure": {
            "patterns": [
                r"^[A-Za-zА-Яа-яЁё]+\s+[—–-]\s+[^.]+\.\s+[A-Za-zА-Яа-яЁё]+",  # Pattern: "Something - explanation. Another"
                r"\.\s+(Это|Такой|Подобный|Данный)\s+(подход|метод|способ)",  # Pattern: ". This approach..."
                r"\.\s+(Однако|Тем не менее|В то же время)\s*,",  # Formulaic transitions
                r"!\s+И\s+это\s+не\s+удивительно",  # "And it's not surprising"
                r"\.\s+(Важно|Стоит|Следует)\s+(отметить|подчеркнуть|упомянуть)",
            ],
            "severity": "medium",
            "suggestion": "Варьируйте структуру предложений",
        },
        "over_explaining": {
            "patterns": [
                r"\bто\s+есть\s+[^.]{20,}\b",
                r"\bа\s+именно\s*:\s*[^.]{30,}\b",
                r"\bдругими\s+словами\b",
                r"\bпроще\s+говоря\b",
                r"\bиными\s+словами\b",
                r"\bin\s+other\s+words\b",
                r"\bthat\s+is\s+to\s+say\b",
                r"\bto\s+put\s+it\s+(simply|another\s+way)\b",
                r"\bessentially\b[^.]{20,}",
            ],
            "severity": "low",
            "suggestion": "Доверяйте читателю понять контекст",
        },
        "formulaic_conclusions": {
            "patterns": [
                r"\bв\s+заключение\s+хотелось\s+бы\s+сказать\b",
                r"\bподводя\s+итог\b",
                r"\bв\s+общем\b[^.]*\bможно\s+сказать\b",
                r"\bрезюмируя\s+вышесказанное\b",
                r"\bтаким\s+образом\b[^.]{0,20}можно\s+сделать\s+вывод\b",
                r"\bin\s+conclusion\b",
                r"\bto\s+sum\s+(up|marize)\b",
                r"\ball\s+in\s+all\b",
                r"\bbottom\s+line\b",
                r"\btakeaway\s+is\b",
            ],
            "severity": "high",
            "suggestion": "Заканчивайте конкретным действием или инсайтом",
        },
        "hedging_language": {
            "patterns": [
                r"\bв\s+некоторой\s+степени\b",
                r"\bв\s+определённом\s+смысле\b",
                r"\bдо\s+некоторой\s+степени\b",
                r"\bможно\s+сказать\s+что\b",
                r"\bпредставляется\s+что\b",
                r"\bкажется\s+что\b",
                r"\bto\s+a\s+certain\s+extent\b",
                r"\bto\s+some\s+degree\b",
                r"\bsomewhat\b",
                r"\bquite\b\s+\w+\b",
                r"\brather\b\s+\w+\b",
            ],
            "severity": "low",
            "suggestion": "Будьте увереннее или приведите конкретные данные",
        },
        "listicle_patterns": {
            "patterns": [
                r"^\d+[\).\]]\s+[A-Za-zА-Яа-яЁё]",  # Numbered lists at start
                r"\bво-первых\b",
                r"\bво-вторых\b",
                r"\bв-третьих\b",
                r"\bнаконец\b",
                r"\bfirstly\b",
                r"\bsecondly\b",
                r"\bthirdly\b",
                r"\bfinally\b",
                r"\blastly\b",
            ],
            "severity": "medium",
            "suggestion": "Интегрируйте элементы в повествование",
        },
        "passive_voice_ru": {
            "patterns": [
                r"\bбыл[аи]?\s+\w+ен[а-я]?\b",
                r"\bбыло\s+\w+ен[оа]\b",
                r"\bявляется\s+\w+\b",
                r"\bостаётся\s+\w+\b",
                r"\bстановится\s+\w+\b",
                r"\bоказывается\s+\w+\b",
            ],
            "severity": "medium",
            "suggestion": "Используйте активный залог",
        },
    }

    # AI probability indicators (weighted)
    AI_INDICATORS = {
        "perfect_grammar": 0.1,
        "balanced_structure": 0.15,
        "neutral_tone": 0.2,
        "no_contractions": 0.1,
        "excessive_hedging": 0.2,
        "formulaic_transitions": 0.25,
        "abstract_examples": 0.15,
        "lack_of_specifics": 0.2,
        "consistent_sentence_length": 0.15,
    }

    def __init__(
        self,
        banned_words_path: Optional[Path] = None,
        custom_patterns: Optional[dict[str, Any]] = None,
    ) -> None:
        self.banned_words_path = banned_words_path
        self._banned_words: dict[str, Any] = {}
        self._custom_patterns = custom_patterns or {}
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}

        self._load_banned_words()
        self._compile_patterns()

    def _load_banned_words(self) -> None:
        """Load banned words from config file."""
        if self.banned_words_path and self.banned_words_path.exists():
            try:
                with open(self.banned_words_path, "r", encoding="utf-8") as f:
                    self._banned_words = json.load(f)
                logger.debug("Loaded banned words from %s", self.banned_words_path)
            except Exception as e:
                logger.warning("Failed to load banned words: %s", e)

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        all_patterns = {**self.AI_PATTERNS, **self._custom_patterns}

        for category, data in all_patterns.items():
            patterns = data.get("patterns", [])
            self._compiled_patterns[category] = [
                re.compile(p, re.IGNORECASE | re.MULTILINE)
                for p in patterns
            ]

    def detect(self, text: str) -> ClicheReport:
        """
        Detect AI cliches and patterns in text.

        Args:
            text: Text to analyze

        Returns:
            ClicheReport with all findings
        """
        report = ClicheReport()

        # Check each pattern category
        for category, data in self.AI_PATTERNS.items():
            patterns = self._compiled_patterns.get(category, [])
            severity = data.get("severity", "medium")
            suggestion = data.get("suggestion", "")

            for pattern in patterns:
                for match in pattern.finditer(text):
                    cliche = ClicheMatch(
                        text=match.group(),
                        category=category,
                        position=(match.start(), match.end()),
                        severity=severity,
                        suggestion=suggestion,
                        context=self._get_context(text, match.start(), match.end()),
                    )
                    report.matches.append(cliche)

                    # Update counts
                    report.categories[category] = report.categories.get(category, 0) + 1
                    if severity == "high":
                        report.high_severity_count += 1
                    elif severity == "medium":
                        report.medium_severity_count += 1
                    else:
                        report.low_severity_count += 1

        report.total_matches = len(report.matches)

        # Calculate AI probability score
        report.ai_probability_score = self._calculate_ai_probability(text, report)

        # Generate humanization suggestions
        report.humanization_suggestions = self._generate_suggestions(report)

        return report

    def _get_context(self, text: str, start: int, end: int, window: int = 30) -> str:
        """Get context around a match."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    def _calculate_ai_probability(self, text: str, report: ClicheReport) -> float:
        """Calculate probability that text was AI-generated."""
        score = 0.0

        # Base score from cliche matches
        if report.total_matches > 0:
            score += min(0.3, report.total_matches * 0.03)

        # High severity matches contribute more
        score += report.high_severity_count * 0.1
        score += report.medium_severity_count * 0.05

        # Check for AI indicators
        score += self._check_perfect_grammar(text) * self.AI_INDICATORS["perfect_grammar"]
        score += self._check_balanced_structure(text) * self.AI_INDICATORS["balanced_structure"]
        score += self._check_neutral_tone(text) * self.AI_INDICATORS["neutral_tone"]
        score += self._check_no_contractions(text) * self.AI_INDICATORS["no_contractions"]
        score += self._check_sentence_consistency(text) * self.AI_INDICATORS["consistent_sentence_length"]

        return min(1.0, score)

    def _check_perfect_grammar(self, text: str) -> float:
        """Check for suspiciously perfect grammar."""
        # AI often produces text without any typos or informal elements
        has_informal = bool(re.search(r"[а-яё]с[а-яё]|[а-яё]ць|що\b|\bdon't\b|\bwon't\b", text.lower()))
        return 0.0 if has_informal else 1.0

    def _check_balanced_structure(self, text: str) -> float:
        """Check for suspiciously balanced paragraph structure."""
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) < 3:
            return 0.0

        lengths = [len(p) for p in paragraphs]
        avg_len = sum(lengths) / len(lengths)
        variance = sum((length - avg_len) ** 2 for length in lengths) / len(lengths)

        # Low variance suggests AI generation
        normalized_variance = variance / (avg_len ** 2) if avg_len > 0 else 0
        return 1.0 if normalized_variance < 0.1 else 0.0

    def _check_neutral_tone(self, text: str) -> float:
        """Check for overly neutral tone."""
        emotional_words = [
            "ужасно", "великолепно", "потрясающе", "отвратительно",
            "amazing", "terrible", "awful", "fantastic", "horrible",
            "!",  # Exclamation marks indicate emotion
        ]
        has_emotion = any(w in text.lower() for w in emotional_words)
        has_exclamations = text.count("!") > 2
        return 0.0 if (has_emotion or has_exclamations) else 1.0

    def _check_no_contractions(self, text: str) -> float:
        """Check for lack of contractions (AI often writes full forms)."""
        # Russian doesn't have contractions, so this is English-specific
        words = text.split()
        if not words:
            return 0.0

        contraction_candidates = ["is not", "do not", "will not", "cannot", "would not"]
        has_contractions = any(c in text.lower() for c in ["n't", "'s", "'re", "'ve", "'ll"])
        has_full_forms = any(c in text.lower() for c in contraction_candidates)

        if has_contractions and not has_full_forms:
            return 0.0
        elif has_full_forms and not has_contractions:
            return 1.0
        return 0.5

    def _check_sentence_consistency(self, text: str) -> float:
        """Check for suspiciously consistent sentence lengths."""
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 5:
            return 0.0

        lengths = [len(s.split()) for s in sentences]
        avg_len = sum(lengths) / len(lengths)

        # Count sentences within 20% of average
        near_avg = sum(1 for length in lengths if abs(length - avg_len) <= avg_len * 0.2)
        ratio = near_avg / len(lengths)

        # High ratio suggests AI generation
        return ratio if ratio > 0.7 else 0.0

    def _generate_suggestions(self, report: ClicheReport) -> list[str]:
        """Generate humanization suggestions based on findings."""
        suggestions = []

        if report.high_severity_count > 0:
            suggestions.append(
                f"Критично: найдено {report.high_severity_count} сильных AI-паттернов. "
                "Перепишите эти места своими словами."
            )

        if "empty_openings" in report.categories:
            suggestions.append(
                "Начните с факта, цифры или истории вместо шаблонного вступления"
            )

        if "formulaic_conclusions" in report.categories:
            suggestions.append(
                "Замените шаблонное заключение на конкретный призыв к действию"
            )

        if "transition_cliches" in report.categories:
            suggestions.append(
                "Используйте более естественные переходы между абзацами"
            )

        if "hollow_intensifiers" in report.categories:
            suggestions.append(
                "Замените усилители на конкретные данные или примеры"
            )

        if "passive_voice_ru" in report.categories:
            suggestions.append(
                "Перепишите в активном залоге для большей энергии"
            )

        if report.ai_probability_score > 0.7:
            suggestions.append(
                f"Высокая вероятность AI-генерации ({report.ai_probability_score:.0%}). "
                "Добавьте личный опыт и конкретные примеры."
            )

        return suggestions

    def get_replacement(self, text: str, cliche: ClicheMatch) -> Optional[str]:
        """Get suggested replacement for a cliche."""
        # Check for specific replacements in banned words
        if self._banned_words:
            replacements = self._banned_words.get("banned_words", {}).get("hype_words", {}).get("replacements", {})
            for original, replacement in replacements.items():
                if original.lower() in cliche.text.lower():
                    return cliche.text.replace(original, replacement)

        # Generic suggestions based on category
        category_suggestions = {
            "hollow_intensifiers": "убрать",
            "transition_cliches": "упростить",
            "empty_openings": "начать с факта",
        }
        return category_suggestions.get(cliche.category)


# Configuration schema
AI_CLICHE_DETECTOR_CONFIG_SCHEMA = {
    "ai_cliche_detection": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable AI cliche detection",
        },
        "min_severity_to_flag": {
            "type": "str",
            "default": "medium",
            "description": "Minimum severity level to flag (low, medium, high)",
        },
        "ai_probability_threshold": {
            "type": "float",
            "default": 0.5,
            "description": "Threshold to flag as likely AI-generated",
        },
        "auto_suggest_replacements": {
            "type": "bool",
            "default": True,
            "description": "Automatically suggest replacements",
        },
    }
}
