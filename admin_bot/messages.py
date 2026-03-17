"""
Message templates for Admin Bot.

Contains formatted message templates for all bot responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


class Messages:
    """Message templates for Admin Bot responses."""

    # =========================================================================
    # Welcome and Help
    # =========================================================================

    @staticmethod
    def welcome() -> str:
        """Welcome message for /start command."""
        return """🤖 <b>TG AI Poster - Admin Panel</b>

Добро пожаловать в панель управления автоматическим постингом!

<b>Доступные команды:</b>
/status - Статус системы
/stats - Статистика постов
/queue - Очередь публикаций
/trigger - Запустить pipeline
/pause - Пауза автопостинга
/resume - Возобновить постинг
/logs - Последние логи
/backup - Создать резервную копию
/help - Справка по командам
"""

    @staticmethod
    def help_text() -> str:
        """Detailed help message."""
        return """📖 <b>Справка по командам</b>

<b>Управление системой:</b>
• /status - Проверить состояние всех компонентов
• /trigger - Принудительно запустить генерацию поста
• /pause - Приостановить автоматический постинг
• /resume - Возобновить автоматический постинг

<b>Мониторинг:</b>
• /stats - Статистика постов за последние 7 дней
• /queue - Показать запланированные публикации
• /logs - Последние 20 строк логов

<b>Резервное копирование:</b>
• /backup - Создать резервную копию данных

<b>Circuit Breaker:</b>
• /circuit - Статус circuit breakers
• /circuit reset - Сбросить все circuit breakers
"""

    # =========================================================================
    # Status Messages
    # =========================================================================

    @staticmethod
    def system_status(
        is_running: bool,
        scheduler_active: bool,
        publisher_mode: str,
        llm_provider: str,
        circuit_breakers: dict[str, dict],
        last_post_time: Optional[datetime] = None,
        posts_today: int = 0,
        errors_today: int = 0,
    ) -> str:
        """System status message."""
        status_emoji = "🟢" if is_running else "🔴"
        scheduler_emoji = "🟢" if scheduler_active else "🔴"

        # Circuit breaker status
        cb_lines = []
        for name, status in circuit_breakers.items():
            state = status.get("state", "unknown")
            if state == "closed":
                cb_emoji = "🟢"
            elif state == "open":
                cb_emoji = "🔴"
            else:
                cb_emoji = "🟡"
            cb_lines.append(f"  {cb_emoji} {name}: {state}")

        cb_text = "\n".join(cb_lines) if cb_lines else "  Нет активных"

        last_post = (
            last_post_time.strftime("%d.%m %H:%M") if last_post_time else "Нет данных"
        )

        return f"""📊 <b>Статус системы</b>

{status_emoji} <b>Система:</b> {"Работает" if is_running else "Остановлена"}
{scheduler_emoji} <b>Планировщик:</b> {"Активен" if scheduler_active else "Пауза"}

<b>Конфигурация:</b>
• Publisher: {publisher_mode}
• LLM: {llm_provider}

<b>Статистика сегодня:</b>
• Постов: {posts_today}
• Ошибок: {errors_today}
• Последний пост: {last_post}

