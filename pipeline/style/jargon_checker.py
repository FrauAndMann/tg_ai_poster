"""
Jargon Checker - Ensures technical content is accessible.

Analyzes text for technical jargon and verifies that:
- Common knowledge terms are identified and allowed
- Non-common jargon has definitions in same/next sentence
- Explanations or links are provided for technical terms
- Recommendations are generated for unexplained jargon
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class JargonTerm:
    """Represents a jargon term found in text."""

    term: str
    position: int
    is_common_knowledge: bool
    has_definition: bool
    context: str
    definition: str | None = None
    category: str | None = None


@dataclass
class JargonReport:
    """Result of jargon accessibility check."""

    jargon_terms: list[JargonTerm] = field(default_factory=list)
    unexplained_count: int = 0
    passes_check: bool = True
    recommendations: list[str] = field(default_factory=list)


class JargonChecker:
    """
    Checks technical jargon accessibility in content.

    Ensures that technical terms are either:
    - Common knowledge (no explanation needed)
    - Have a definition in the same or next sentence
    - Have a link to an explanation

    The checker loads a jargon database from YAML config and
    provides recommendations for making content more accessible.
    """

    # Patterns that indicate a definition follows
    DEFINITION_PATTERNS = [
        r"\s+stands\s+for\s+",
        r"\s+means\s+",
        r"\s+refers\s+to\s+",
        r"\s+is\s+defined\s+as\s+",
        r"\s+is\s+a\s+",
        r"\s+are\s+",
        r":\s*",
        r"\s*-\s*",
        r"\(",
        r"\[",
    ]

    # Link patterns that indicate explanation
    LINK_PATTERNS = [
        r"\[.*?\]\(.*?\)",  # Markdown links
        r"https?://[^\s]+",  # URLs
    ]

    def __init__(self, config_path: str = "config/tech_jargon.yaml") -> None:
        """
        Initialize the jargon checker.

        Args:
            config_path: Path to the jargon config YAML file
        """
        self.config_path = config_path
        self._jargon_db: dict[str, dict[str, Any]] = {}
        self._definitions: dict[str, str] = {}
        self._definition_patterns: list[str] = []
        self._load_config()
        self._compile_patterns()

    def _load_config(self) -> None:
        """Load jargon database from YAML config."""
        config_file = Path(self.config_path)

        if not config_file.exists():
            logger.warning(f"Jargon config not found: {self.config_path}")
            return

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            jargon_list = config.get("jargon", [])
            for item in jargon_list:
                term = item.get("term", "")
                if term:
                    key = term.lower()
                    self._jargon_db[key] = {
                        "term": term,
                        "category": item.get("category", "general"),
                        "common_knowledge": item.get("common_knowledge", False),
                        "definition": item.get("definition", ""),
                        "aliases": item.get("aliases", []),
                    }

                    # Store definition for lookup
                    if item.get("definition"):
                        self._definitions[term.lower()] = item["definition"]

            self._definition_patterns = config.get("definition_patterns", [])
            logger.info(f"Loaded {len(self._jargon_db)} jargon terms from config")

        except Exception as e:
            logger.error(f"Failed to load jargon config: {e}")

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self._compiled_definition_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DEFINITION_PATTERNS
        ]
        self._compiled_link_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.LINK_PATTERNS
        ]

    def check(self, text: str) -> JargonReport:
        """
        Check text for jargon accessibility.

        Args:
            text: Text to analyze

        Returns:
            JargonReport with findings
        """
        report = JargonReport()

        if not text or not text.strip():
            return report

        # Find all jargon terms in text
        jargon_terms = self._find_jargon_terms(text)

        # Check each term for definition/explanation
        for term in jargon_terms:
            if term.is_common_knowledge:
                term.has_definition = True  # Common knowledge counts as explained
            else:
                term.has_definition = self._check_has_definition(text, term)

            report.jargon_terms.append(term)

            if not term.has_definition:
                report.unexplained_count += 1

        # Generate recommendations for unexplained terms
        report.recommendations = self._generate_recommendations(report.jargon_terms)

        # Pass check if no unexplained jargon
        report.passes_check = report.unexplained_count == 0

        return report

    def _find_jargon_terms(self, text: str) -> list[JargonTerm]:
        """
        Find all jargon terms in text.

        Args:
            text: Text to search

        Returns:
            List of JargonTerm objects
        """
        terms: list[JargonTerm] = []
        found_positions: set[tuple[str, int]] = set()  # Track (term, position) to avoid duplicates

        for term_key, term_info in self._jargon_db.items():
            term = term_info["term"]

            # Create pattern to match the term (word boundary)
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)

            for match in pattern.finditer(text):
                position = match.start()

                # Avoid duplicate entries for same position
                pos_key = (term.lower(), position)
                if pos_key in found_positions:
                    continue
                found_positions.add(pos_key)

                # Extract context (surrounding text)
                context = self._extract_context(text, position, len(term))

                jargon_term = JargonTerm(
                    term=term,
                    position=position,
                    is_common_knowledge=term_info.get("common_knowledge", False),
                    has_definition=False,  # Will be checked later
                    context=context,
                    definition=term_info.get("definition"),
                    category=term_info.get("category"),
                )
                terms.append(jargon_term)

            # Also check aliases
            for alias in term_info.get("aliases", []):
                alias_pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
                for match in alias_pattern.finditer(text):
                    position = match.start()
                    pos_key = (term.lower(), position)
                    if pos_key in found_positions:
                        continue
                    # Mark alias position but track as main term
                    found_positions.add(pos_key)

        # Sort by position
        terms.sort(key=lambda t: t.position)

        return terms

    def _extract_context(self, text: str, position: int, term_length: int, context_chars: int = 50) -> str:
        """
        Extract context around a jargon term.

        Args:
            text: Full text
            position: Start position of term
            term_length: Length of the term
            context_chars: Number of characters to include on each side

        Returns:
            Context string with the term in the middle
        """
        start = max(0, position - context_chars)
        end = min(len(text), position + term_length + context_chars)
        return text[start:end]

    def _check_has_definition(self, text: str, term: JargonTerm) -> bool:
        """
        Check if a jargon term has a definition nearby.

        Checks:
        - Definition in the same sentence
        - Definition in the next sentence
        - Link to explanation nearby

        Args:
            text: Full text
            term: JargonTerm to check

        Returns:
            True if definition/explanation found
        """
        term_lower = term.term.lower()
        term_info = self._jargon_db.get(term_lower, {})
        definition = term_info.get("definition", "")
        aliases = term_info.get("aliases", [])

        # Get the sentence containing the term and adjacent sentences
        sentences = self._get_sentences_around(text, term.position)

        for i, sentence in enumerate(sentences):
            # Check if this sentence contains the term
            term_in_sentence = (
                re.search(rf"\b{re.escape(term.term)}\b", sentence, re.IGNORECASE) is not None
            )

            if term_in_sentence:
                # Check for definition patterns in same or next sentence
                if self._has_definition_pattern(sentence, term.term, definition, aliases):
                    return True

                # Check next sentence for definition
                if i + 1 < len(sentences):
                    next_sentence = sentences[i + 1]
                    if self._has_definition_pattern(next_sentence, term.term, definition, aliases):
                        return True

                # Check previous sentence for definition (definition before term)
                if i > 0:
                    prev_sentence = sentences[i - 1]
                    if self._has_definition_pattern(prev_sentence, term.term, definition, aliases):
                        return True

                # Check for links in same sentence
                if self._has_link(sentence):
                    return True

        return False

    def _get_sentences_around(self, text: str, position: int) -> list[str]:
        """
        Get sentences around a position in text.

        Args:
            text: Full text
            position: Position to center around

        Returns:
            List of sentences (current, previous, next)
        """
        # Split text into sentences
        # This is a simple split - could be improved with NLP
        sentences = re.split(r"(?<=[.!?])\s+", text)

        # Find which sentence contains the position
        current_pos = 0
        target_idx = 0
        for i, sentence in enumerate(sentences):
            sentence_end = current_pos + len(sentence)
            if current_pos <= position < sentence_end:
                target_idx = i
                break
            current_pos = sentence_end + 1  # +1 for the space after split

        # Return previous, current, and next sentences
        result = []
        for offset in [-1, 0, 1]:
            idx = target_idx + offset
            if 0 <= idx < len(sentences):
                result.append(sentences[idx])

        return result

    def _has_definition_pattern(self, sentence: str, term: str, definition: str, aliases: list[str]) -> bool:
        """
        Check if sentence contains a definition pattern for the term.

        Args:
            sentence: Sentence to check
            term: The jargon term
            definition: Expected definition from config
            aliases: Alternative names/definitions

        Returns:
            True if definition pattern found
        """
        # Check if the definition text appears in the sentence
        if definition and definition.lower() in sentence.lower():
            return True

        # Check if any alias appears in the sentence
        for alias in aliases:
            if alias.lower() in sentence.lower():
                return True

        # Check if term appears with a definition pattern
        # Pattern: "term (definition)" or "term - definition" or "term: definition"
        for pattern in self._compiled_definition_patterns:
            if pattern.search(sentence):
                # Check if the pattern is near the term
                term_match = re.search(rf"\b{re.escape(term)}\b", sentence, re.IGNORECASE)
                if term_match:
                    pattern_match = pattern.search(sentence)
                    if pattern_match:
                        # Pattern should appear after the term (within 30 chars)
                        if 0 < pattern_match.start() - term_match.end() < 30:
                            return True

        return False

    def _has_link(self, sentence: str) -> bool:
        """
        Check if sentence contains a link.

        Args:
            sentence: Sentence to check

        Returns:
            True if link found
        """
        for pattern in self._compiled_link_patterns:
            if pattern.search(sentence):
                return True
        return False

    def _generate_recommendations(self, terms: list[JargonTerm]) -> list[str]:
        """
        Generate recommendations for unexplained jargon terms.

        Args:
            terms: List of JargonTerm objects

        Returns:
            List of recommendation strings
        """
        recommendations = []
        unexplained = [t for t in terms if not t.has_definition]

        if not unexplained:
            return recommendations

        # Group by term to avoid duplicates
        seen_terms: set[str] = set()

        for term in unexplained:
            if term.term.lower() in seen_terms:
                continue
            seen_terms.add(term.term.lower())

            definition = term.definition
            if definition:
                recommendations.append(
                    f'Add explanation for "{term.term}": e.g., "{term.term} ({definition})"'
                )
            else:
                recommendations.append(
                    f'Add explanation for technical term "{term.term}" in same or next sentence'
                )

        if len(unexplained) > 0:
            recommendations.append(
                "Consider adding a glossary section or links to external resources for technical terms"
            )

        return recommendations

    @property
    def grade(self) -> str:
        """
        Get grade description for the checker.

        Returns:
            Description of the jargon checker
        """
        return "JargonChecker - Technical jargon accessibility checker"


# Configuration schema
JARGON_CHECKER_CONFIG_SCHEMA = {
    "jargon_checker": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable jargon accessibility checking",
        },
        "config_path": {
            "type": "str",
            "default": "config/tech_jargon.yaml",
            "description": "Path to jargon config YAML file",
        },
        "flag_all_jargon": {
            "type": "bool",
            "default": False,
            "description": "Flag all jargon even if explained",
        },
    }
}
