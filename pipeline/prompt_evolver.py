"""
Prompt Evolution System - Evolves generation prompts based on performance.

Treats prompts as evolving artifacts. Analyzes high vs low engagement posts,
uses LLM to generate improved variants, and runs A/B tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter
    from pipeline.ab_test_manager import ABTestManager

logger = get_logger(__name__)


@dataclass(slots=True)
class PromptVariant:
    """A generation prompt variant."""

    id: str
    name: str
    prompt_text: str
    version: int = 1
    parent_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    performance_score: float = 0.0
    posts_generated: int = 0
    avg_engagement: float = 0.0
    is_active: bool = True
    improvement_reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "performance_score": self.performance_score,
            "posts_generated": self.posts_generated,
            "avg_engagement": self.avg_engagement,
            "is_active": self.is_active,
        }


class PromptEvolver:
    """
    Dynamic prompt evolution system.

    Features:
    - Tracks prompt performance
    - Generates improved variants via LLM
    - A/B tests new variants
    - Auto-selects best performers
    """

    ANALYSIS_PROMPT = """Проанализируй промпты генерации постов и предложи улучшения.

МЕТРИКА:
- Высокая вовлеченность (топ 20%): {high_performing_prompts}
- Низкая вовлеченность (низ 20%): {low_performing_prompts}

ЧАСТОТЫ ИСПОЛЬЗОВАНИЯ:
{usage_stats}

ПРОАНАЛИЗИРУЙ:
1. Какие фразы чаще встречаются в успешных промптах?
2. Какие элементы отсутствуют в неуспешных?
3. Какие структурные паттерны работают лучше?

Верни JSON:
{{
    "improvements": [
        {
            "area": "hook" | "body" | "analysis" | "tldr",
            "suggestion": "конкретное предложение",
            "reasoning": "почему это улучшит"
        }
    ],
    "new_prompt_variant": "улучшенная версия промпта с изменениями"
}}"""

    EVOLUTION_PROMPT = """Создай улучшенную версию промпта генерации постов на основе анализа.

ТЕКУЩИЙ ПРООМПТ:
{current_prompt}

УЛУЧШЕНИЯ:
{improvements}

ПРАВИЛА:
1. Сохрани я структуру и базовый шаблон
2. Внеси улучшения в указанные области
3. Добавь специфические инструкции для каждой области
4. Убери клише и AI-фразы

5. Сделай промпт более конкретным и практичным

