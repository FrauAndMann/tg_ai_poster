"""
Collection stage.

Collects articles from RSS feeds, HackerNews, and ProductHunt.
"""

from __future__ import annotations

from typing import Any

from core.events import EventType
from pipeline.source_collector import SourceCollector
from .base import BaseStage


class CollectionStage(BaseStage):
    """Collects articles from configured sources."""

    def __init__(self, event_bus, collector: SourceCollector):
        super().__init__(event_bus)
        self.collector = collector

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Collect articles from all sources."""
        articles = await self.collector.collect(max_age_days=7)

        self.emit_event(
            EventType.SOURCES_COLLECTED,
            {"articles": articles, "count": len(articles)},
        )

        context["articles"] = articles
        return context
