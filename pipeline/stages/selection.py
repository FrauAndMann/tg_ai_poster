"""
Selection stage.

Selects topic from collected articles using LLM.
"""

from __future__ import annotations

from typing import Any

from core.events import EventType
from pipeline.content_filter import ContentFilter
from pipeline.topic_selector import TopicSelector
from .base import BaseStage


class SelectionStage(BaseStage):
    """Selects topic for the post."""

    def __init__(
        self,
        event_bus,
        topic_selector: TopicSelector,
        content_filter: ContentFilter,
    ):
        super().__init__(event_bus)
        self.topic_selector = topic_selector
        self.content_filter = content_filter

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Select topic from collected articles."""
        articles = context.get("articles", [])

        if not articles:
            # Generate topic from scratch
            result = await self.topic_selector.generate_topic_idea()
            topic = result.get("selected_topic", "")
            topic_meta = result
        else:
            # Score and filter articles
            scored = self.content_filter.filter_and_score(articles, top_n=5)

            if not scored:
                result = await self.topic_selector.generate_topic_idea()
                topic = result.get("selected_topic", "")
                topic_meta = result
            else:
                # Select best topic using LLM
                top_articles = [sa.article for sa in scored]
                result = await self.topic_selector.select_from_articles(top_articles)
                topic = result.get("selected_topic", "")
                topic_meta = result

        self.emit_event(
            EventType.TOPIC_SELECTED,
            {"topic": topic, "meta": topic_meta},
        )

        context["topic"] = topic
        context["topic_meta"] = topic_meta
        return context