Верни только улучшенный промпт, без объяснений."""

    def __init__(
        self,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
        ab_manager: Optional["ABTestManager"] = None,
        prompts_path: str = "llm/prompts",
        analysis_interval: int = 50,
    ) -> None:
        """
        Initialize prompt evolver.

        Args:
            llm_adapter: LLM for analysis
            ab_manager: A/B test manager
            prompts_path: Path to prompts directory
            analysis_interval: Posts between analysis cycles
        """
        self.llm = llm_adapter
        self.ab_manager = ab_manager
        self.prompts_path = Path(prompts_path)
        self.analysis_interval = analysis_interval

        self._variants: dict[str, PromptVariant] = {}
        self._current_best: Optional[str] = None
        self._last_analysis: Optional[datetime] = None
        self._posts_since_analysis: int = 0

    def load_prompt(self, name: str) -> Optional[str]:
        """Load a prompt from file."""
        prompt_file = self.prompts_path / f"{name}.txt"
        if not prompt_file.exists():
            logger.warning("Prompt file not found: %s", prompt_file)
            return None
        return prompt_file.read_text(encoding="utf-8")

    def save_prompt(self, name: str, content: str, variant_id: Optional[str] = None) -> bool:
        """Save a prompt variant to file."""
        if variant_id:
            filename = f"{name}_v{variant_id}.txt"
        else:
            filename = f"{name}.txt"
        path = self.prompts_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info("Saved prompt variant: %s", filename)
        return True
    def record_performance(
        self,
        prompt_id: str,
        engagement_score: float,
    ) -> None:
        """Record performance for a prompt variant."""
        if prompt_id not in self._variants:
            return
        variant = self._variants[prompt_id]
        variant.posts_generated += 1
        # Running average engagement
        current_avg = variant.avg_engagement
        n = variant.posts_generated
        variant.avg_engagement = (current_avg * (n - 1) + engagement_score) / n
        # Update performance score
        variant.performance_score = variant.avg_engagement * (1 + variant.posts_generated / 100)
        self._posts_since_analysis += 1
    def should_analyze(self) -> bool:
        """Check if it's time for analysis."""
        if self._posts_since_analysis < self.analysis_interval:
            return False
        if self._last_analysis is None:
            return True
        days_since = (datetime.now() - self._last_analysis).days
        return days_since >= 1  # Analyze daily
    async def run_analysis(self) -> None:
        """Run prompt performance analysis and generate improvements."""
        if not self.llm:
            logger.warning("No LLM adapter for analysis")
            return
        logger.info("Running prompt evolution analysis")
        # Get high and low performing prompts
        high_performers = [
            v for v in self._variants.values()
            if v.performance_score >= 0.7
        ]
        low_performers = [
            v for v in self._variants.values()
            if v.performance_score < 0.3
        ]
        if not high_performers or not low_performers:
            return
        # Build usage stats
        usage_stats = {}
        for v in self._variants.values():
            usage_stats[v.name] = {
                "posts": v.posts_generated,
                "avg_engagement": v.avg_engagement,
            }
        # Run analysis
        prompt = self.ANALYSIS_PROMPT.format(
            high_performing_prompts="\n".join(v.prompt_text[:500] for v in high_performers[:3]),
            low_performing_prompts="\n".join(v.prompt_text[:500] for v in low_performers[:3]),
            usage_stats=json.dumps(usage_stats),
        )
        response = await self.llm.generate(prompt)
        analysis = self._parse_analysis(response.content)
        if analysis:
            await self._apply_improvements(analysis)
        self._last_analysis = datetime.now()
        self._posts_since_analysis = 0
    def _parse_analysis(self, content: str) -> Optional[dict]:
        """Parse analysis response."""
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, KeyError):
            return None
    async def _apply_improvements(self, analysis: dict) -> None:
        """Apply improvements from analysis."""
        improvements = analysis.get("improvements", [])
        new_prompt_text = analysis.get("new_prompt_variant")
        if not new_prompt_text:
            return
        # Create new variant
        import uuid
        variant_id = str(uuid.uuid4())[:8]
        current_version = max(v.version for v in self._variants.values()) + 1
        new_variant = PromptVariant(
            id=variant_id,
            name="post_generator_evolved",
            prompt_text=new_prompt_text,
            version=current_version + 1,
            parent_id=self._current_best,
            improvement_reason="; ".join(
                f"{i['area']}: {i['suggestion']}"
                for i in improvements[:3]
            ),
        )
        self._variants[variant_id] = new_variant
        self.save_prompt("post_generator", new_prompt_text, variant_id)
        # Start A/B test if manager available
        if self.ab_manager:
            await self.ab_manager.create_experiment(
                name=f"prompt_evolution_{datetime.now().strftime('%Y%m%d')}",
                description=f"Testing evolved prompt variant {variant_id}",
                variants={
                    "control": self._current_best or "original",
                    "treatment": variant_id,
                },
            )
        logger.info("Created evolved prompt variant: %s", variant_id)
    def get_best_prompt(self) -> Optional[str]:
        """Get current best performing prompt."""
        if not self._variants:
            return None
        best = max(self._variants.values(), key=lambda v: v.performance_score)
        return best.prompt_text if best else None
    def get_prompt_for_post(self, post_type: str = "analysis") -> str:
        """Get appropriate prompt for post type."""
        # Check for evolved variant
        if self._current_best and self._current_best in self._variants:
            return self._variants[self._current_best].prompt_text
        # Fall back to file-based prompt
        prompt = self.load_prompt(f"{post_type}_generator")
        if prompt:
            return prompt
        # Ultimate fallback
        return self.load_prompt("post_generator")


# Configuration schema
PROMPT_EVOLVER_CONFIG_SCHEMA = {
    "prompt_evolution": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable prompt evolution system",
        },
        "analysis_interval": {
            "type": "int",
            "default": 50,
            "description": "Posts between analysis cycles",
        },
    }
}
