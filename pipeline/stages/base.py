"""
Base stage implementation.

Provides abstract base class for all pipeline stages.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.events import EventBus, EventType, PipelineEvent
from core.logger import get_logger

logger = get_logger(__name__)


class BaseStage(ABC):
    """
    Abstract base class for pipeline stages.

    Each stage is responsible for a single step in the content pipeline
    and emits events upon completion.
    """

    def __init__(self, event_bus: EventBus):
        """
        Initialize stage.

        Args:
            event_bus: Event bus for emitting events
        """
        self.bus = event_bus

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the stage.

        Args:
            context: Pipeline context with data from previous stages

        Returns:
            Updated context with stage results
        """
        pass

    def emit_event(self, event_type: EventType, data: dict[str, Any]) -> None:
        """
        Emit a pipeline event.

        Args:
            event_type: Type of event to emit
            data: Event data
        """
        event = PipelineEvent(type=event_type, data=data)
        self.bus.emit(event_type.value, event)
        logger.debug(f"Emitted event: {event_type.value}")

    def emit_error(self, stage_name: str, error: Exception) -> None:
        """
        Emit an error event.

        Args:
            stage_name: Name of the failing stage
            error: Exception that occurred
        """
        event = PipelineEvent(
            type=EventType.STAGE_FAILED,
            data={"stage": stage_name},
            error=str(error),
        )
        self.bus.emit(EventType.STAGE_FAILED.value, event)
        logger.error(f"Stage {stage_name} failed: {error}")
