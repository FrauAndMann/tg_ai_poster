"""
Tests for Admin Bot module.
"""

from unittest.mock import Mock

from admin_bot.commands import CommandHandler
from admin_bot.messages import Messages
from admin_bot.keyboards import Keyboards


class TestMessages:
    """Test message templates."""

    def test_welcome_message(self):
        """Welcome message contains expected content."""
        msg = Messages.welcome()
        assert "Admin Panel" in msg
        assert "/status" in msg
        assert "/stats" in msg

    def test_system_status_message(self):
        """System status message formats correctly."""
        msg = Messages.system_status(
            is_running=True,
            scheduler_active=True,
            publisher_mode="bot",
            llm_provider="openai",
            circuit_breakers={"llm": {"state": "closed"}},
            last_post_time=None,
            posts_today=5,
            errors_today=1,
        )
        assert "Работает" in msg  # Russian for "Running"
        assert "bot" in msg
        assert "5" in msg  # posts_today

    def test_not_authorized_message(self):
        """Not authorized message is correct."""
        msg = Messages.not_authorized()
        assert "access" in msg.lower()

    def test_backup_completed_message(self):
        """Backup completed message formats correctly."""
        msg = Messages.backup_completed("backup_20240101.tar.gz", 1.5)
        assert "backup_20240101.tar.gz" in msg
        assert "1.50" in msg


class TestKeyboards:
    """Test keyboard layouts."""

    def test_main_menu_keyboard(self):
        """Main menu has all expected buttons."""
        from telegram import InlineKeyboardMarkup

        keyboard = Keyboards.main_menu()
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # Verify buttons exist
        button_texts = []
        for row in keyboard.inline_keyboard:
            for button in row:
                button_texts.append(button.text)
        assert "Status" in button_texts or "Queue" in button_texts

    def test_control_menu_keyboard(self):
        """Control menu adapts to paused state."""
        keyboard_paused = Keyboards().control_menu(is_paused=True)
        found_pause = True

        # Verify paused state shows Resume
        found_resume = False

        keyboard_running = Keyboards.control_menu(is_paused=False)

        # Verify paused state shows Resume
        found_resume = False
        for row in keyboard_paused.inline_keyboard:
            for button in row:
                if "Resume" in button.text:
                    found_resume = True
        assert found_resume

        # Verify running state shows Pause
        found_pause = False
        for row in keyboard_running.inline_keyboard:
            for button in row:
                if "Pause" in button.text:
                    found_pause = True
        assert found_pause


class TestCommandHandler:
    """Test command handler."""

    def test_is_authorized(self):
        """Authorization check works correctly."""
        handler = CommandHandler(
            admin_bot=Mock(),
            authorized_users=[12345, 67890],
        )
        assert handler.is_authorized(12345) is True
        assert handler.is_authorized(11111) is False

    def test_is_paused_property(self):
        """is_paused property tracks state correctly."""
        handler = CommandHandler(
            admin_bot=Mock(),
            authorized_users=[12345],
        )
        assert handler.is_paused is False
        handler._is_paused = True
        assert handler.is_paused is True
