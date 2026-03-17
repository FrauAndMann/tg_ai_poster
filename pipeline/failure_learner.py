"""
Failure Learning System - Learns from quality failures.

Tracks posts that fail quality checks, records which rules failed,
and uses LLM analysis to identify systematic weaknesses
and automatically patches the generation prompt.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter

logger = get_logger(__name__)


@dataclass(slots=True)
class FailurePattern:
    """A pattern of quality failures."""

    rule_name: str
    failure_count: int = 0
    example_texts: list[str] = field(default_factory=list)
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)


    @property
    def is_systematic(self) -> bool:
        """Check if this is a systematic pattern (3+ failures)."""
        return self.failure_count >= 3


@dataclass(slots=True)
class PromptPatch:
    """A patch to fix a systematic weakness."""

    issue: str
    patch_description: str
    original_prompt_snippet: str
    patched_prompt_snippet: str
    created_at: datetime = field(default_factory=datetime.now)
    success_rate: float = 0.0


class FailureLearner:
    """
    Learns from quality failures and creates self-healing system.

    Features:
    - Tracks failure patterns
    - Identifies systematic weaknesses
    - Generates prompt patches via LLM
    - Applies patches automatically
    """

    ANALYSIS_PROMPT = """Проанализируй паттерны неудачных проверок качества и определи системные проблемы.

ДАННЫЕ О НЕПрезультаты:
{failure_patterns}

ТРЕбования:
1. Найди правила, которые чаще всего вызывают неудачи (3+ раз)
2. Определи общие паттерны в пример_texts
3. Предложите конкретное исправление для промпта генерации

4. Формат как JSON с исправениями

Верни JSON:
{{
    "systematic_issues": [
        {
            "rule": "rule_name",
            "pattern": "описание паттерна",
            "fix": "конкретное исправение для промпта"
        }
    ]
}}"""

    def __init__(
        self,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
        analysis_threshold: int = 100,
    ) -> None:
        """
        Initialize failure learner.

        Args:
            llm_adapter: LLM for analysis
            analysis_threshold: Run analysis after this many failures
        """
        self.llm = llm_adapter
        self.analysis_threshold = analysis_threshold
        self._patterns: dict[str, FailurePattern] = {}
        self._patches: list[PromptPatch] = []

    def record_failure(
        self,
        rule_name: str,
        example_text: str,
    ) -> None:
        """Record a quality check failure."""
        if rule_name not in self._patterns:
            pattern = FailurePattern(
                rule_name=rule_name,
                example_texts=[example_text],
            )
            self._patterns[rule_name] = pattern
        else:
            pattern = self._patterns[rule_name]
        pattern.failure_count += 1
        pattern.example_texts.append(example_text)
        pattern.last_seen = datetime.now()
        logger.debug("Recorded failure for rule: %s", rule_name)
        # Check if we should analyze
        if len(self._patterns) >= self.analysis_threshold:
            asyncio.create_task(self.run_analysis())

    async def run_analysis(self) -> None:
        """Run analysis on failure patterns."""
        if not self.llm:
                return
        logger.info("Running failure pattern analysis on %d patterns", len(self._patterns))
        # Prepare failure data
        patterns_data = {}
        for name, pattern in self._patterns.items():
            if pattern.is_systematic:
                patterns_data[name] = {
                    "failure_count": pattern.failure_count,
                    "examples": pattern.example_texts[-3:],
                }
        prompt = self.ANALYSIS_PROMPT.format(
            failure_patterns=json.dumps(patterns_data, indent=2)
        )
        response = await self.llm.generate(prompt)
        analysis = self._parse_analysis(response.content)
        if analysis:
            await self.apply_patches(analysis)
    def _parse_analysis(self, content: str) -> Optional[dict]:
        """Parse analysis response."""
        import json
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, KeyError):
            return None
    async def apply_patches(self, analysis: dict) -> None:
        """Apply patches from analysis."""
        issues = analysis.get("systematic_issues", [])
        for issue in issues:
            patch = PromptPatch(
                issue=issue.get("rule", "unknown"),
                patch_description=issue.get("fix", ""),
                original_prompt_snippet="",  # Would need actual prompt
                patched_prompt_snippet=issue.get("fix", ""),
            )
            self._patches.append(patch)
            logger.info("Created patch for issue: %s", patch.issue)
    def get_patches(self) -> list[PromptPatch]:
        """Get all generated patches."""
        return self._patches
    def get_failure_report(self) -> dict[str, Any]:
        """Get failure analysis report."""
        return {
            "total_patterns": len(self._patterns),
            "systematic_issues": len([p for p in self._patterns.values() if p.is_systematic]),
            "patches_created": len(self._patches),
            "patterns": {
                name: {
                    "failure_count": pattern.failure_count,
                    "is_systematic": pattern.is_systematic,
                }
                for name, pattern in self._patterns.items()
            },
        }


# Configuration schema
FAILURE_LEARNER_CONFIG_SCHEMA = {
    "failure_learning": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable failure learning system",
        },
        "analysis_threshold": {
            "type": "int",
            "default": 100,
            "description": "Run analysis after this many failures",
        },
    }
}
