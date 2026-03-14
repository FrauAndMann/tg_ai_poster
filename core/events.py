"""
Event system for pipeline orchestration.

Provides event bus and event types for the event-driven pipeline architecture.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pyee.asyncio import AsyncIOEventEmitter


class EventType(Enum):
    """Types of events in the pipeline."""

    # Pipeline lifecycle
    PIPELINE_START = "pipeline:start"
    PIPELINE_COMPLETE = "pipeline:complete"
    PIPELINE_ERROR = "pipeline:error"

    # Stage events
    SOURCES_COLLECTED = "sources:collected"
    TOPIC_SELECTED = "topic:selected"
    POST_GENERATED = "post:generated"
    POST_REVIEWED = "post:reviewed"
    QUALITY_CHECKED = "quality:checked"
    MEDIA_FETCHED = "media:fetched"
    POST_FORMATTED = "post:formatted"
    POST_PUBLISHED = "post:published"

    # Error events
    STAGE_FAILED = "stage:failed"


@dataclass
class PipelineEvent:
    """Event payload for pipeline events."""

    type: EventType
    data: dict[str, Any]
    post_id: Optional[int] = None
    error: Optional[str] = None


# Global event bus singleton
event_bus = AsyncIOEventEmitter()
