"""
Media stage.

Fetches media for posts from configured providers.
"""

from __future__ import annotations

from typing import Any

from core.events import EventType
from core.logger import get_logger
from domain.post import POST_TYPE_CONFIGS
from domain.media import Media
from plugins.media.base import MediaProvider
from .base import BaseStage

logger = get_logger(__name__)


class MediaStage(BaseStage):
    """Fetches media for posts."""

    def __init__(
        self,
        event_bus,
        providers: list[MediaProvider],
    ):
        super().__init__(event_bus)
        # Sort providers by remaining rate limit
        self.providers = sorted(
            providers,
            key=lambda p: p.rate_limit[1],
            reverse=True,
        )

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Fetch media for the post."""
        post = context.get("post")
        context.get("content")

        if not post:
            return context

        config = POST_TYPE_CONFIGS.get(post.post_type)
        if not config:
            context["media"] = None
            return context

        if not config.require_media:
            context["media"] = None
            self.emit_event(
                EventType.MEDIA_FETCHED,
                {"media": None, "skipped": True},
            )
            return context

        # Try each provider
        for provider in self.providers:
            try:
                result = await provider.get_random(post.topic)
                if result:
                    media = Media(
                        url=result.url,
                        source=result.source,
                        photographer=result.photographer,
                    )

                    self.emit_event(
                        EventType.MEDIA_FETCHED,
                        {"media": media, "provider": provider.name},
                    )

                    context["media"] = media
                    return context

            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue

        # All providers failed
        logger.warning("All media providers failed")
        context["media"] = None
        self.emit_event(
            EventType.MEDIA_FETCHED,
            {"media": None, "failed": True},
        )
        return context
