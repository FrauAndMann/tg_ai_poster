"""
Tests for publisher components.

Tests Bot API and Telethon publishers.
"""

import pytest

from publisher.base import BasePublisher
from publisher import get_publisher


class TestPublisherFactory:
    """Tests for publisher factory."""

    def test_get_bot_publisher(self):
        """Test getting Bot publisher."""
        publisher = get_publisher(
            mode="bot",
            bot_token="test_token",
            channel_id="@test_channel",
        )
        assert publisher.channel_id == "@test_channel"

    def test_get_telethon_publisher(self):
        """Test getting Telethon publisher."""
        publisher = get_publisher(
            mode="telethon",
            channel_id="@test_channel",
            telethon_api_id=12345,
            telethon_api_hash="test_hash",
            telethon_phone="+79991234567",
        )
        assert publisher.channel_id == "@test_channel"

    def test_invalid_mode(self):
        """Test invalid publisher mode."""
        with pytest.raises(ValueError):
            get_publisher(mode="invalid", channel_id="@test")


class TestBasePublisher:
    """Tests for BasePublisher abstract class."""

    def test_channel_id(self):
        """Test channel ID initialization."""
        # Create concrete implementation for testing
        class ConcretePublisher(BasePublisher):
            async def send_post(self, text, parse_mode="MarkdownV2"):
                return 1
            async def send_post_with_image(self, text, image_url, parse_mode="MarkdownV2"):
                return 1
            async def edit_post(self, message_id, text, parse_mode="MarkdownV2"):
                return True
            async def delete_post(self, message_id):
                return True
            async def pin_post(self, message_id):
                return True
            async def unpin_post(self, message_id):
                return True
            async def get_post_views(self, message_id):
                return None
            async def start(self):
                pass
            async def stop(self):
                pass
            async def health_check(self):
                return True

        publisher = ConcretePublisher(channel_id="@test_channel")
        assert publisher.channel_id == "@test_channel"
