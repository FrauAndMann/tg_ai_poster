"""
Media provider base interface.

Defines the contract for media provider implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MediaSearchResult:
    """Immutable result from media search."""

    url: str
    photographer: str
    source: str  # "unsplash" | "pexels" | "generated"
    width: int = 0
    height: int = 0
    alt_description: str = ""


class MediaProvider(ABC):
    """Abstract base class for media providers."""

    name: str = "base"
    rate_limit: tuple[int, int] = (50, 50)  # (used, remaining)

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[MediaSearchResult]:
        """
        Search for media by query.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of media search results
        """
        pass

    @abstractmethod
    async def get_random(self, topic: str) -> Optional[MediaSearchResult]:
        """
        Get a random image for a topic.

        Args:
            topic: Topic to find image for

        Returns:
            Single media result or None if not found
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if provider is available and configured.

        Returns:
            True if provider is healthy
        """
        pass
