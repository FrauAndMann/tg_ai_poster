"""
Bot API publisher implementation.

Publishes posts using python-telegram-bot library.
"""

from __future__ import annotations

from typing import Optional

from telegram import Bot, InputFile
from telegram.error import TelegramError
from telegram.request import HTTPXRequest

from core.logger import get_logger
from publisher.base import BasePublisher
from utils.retry import with_retry

logger = get_logger(__name__)


class BotPublisher(BasePublisher):
    """
    Telegram Bot API publisher.

    MODE A - Official Bot API
    =========================

    HOW IT WORKS:
    - Uses official Telegram Bot API
    - Bot must be added as channel administrator
    - Posts appear with "via @botname" label

    SETUP STEPS:
    1. Create bot via @BotFather on Telegram
    2. Get bot token from @BotFather
    3. Add bot to channel as administrator
    4. Grant "Post Messages" permission

    PROS:
    + Official API - no ban risk
    + Easy setup and maintenance
    + Reliable and well-documented
    + No session management needed

    CONS:
    - Shows "via bot" label on posts
    - Bot must be channel admin
    - Limited to Bot API capabilities
    - Some features require explicit permissions

    USAGE:
        publisher = BotPublisher(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            channel_id="@my_channel"  # or "-1001234567890"
        )
        await publisher.start()
        message_id = await publisher.send_post("Hello, world!")
    """

    def __init__(
        self,
        bot_token: str,
        channel_id: str,
        connect_timeout: float = 20.0,
        read_timeout: float = 20.0,
        write_timeout: float = 20.0,
        pool_timeout: float = 1.0,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize Bot API publisher.

        Args:
            bot_token: Telegram bot token from @BotFather
            channel_id: Target channel ID or username
            connect_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
            write_timeout: Write timeout in seconds
            pool_timeout: Pool timeout in seconds
            max_retries: Maximum retry attempts
        """
        super().__init__(channel_id)

        self.bot_token = bot_token
        self.max_retries = max_retries

        # Configure request timeouts
        self.request = HTTPXRequest(
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            pool_timeout=pool_timeout,
        )

        self._bot: Optional[Bot] = None
        self._started = False

    async def start(self) -> None:
        """Initialize the bot."""
        if self._started:
            logger.warning("Bot publisher already started")
            return

        self._bot = Bot(token=self.bot_token, request=self.request)

        # Verify bot info
        try:
            me = await self._bot.get_me()
            logger.info(f"Bot publisher initialized: @{me.username}")

            # Verify channel access
            try:
                chat = await self._bot.get_chat(self.channel_id)
                logger.info(f"Channel access verified: {chat.title}")
            except TelegramError as e:
                logger.warning(f"Could not verify channel access: {e}")

            self._started = True

        except TelegramError as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise

    async def stop(self) -> None:
        """Stop and cleanup the bot."""
        if self._bot:
            # python-telegram-bot doesn't require explicit cleanup
            self._bot = None

        self._started = False
        logger.info("Bot publisher stopped")

    async def health_check(self) -> bool:
        """Check if bot is healthy."""
        if not self._bot:
            return False

        try:
            await self._bot.get_me()
            return True
        except TelegramError:
            return False

    @with_retry(max_attempts=3, backoff_base=2.0, exceptions=(TelegramError,))
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
            int | None: Message ID if successful
        """
        if not self._bot:
            raise RuntimeError("Publisher not started")

        try:
            message = await self._bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=False,
            )

            logger.info(f"Post sent: message_id={message.message_id}")
            return message.message_id

        except TelegramError as e:
            logger.error(f"Failed to send post: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0, exceptions=(TelegramError,))
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
            int | None: Message ID if successful
        """
        if not self._bot:
            raise RuntimeError("Publisher not started")

        try:
            # Check if it's a URL or file path
            if image_url.startswith(("http://", "https://")):
                # Send from URL
                message = await self._bot.send_photo(
                    chat_id=self.channel_id,
                    photo=image_url,
                    caption=text,
                    parse_mode=parse_mode,
                )
            else:
                # Send from file
                with open(image_url, "rb") as image_file:
                    message = await self._bot.send_photo(
                        chat_id=self.channel_id,
                        photo=InputFile(image_file),
                        caption=text,
                        parse_mode=parse_mode,
                    )

            logger.info(f"Post with image sent: message_id={message.message_id}")
            return message.message_id

        except TelegramError as e:
            logger.error(f"Failed to send post with image: {e}")
            raise
        except FileNotFoundError as e:
            logger.error(f"Image file not found: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0, exceptions=(TelegramError,))
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
        if not self._bot:
            raise RuntimeError("Publisher not started")

        try:
            await self._bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=message_id,
                text=text,
                parse_mode=parse_mode,
            )

            logger.info(f"Post edited: message_id={message_id}")
            return True

        except TelegramError as e:
            logger.error(f"Failed to edit post: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0, exceptions=(TelegramError,))
    async def delete_post(self, message_id: int) -> bool:
        """
        Delete a post.

        Args:
            message_id: Message ID to delete

        Returns:
            bool: Success status
        """
        if not self._bot:
            raise RuntimeError("Publisher not started")

        try:
            await self._bot.delete_message(
                chat_id=self.channel_id,
                message_id=message_id,
            )

            logger.info(f"Post deleted: message_id={message_id}")
            return True

        except TelegramError as e:
            logger.error(f"Failed to delete post: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0, exceptions=(TelegramError,))
    async def pin_post(self, message_id: int) -> bool:
        """
        Pin a post in the channel.

        Args:
            message_id: Message ID to pin

        Returns:
            bool: Success status
        """
        if not self._bot:
            raise RuntimeError("Publisher not started")

        try:
            await self._bot.pin_chat_message(
                chat_id=self.channel_id,
                message_id=message_id,
                disable_notification=False,
            )

            logger.info(f"Post pinned: message_id={message_id}")
            return True

        except TelegramError as e:
            logger.error(f"Failed to pin post: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0, exceptions=(TelegramError,))
    async def unpin_post(self, message_id: int) -> bool:
        """
        Unpin a post from the channel.

        Args:
            message_id: Message ID to unpin

        Returns:
            bool: Success status
        """
        if not self._bot:
            raise RuntimeError("Publisher not started")

        try:
            await self._bot.unpin_chat_message(
                chat_id=self.channel_id,
                message_id=message_id,
            )

            logger.info(f"Post unpinned: message_id={message_id}")
            return True

        except TelegramError as e:
            logger.error(f"Failed to unpin post: {e}")
            raise

    async def get_post_views(self, message_id: int) -> Optional[int]:
        """
        Get view count for a post.

        Note: Bot API doesn't support view counts directly.
        This method returns None.

        Args:
            message_id: Message ID

        Returns:
            int | None: None (not supported)
        """
        # Bot API doesn't provide view counts
        logger.warning("View counts not available via Bot API")
        return None

    async def get_channel_info(self) -> Optional[dict]:
        """
        Get channel information.

        Returns:
            dict | None: Channel info or None
        """
        if not self._bot:
            return None

        try:
            chat = await self._bot.get_chat(self.channel_id)
            return {
                "id": chat.id,
                "title": chat.title,
                "username": chat.username,
                "type": chat.type,
                "member_count": chat.member_count,
            }
        except TelegramError:
            return None
