"""
Multi-Channel Support - Manages multiple Telegram channels simultaneously.

Each channel has its own topic, schedule, language, and LLM configuration.
The orchestrator runs independent pipelines per channel in parallel.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from core.config import Settings
    from pipeline.orchestrator import PipelineOrchestrator

logger = get_logger(__name__)


@dataclass(slots=True)
class ChannelConfig:
    """Configuration for a single channel."""

    id: str
    name: str
    topic: str
    language: str = "ru"
    schedule_type: str = "fixed"
    schedule_times: list[str] = field(
        default_factory=lambda: ["09:30", "14:00", "20:00"]
    )
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: float = 0.2
    post_length_min: int = 200
    post_length_max: int = 4096
    emojis_per_post: int = 3
    hashtags_count: int = 3
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "ChannelConfig":
        """Create ChannelConfig from dictionary."""
        return cls(
            id=data.get("id", "default"),
            name=data.get("name", "Default Channel"),
            topic=data.get("topic", ""),
            language=data.get("language", "ru"),
            schedule_type=data.get("schedule_type", "fixed"),
            schedule_times=data.get("schedule_times", ["09:30", "14:00", "20:00"]),
            llm_provider=data.get("llm_provider"),
            llm_model=data.get("llm_model"),
            llm_temperature=data.get("llm_temperature", 0.2),
            post_length_min=data.get("post_length_min", 200),
            post_length_max=data.get("post_length_max", 4096),
            emojis_per_post=data.get("emojis_per_post", 3),
            hashtags_count=data.get("hashtags_count", 3),
            enabled=data.get("enabled", True),
        )


@dataclass(slots=True)
class ChannelStatus:
    """Runtime status of a channel."""

    channel_id: str
    is_active: bool = True
    last_post_at: Optional[datetime] = None
    posts_today: int = 0
    total_posts: int = 0
    last_error: Optional[str] = None
    consecutive_failures: int = 0


class MultiChannelManager:
    """
    Manages multiple Telegram channels with independent configurations.

    Features:
    - Per-channel topic and style configuration
    - Independent scheduling per channel
    - Parallel pipeline execution
    - Channel-specific LLM settings
    """

    def __init__(self, settings: "Settings") -> None:
        """
        Initialize multi-channel manager.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.channels: dict[str, ChannelConfig] = {}
        self.statuses: dict[str, ChannelStatus] = {}
        self._orchestrators: dict[str, "PipelineOrchestrator"] = {}
        self._tasks: dict[str, asyncio.Task] = {}

        self._load_channels()

    def _load_channels(self) -> None:
        """Load channel configurations from settings."""
        # Get channels config from settings
        channels_config = getattr(self.settings, "channels", None)

        if not channels_config or not getattr(channels_config, "enabled", False):
            # Single-channel mode: create default channel from main config
            default_channel = ChannelConfig(
                id="default",
                name="Main Channel",
                topic=self.settings.channel.topic,
                language=self.settings.channel.language,
                schedule_type=self.settings.schedule.type,
                schedule_times=self.settings.schedule.fixed_times,
                llm_provider=self.settings.llm.provider,
                llm_model=self.settings.llm.model,
                llm_temperature=self.settings.llm.temperature,
                post_length_min=self.settings.channel.post_length_min,
                post_length_max=self.settings.channel.post_length_max,
                emojis_per_post=self.settings.channel.emojis_per_post,
                hashtags_count=self.settings.channel.hashtags_count,
            )
            self.channels["default"] = default_channel
            logger.info("Single-channel mode enabled")
        else:
            # Multi-channel mode
            channel_list = getattr(channels_config, "list", [])
            for ch_data in channel_list:
                channel = ChannelConfig.from_dict(ch_data)
                self.channels[channel.id] = channel
            logger.info("Multi-channel mode enabled: %d channels", len(self.channels))

        # Initialize statuses
        for channel_id in self.channels:
            self.statuses[channel_id] = ChannelStatus(channel_id=channel_id)

    def get_channel(self, channel_id: str) -> Optional[ChannelConfig]:
        """Get channel configuration by ID."""
        return self.channels.get(channel_id)

    def get_active_channels(self) -> list[ChannelConfig]:
        """Get list of all active channels."""
        return [ch for ch in self.channels.values() if ch.enabled]

    def update_status(
        self,
        channel_id: str,
        is_active: Optional[bool] = None,
        posts_today: Optional[int] = None,
        last_error: Optional[str] = None,
    ) -> None:
        """Update channel status."""
        if channel_id not in self.statuses:
            return

        status = self.statuses[channel_id]

        if is_active is not None:
            status.is_active = is_active
        if posts_today is not None:
            status.posts_today = posts_today
        if last_error is not None:
            status.last_error = last_error
            status.consecutive_failures += 1
        elif status.consecutive_failures > 0:
            # Reset on success
            status.consecutive_failures = 0

    def record_post(self, channel_id: str) -> None:
        """Record a successful post for a channel."""
        if channel_id not in self.statuses:
            return

        status = self.statuses[channel_id]
        status.last_post_at = datetime.now()
        status.posts_today += 1
        status.total_posts += 1
        status.consecutive_failures = 0

    async def run_channel_pipeline(
        self,
        channel_id: str,
        orchestrator: "PipelineOrchestrator",
    ) -> bool:
        """
        Run the pipeline for a specific channel.

        Args:
            channel_id: Channel to run
            orchestrator: Pipeline orchestrator instance

        Returns:
            bool: True if successful
        """
        channel = self.get_channel(channel_id)
        if not channel or not channel.enabled:
            logger.warning("Channel %s not found or disabled", channel_id)
            return False

        try:
            # Run pipeline with channel-specific settings
            result = await orchestrator.run_once(channel_config=channel)

            if result:
                self.record_post(channel_id)
                logger.info("Channel %s: post published successfully", channel_id)
                return True
            else:
                logger.warning("Channel %s: pipeline returned no result", channel_id)
                return False

        except Exception as e:
            logger.exception("Channel %s: pipeline failed: %s", channel_id, e)
            self.update_status(channel_id, last_error=str(e))
            return False

    async def run_all_channels(
        self,
        orchestrator: "PipelineOrchestrator",
    ) -> dict[str, bool]:
        """
        Run pipelines for all active channels in parallel.

        Args:
            orchestrator: Pipeline orchestrator instance

        Returns:
            dict[str, bool]: Results per channel (True = success)
        """
        active_channels = self.get_active_channels()

        if not active_channels:
            logger.warning("No active channels to run")
            return {}

        logger.info("Running pipelines for %d channels", len(active_channels))

        # Run all channels in parallel
        tasks = {
            ch.id: self.run_channel_pipeline(ch.id, orchestrator)
            for ch in active_channels
        }

        results = {}
        for channel_id, task in tasks.items():
            try:
                results[channel_id] = await task
            except Exception as e:
                logger.error("Channel %s task failed: %s", channel_id, e)
                results[channel_id] = False

        # Log summary
        successful = sum(1 for v in results.values() if v)
        logger.info(
            "Pipeline run complete: %d/%d channels successful", successful, len(results)
        )

        return results

    def get_status_report(self) -> dict[str, Any]:
        """Get status report for all channels."""
        return {
            "total_channels": len(self.channels),
            "active_channels": len(self.get_active_channels()),
            "channels": {
                ch_id: {
                    "name": ch.name,
                    "enabled": ch.enabled,
                    "status": {
                        "is_active": self.statuses[ch_id].is_active,
                        "last_post": self.statuses[ch_id].last_post_at.isoformat()
                        if self.statuses[ch_id].last_post_at
                        else None,
                        "posts_today": self.statuses[ch_id].posts_today,
                        "total_posts": self.statuses[ch_id].total_posts,
                        "consecutive_failures": self.statuses[
                            ch_id
                        ].consecutive_failures,
                    },
                }
                for ch_id, ch in self.channels.items()
            },
        }

    def pause_channel(self, channel_id: str) -> bool:
        """Pause a channel."""
        if channel_id not in self.channels:
            return False
        self.channels[channel_id].enabled = False
        self.statuses[channel_id].is_active = False
        logger.info("Channel %s paused", channel_id)
        return True

    def resume_channel(self, channel_id: str) -> bool:
        """Resume a paused channel."""
        if channel_id not in self.channels:
            return False
        self.channels[channel_id].enabled = True
        self.statuses[channel_id].is_active = True
        logger.info("Channel %s resumed", channel_id)
        return True


# Configuration schema for config.yaml
MULTI_CHANNEL_CONFIG_SCHEMA = {
    "channels": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable multi-channel support",
        },
        "list": {
            "type": "list",
            "description": "List of channel configurations",
            "items": {
                "id": {"type": "str", "required": True},
                "name": {"type": "str", "required": True},
                "topic": {"type": "str", "required": True},
                "language": {"type": "str", "default": "ru"},
                "schedule_type": {"type": "str", "default": "fixed"},
                "schedule_times": {
                    "type": "list",
                    "default": ["09:30", "14:00", "20:00"],
                },
                "llm_provider": {"type": "str", "optional": True},
                "llm_model": {"type": "str", "optional": True},
                "llm_temperature": {"type": "float", "default": 0.2},
                "enabled": {"type": "bool", "default": True},
            },
        },
    }
}
