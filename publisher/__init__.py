"""
Publisher module for TG AI Poster.

Contains base class and implementations for different posting modes.
"""

from .base import BasePublisher
from .bot_publisher import BotPublisher
from .telethon_publisher import TelethonPublisher

__all__ = [
    "BasePublisher",
    "BotPublisher",
    "TelethonPublisher",
]


def get_publisher(
    mode: str,
    bot_token: str = "",
    channel_id: str = "",
    telethon_api_id: int = 0,
    telethon_api_hash: str = "",
    telethon_phone: str = "",
    telethon_session_path: str = "sessions/user.session",
) -> BasePublisher:
    """
    Factory function to get the appropriate publisher.

    Args:
        mode: Publishing mode ("bot" or "telethon")
        bot_token: Telegram bot token
        channel_id: Target channel ID
        telethon_api_id: Telethon API ID
        telethon_api_hash: Telethon API hash
        telethon_phone: Telethon phone number
        telethon_session_path: Path to Telethon session file

    Returns:
        BasePublisher: Configured publisher instance
    """
    if mode == "bot":
        return BotPublisher(
            bot_token=bot_token,
            channel_id=channel_id,
        )
    elif mode == "telethon":
        return TelethonPublisher(
            api_id=telethon_api_id,
            api_hash=telethon_api_hash,
            phone=telethon_phone,
            channel_id=channel_id,
            session_path=telethon_session_path,
        )
    else:
        raise ValueError(f"Unknown publisher mode: {mode}")
