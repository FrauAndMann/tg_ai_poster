"""
Inline keyboards for Admin Bot.

Provides keyboard layouts for interactive commands.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class Keyboards:
    """Inline keyboard layouts for Admin Bot."""

    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Main menu keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("Status", callback_data="status"),
                InlineKeyboardButton("Stats", callback_data="stats"),
            ],
            [
                InlineKeyboardButton("Queue", callback_data="queue"),
                InlineKeyboardButton("Logs", callback_data="logs"),
            ],
            [
                InlineKeyboardButton("Trigger", callback_data="trigger"),
            ],
            [
                InlineKeyboardButton("Pause", callback_data="pause"),
                InlineKeyboardButton("Resume", callback_data="resume"),
            ],
            [
                InlineKeyboardButton("Backup", callback_data="backup"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def status_menu() -> InlineKeyboardMarkup:
        """Status menu keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("Refresh", callback_data="status"),
            ],
            [
                InlineKeyboardButton("Circuit Breakers", callback_data="circuit"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def circuit_menu(has_open_circuits: bool = False) -> InlineKeyboardMarkup:
        """Circuit breaker menu keyboard."""
        keyboard = []

        if has_open_circuits:
            keyboard.append(
                [
                    InlineKeyboardButton("Reset All", callback_data="circuit_reset"),
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton("Refresh", callback_data="circuit"),
            ]
        )

        keyboard.append(
            [
                InlineKeyboardButton("Back", callback_data="status"),
            ]
        )

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def confirm(action: str) -> InlineKeyboardMarkup:
        """Confirmation keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("Yes", callback_data=f"confirm_{action}"),
                InlineKeyboardButton("No", callback_data="cancel"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def back_only(back_to: str = "main_menu") -> InlineKeyboardMarkup:
        """Keyboard with only back button."""
        keyboard = [
            [
                InlineKeyboardButton("Back", callback_data=back_to),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def queue_menu(has_items: bool = False) -> InlineKeyboardMarkup:
        """Queue menu keyboard."""
        keyboard = []

        if has_items:
            keyboard.append(
                [
                    InlineKeyboardButton("Clear Queue", callback_data="queue_clear"),
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton("Refresh", callback_data="queue"),
            ]
        )

        keyboard.append(
            [
                InlineKeyboardButton("Back", callback_data="main_menu"),
            ]
        )

        return InlineKeyboardMarkup(keyboard)
