"""
Quality stage.

Performs quality check on generated content.
"""

from __future__ import annotations

from typing import Any

from core.events import EventType
from pipeline.quality_checker import QualityChecker
from .base import BaseStage


class QualityStage(BaseStage):
    """Performs quality check on content."""

    def __init__(self, event_bus, checker: QualityChecker):
        super().__init__(event_bus)
        self.checker = checker

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Check content quality."""
        content = context.get("content")
        if not content:
            return context

        result = await self.checker.check_with_ai(content)

        self.emit_event(
            EventType.QUALITY_CHECKED,
            {
                "approved": result.approved,
                "score": result.score,
                "issues": result.issues,
            },
        )

        context["quality_result"] = result
        return context
