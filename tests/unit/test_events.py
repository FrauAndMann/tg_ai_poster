"""
Tests for the event system.

Tests event emission, handling, and pipeline flow.
"""

from __future__ import annotations

import pytest

from core.events import EventType, PipelineEvent, event_bus


class TestEventType:
    """Tests for EventType enum."""

    def test_event_type_values(self):
        """Test that event types have correct string values."""
        assert EventType.PIPELINE_START.value == "pipeline:start"
        assert EventType.PIPELINE_COMPLETE.value == "pipeline:complete"
        assert EventType.SOURCES_COLLECTED.value == "sources:collected"
        assert EventType.POST_GENERATED.value == "post:generated"
        assert EventType.STAGE_FAILED.value == "stage:failed"

    def test_all_pipeline_events_exist(self):
        """Test that all expected event types exist."""
        expected_events = {
            "pipeline:start",
            "pipeline:complete",
            "pipeline:error",
            "sources:collected",
            "topic:selected",
            "post:generated",
            "post:reviewed",
            "quality:checked",
            "media:fetched",
            "post:formatted",
            "post:published",
            "stage:failed",
        }
        actual_events = {e.value for e in EventType}
        assert expected_events == actual_events


class TestPipelineEvent:
    """Tests for PipelineEvent dataclass."""

    def test_pipeline_event_creation(self):
        """Test creating a pipeline event."""
        event = PipelineEvent(
            type=EventType.POST_GENERATED,
            data={"content": "Test post"},
        )
        assert event.type == EventType.POST_GENERATED
        assert event.data == {"content": "Test post"}
        assert event.post_id is None
        assert event.error is None

    def test_pipeline_event_with_post_id(self):
        """Test creating event with post_id."""
        event = PipelineEvent(
            type=EventType.POST_PUBLISHED,
            data={"success": True},
            post_id=123,
        )
        assert event.post_id == 123

    def test_pipeline_event_with_error(self):
        """Test creating error event."""
        event = PipelineEvent(
            type=EventType.STAGE_FAILED,
            data={"stage": "generation"},
            error="LLM timeout",
        )
        assert event.error == "LLM timeout"


class TestEventBus:
    """Tests for event bus functionality."""

    def test_event_bus_exists(self):
        """Test that event bus singleton exists."""
        from pyee.asyncio import AsyncIOEventEmitter
        assert isinstance(event_bus, AsyncIOEventEmitter)

    @pytest.mark.asyncio
    async def test_event_emission_and_handling(self):
        """Test emitting and handling events."""
        received_events = []

        def handler(event: PipelineEvent):
            received_events.append(event)

        # Register handler
        event_bus.on(EventType.POST_GENERATED.value, handler)

        # Emit event
        test_event = PipelineEvent(
            type=EventType.POST_GENERATED,
            data={"content": "Test"},
        )
        event_bus.emit(EventType.POST_GENERATED.value, test_event)

        # Verify handler was called
        assert len(received_events) == 1
        assert received_events[0].type == EventType.POST_GENERATED

        # Clean up
        event_bus.remove_listener(EventType.POST_GENERATED.value, handler)

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        """Test multiple handlers for same event."""
        call_order = []

        def handler1(event: PipelineEvent):
            call_order.append("handler1")

        def handler2(event: PipelineEvent):
            call_order.append("handler2")

        event_bus.on(EventType.PIPELINE_START.value, handler1)
        event_bus.on(EventType.PIPELINE_START.value, handler2)

        event_bus.emit(
            EventType.PIPELINE_START.value,
            PipelineEvent(type=EventType.PIPELINE_START, data={}),
        )

        assert "handler1" in call_order
        assert "handler2" in call_order

        # Clean up
        event_bus.remove_listener(EventType.PIPELINE_START.value, handler1)
        event_bus.remove_listener(EventType.PIPELINE_START.value, handler2)
