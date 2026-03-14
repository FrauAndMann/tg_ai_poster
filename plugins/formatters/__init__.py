"""
Formatters plugins module.

Provides interfaces and implementations for post formatters.
"""

from __future__ import annotations

from plugins.formatters.base import PostFormatter
from plugins.formatters.telegram import TelegramFormatter

__all__ = [
    "PostFormatter",
    "TelegramFormatter",
]
