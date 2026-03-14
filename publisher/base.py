"""
Base publisher interface.

Defines the abstract interface for all publisher implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class BasePublisher(ABC):
    """
    Abstract base class for Telegram publishers.

    All publisher implementations must implement this interface.
    """

    def __init__(self, channel_id: str) -> None:
        """
        Initialize publisher.

        Args:
            channel_id: Target channel ID or username
        """
        self.channel_id = channel_id

    @abstractmethod
    async def send_post(
        self,
        text: str,
        parse_mode: str = "MarkdownV2",
    ) -> Optional[int]:
        """
        Send a text post to the channel.

        Args:
            text: Post content
            parse_mode: Text parsing mode

        Returns:
            int | None: Message ID if successful, None otherwise
        """
        pass

    @abstractmethod
    async def send_post_with_image(
        self,
        text: str,
        image_url: str,
        parse_mode: str = "MarkdownV2",
    ) -> Optional[int]:
        """
        Send a post with an image.

        Args:
            text: Post content (caption)
            image_url: Image URL or file path
            parse_mode: Text parsing mode

        Returns:
            int | None: Message ID if successful, None otherwise
        """
        pass

    @abstractmethod
    async def edit_post(
        self,
        message_id: int,
        text: str,
        parse_mode: str = "MarkdownV2",
    ) -> bool:
        """
        Edit an existing post.

        Args:
            message_id: Message ID to edit
            text: New post content
            parse_mode: Text parsing mode

        Returns:
            bool: Success status
        """
        pass

    @abstractmethod
    async def delete_post(self, message_id: int) -> bool:
        """
        Delete a post.

        Args:
            message_id: Message ID to delete

        Returns:
            bool: Success status
        """
        pass

    @abstractmethod
    async def pin_post(self, message_id: int) -> bool:
        """
        Pin a post in the channel.

        Args:
            message_id: Message ID to pin

        Returns:
            bool: Success status
        """
        pass

    @abstractmethod
    async def unpin_post(self, message_id: int) -> bool:
        """
        Unpin a post from the channel.

        Args:
            message_id: Message ID to unpin

        Returns:
            bool: Success status
        """
        pass

    @abstractmethod
    async def get_post_views(self, message_id: int) -> Optional[int]:
        """
        Get view count for a post.

        Args:
            message_id: Message ID

        Returns:
            int | None: View count or None if unavailable
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """Initialize and start the publisher."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop and cleanup the publisher."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if publisher is healthy and connected.

        Returns:
            bool: True if healthy
        """
        pass

    async def __aenter__(self) -> "BasePublisher":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
