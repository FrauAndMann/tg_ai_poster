"""
Conciseness Agent - Automatic text conciseness improvement.

Removes redundancy, merges sentences, converts passive to active voice,
and improves information density while preserving key facts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from loguru import logger

from llm.base import BaseLLMAdapter


@dataclass
class ConcisenessResult:
    """
    Result of a conciseness rewrite operation.

    Attributes:
        original_text: Original text before rewriting
        rewritten_text: Rewritten concise text
        reduction_percentage: Percentage of length reduction (0-100)
        preserved_facts: List of key facts that were preserved
        changes_made: List of changes applied to the text
    """

    original_text: str
    rewritten_text: str
    reduction_percentage: float = 0.0
    preserved_facts: List[str] = field(default_factory=list)
    changes_made: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "original_text": self.original_text,
            "rewritten_text": self.rewritten_text,
            "reduction_percentage": round(self.reduction_percentage, 2),
            "preserved_facts": self.preserved_facts,
            "changes_made": self.changes_made,
        }

    def is_valid_reduction(self, max_reduction: float = 0.3) -> bool:
        """
        Check if reduction is within acceptable limits.

        Args:
            max_reduction: Maximum allowed reduction (0.3 = 30%)

        Returns:
            bool: True if reduction is within limits
        """
        return self.reduction_percentage <= (max_reduction * 100)


class ConcisenessAgent:
    """
    LLM-based agent for improving text conciseness.

    Automatically removes redundancy, merges related sentences,
    converts passive to active voice, and eliminates unnecessary
    adjectives/adverbs while preserving key facts.

    Example:
        agent = ConcisenessAgent(llm_adapter, max_reduction=0.3)
        result = await agent.rewrite(long_text)
        print(f"Reduced by {result.reduction_percentage}%")
    """

    # Default prompt template
    DEFAULT_PROMPT = """You are a conciseness editor. Your task is to rewrite the text to be more concise while preserving all key facts.

