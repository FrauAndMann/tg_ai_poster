"""
Media plugins module.

Provides interfaces and implementations for media providers.
"""

from __future__ import annotations

from plugins.media.base import MediaProvider, MediaSearchResult

__all__ = [
    "MediaProvider",
    "MediaSearchResult",
]
