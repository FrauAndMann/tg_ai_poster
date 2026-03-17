"""
Command handlers for Admin Bot.

Processes Telegram commands and callback queries.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from telegram import Update
from telegram.ext import ContextTypes

from admin_bot.keyboards import Keyboards
from admin_bot.messages import Messages
from utils.circuit_breaker import CircuitBreakerRegistry

if TYPE_CHECKING:
    from admin_bot.admin_bot import AdminBot

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handler for Telegram commands and callbacks."""

    def __init__(
        self,
        admin_bot: "AdminBot",
        authorized_users: list[int],
    ):
        """
        Initialize command handler.

        Args:
            admin_bot: AdminBot instance for accessing system state
            authorized_users: List of authorized Telegram user IDs
        """
        self.admin_bot = admin_bot
        self.authorized_users = set(authorized_users)
        self._is_paused = False

    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        return user_id in self.authorized_users

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        await update.message.reply_text(
            Messages.welcome(),
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(),
        )

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /help command."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        await update.message.reply_text(
            Messages.help_text(),
            parse_mode="HTML",
        )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        status_data = await self._get_system_status()
        message = Messages.system_status(**status_data)

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.status_menu(),
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.status_menu(),
            )

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        stats_data = await self._get_post_stats()
        message = Messages.post_stats(**stats_data)

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.back_only(),
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.back_only(),
            )

    async def queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /queue command."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        posts = await self._get_scheduled_posts()
        message = Messages.scheduled_queue(posts)

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.queue_menu(has_items=bool(posts)),
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.queue_menu(has_items=bool(posts)),
            )

    async def trigger(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /trigger command - run pipeline manually."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        try:
            asyncio.create_task(self._run_pipeline())
            message = Messages.trigger_started()
        except Exception as e:
            message = Messages.trigger_failed(str(e))

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.back_only(),
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.back_only(),
            )

    async def pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pause command."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        if self._is_paused:
            message = Messages.already_paused()
        else:
            self._is_paused = True
            message = Messages.paused()

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.control_menu(is_paused=True),
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.control_menu(is_paused=True),
            )

    async def resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /resume command."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        if not self._is_paused:
            message = Messages.already_running()
        else:
            self._is_paused = False
            message = Messages.resumed()

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.control_menu(is_paused=False),
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.control_menu(is_paused=False),
            )

    async def logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /logs command."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        logs_text = await self._get_recent_logs(20)
        message = Messages.logs(logs_text)

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.back_only(),
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.back_only(),
            )

    async def backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /backup command."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        try:
            backup_file, size_mb = await self._create_backup()
            message = Messages.backup_completed(backup_file, size_mb)
        except Exception as e:
            message = Messages.backup_failed(str(e))

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.back_only(),
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.back_only(),
            )

    async def circuit_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle circuit breaker status."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.not_authorized())
            return

        cb_status = CircuitBreakerRegistry.get_all_status()
        message = Messages.circuit_breaker_status(cb_status)

        has_open = any(cb.get("state") == "open" for cb in cb_status.values())

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.circuit_menu(has_open_circuits=has_open),
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=Keyboards.circuit_menu(has_open_circuits=has_open),
            )

    async def circuit_reset(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Reset all circuit breakers."""
        if not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            return

        CircuitBreakerRegistry.reset_all()

        if update.callback_query:
            await self.circuit_status(update, context)

    async def callback_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle callback queries from inline keyboards."""
        if not update.callback_query or not update.effective_user:
            return

        if not self.is_authorized(update.effective_user.id):
            await update.callback_query.answer("Not authorized", show_alert=True)
            return

        query = update.callback_query
        await query.answer()

        data = query.data

        callback_map = {
            "main_menu": self._show_main_menu,
            "status": self.status,
            "stats": self.stats,
            "queue": self.queue,
            "trigger": self.trigger,
            "pause": self.pause,
            "resume": self.resume,
            "logs": self.logs,
            "backup": self.backup,
            "circuit": self.circuit_status,
            "circuit_reset": self.circuit_reset,
        }

        handler = callback_map.get(data)
        if handler:
            await handler(update, context)

    async def _show_main_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Show main menu."""
        if update.callback_query:
            await update.callback_query.edit_message_text(
                Messages.welcome(),
                parse_mode="HTML",
                reply_markup=Keyboards.main_menu(),
            )

    async def _get_system_status(self) -> dict[str, Any]:
        """Get system status data."""
        circuit_breakers = CircuitBreakerRegistry.get_all_status()
        last_post_time = None
        posts_today = 0
        errors_today = 0

        if self.admin_bot.db:
            try:
                from sqlalchemy import select, func
                from memory.models import Post

                async with self.admin_bot.db.session() as session:
                    result = await session.execute(
                        select(Post)
                        .where(Post.status == "published")
                        .order_by(Post.created_at.desc())
                        .limit(1)
                    )
                    last_post = result.scalar_one_or_none()
                    if last_post:
                        last_post_time = last_post.created_at

                    today = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    result = await session.execute(
                        select(func.count(Post.id))
                        .where(Post.status == "published")
                        .where(Post.created_at >= today)
                    )
                    posts_today = result.scalar() or 0
            except Exception as e:
                logger.error(f"Error getting status from database: {e}")

        return {
            "is_running": self.admin_bot.is_running and not self._is_paused,
            "scheduler_active": self.admin_bot.is_running and not self._is_paused,
            "publisher_mode": self.admin_bot.settings.telegram.posting_mode,
            "llm_provider": self.admin_bot.settings.llm.provider,
            "circuit_breakers": circuit_breakers,
            "last_post_time": last_post_time,
            "posts_today": posts_today,
            "errors_today": errors_today,
        }

    async def _get_post_stats(self) -> dict[str, Any]:
        """Get post statistics for the last 7 days."""
        total_posts = 0
        avg_quality = 0.0
        avg_views = None
        top_post_day = None
        posts_by_type: dict[str, int] = {}

        if self.admin_bot.db:
            try:
                from sqlalchemy import select, func
                from memory.models import Post

                async with self.admin_bot.db.session() as session:
                    week_ago = datetime.now() - timedelta(days=7)

                    result = await session.execute(
                        select(func.count(Post.id))
                        .where(Post.status == "published")
                        .where(Post.created_at >= week_ago)
                    )
                    total_posts = result.scalar() or 0

                    result = await session.execute(
                        select(func.avg(Post.quality_score))
                        .where(Post.status == "published")
                        .where(Post.created_at >= week_ago)
                    )
                    avg_quality = result.scalar() or 0.0

                    result = await session.execute(
                        select(Post.post_type, func.count(Post.id))
                        .where(Post.status == "published")
                        .where(Post.created_at >= week_ago)
                        .group_by(Post.post_type)
                    )
                    for row in result:
                        if row[0]:
                            posts_by_type[row[0]] = row[1]

                    result = await session.execute(
                        select(func.date(Post.created_at), func.count(Post.id))
                        .where(Post.status == "published")
                        .where(Post.created_at >= week_ago)
                        .group_by(func.date(Post.created_at))
                        .order_by(func.count(Post.id).desc())
                        .limit(1)
                    )
                    top = result.first()
                    if top:
                        top_post_day = str(top[0])

            except Exception as e:
                logger.error(f"Error getting stats from database: {e}")

        return {
            "total_posts": total_posts,
            "avg_quality": avg_quality,
            "avg_views": avg_views,
            "top_post_day": top_post_day,
            "posts_by_type": posts_by_type,
        }

    async def _get_scheduled_posts(self) -> list[dict]:
        """Get scheduled posts from queue."""
        return []

    async def _get_recent_logs(self, lines: int = 20) -> str:
        """Get recent log lines."""
        import os

        log_dir = "logs"
        log_files = []

        if os.path.exists(log_dir):
            for f in os.listdir(log_dir):
                if f.endswith(".log"):
                    log_files.append(os.path.join(log_dir, f))

        if not log_files:
            return "No log files found"

        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        latest_log = log_files[0]

        try:
            with open(latest_log, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return "".join(recent).strip()
        except Exception as e:
            return f"Error reading log file: {e}"

    async def _run_pipeline(self) -> None:
        """Run the pipeline manually."""
        if self.admin_bot.orchestrator:
            try:
                await self.admin_bot.orchestrator.run(dry_run=False)
            except Exception as e:
                logger.error(f"Pipeline trigger failed: {e}")

    async def _create_backup(self) -> tuple[str, float]:
        """Create a backup and return (filename, size_mb)."""
        from backup.backup_manager import BackupManager

        backup_manager = BackupManager(self.admin_bot.settings)
        backup_file = await backup_manager.create_backup()
        size_mb = backup_manager.get_backup_size(backup_file)
        return backup_file, size_mb

    @property
    def is_paused(self) -> bool:
        """Check if system is paused."""
        return self._is_paused
