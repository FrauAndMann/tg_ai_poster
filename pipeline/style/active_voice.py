"""
Active Voice Enforcer - Detects passive voice and converts to active voice.

Provides analysis of passive voice usage with scoring and conversion suggestions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class PassiveVoiceMatch:
    """Single passive voice match found in text."""

    text: str
    start: int
    end: int
    auxiliary_verb: str
    main_verb: str
    sentence: str
    suggested_active: Optional[str] = None


@dataclass(slots=True)
class PassiveVoiceReport:
    """Complete passive voice analysis report."""

    matches: list[PassiveVoiceMatch] = field(default_factory=list)
    total_sentences: int = 0
    passive_sentence_count: int = 0
    passive_percentage: float = 0.0
    score: float = 100.0  # 0-100, higher is better (more active voice)
    is_acceptable: bool = True
    recommendations: list[str] = field(default_factory=list)


class ActiveVoiceChecker:
    """
    Checker for detecting and analyzing passive voice patterns.

    Supports both Russian and English text with comprehensive
    passive voice detection and conversion suggestions.

    Features:
    - Passive voice pattern detection
    - Percentage calculation of passive sentences
    - Score from 0-100 (higher = more active)
    - Conversion suggestions to active voice
    """

    # English passive voice patterns
    # Pattern: auxiliary verb (be/have been) + past participle
    ENGLISH_PASSIVE_PATTERNS = [
        # Common "be" + past participle patterns
        r"\b(am|is|are|was|were|been|being)\s+(\w+ed)\b",
        r"\b(am|is|are|was|were|been|being)\s+(\w+en)\b",
        r"\b(am|is|are|was|were|been|being)\s+(\w+t)\b",
        # "has/have been" + past participle
        r"\b(has|have)\s+been\s+(\w+ed)\b",
        r"\b(has|have)\s+been\s+(\w+en)\b",
        # "will be" + past participle
        r"\bwill\s+be\s+(\w+ed)\b",
        # Common irregular past participles
        r"\b(am|is|are|was|were)\s+(written|given|taken|seen|done|made|known|used|found|shown)\b",
        r"\b(has|have)\s+been\s+(written|given|taken|seen|done|made|known|used|found|shown)\b",
    ]

    # Russian passive voice patterns
    # Pattern: reflexive verbs with -sya or participles
    RUSSIAN_PASSIVE_PATTERNS = [
        # Reflexive verbs ending in -sya/-сь (often indicate passive)
        r"\b(\w+(?:ае|ое|ие|ы|и|а|я|е|ь)(?:м|шь|т|м|те|ют|ат|ит|ят|в)(?:ся|сь))\b",
        # Short passive participles
        r"\b(?:был|была|было|были|будет|будут)\s+(\w+(?:ен|ён|н|т)(?:а|о|ы|и)?)\b",
        # Passive constructions with "быть" + participle
        r"\b(?:является|являлся|являлась|являются|являлись)\s+(\w+(?:ым|ым|им|ым|ой|ою|ею))\b",
        # Common passive markers
        r"\b(?:был|была|было|были)\s+\w+(?:ен|ён|н|ан|ян)(?:а|о|ы|и)?\b",
        # "был сделан", "была написана" patterns
        r"\b(?:был|была|было|были)\s+(\w+ен(?:а|о|ы|и)?|\w+ён(?:а|о|ы|и)?|\w+н(?:а|о|ы|и)?)\b",
        # Present passive "делается", "создается"
        r"\b\w+(?:ается|яется|уется|ется|ётся|ается)\b",
        # Past passive participles in short form
        r"\b(?:написан|сделан|создан|открыт|закрыт|найден|взят|дан)(?:а|о|ы|и)?\b",
    ]

    # Common English irregular verbs for conversion (past participle -> base form)
    ENGLISH_IRREGULAR_VERBS = {
        "written": "write",
        "given": "give",
        "taken": "take",
        "seen": "see",
        "done": "do",
        "made": "make",
        "known": "know",
        "used": "use",
        "found": "find",
        "shown": "show",
        "said": "say",
        "thought": "think",
        "told": "tell",
        "sent": "send",
        "brought": "bring",
        "bought": "buy",
        "sold": "sell",
        "built": "build",
        "held": "hold",
        "kept": "keep",
        "left": "leave",
        "lost": "lose",
        "paid": "pay",
        "put": "put",
        "read": "read",
        "run": "run",
        "set": "set",
        "spoken": "speak",
        "spent": "spend",
        "taught": "teach",
        "won": "win",
        "written": "write",
    }

    # Russian verb conversions (passive -> active suggestions)
    RUSSIAN_VERB_CONVERSIONS = {
        "был сделан": "сделал",
        "была сделана": "сделала",
        "было сделано": "сделало",
        "были сделаны": "сделали",
        "был написан": "написал",
        "была написана": "написала",
        "было написано": "написало",
        "были написаны": "написали",
        "был создан": "создал",
        "была создана": "создала",
        "было создано": "создало",
        "были созданы": "создали",
        "является": "есть",
        "являлся": "был",
        "являются": "есть",
        "являлись": "были",
    }

    # Score thresholds
    PASSIVE_THRESHOLD_EXCELLENT = 10.0  # Less than 10% passive is excellent
    PASSIVE_THRESHOLD_ACCEPTABLE = 20.0  # Less than 20% is acceptable
    PASSIVE_THRESHOLD_WARNING = 35.0  # Less than 35% is warning

    def __init__(
        self,
        max_passive_percentage: float = 20.0,
        language: str = "auto",
    ) -> None:
        """
        Initialize active voice checker.

        Args:
            max_passive_percentage: Maximum acceptable passive voice percentage
            language: Language to check ("en", "ru", or "auto" for detection)
        """
        self.max_passive_percentage = max_passive_percentage
        self.language = language
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self._compiled_patterns["en"] = [
            re.compile(p, re.IGNORECASE) for p in self.ENGLISH_PASSIVE_PATTERNS
        ]
        self._compiled_patterns["ru"] = [
            re.compile(p, re.IGNORECASE) for p in self.RUSSIAN_PASSIVE_PATTERNS
        ]

    @property
    def passive_voice_report(self) -> PassiveVoiceReport:
        """
        Get the last generated passive voice report.

        Note: This is a property for compatibility. Call check() first.
        """
        if not hasattr(self, "_last_report"):
            self._last_report = PassiveVoiceReport()
        return self._last_report

    def _detect_language(self, text: str) -> str:
        """
        Detect if text is primarily Russian or English.

        Args:
            text: Text to analyze

        Returns:
            "ru" for Russian, "en" for English
        """
        # Count Cyrillic vs Latin characters
        cyrillic_count = len(re.findall(r"[а-яё]", text.lower()))
        latin_count = len(re.findall(r"[a-z]", text.lower()))

        if cyrillic_count > latin_count:
            return "ru"
        return "en"

    def _get_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Split on sentence-ending punctuation followed by space or end
        sentences = re.split(r"[.!?]+(?:\s+|$)", text)
        return [s.strip() for s in sentences if s.strip()]

    def _check_passive_voice(self, text: str, language: str = "auto") -> list[PassiveVoiceMatch]:
        """
        Detect passive voice patterns in text.

        Args:
            text: Text to analyze
            language: Language to check ("en", "ru", or "auto")

        Returns:
            List of PassiveVoiceMatch objects
        """
        if language == "auto":
            language = self._detect_language(text)

        matches: list[PassiveVoiceMatch] = []
        sentences = self._get_sentences(text)

        patterns = self._compiled_patterns.get(language, [])

        for sentence in sentences:
            sentence_start = text.find(sentence)
            if sentence_start == -1:
                continue

            for pattern in patterns:
                for match in pattern.finditer(sentence):
                    matched_text = match.group()
                    match_start = sentence_start + match.start()
                    match_end = sentence_start + match.end()

                    # Extract auxiliary verb and main verb
                    groups = match.groups()
                    auxiliary = groups[0] if groups else ""
                    main_verb = groups[1] if len(groups) > 1 else ""

                    # Try to generate active voice suggestion
                    suggested_active = self._suggest_active_voice(
                        matched_text, auxiliary, main_verb, language
                    )

                    matches.append(PassiveVoiceMatch(
                        text=matched_text,
                        start=match_start,
                        end=match_end,
                        auxiliary_verb=auxiliary,
                        main_verb=main_verb,
                        sentence=sentence,
                        suggested_active=suggested_active,
                    ))

        # Remove duplicate matches
        seen = set()
        unique_matches = []
        for m in matches:
            if (m.start, m.end) not in seen:
                seen.add((m.start, m.end))
                unique_matches.append(m)

        return unique_matches

    def _suggest_active_voice(
        self,
        passive_text: str,
        auxiliary: str,
        main_verb: str,
        language: str,
    ) -> Optional[str]:
        """
        Generate active voice suggestion for a passive construction.

        Args:
            passive_text: The matched passive text
            auxiliary: Auxiliary verb (be/have)
            main_verb: Main verb (past participle)
            language: Language code

        Returns:
            Suggested active voice form or None
        """
        if language == "en":
            # Try to convert irregular verbs
            base_verb = self.ENGLISH_IRREGULAR_VERBS.get(main_verb.lower())
            if base_verb:
                # Simple suggestion: "was written" -> "[subject] wrote"
                return f"[subject] {base_verb}"
            # For regular verbs, remove -ed and add subject
            if main_verb.lower().endswith("ed"):
                base = main_verb[:-2] if len(main_verb) > 4 else main_verb[:-1]
                return f"[subject] {base}s/{base}ed"
        elif language == "ru":
            # Try Russian conversions
            passive_lower = passive_text.lower()
            for passive, active in self.RUSSIAN_VERB_CONVERSIONS.items():
                if passive in passive_lower:
                    return f"[субъект] {active}"

        return None

    def _score_passive_voice(
        self,
        matches: list[PassiveVoiceMatch],
        total_sentences: int,
    ) -> tuple[float, int, float]:
        """
        Calculate passive voice percentage and score.

        Args:
            matches: List of passive voice matches
            total_sentences: Total number of sentences

        Returns:
            Tuple of (score, passive_sentence_count, passive_percentage)
        """
        if total_sentences == 0:
            return 100.0, 0, 0.0

        # Count unique sentences with passive voice
        passive_sentences = set()
        for match in matches:
            passive_sentences.add(match.sentence)

        passive_count = len(passive_sentences)
        passive_percentage = (passive_count / total_sentences) * 100

        # Calculate score (0-100, higher is better)
        # Score decreases as passive percentage increases
        if passive_percentage <= self.PASSIVE_THRESHOLD_EXCELLENT:
            score = 100.0 - (passive_percentage * 0.5)  # Minor penalty
        elif passive_percentage <= self.PASSIVE_THRESHOLD_ACCEPTABLE:
            score = 95.0 - ((passive_percentage - self.PASSIVE_THRESHOLD_EXCELLENT) * 1.5)
        elif passive_percentage <= self.PASSIVE_THRESHOLD_WARNING:
            score = 80.0 - ((passive_percentage - self.PASSIVE_THRESHOLD_ACCEPTABLE) * 2)
        else:
            score = 50.0 - ((passive_percentage - self.PASSIVE_THRESHOLD_WARNING) * 1)
            score = max(0, score)  # Don't go below 0

        return round(score, 1), passive_count, round(passive_percentage, 1)

    def _generate_report(
        self,
        text: str,
        matches: list[PassiveVoiceMatch],
        total_sentences: int,
        passive_count: int,
        passive_percentage: float,
        score: float,
    ) -> PassiveVoiceReport:
        """
        Generate comprehensive passive voice report.

        Args:
            text: Original text
            matches: List of passive voice matches
            total_sentences: Total sentence count
            passive_count: Sentences with passive voice
            passive_percentage: Percentage of passive sentences
            score: Overall score

        Returns:
            PassiveVoiceReport with all findings
        """
        is_acceptable = passive_percentage <= self.max_passive_percentage

        recommendations = []

        if passive_percentage > self.max_passive_percentage:
            recommendations.append(
                f"Passive voice usage ({passive_percentage:.1f}%) exceeds "
                f"recommended maximum ({self.max_passive_percentage}%)"
            )

        if matches:
            # List specific passive constructions
            examples = list(set(m.text for m in matches[:5]))
            if examples:
                recommendations.append(
                    f"Consider rephrasing: {', '.join(examples)}"
                )

        if passive_percentage > self.PASSIVE_THRESHOLD_WARNING:
            recommendations.append(
                "High passive voice usage reduces clarity and engagement. "
                "Consider using active voice for more direct communication."
            )

        report = PassiveVoiceReport(
            matches=matches,
            total_sentences=total_sentences,
            passive_sentence_count=passive_count,
            passive_percentage=passive_percentage,
            score=score,
            is_acceptable=is_acceptable,
            recommendations=recommendations,
        )

        # Store for passive_voice_report property
        self._last_report = report

        return report

    def check(self, text: str, language: str = "auto") -> PassiveVoiceReport:
        """
        Perform comprehensive passive voice analysis.

        Args:
            text: Text to analyze
            language: Language to check ("en", "ru", or "auto")

        Returns:
            PassiveVoiceReport with all findings
        """
        if language == "auto":
            language = self._detect_language(text)

        # Get sentences
        sentences = self._get_sentences(text)
        total_sentences = len(sentences)

        # Check for passive voice
        matches = self._check_passive_voice(text, language)

        # Calculate score
        score, passive_count, passive_percentage = self._score_passive_voice(
            matches, total_sentences
        )

        # Generate report
        return self._generate_report(
            text=text,
            matches=matches,
            total_sentences=total_sentences,
            passive_count=passive_count,
            passive_percentage=passive_percentage,
            score=score,
        )

    def get_passive_percentage(self, text: str) -> float:
        """
        Get the percentage of sentences with passive voice.

        Args:
            text: Text to analyze

        Returns:
            Percentage of passive voice sentences (0-100)
        """
        report = self.check(text)
        return report.passive_percentage

    def convert_to_active_voice(self, text: str) -> str:
        """
        Attempt to convert passive voice to active voice.

        This is a simplified conversion that replaces common patterns.
        For accurate conversion, consider using an LLM.

        Args:
            text: Text to convert

        Returns:
            Text with passive constructions replaced where possible
        """
        language = self._detect_language(text)
        result = text

        if language == "en":
            # Replace common English passive patterns
            for passive, active in [
                (r"\bwas\s+(\w+ed)\b", r"[subject] \1"),
                (r"\bwere\s+(\w+ed)\b", r"[subjects] \1"),
                (r"\bis\s+(\w+ed)\b", r"[subject] \1s"),
                (r"\bare\s+(\w+ed)\b", r"[subjects] \1"),
            ]:
                result = re.sub(passive, active, result, flags=re.IGNORECASE)

            # Replace irregular verbs
            for past_part, base in self.ENGLISH_IRREGULAR_VERBS.items():
                result = re.sub(
                    rf"\b(was|were)\s+{past_part}\b",
                    rf"[subject] {base}",
                    result,
                    flags=re.IGNORECASE,
                )

        elif language == "ru":
            # Replace common Russian passive patterns
            for passive, active in self.RUSSIAN_VERB_CONVERSIONS.items():
                result = re.sub(passive, active, result, flags=re.IGNORECASE)

        return result

    def __repr__(self) -> str:
        return (
            f"ActiveVoiceChecker("
            f"max_passive_percentage={self.max_passive_percentage}, "
            f"language='{self.language}')"
        )
