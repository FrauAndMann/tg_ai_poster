"""
Pipeline factory.

Creates and wires pipeline components together.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional


from core.config import Settings
from core.events import event_bus
from core.logger import get_logger
from pipeline.coordinator import PipelineCoordinator
from pipeline.stages import (
    CollectionStage,
    SelectionStage,
    GenerationStage,
    ReviewStage,
    QualityStage,
    MediaStage,
    FormattingStage,
)
from plugins.media.unsplash import UnsplashProvider
from plugins.media.pexels import PexelsProvider
from plugins.formatters.telegram import TelegramFormatter

if TYPE_CHECKING:
    from memory.database import Database
    from publisher.base import BasePublisher

logger = get_logger(__name__)


class PipelineFactory:
    """Factory for creating pipeline components."""

    @staticmethod
    async def create_coordinator(
        settings: Settings,
        db: "Database",
        publisher: Optional["BasePublisher"] = None,
    ) -> PipelineCoordinator:
        """
        Create a fully wired pipeline coordinator.

        Args:
            settings: Application settings
            db: Database instance
            publisher: Optional publisher for posting

        Returns:
            Configured PipelineCoordinator
        """
        # Create event bus (use global or create new)
        bus = event_bus

        # Create media providers
        media_providers = []
        if settings.media and settings.media.enabled:
            if settings.media.unsplash_access_key:
                media_providers.append(
                    UnsplashProvider(access_key=settings.media.unsplash_access_key)
                )
                logger.info("Unsplash provider configured")
            if settings.media.pexels_api_key:
                media_providers.append(
                    PexelsProvider(api_key=settings.media.pexels_api_key)
                )
                logger.info("Pexels provider configured (fallback)")

        # Create formatter
        formatter = TelegramFormatter(
            parse_mode="MarkdownV2",
            max_length=4096,
        )

        # Import existing pipeline components
        from llm import get_llm_adapter
        from memory.post_store import PostStore
        from memory.topic_store import TopicStore
        from pipeline.source_collector import SourceCollector
        from pipeline.source_verification import SourceVerifier
        from pipeline.content_filter import ContentFilter
        from pipeline.topic_selector import TopicSelector
        from pipeline.llm_generator import LLMGenerator
        from pipeline.prompt_builder import PromptBuilder
        from pipeline.editor_review import EditorReviewer
        from pipeline.quality_checker import QualityChecker

        # Initialize stores
        post_store = PostStore(db)
        topic_store = TopicStore(db)

        # Create LLM adapter
        llm_kwargs = {
            "model": settings.llm.model,
            "max_tokens": settings.llm.max_tokens,
            "temperature": settings.llm.temperature,
        }
        if settings.llm.provider != "claude-cli":
            llm_kwargs["api_key"] = settings.llm.api_key
            llm_kwargs["base_url"] = settings.llm.get_base_url()

        llm = get_llm_adapter(provider=settings.llm.provider, **llm_kwargs)

        # Create legacy components (to be wrapped by stages)
        source_collector = SourceCollector(
            rss_feeds=settings.sources.rss_feeds,
            max_articles_per_feed=settings.sources.max_articles_per_feed,
            feed_cache_ttl_minutes=settings.sources.feed_cache_ttl_minutes,
            max_concurrent_fetches=settings.sources.max_concurrent_fetches,
            max_article_age_days=settings.sources.max_article_age_days,
            source_weights=settings.sources.source_weights,
            request_retries=settings.sources.request_retries,
            retry_base_delay_ms=settings.sources.retry_base_delay_ms,
            disable_after_failures=settings.sources.disable_after_failures,
            disable_duration_minutes=settings.sources.disable_duration_minutes,
            state_path=settings.sources.state_path,
        )

        SourceVerifier(
            llm_adapter=llm,
            min_sources=1,
            min_trust_score=50.0,
            min_credibility=60.0,
        )

        content_filter = ContentFilter(
            channel_topic=settings.channel.topic,
            min_score=30.0,
        )

        prompt_builder = PromptBuilder(
            channel_topic=settings.channel.topic,
            channel_style=settings.channel.style,
            language=settings.channel.language,
            post_length_min=settings.channel.post_length_min,
            post_length_max=settings.channel.post_length_max,
            emojis_per_post=settings.channel.emojis_per_post,
            hashtags_count=settings.channel.hashtags_count,
            post_store=post_store,
        )

        topic_selector = TopicSelector(
            llm_adapter=llm,
            topic_store=topic_store,
            channel_topic=settings.channel.topic,
        )

        generator = LLMGenerator(
            llm_adapter=llm,
            prompt_builder=prompt_builder,
            max_retries=settings.safety.max_regeneration_attempts,
        )

        editor_reviewer = EditorReviewer(
            llm_adapter=llm,
            min_score=70.0,
        )

        quality_checker = QualityChecker(
            llm_adapter=llm,
            post_store=post_store,
            min_length=settings.channel.post_length_min,
            max_length=settings.channel.post_length_max,
            min_emojis=1,
            max_emojis=settings.channel.emojis_per_post + 2,
            min_hashtags=1,
            max_hashtags=settings.channel.hashtags_count + 1,
            similarity_threshold=settings.safety.similarity_threshold,
            forbidden_words=settings.safety.forbidden_words,
        )

        # Create stages
        stages = {
            "collection": CollectionStage(
                event_bus=bus,
                source_collector=source_collector,
            ),
            "selection": SelectionStage(
                event_bus=bus,
                topic_selector=topic_selector,
                content_filter=content_filter,
            ),
            "generation": GenerationStage(
                event_bus=bus,
                generator=generator,
                topic_store=topic_store,
            ),
            "review": ReviewStage(
                event_bus=bus,
                editor_reviewer=editor_reviewer,
            ),
            "quality": QualityStage(
                event_bus=bus,
                checker=quality_checker,
            ),
            "media": MediaStage(
                event_bus=bus,
                providers=media_providers,
            ),
            "formatting": FormattingStage(
                event_bus=bus,
                formatter=formatter,
            ),
        }

        # Create coordinator
        coordinator = PipelineCoordinator(
            event_bus=bus,
            stages=stages,
            publisher=publisher,
        )

        logger.info("Pipeline coordinator created with all stages")
        return coordinator

    @staticmethod
    def create_media_providers(settings: Settings) -> list:
        """
        Create media providers based on settings.

        Args:
            settings: Application settings

        Returns:
            List of configured media providers
        """
        providers = []

        # Check for Unsplash
        unsplash_key = getattr(settings, "unsplash_access_key", None)
        if unsplash_key:
            providers.append(UnsplashProvider(access_key=unsplash_key))

        # Check for Pexels (fallback)
        pexels_key = getattr(settings, "pexels_api_key", None)
        if pexels_key:
            providers.append(PexelsProvider(api_key=pexels_key))

        return providers