<b>Circuit Breakers:</b>
{cb_text}
"""

    @staticmethod
    def circuit_breaker_status(circuit_breakers: dict[str, dict]) -> str:
        """Circuit breaker status message."""
        if not circuit_breakers:
            return "⚡ <b>Circuit Breakers</b>\n\nНет активных circuit breakers."

        lines = ["⚡ <b>Circuit Breakers</b>\n"]
        for name, status in circuit_breakers.items():
            state = status.get("state", "unknown")
            failures = status.get("failure_count", 0)
            threshold = status.get("failure_threshold", 0)
            stats = status.get("stats", {})
            rejected = stats.get("rejected_calls", 0)

            if state == "closed":
                emoji = "🟢"
            elif state == "open":
                emoji = "🔴"
            else:
                emoji = "🟡"

            lines.append(f"{emoji} <b>{name}</b>")
            lines.append(f"   State: {state}")
            lines.append(f"   Failures: {failures}/{threshold}")
            lines.append(f"   Rejected: {rejected}")
            lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # Statistics Messages
    # =========================================================================

    @staticmethod
    def post_stats(
        total_posts: int,
        avg_quality: float,
        avg_views: Optional[int] = None,
        top_post_day: Optional[str] = None,
        posts_by_type: Optional[dict] = None,
    ) -> str:
        """Post statistics message."""
        views_text = f"{avg_views:,}" if avg_views else "Нет данных"
        quality_text = f"{avg_quality:.1%}" if avg_quality else "Нет данных"

        lines = [
            "📈 <b>Статистика постов (7 дней)</b>",
            "",
            f"• Всего постов: {total_posts}",
            f"• Среднее качество: {quality_text}",
            f"• Средние просмотры: {views_text}",
        ]

        if posts_by_type:
            lines.append("")
            lines.append("<b>По типам:</b>")
            for post_type, count in posts_by_type.items():
                lines.append(f"  • {post_type}: {count}")

        if top_post_day:
            lines.append("")
            lines.append(f"🔥 Лучший день: {top_post_day}")

        return "\n".join(lines)

    # =========================================================================
    # Queue Messages
    # =========================================================================

    @staticmethod
    def scheduled_queue(posts: list[dict]) -> str:
        """Scheduled posts queue message."""
        if not posts:
            return "📋 <b>Очередь публикаций</b>\n\nОчередь пуста."

        lines = ["📋 <b>Очередь публикаций</b>\n"]
        for i, post in enumerate(posts[:10], 1):  # Show max 10
            scheduled_time = post.get("scheduled_time", "?")
            title = post.get("title", "Без названия")[:30]
            lines.append(f"{i}. [{scheduled_time}] {title}...")

        if len(posts) > 10:
            lines.append(f"\n... и ещё {len(posts) - 10} постов")

        return "\n".join(lines)

    # =========================================================================
    # Action Results
    # =========================================================================

    @staticmethod
    def trigger_started() -> str:
        """Pipeline trigger started message."""
        return "🚀 Pipeline запущен. Результат будет в логах."

    @staticmethod
    def trigger_failed(error: str) -> str:
        """Pipeline trigger failed message."""
        return f"❌ Ошибка запуска pipeline:\n\n{error}"

    @staticmethod
    def paused() -> str:
        """System paused message."""
        return "⏸️ Автопостинг приостановлен.\n\nИспользуйте /resume для возобновления."

    @staticmethod
    def resumed() -> str:
        """System resumed message."""
        return "▶️ Автопостинг возобновлён."

    @staticmethod
    def backup_started() -> str:
        """Backup started message."""
        return "💾 Создание резервной копии начато..."

    @staticmethod
    def backup_completed(backup_file: str, size_mb: float) -> str:
        """Backup completed message."""
        return f"✅ Резервная копия создана!\n\n📁 {backup_file}\n📊 Размер: {size_mb:.2f} MB"

    @staticmethod
    def backup_failed(error: str) -> str:
        """Backup failed message."""
        return f"❌ Ошибка создания backup:\n\n{error}"

    @staticmethod
    def logs(logs_text: str) -> str:
        """Recent logs message."""
        return f"📜 <b>Последние логи</b>\n\n<pre>{logs_text}</pre>"

    @staticmethod
    def already_paused() -> str:
        """System already paused message."""
        return "System is already paused."

    @staticmethod
    def already_running() -> str:
        """System already running message."""
        return "System is already running."

    @staticmethod
    def not_authorized() -> str:
        """Not authorized message."""
        return "You do not have access to this bot."

    # =========================================================================
    # Error Messages
    # =========================================================================

    @staticmethod
    def error(message: str) -> str:
        """Generic error message."""
        return f"❌ Ошибка: {message}"

    @staticmethod
    def command_failed(command: str, error: str) -> str:
        """Command failed message."""
        return f"❌ Команда /{command} не выполнена:\n\n{error}"
