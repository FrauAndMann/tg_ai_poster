"""
Grammar Checker - Checks spelling, grammar, and style.

Uses language-tool-python for comprehensive Russian language checking
plus custom readability metrics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)

# Try to import language_tool_python (optional dependency)
try:
    import language_tool_python
    LANGUAGE_TOOL_AVAILABLE = True
except ImportError:
    LANGUAGE_TOOL_AVAILABLE = False
    logger.warning("language-tool-python not installed. Grammar checking disabled.")


@dataclass(slots=True)
class GrammarIssue:
    """Single grammar/spelling issue."""
    message: str
    context: str
    offset: int
    length: int
    category: str
    severity: str  # "error", "warning", "suggestion"
    replacements: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReadabilityScore:
    """Readability metrics for Russian text."""
    flesch_kincaid_grade: float = 0.0
    avg_sentence_length: float = 0.0
    avg_word_length: float = 0.0
    paragraph_count: int = 0
    complex_sentence_ratio: float = 0.0
    reading_time_minutes: float = 0.0
    grade_level: str = "unknown"


@dataclass(slots=True)
class GrammarReport:
    """Complete grammar and readability report."""
    issues: list[GrammarIssue] = field(default_factory=list)
    readability: Optional[ReadabilityScore] = None
    error_count: int = 0
    warning_count: int = 0
    suggestion_count: int = 0
    overall_score: float = 100.0
    is_clean: bool = True
    summary: str = ""


class GrammarChecker:
    """
    Comprehensive grammar and readability checker.

    Features:
    - Spelling and grammar check via language-tool-python
    - Russian language optimizations
    - Readability metrics
    - Style suggestions
    """

    # Common Russian grammar mistakes patterns
    RUSSIAN_COMMON_ERRORS = [
        (r"\bв течении\b(?!\s+\d+)", "в течение", "Предлог 'в течение' (время)"),
        (r"\bв течении\s+\d+", None, "'в течении' допустимо с родительным падежом"),
        (r"\bне\s+(\w+ся)\b", r"не \1", "Проверьте написание глагола с -ся"),
        (r"\bтся\b(?![а-яё])", "ться/тся", "Проверьте -тся/-ться"),
        (r"\bться\b(?=\s+[а-яё])", "тся/ться", "Проверьте -тся/-ться"),
        (r"\s{2,}", " ", "Двойные пробелы"),
        (r"\bи\s+и\b", None, "Возможно, повтор союза 'и'"),
        (r"[.]{4,}", "...", "Многоточие - 3 точки"),
        (r"[!?]{2,}", None, "Двойные знаки препинания"),
    ]

    # Words that indicate complex sentences
    COMPLEXITY_MARKERS = [
        "который", "которая", "которое", "которые",
        "поскольку", "так как", "потому что", "из-за того что",
        "несмотря на то что", "хотя", "однако", "зато",
        "для того чтобы", "с тем чтобы", "прежде чем",
    ]

    def __init__(self, language: str = "ru"):
        """
        Initialize grammar checker.

        Args:
            language: Language code (default: Russian)
        """
        self.language = language
        self._tool = None

        if LANGUAGE_TOOL_AVAILABLE:
            try:
                self._tool = language_tool_python.LanguageTool(language)
                logger.info(f"LanguageTool initialized for {language}")
            except Exception as e:
                logger.warning(f"Failed to initialize LanguageTool: {e}")

    def check_grammar(self, text: str) -> list[GrammarIssue]:
        """
        Check text for grammar and spelling errors.

        Args:
            text: Text to check

        Returns:
            List of grammar issues
        """
        issues = []

        # Use language-tool if available
        if self._tool:
            try:
                matches = self._tool.check(text)
                for match in matches:
                    issues.append(GrammarIssue(
                        message=match.message,
                        context=match.context,
                        offset=match.offset,
                        length=match.errorLength,
                        category=match.category,
                        severity=self._get_severity(match),
                        replacements=list(match.replacements[:5]) if match.replacements else [],
                    ))
            except Exception as e:
                logger.error(f"LanguageTool error: {e}")

        # Add custom Russian checks
        issues.extend(self._check_russian_specific(text))

        return issues

    def _get_severity(self, match) -> str:
        """Determine issue severity from LanguageTool match."""
        category = getattr(match, 'category', '')
        rule_id = getattr(match, 'ruleId', '')

        # Critical errors
        if 'SPELLER' in rule_id.upper() or 'SPELL' in category.upper():
            return "error"
        if 'GRAMMAR' in category.upper():
            return "error"

        # Style suggestions
        if 'STYLE' in category.upper() or 'REDUNDANCY' in category.upper():
            return "suggestion"

        return "warning"

    def _check_russian_specific(self, text: str) -> list[GrammarIssue]:
        """Check for common Russian-specific issues."""
        issues = []

        for pattern, replacement, message in self.RUSSIAN_COMMON_ERRORS:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                if replacement:
                    issues.append(GrammarIssue(
                        message=message,
                        context=text[max(0, match.start()-20):match.end()+20],
                        offset=match.start(),
                        length=match.end() - match.start(),
                        category="Russian",
                        severity="warning",
                        replacements=[replacement],
                    ))

        return issues

    def calculate_readability(self, text: str) -> ReadabilityScore:
        """
        Calculate readability metrics for Russian text.

        Args:
            text: Text to analyze

        Returns:
            ReadabilityScore with metrics
        """
        # Split into sentences (Russian-aware)
        sentences = re.split(r'[.!?]+\s*', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Split into words
        words = re.findall(r'\b[а-яёa-z0-9]+\b', text.lower())

        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        if not sentences or not words:
            return ReadabilityScore(grade_level="empty")

        # Calculate metrics
        avg_sentence_length = len(words) / len(sentences)
        avg_word_length = sum(len(w) for w in words) / len(words)

        # Count complex sentences (those with complexity markers)
        complex_count = 0
        for sentence in sentences:
            if any(marker in sentence.lower() for marker in self.COMPLEXITY_MARKERS):
                complex_count += 1

        complex_ratio = complex_count / len(sentences) if sentences else 0

        # Estimate reading time (average 150 words per minute for Russian)
        reading_time = len(words) / 150

        # Estimate grade level (simplified for Russian)
        # Based on sentence length and word length
        if avg_sentence_length < 15 and avg_word_length < 5:
            grade = "easy"
            fk_grade = 6
        elif avg_sentence_length < 20 and avg_word_length < 6:
            grade = "medium"
            fk_grade = 10
        else:
            grade = "complex"
            fk_grade = 14

        return ReadabilityScore(
            flesch_kincaid_grade=fk_grade,
            avg_sentence_length=round(avg_sentence_length, 1),
            avg_word_length=round(avg_word_length, 1),
            paragraph_count=len(paragraphs),
            complex_sentence_ratio=round(complex_ratio, 2),
            reading_time_minutes=round(reading_time, 1),
            grade_level=grade,
        )

    def check(self, text: str, check_grammar: bool = True, check_readability: bool = True) -> GrammarReport:
        """
        Perform comprehensive grammar and readability check.

        Args:
            text: Text to check
            check_grammar: Whether to check grammar
            check_readability: Whether to check readability

        Returns:
            GrammarReport with all findings
        """
        issues = []
        readability = None

        if check_grammar:
            issues = self.check_grammar(text)

        if check_readability:
            readability = self.calculate_readability(text)

        # Count by severity
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        suggestion_count = sum(1 for i in issues if i.severity == "suggestion")

        # Calculate overall score
        # Start at 100, subtract for each issue
        score = 100.0
        score -= error_count * 10  # Errors are costly
        score -= warning_count * 3  # Warnings less so
        score -= suggestion_count * 1  # Suggestions minimal

        # Adjust for readability if too complex
        if readability and readability.grade_level == "complex":
            score -= 5

        score = max(0, min(100, score))

        # Generate summary
        if error_count == 0 and warning_count == 0:
            summary = "Текст грамматически корректен"
            if suggestion_count > 0:
                summary += f", есть {suggestion_count} рекомендаций по стилю"
        else:
            parts = []
            if error_count > 0:
                parts.append(f"{error_count} ошибок")
            if warning_count > 0:
                parts.append(f"{warning_count} предупреждений")
            summary = f"Обнаружено: {', '.join(parts)}"

        return GrammarReport(
            issues=issues,
            readability=readability,
            error_count=error_count,
            warning_count=warning_count,
            suggestion_count=suggestion_count,
            overall_score=score,
            is_clean=error_count == 0,
            summary=summary,
        )

    def get_corrections(self, text: str) -> str:
        """
        Get corrected version of text with auto-fixes applied.

        Args:
            text: Original text

        Returns:
            Corrected text
        """
        if not self._tool:
            return text

        try:
            return self._tool.correct(text)
        except Exception as e:
            logger.error(f"Auto-correction failed: {e}")
            return text

    def close(self) -> None:
        """Close language tool connection."""
        if self._tool:
            try:
                self._tool.close()
            except Exception:
                pass


# Singleton instance
_checker_instance: Optional[GrammarChecker] = None


def get_grammar_checker(language: str = "ru") -> GrammarChecker:
    """Get or create grammar checker instance."""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = GrammarChecker(language)
    return _checker_instance
