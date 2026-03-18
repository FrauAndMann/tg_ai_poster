"""
Editor Agent for style, tone, and flow improvements.

Part of the pipeline architecture:
[Writer] -> [Conciseness Agent] -> [FactChecker Agent] -> [Content Validator]
    -> [Editor Agent] -> [Quality Scorer] -> [Publisher]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from core.logger import get_logger
from llm.base import BaseLLMAdapter

logger = get_logger(__name__)


# AI-typical phrases that should be removed
AI_FILLER_PHRASES = [
    # Russian AI cliches
    "в современном мире",
    "на сегодняшний день",
    "в наши дни",
    "в настоящее время",
    "стоит отметить",
    "важно отметить",
    "важно понимать",
    "следует подчеркнуть",
    "не секрет что",
    "как известно",
    "в заключение",
    "для подведения итогов",
    "в данной статье",
    "в этом посте мы рассмотрим",
    "хотелось бы отметить",
    "интересно отметить",
    "безусловно",
    "несомненно",
    "естественно",
    "разумеется",
    "весьма",
    "крайне",
]

# Generic opening phrases
GENERIC_OPENINGS = [
    "знаете ли вы что",
    "знаете ли вы, что",
    "задумывались ли вы",
    "сегодня мы поговорим о",
    "давайте поговорим о",
    "в этом посте мы",
    "здесь мы рассмотрим",
    "рассмотрим подробнее",
]

# Weak transitions
WEAK_TRANSITIONS = [
    "кроме того",
    "более того",
    "также стоит",
    "необходимо упомянуть",
    "следует добавить",
]


@dataclass
class EditChange:
    """
    Represents a single edit change.

    Attributes:
        type: Type of change ("tone", "flow", "hook", "clarity")
        original: Original text fragment
        edited: Edited text fragment (empty if removed)
        reason: Reason for the change
    """
    type: str  # "tone", "flow", "hook", "clarity"
    original: str
    edited: str
    reason: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "original": self.original,
            "edited": self.edited,
            "reason": self.reason,
        }


@dataclass
class EditResult:
    """
    Result of editing operation.

    Attributes:
        original_text: The original input text
        edited_text: The improved/edited text
        changes: List of changes made
        style_score: Style quality score (0-100)
    """
    original_text: str
    edited_text: str
    changes: List[EditChange] = field(default_factory=list)
    style_score: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "original_text": self.original_text,
            "edited_text": self.edited_text,
            "changes": [c.to_dict() for c in self.changes],
            "style_score": self.style_score,
        }


class EditorAgent:
    """
    Editor Agent for improving text style, tone, and flow.

    Performs rule-based improvements by default, with optional
    LLM-assisted editing for more sophisticated improvements.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        llm_adapter: Optional[BaseLLMAdapter] = None,
        prompts_dir: str | Path = "llm/prompts",
    ) -> None:
        """
        Initialize Editor Agent.

        Args:
            model: LLM model to use for AI-assisted editing
            llm_adapter: Optional LLM adapter for AI-assisted editing
            prompts_dir: Directory containing prompt templates
        """
        self.model = model
        self.llm = llm_adapter
        self.prompts_dir = Path(prompts_dir)

        # Load prompt template
        self._load_prompt_template()

    def _load_prompt_template(self) -> None:
        """Load editor prompt template from file."""
        prompt_file = self.prompts_dir / "editor_agent.txt"
        if prompt_file.exists():
            self.prompt_template = prompt_file.read_text(encoding="utf-8")
        else:
            # Fallback template
            self.prompt_template = """Edit the following text to improve style, tone, and flow.

Original text:
{text}

Edited version:"""

    def edit(self, text: str) -> EditResult:
        """
        Perform rule-based editing on text.

        Args:
            text: Text to edit

        Returns:
            EditResult with edited text and changes
        """
        if not text or not text.strip():
            return EditResult(
                original_text=text,
                edited_text=text,
                changes=[],
                style_score=0.0,
            )

        changes: List[EditChange] = []
        edited = text

        # 1. Remove AI filler phrases
        edited, filler_changes = self._remove_filler_phrases(edited)
        changes.extend(filler_changes)

        # 2. Fix generic openings
        edited, opening_changes = self._fix_generic_openings(edited)
        changes.extend(opening_changes)

        # 3. Improve weak transitions
        edited, transition_changes = self._improve_transitions(edited)
        changes.extend(transition_changes)

        # 4. Clean up whitespace
        edited = self._clean_whitespace(edited)

        # Calculate style score
        style_score = self._calculate_style_score(edited)

        return EditResult(
            original_text=text,
            edited_text=edited,
            changes=changes,
            style_score=style_score,
        )

    async def edit_async(self, text: str) -> EditResult:
        """
        Perform AI-assisted editing using LLM.

        Args:
            text: Text to edit

        Returns:
            EditResult with edited text and changes
        """
        # First do rule-based editing
        base_result = self.edit(text)

        # If no LLM, return base result
        if not self.llm:
            return base_result

        try:
            prompt = self.prompt_template.format(text=text)

            response = await self.llm.generate(prompt)
            edited_text = response.content.strip()

            if not edited_text:
                logger.warning("LLM returned empty response, using base result")
                return base_result

            # Extract changes by comparing
            changes = self._extract_changes(text, edited_text)

            # Calculate style score
            style_score = self._calculate_style_score(edited_text)

            return EditResult(
                original_text=text,
                edited_text=edited_text,
                changes=changes,
                style_score=style_score,
            )

        except Exception as e:
            logger.error(f"LLM editing failed: {e}")
            return base_result

    def _remove_filler_phrases(self, text: str) -> tuple[str, List[EditChange]]:
        """Remove AI-typical filler phrases."""
        changes: List[EditChange] = []
        result = text

        for phrase in AI_FILLER_PHRASES:
            # Case-insensitive search
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            match = pattern.search(result)

            if match:
                original_fragment = match.group()
                result = pattern.sub("", result)
                changes.append(EditChange(
                    type="tone",
                    original=original_fragment,
                    edited="",
                    reason=f"Removed AI filler phrase: '{phrase}'"
                ))

        return result, changes

    def _fix_generic_openings(self, text: str) -> tuple[str, List[EditChange]]:
        """Fix generic opening phrases."""
        changes: List[EditChange] = []
        result = text

        # Check first 200 characters for openings
        first_part = result[:300].lower()

        for opening in GENERIC_OPENINGS:
            if opening in first_part:
                # Find the actual text (with original case)
                pattern = re.compile(re.escape(opening), re.IGNORECASE)
                match = pattern.search(result)

                if match:
                    original_fragment = match.group()
                    result = pattern.sub("", result, count=1)
                    changes.append(EditChange(
                        type="hook",
                        original=original_fragment,
                        edited="",
                        reason="Removed generic opening phrase"
                    ))
                    break  # Only fix first opening

        return result, changes

    def _improve_transitions(self, text: str) -> tuple[str, List[EditChange]]:
        """Identify weak transitions for improvement."""
        changes: List[EditChange] = []
        result = text

        for transition in WEAK_TRANSITIONS:
            pattern = re.compile(re.escape(transition), re.IGNORECASE)
            match = pattern.search(result)

            if match:
                original_fragment = match.group()
                # Mark for improvement but don't remove (context needed)
                changes.append(EditChange(
                    type="flow",
                    original=original_fragment,
                    edited=original_fragment,  # Keep as-is in rule-based mode
                    reason="Weak transition detected - consider improving"
                ))

        return result, changes

    def _clean_whitespace(self, text: str) -> str:
        """Clean up whitespace issues."""
        result = text

        # Remove double spaces
        result = re.sub(r" +", " ", result)

        # Fix multiple newlines (more than 2)
        result = re.sub(r"\n{3,}", "\n\n", result)

        # Remove leading/trailing whitespace from lines
        lines = result.split("\n")
        lines = [line.strip() for line in lines]
        result = "\n".join(lines)

        return result.strip()

    def _extract_changes(self, original: str, edited: str) -> List[EditChange]:
        """
        Extract changes by comparing original and edited texts.

        Uses simple heuristics to identify what changed.
        """
        changes: List[EditChange] = []

        # Split into words for comparison
        original_words = set(original.lower().split())
        edited_words = set(edited.lower().split())

        # Find removed words
        removed = original_words - edited_words
        for word in removed:
            if len(word) > 4:  # Skip short words
                # Find the original context
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                match = pattern.search(original)
                if match:
                    changes.append(EditChange(
                        type="tone",
                        original=word,
                        edited="",
                        reason=f"Removed: '{word}'"
                    ))

        # Find added words
        added = edited_words - original_words
        for word in added:
            if len(word) > 4:  # Skip short words
                changes.append(EditChange(
                    type="clarity",
                    original="",
                    edited=word,
                    reason=f"Added: '{word}'"
                ))

        # Limit changes to avoid noise
        return changes[:10]

    def _calculate_style_score(self, text: str) -> float:
        """
        Calculate style quality score.

        Score based on:
        - Absence of filler phrases
        - Text length appropriateness
        - Presence of specific facts/numbers
        - Sentence variety
        """
        if not text or not text.strip():
            return 0.0

        score = 80.0  # Base score

        text_lower = text.lower()

        # Penalize filler phrases
        for phrase in AI_FILLER_PHRASES:
            if phrase in text_lower:
                score -= 5

        # Penalize generic openings
        for opening in GENERIC_OPENINGS:
            if opening in text_lower[:300]:
                score -= 10

        # Penalize weak transitions
        for transition in WEAK_TRANSITIONS:
            if transition in text_lower:
                score -= 3

        # Bonus for specific content
        if re.search(r'\d+', text):  # Contains numbers
            score += 5
        if re.search(r'[$€₽]', text):  # Contains currency
            score += 3
        if re.search(r'\d{4}', text):  # Contains year
            score += 3
        if re.search(r'\d+%', text):  # Contains percentage
            score += 3

        # Word count check
        word_count = len(text.split())
        if word_count < 20:
            score -= 20
        elif word_count > 500:
            score -= 10
        elif 50 <= word_count <= 300:
            score += 5  # Optimal length

        # Ensure score is in bounds
        return max(0.0, min(100.0, score))
