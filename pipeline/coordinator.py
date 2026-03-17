"""
Pipeline coordinator.

Orchestrates the event-driven pipeline using EventBus and async state machine.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from pyee.asyncio import AsyncIOEventEmitter

from core.events import EventType, PipelineEvent
from core.result import PipelineResult
from core.logger import get_logger

logger = get_logger(__name__)


class PipelineCoordinator:
    """
    Orchestrates pipeline flow via event subscriptions.

    Uses async state machine pattern to manage stage transitions.
    """

    def __init__(
        self,
        event_bus: AsyncIOEventEmitter,
        stages: dict[str, Any],
        publisher: Optional[Any] = None,
    ):
        """
        Initialize coordinator.

        Args:
            event_bus: Event bus for stage events
            stages: Dict of stage name -> stage instance
            publisher: Optional publisher for posting
        """
        self.bus = event_bus
        self.stages = stages
        self.publisher = publisher

        # Pipeline state
        self._current_state = "idle"
        self._pipeline_data: dict[str, Any] = {}
        self._result_future: Optional[asyncio.Future] = None

        # Setup event handlers
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Subscribe to stage completion events."""
        self.bus.on(EventType.SOURCES_COLLECTED.value, self._on_sources_collected)
        self.bus.on(EventType.TOPIC_SELECTED.value, self._on_topic_selected)
        self.bus.on(EventType.POST_GENERATED.value, self._on_post_generated)
        self.bus.on(EventType.POST_REVIEWED.value, self._on_post_reviewed)
        self.bus.on(EventType.QUALITY_CHECKED.value, self._on_quality_checked)
        self.bus.on(EventType.MEDIA_FETCHED.value, self._on_media_fetched)
        self.bus.on(EventType.POST_FORMATTED.value, self._on_post_formatted)

        self.bus.on(EventType.STAGE_FAILED.value, self._on_stage_failed)

    async def run(self, dry_run: bool = False) -> PipelineResult:
        """Execute full pipeline and wait for completion."""
        self._result_future = asyncio.Future()
        self._pipeline_data = {
            "dry_run": dry_run,
            "start_time": time.time(),
        }

        # Emit start event
        self.bus.emit(
            EventType.PIPELINE_START.value,
            PipelineEvent(type=EventType.PIPELINE_START, data={"dry_run": dry_run}),
        )

        # Trigger first stage
        await self._run_stage("collection")

        # Wait for completion
        return await self._result_future

    async def _run_stage(self, stage_name: str) -> None:
        """Execute a stage and handle result."""
        if stage_name not in self.stages:
            logger.error(f"Unknown stage: {stage_name}")
            self._fail_pipeline(f"Unknown stage: {stage_name}")
            return

        stage = self.stages[stage_name]
        try:
            await stage.execute(self._pipeline_data)
        except Exception as e:
            logger.error(f"Stage {stage_name} failed: {e}")
            self._fail_pipeline(f"Stage {stage_name} failed: {e}")

    def _on_sources_collected(self, event: PipelineEvent) -> None:
        """Handle sources collected event."""
        self._pipeline_data["articles"] = event.data.get("articles", [])
        asyncio.create_task(self._run_stage("selection"))

    def _on_topic_selected(self, event: PipelineEvent) -> None:
        """Handle topic selected event."""
        self._pipeline_data["topic"] = event.data.get("topic")
        self._pipeline_data["topic_meta"] = event.data.get("meta")
        asyncio.create_task(self._run_stage("generation"))

    def _on_post_generated(self, event: PipelineEvent) -> None:
        """Handle post generated event."""
        self._pipeline_data["generated"] = event.data.get("generated")
        asyncio.create_task(self._run_stage("review"))

    def _on_post_reviewed(self, event: PipelineEvent) -> None:
        """Handle post reviewed event."""
        result = event.data
        self._pipeline_data["editor_result"] = result

        # Use improved content if available
        if result.get("improved_content"):
            self._pipeline_data["content"] = result["improved_content"]

        asyncio.create_task(self._run_stage("quality"))

    def _on_quality_checked(self, event: PipelineEvent) -> None:
        """Handle quality checked event."""
        result = event.data
        self._pipeline_data["quality_result"] = result

        if not result.get("approved"):
            logger.warning(f"Quality check not approved: {result.get('issues')}")

        asyncio.create_task(self._run_stage("media"))

    def _on_media_fetched(self, event: PipelineEvent) -> None:
        """Handle media fetched event."""
        self._pipeline_data["media"] = event.data.get("media")
        asyncio.create_task(self._run_stage("formatting"))

    def _on_post_formatted(self, event: PipelineEvent) -> None:
        """Handle post formatted event - publish or complete."""
        formatted_content = event.data.get("content")

        if self._pipeline_data.get("dry_run"):
            logger.info("[DRY RUN] Would publish post")
            self._complete_pipeline(formatted_content)
        elif self.publisher:
            asyncio.create_task(self._publish_post(formatted_content))
        else:
            logger.warning("No publisher configured")
            self._complete_pipeline(formatted_content)

    async def _publish_post(self, content: str) -> None:
        """Publish post to Telegram."""
        if not self.publisher:
            self._complete_pipeline(content)
            return

        try:
            media = self._pipeline_data.get("media")
            if media:
                message_id = await self.publisher.send_post_with_image(
                    text=content,
                    image_url=media.url,
                )
            else:
                message_id = await self.publisher.send_post(content)

            self._pipeline_data["message_id"] = message_id
            self._complete_pipeline(content)
        except Exception as e:
            logger.error(f"Failed to publish post: {e}")
            self._fail_pipeline(f"Publishing failed: {e}")

    def _on_stage_failed(self, event: PipelineEvent) -> None:
        """Handle stage failure event."""
        error = event.error or event.data.get("error", "Unknown error")
        stage = event.data.get("stage", "unknown")
        logger.error(f"Stage {stage} failed: {error}")
        self._fail_pipeline(f"Stage {stage} failed: {error}")

    def _complete_pipeline(self, content: str) -> None:
        """Mark pipeline as complete."""
        if self._result_future and not self._result_future.done():
            duration = time.time() - self._pipeline_data.get("start_time", time.time())
            result = PipelineResult(
                success=True,
                post_id=self._pipeline_data.get("post_id"),
                content=content,
                topic=self._pipeline_data.get("topic"),
                media_url=self._pipeline_data.get("media", {}).get("url") if self._pipeline_data.get("media") else None,
                duration=duration,
            )
            self._result_future.set_result(result)

            # Emit completion event
            self.bus.emit(
                EventType.PIPELINE_COMPLETE.value,
                PipelineEvent(type=EventType.PIPELINE_COMPLETE, data={"result": result}),
            )

    def _fail_pipeline(self, error: str) -> None:
        """Mark pipeline as failed."""
        if self._result_future and not self._result_future.done():
            duration = time.time() - self._pipeline_data.get("start_time", time.time())
            result = PipelineResult(
                success=False,
                error=error,
                duration=duration,
            )
            self._result_future.set_result(result)

            # Emit error event
            self.bus.emit(
                EventType.PIPELINE_ERROR.value,
                PipelineEvent(type=EventType.PIPELINE_ERROR, data={"error": error}),
            )
