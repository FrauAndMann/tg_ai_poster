"""
Admin Bot for TG AI Poster.

Provides Telegram-based control panel for managing the posting system.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from telegram import Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram.request import HTTPXRequest

from admin_bot.commands import CommandHandler
from admin_bot.keyboards import Keyboards
from core.config import Settings

if TYPE_CHECKING:
    from memory.database import Database
    from pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


class AdminBot:
    """
    Telegram Admin Bot for managing TG AI Poster.

    Provides commands for:
    - System status monitoring
    - Statistics viewing
    - Pipeline triggering
    - Pause/resume control
    - Backup management
    - Circuit breaker monitoring
    """

    def __init__(
        self,
        bot_token: str,
        authorized_users: list[int],
        settings: Settings,
        db: Optional["Database"] = None,
        orchestrator: Optional["PipelineOrchestrator"] = None,
    ):
        """
        Initialize Admin Bot.

        Args:
            bot_token: Telegram bot token
            authorized_users: List of authorized Telegram user IDs
            settings: Application settings
            db: Database instance
            orchestrator: Pipeline orchestrator instance
        """
        self.bot_token = bot_token
        self.authorized_users = authorized_users
        self.settings = settings
        self.db = db
        self.orchestrator = orchestrator

        self._is_running = False
        self._application: Optional[Application] = None
        self._command_handler: Optional[CommandHandler] = None

    async def start(self) -> None:
        """Start the admin bot."""
        if self._is_running:
            logger.warning("Admin bot already running")
            return

        try:
            # Create application
            request = HTTPXRequest(
                connect_timeout=20.0,
                read_timeout=20.0,
            )

            self._application = (
                Application.builder()
                .token(self.bot_token)
                .request(request)
                .build()
            )

            # Create command handler
            self._command_handler = CommandHandler(
                admin_bot=self,
                authorized_users=self.authorized_users,
            )

            # Register handlers
            self._register_handlers()

            # Initialize and start
            await self._application.initialize()
            await self._application.start()
            await self._application.updater.start_polling()

            self._is_running = True
            logger.info("Admin bot started successfully")

        except Exception as e:
            logger.error(f"Failed to start admin bot: {e}")
            raise

    async def stop(self) -> None:
        """Stop the admin bot."""
        if not self._is_running:
            return

        try:
            if self._application:
                await self._application.updater.stop()
                await self._application.stop()
                await self._application.shutdown()

            self._is_running = False
            logger.info("Admin bot stopped")

        except Exception as e:
            logger.error(f"Error stopping admin bot: {e}")

    def _register_handlers(self) -> None:
        """Register all command and callback handlers."""
        if not self._application or not self._command_handler:
            return

        # Command handlers
        self._application.add_handler(
            CommandHandler("start", self._command_handler.start)
        )
        self._application.add_handler(
            CommandHandler("help", self._command_handler.help_command)
        )
        self._application.add_handler(
            CommandHandler("status", self._command_handler.status)
        )
        self._application.add_handler(
            CommandHandler("stats", self._command_handler.stats)
        )
        self._application.add_handler(
            CommandHandler("queue", self._command_handler.queue)
        )
        self._application.add_handler(
            CommandHandler("trigger", self._command_handler.trigger)
        )
        self._application.add_handler(
            CommandHandler("pause", self._command_handler.pause)
        )
        self._application.add_handler(
            CommandHandler("resume", self._command_handler.resume)
        )
        self._application.add_handler(
            CommandHandler("logs", self._command_handler.logs)
        )
        self._application.add_handler(
            CommandHandler("backup", self._command_handler.backup)
        )

        # Callback query handler
        self._application.add_handler(
            CallbackQueryHandler(self._command_handler.callback_handler)
        )

    @property
    def is_running(self) -> bool:
        """Check if admin bot is running."""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """Check if posting is paused."""
        if self._command_handler:
            return self._command_handler.is_paused
        return False

    async def send_notification(self, user_id: int, message: str) -> bool:
        """
        Send notification to specific user.

        Args:
            user_id: Telegram user ID
            message: Message to send (HTML formatted)

        Returns:
            bool: Success status
        """
        if not self._application:
            return False

        try:
            await self._application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="HTML",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    async def broadcast(self, message: str) -> int:
        """
        Broadcast message to all authorized users.

        Args:
            message: Message to send (HTML formatted)

        Returns:
            int: Number of successful sends
        """
        success_count = 0

        for user_id in self.authorized_users:
            if await self.send_notification(user_id, message):
                success_count += 1

        return success_count
