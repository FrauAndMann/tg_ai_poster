"""
Formatting stage.

Formats post for Telegram publishing.
"""

from __future__ import annotations

from typing import Any

from core.events import EventType
from core.logger import get_logger
from plugins.formatters.telegram import TelegramFormatter
from .base import BaseStage

logger = get_logger(__name__)


class FormattingStage(BaseStage):
    """Formats post for Telegram."""

    def __init__(
        self,
        event_bus,
        formatter: TelegramFormatter,
    ):
        super().__init__(event_bus)
        self.formatter = formatter

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Format post for Telegram."""
        post = context.get("post")
        if not post:
            return context

        # Format using Telegram formatter
        formatted = self.formatter.format(post)

        # Validate formatting
        is_valid, error = self.formatter.validate(formatted.text)
        if not is_valid:
            logger.warning(f"Formatted post validation failed: {error}")

        self.emit_event(
            EventType.POST_FORMATTED,
            {
                "content": formatted.text,
                "valid": is_valid,
                "error": error,
            },
        )

        context["formatted_content"] = formatted.text
        return context
