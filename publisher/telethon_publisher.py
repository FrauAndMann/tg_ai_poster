"""
Telethon publisher implementation.

Publishes posts using user account via Telethon library.

WARNING: This mode has risks and limitations. See documentation below.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    ChatWriteForbiddenError,
    SessionPasswordNeededError,
    UserBannedInChannelError,
)
from telethon.tl.types import InputPeerChannel

from core.logger import get_logger
from publisher.base import BasePublisher
from utils.retry import with_retry

logger = get_logger(__name__)


class TelethonPublisher(BasePublisher):
    """
    Telethon (User Account) publisher.

    MODE B - User Account via Telethon
    ===================================

    HOW IT WORKS:
    - Uses Telethon library to connect as a regular user
    - Posts appear as regular user messages
    - Requires phone authentication (one-time)

    SETUP STEPS:
    1. Get API credentials from https://my.telegram.org
    2. Run first-time authentication (will prompt for phone code)
    3. Session is saved for subsequent runs
    4. User must be channel member/admin as needed

    AUTHENTICATION FLOW:
    1. First run: Enter phone number
    2. Receive SMS/app code from Telegram
    3. Enter the code
    4. If 2FA enabled: Enter password
    5. Session saved to file for future use

    PROS:
    + Posts appear as real user messages (no "via bot" label)
    + Full account capabilities
    + Can view post statistics
    + Works in any channel where user can post

    CONS:
    - RISK OF ACCOUNT BAN if detected as automated
    - Requires storing session file securely
    - Violates Telegram ToS for automation
    - Phone authentication required
    - More complex setup

    ⚠️  WARNING - ACCOUNT BAN RISK:
    - Telegram may ban accounts used for automation
    - Use on a DEDICATED account, NOT your main account
    - Follow rate limits strictly
    - Don't post too frequently
    - Consider using Bot API instead for safety

    USAGE:
        publisher = TelethonPublisher(
            api_id=12345,
            api_hash="abcdef1234567890",
            phone="+1234567890",
            channel_id="@my_channel"
        )
        await publisher.start()  # Will prompt for code on first run
        message_id = await publisher.send_post("Hello, world!")
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        channel_id: str,
        session_path: str = "sessions/user.session",
        max_retries: int = 3,
    ) -> None:
        """
        Initialize Telethon publisher.

        Args:
            api_id: Telegram API ID from my.telegram.org
            api_hash: Telegram API Hash from my.telegram.org
            phone: Phone number with country code
            channel_id: Target channel ID or username
            session_path: Path to store session file
            max_retries: Maximum retry attempts
        """
        super().__init__(channel_id)

        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_path = session_path
        self.max_retries = max_retries

        self._client: Optional[TelegramClient] = None
        self._started = False
        self._channel_entity = None

        # Ensure session directory exists
        session_dir = Path(session_path).parent
        session_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """Initialize and authenticate the client."""
        if self._started:
            logger.warning("Telethon publisher already started")
            return

        if not self.api_id or not self.api_hash:
            raise ValueError("API ID and API Hash are required")

        self._client = TelegramClient(
            self.session_path,
            self.api_id,
            self.api_hash,
        )

        await self._client.connect()

        # Check if already authorized
        if not await self._client.is_user_authorized():
            logger.info("User not authorized, starting authentication flow")
            await self._authenticate()

        # Get channel entity
        try:
            self._channel_entity = await self._client.get_entity(self.channel_id)
            logger.info(f"Channel entity resolved: {getattr(self._channel_entity, 'title', self.channel_id)}")
        except Exception as e:
            logger.warning(f"Could not resolve channel entity: {e}")

        me = await self._client.get_me()
        logger.info(f"Telethon publisher initialized: @{me.username}")

        self._started = True

    async def _authenticate(self) -> None:
        """Handle phone authentication flow."""
        if not self._client:
            raise RuntimeError("Client not initialized")

        # Send code request
        await self._client.send_code_request(self.phone)

        logger.info(f"Verification code sent to {self.phone}")

        # Get code from user (this blocks, but it's one-time setup)
        code = input("Enter the verification code: ")

        try:
            await self._client.sign_in(self.phone, code)
            logger.info("Authentication successful")

        except SessionPasswordNeededError:
            # 2FA is enabled
            password = input("Enter your 2FA password: ")
            await self._client.sign_in(password=password)
            logger.info("2FA authentication successful")

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise

    async def stop(self) -> None:
        """Disconnect the client."""
        if self._client:
            await self._client.disconnect()
            self._client = None

        self._started = False
        self._channel_entity = None
        logger.info("Telethon publisher stopped")

    async def health_check(self) -> bool:
        """Check if client is healthy and connected."""
        if not self._client:
            return False

        try:
            await self._client.get_me()
            return True
        except Exception as e:
            logger.debug("Telethon health check failed: %s", e)
            return False

    def _get_channel_peer(self):
        """Get channel peer for API calls."""
        if self._channel_entity:
            if hasattr(self._channel_entity, "channel_id"):
                return InputPeerChannel(
                    channel_id=self._channel_entity.id,
                    access_hash=self._channel_entity.access_hash,
                )
            return self._channel_entity
        return self.channel_id

    @with_retry(max_attempts=3, backoff_base=2.0)
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
        if not self._client:
            raise RuntimeError("Publisher not started")

        try:
            # Telethon uses different parse modes
            # Convert MarkdownV2 to Telethon's markdown
            telethon_parse_mode = "md" if parse_mode in ["Markdown", "MarkdownV2"] else parse_mode

            message = await self._client.send_message(
                self.channel_id,
                text,
                parse_mode=telethon_parse_mode,
                link_preview=True,
            )

            logger.info(f"Post sent: message_id={message.id}")
            return message.id

        except UserBannedInChannelError:
            logger.error("User is banned from this channel")
            raise
        except ChatWriteForbiddenError:
            logger.error("No permission to write in this channel")
            raise
        except Exception as e:
            logger.error(f"Failed to send post: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0)
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
        if not self._client:
            raise RuntimeError("Publisher not started")

        try:
            telethon_parse_mode = "md" if parse_mode in ["Markdown", "MarkdownV2"] else parse_mode

            # Check if it's a URL or file path
            if image_url.startswith(("http://", "https://")):
                # Download and send
                message = await self._client.send_message(
                    self.channel_id,
                    text,
                    file=image_url,
                    parse_mode=telethon_parse_mode,
                )
            else:
                # Send from file
                message = await self._client.send_message(
                    self.channel_id,
                    text,
                    file=image_url,
                    parse_mode=telethon_parse_mode,
                )

            logger.info(f"Post with image sent: message_id={message.id}")
            return message.id

        except Exception as e:
            logger.error(f"Failed to send post with image: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0)
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
        if not self._client:
            raise RuntimeError("Publisher not started")

        try:
            telethon_parse_mode = "md" if parse_mode in ["Markdown", "MarkdownV2"] else parse_mode

            await self._client.edit_message(
                self.channel_id,
                message_id,
                text,
                parse_mode=telethon_parse_mode,
            )

            logger.info(f"Post edited: message_id={message_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to edit post: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0)
    async def delete_post(self, message_id: int) -> bool:
        """
        Delete a post.

        Args:
            message_id: Message ID to delete

        Returns:
            bool: Success status
        """
        if not self._client:
            raise RuntimeError("Publisher not started")

        try:
            await self._client.delete_messages(
                self.channel_id,
                [message_id],
            )

            logger.info(f"Post deleted: message_id={message_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete post: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0)
    async def pin_post(self, message_id: int) -> bool:
        """
        Pin a post in the channel.

        Args:
            message_id: Message ID to pin

        Returns:
            bool: Success status
        """
        if not self._client:
            raise RuntimeError("Publisher not started")

        try:
            await self._client.pin_message(
                self.channel_id,
                message_id,
                notify=False,
            )

            logger.info(f"Post pinned: message_id={message_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to pin post: {e}")
            raise

    @with_retry(max_attempts=3, backoff_base=2.0)
    async def unpin_post(self, message_id: int) -> bool:
        """
        Unpin a post from the channel.

        Args:
            message_id: Message ID to unpin

        Returns:
            bool: Success status
        """
        if not self._client:
            raise RuntimeError("Publisher not started")

        try:
            await self._client.unpin_message(
                self.channel_id,
                message_id,
            )

            logger.info(f"Post unpinned: message_id={message_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unpin post: {e}")
            raise

    async def get_post_views(self, message_id: int) -> Optional[int]:
        """
        Get view count for a post.

        This is a Telethon advantage - we can get actual view counts.

        Args:
            message_id: Message ID

        Returns:
            int | None: View count or None
        """
        if not self._client:
            return None

        try:
            messages = await self._client.get_messages(
                self.channel_id,
                ids=message_id,
            )

            if messages and hasattr(messages, "views"):
                return messages.views

            return None

        except Exception as e:
            logger.warning(f"Could not get post views: {e}")
            return None

    async def get_channel_info(self) -> Optional[dict]:
        """
        Get channel information.

        Returns:
            dict | None: Channel info or None
        """
        if not self._client:
            return None

        try:
            entity = await self._client.get_entity(self.channel_id)

            return {
                "id": entity.id,
                "title": getattr(entity, "title", ""),
                "username": getattr(entity, "username", ""),
            }

        except Exception as e:
            logger.warning(f"Could not get channel info: {e}")
            return None

    async def get_post_reactions(self, message_id: int) -> Optional[dict]:
        """
        Get reactions for a post.

        Args:
            message_id: Message ID

        Returns:
            dict | None: Reactions by type
        """
        if not self._client:
            return None

        try:
            messages = await self._client.get_messages(
                self.channel_id,
                ids=message_id,
            )

            if messages and hasattr(messages, "reactions"):
                reactions = {}
                for reaction in messages.reactions.results:
                    emoji = reaction.reaction.emoticon
                    reactions[emoji] = reaction.count
                return reactions

            return None

        except Exception as e:
            logger.warning(f"Could not get post reactions: {e}")
            return None
