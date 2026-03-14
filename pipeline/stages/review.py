"""
Review stage.

Performs editorial review on generated content.
"""

from __future__ import annotations

from typing import Any

from core.events import EventType
from pipeline.editor_review import EditorReviewer
from .base import BaseStage


class ReviewStage(BaseStage):
    """Performs editorial review on generated content."""

    def __init__(self, event_bus, reviewer: EditorReviewer):
        super().__init__(event_bus)
        self.reviewer = reviewer

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Review generated content."""
        generated = context.get("generated")
        if not generated:
            return context

        content = generated.content
        result = await self.reviewer.review_with_ai(content)

        self.emit_event(
            EventType.POST_REVIEWED,
            {
                "approved": result.approved,
                "score": result.score,
                "improved_content": result.improved_content,
                "concerns": result.remaining_concerns,
            },
        )

        context["editor_result"] = result
        return context
