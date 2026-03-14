"""
Generation stage.

Generates post content using LLM.
"""

from __future__ import annotations

from typing import Any

from core.events import EventType
from pipeline.llm_generator import LLMGenerator
from pipeline.orchestrator import parse_json_post
from .base import BaseStage


class GenerationStage(BaseStage):
    """Generates post content."""

    def __init__(self, event_bus, generator: LLMGenerator):
        super().__init__(event_bus)
        self.generator = generator

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Generate post content."""
        topic = context.get("topic", "")
        topic_meta = context.get("topic_meta", {})

        # Prepare source context
        source_context = None
        if topic_meta and topic_meta.get("source_article"):
            article = topic_meta["source_article"]
            source_context = f"Source: {article.get('source', '')}\n{article.get('summary', '')}"

        # Generate post
        post = await self.generator.generate_with_retry(
            topic=topic,
            source_context=source_context,
        )

        # Parse JSON response if needed
        post_data = parse_json_post(post.content)
        post.parsed_data = post_data

        self.emit_event(
            EventType.POST_GENERATED,
            {
                "content": post.content,
                "model": post.model,
                "tokens_used": post.tokens_used,
                "parsed_data": post_data,
            },
        )

        context["generated_post"] = post
        context["post_data"] = post_data
        return context