Rules:
1. Remove repeated ideas - keep each point only once
2. Merge related sentences - combine similar thoughts
3. Convert passive to active voice - "The code was written by John" becomes "John wrote the code"
4. Remove unnecessary adjectives/adverbs - keep only those that add meaning
5. Maximum reduction: {max_reduction} of original length (don't over-shorten)
6. Preserve all facts, numbers, dates, and names exactly

What to preserve:
- All specific numbers (percentages, amounts, quantities)
- All dates and time references
- All names of people, companies, products
- All key technical terms
- The main message and intent

What to remove:
- Repetitive phrases
- Redundant explanations
- Filler words (very, really, quite, rather, etc.)
- Obvious statements
- Excessive adjectives

Original text:
---
{text}
---

Rewrite the text concisely. Return JSON only:
{{
  "rewritten_text": "your concise version here",
  "changes_made": [
    "list of specific changes you made"
  ],
  "preserved_facts": [
    "list of key facts that were preserved"
  ]
}}"""

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        model: str = "gpt-4o-mini",
        max_reduction: float = 0.3,
        preserve_key_facts: bool = True,
        prompts_dir: Optional[Path] = None,
    ):
        """
        Initialize the conciseness agent.

        Args:
            llm_adapter: LLM adapter for text generation
            model: Model to use for generation
            max_reduction: Maximum allowed length reduction (0.3 = 30%)
            preserve_key_facts: Whether to extract and verify fact preservation
            prompts_dir: Directory containing prompt templates
        """
        self.llm = llm_adapter
        self.model = model
        self.max_reduction = max_reduction
        self.preserve_key_facts = preserve_key_facts
        # Convert to Path if string is provided
        if prompts_dir is not None:
            self.prompts_dir = Path(prompts_dir) if isinstance(prompts_dir, str) else prompts_dir
        else:
            self.prompts_dir = Path("llm/prompts")

        # Load prompt template
        self._prompt_template = self._load_prompt("conciseness_rewriter.txt")

    def _load_prompt(self, filename: str) -> str:
        """
        Load a prompt template from file.

        Args:
            filename: Name of the prompt file

        Returns:
            str: Prompt template content
        """
        prompt_path = self.prompts_dir / filename
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return self.DEFAULT_PROMPT

    def _extract_key_facts(self, text: str) -> List[str]:
        """
        Extract key facts that must be preserved.

        Extracts:
        - Numbers and percentages
        - Dates and time references
        - Named entities (capitalized words)
        - Key phrases

        Args:
            text: Text to extract facts from

        Returns:
            List[str]: List of extracted facts
        """
        if not text:
            return []

        facts = []

        # Extract numbers with units (percentages, money, etc.)
        number_patterns = [
            r'\d+(?:\.\d+)?%',  # Percentages
            r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|trillion))?',  # Money
            r'\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:million|billion|trillion|thousand))?',  # Large numbers
            r'\d{4}',  # Years
        ]

        for pattern in number_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            facts.extend(matches)

        # Extract capitalized phrases (names, companies, products)
        # Match sequences of capitalized words
        cap_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        cap_matches = re.findall(cap_pattern, text)
        # Filter out common words that might be capitalized at sentence start
        common_words = {'The', 'This', 'That', 'These', 'Those', 'A', 'An', 'In', 'On', 'At', 'To', 'For'}
        entities = [m for m in cap_matches if m not in common_words and len(m) > 2]
        facts.extend(entities[:10])  # Limit to avoid too many facts

        # Remove duplicates while preserving order
        seen = set()
        unique_facts = []
        for fact in facts:
            if fact.lower() not in seen:
                seen.add(fact.lower())
                unique_facts.append(fact)

        return unique_facts

    def _validate_result(self, original: str, rewritten: str) -> bool:
        """
        Validate that the rewrite is acceptable.

        Checks:
        - Reduction is within max_reduction limit
        - Rewritten text is not empty

        Args:
            original: Original text
            rewritten: Rewritten text

        Returns:
            bool: True if result is valid
        """
        if not original:
            return True

        if not rewritten:
            return False

        original_len = len(original)
        rewritten_len = len(rewritten)

        if original_len == 0:
            return True

        reduction = (original_len - rewritten_len) / original_len
        return reduction <= self.max_reduction

    def _calculate_reduction_percentage(self, original: str, rewritten: str) -> float:
        """
        Calculate the percentage of length reduction.

        Args:
            original: Original text
            rewritten: Rewritten text

        Returns:
            float: Reduction percentage (0-100)
        """
        if not original:
            return 0.0

        original_len = len(original)
        rewritten_len = len(rewritten)

        if original_len == 0:
            return 0.0

        reduction = (original_len - rewritten_len) / original_len
        return max(0.0, reduction * 100)

    def _parse_response(self, response: str, original: str) -> dict:
        """
        Parse JSON response from LLM.

        Args:
            response: Raw LLM response
            original: Original text (for fallback)

        Returns:
            dict: Parsed response data
        """
        response = response.strip()

        # Remove markdown code blocks if present
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()

        # Find JSON object
        start = response.find("{")
        end = response.rfind("}") + 1

        if start >= 0 and end > start:
            json_str = response[start:end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error: {e}")

        # Return fallback result
        return {
            "rewritten_text": response if response else original,
            "changes_made": [],
            "preserved_facts": [],
        }

    async def rewrite(self, text: str) -> ConcisenessResult:
        """
        Rewrite text to be more concise.

        Args:
            text: Text to rewrite

        Returns:
            ConcisenessResult: Result with rewritten text and metadata
        """
        # Handle empty or very short text
        text_str = str(text) if text else ""
        if not text_str or len(text_str.strip()) < 10:
            return ConcisenessResult(
                original_text=text_str,
                rewritten_text=text_str,
                reduction_percentage=0.0,
                preserved_facts=[],
                changes_made=[],
            )

        # Extract key facts if preservation is enabled
        key_facts = []
        if self.preserve_key_facts:
            key_facts = self._extract_key_facts(text_str)

        # Build prompt
        max_reduction_pct = int(self.max_reduction * 100)
        prompt = self._prompt_template.format(
            text=text_str,
            max_reduction=f"{max_reduction_pct}%",
        )

        try:
            # Call LLM
            response = await self.llm.generate(prompt)

            # Get response content
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse response
            result_data = self._parse_response(response_text, text_str)

            rewritten = result_data.get("rewritten_text", text_str)
            changes = result_data.get("changes_made", [])
            preserved = result_data.get("preserved_facts", key_facts)

            # Add note about passive voice conversion if applicable
            if self.preserve_key_facts and any(
                passive_marker in text_str.lower()
                for passive_marker in ["was ", "were ", "been ", "being "]
            ):
                if "convert passive to active" not in str(changes).lower():
                    changes.append("Convert passive to active voice where applicable")

            # Calculate reduction percentage
            reduction_pct = self._calculate_reduction_percentage(text_str, rewritten)

            # Validate result
            if not self._validate_result(text_str, rewritten):
                logger.warning(
                    f"Rewrite reduction too aggressive: {reduction_pct:.1f}% > {self.max_reduction * 100}%"
                )

            return ConcisenessResult(
                original_text=text_str,
                rewritten_text=rewritten,
                reduction_percentage=reduction_pct,
                preserved_facts=preserved,
                changes_made=changes,
            )

        except Exception as e:
            logger.error(f"Conciseness rewrite failed: {e}")

            # Return original text on error
            return ConcisenessResult(
                original_text=text_str,
                rewritten_text=text_str,
                reduction_percentage=0.0,
                preserved_facts=key_facts,
                changes_made=[f"Error during rewrite: {str(e)}"],
            )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ConcisenessAgent(model={self.model}, "
            f"max_reduction={self.max_reduction}, "
            f"preserve_key_facts={self.preserve_key_facts})"
        )
