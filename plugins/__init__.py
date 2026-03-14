"""
Plugins module.

Contains plugin interfaces and implementations for the TG AI Poster system.
"""

from __future__ import annotations

from plugins.media import MediaProvider, MediaSearchResult
from plugins.formatters import PostFormatter

__all__ = [
    "MediaProvider",
    "MediaSearchResult",
    "PostFormatter",
]
