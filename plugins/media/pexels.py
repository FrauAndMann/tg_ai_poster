"""
Pexels media provider.

Fallback media provider using Pexels API.
"""

from __future__ import annotations

import os
import random
from typing import Optional

import aiohttp

from plugins.media.base import MediaProvider, MediaSearchResult
from core.logger import get_logger

logger = get_logger(__name__)


class PexelsProvider(MediaProvider):
    """Pexels API media provider."""

    name = "pexels"
    base_url = "https://api.pexels.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Pexels provider.

        Args:
            api_key: Pexels API key (defaults to PEXELS_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("PEXELS_API_KEY")
        self.rate_limit = (0, 200)  # (used, remaining) - Pexels has higher limits
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            headers = {
                "Authorization": self.api_key,
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[MediaSearchResult]:
        """
        Search for images on Pexels.

        Args:
            query: Search query
            limit: Maximum results (default 5)

        Returns:
            List of media search results
        """
        if not self.api_key:
            logger.warning("Pexels API key not configured")
            return []

        session = await self._get_session()

        try:
            url = f"{self.base_url}/search"
            params = {
                "query": query,
                "per_page": limit,
                "orientation": "landscape",
            }

            async with session.get(url, params=params) as response:
                if response.status == 401:
                    logger.error("Pexels API unauthorized - check API key")
                    return []

                if response.status == 429:
                    logger.error("Pexels API rate limit exceeded")
                    return []

                response.raise_for_status()
                data = await response.json()

            results = []
            for item in data.get("photos", []):
                results.append(
                    MediaSearchResult(
                        url=item["src"]["large"],
                        photographer=item["photographer"],
                        source="pexels",
                        width=item.get("width", 0),
                        height=item.get("height", 0),
                        alt_description=item.get("alt", ""),
                    )
                )

            return results

        except aiohttp.ClientError as e:
            logger.error(f"Pexels search failed: {e}")
            return []

    async def get_random(self, topic: str) -> Optional[MediaSearchResult]:
        """
        Get a random image for a topic.

        Args:
            topic: Topic to search for

        Returns:
            Random media result or None
        """
        if not self.api_key:
            logger.warning("Pexels API key not configured")
            return None

        try:
            results = await self.search(topic, limit=15)

            if results:
                return random.choice(results)

            # Fallback to generic tech search
            results = await self.search("technology", limit=10)
            if results:
                return random.choice(results)

            return None

        except Exception as e:
            logger.error(f"Pexels get_random failed: {e}")
            return None

    async def health_check(self) -> bool:
        """
        Check if Pexels API is accessible.

        Returns:
            True if API responds correctly
        """
        if not self.api_key:
            return False

        session = await self._get_session()

        try:
            # Search with minimal results to check connectivity
            url = f"{self.base_url}/search"
            params = {"query": "test", "per_page": 1}
            async with session.get(url, params=params) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
