"""
Unsplash media provider.

Fetches images from Unsplash API.
"""

from __future__ import annotations

import os
import random
from typing import Optional

import aiohttp

from plugins.media.base import MediaProvider, MediaSearchResult
from core.logger import get_logger

logger = get_logger(__name__)


class UnsplashProvider(MediaProvider):
    """Unsplash API media provider."""

    name = "unsplash"
    base_url = "https://api.unsplash.com"

    def __init__(self, access_key: Optional[str] = None):
        """
        Initialize Unsplash provider.

        Args:
            access_key: Unsplash API access key (defaults to UNSPLASH_ACCESS_KEY env var)
        """
        self.access_key = access_key or os.getenv("UNSPLASH_ACCESS_KEY")
        self.rate_limit = (0, 50)  # (used, remaining)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            headers = {
                "Accept-Version": "v1",
                "Authorization": f"Client-ID {self.access_key}",
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[MediaSearchResult]:
        """
        Search for images on Unsplash.

        Args:
            query: Search query
            limit: Maximum results (default 5)

        Returns:
            List of media search results
        """
        if not self.access_key:
            logger.warning("Unsplash access key not configured")
            return []

        session = await self._get_session()

        try:
            url = f"{self.base_url}/search/photos"
            params = {
                "query": query,
                "per_page": limit,
                "orientation": "landscape",
            }

            async with session.get(url, params=params) as response:
                # Update rate limit from headers
                self._update_rate_limit(response)

                if response.status == 401:
                    logger.error("Unsplash API unauthorized - check access key")
                    return []

                if response.status == 403:
                    logger.error("Unsplash API rate limit exceeded")
                    return []

                response.raise_for_status()
                data = await response.json()

            results = []
            for item in data.get("results", []):
                results.append(
                    MediaSearchResult(
                        url=item["urls"]["regular"],
                        photographer=item["user"]["name"],
                        source="unsplash",
                        width=item.get("width", 0),
                        height=item.get("height", 0),
                        alt_description=item.get("alt_description", ""),
                    )
                )

            return results

        except aiohttp.ClientError as e:
            logger.error(f"Unsplash search failed: {e}")
            return []

    async def get_random(self, topic: str) -> Optional[MediaSearchResult]:
        """
        Get a random image for a topic.

        Args:
            topic: Topic to search for

        Returns:
            Random media result or None
        """
        if not self.access_key:
            logger.warning("Unsplash access key not configured")
            return None

        session = await self._get_session()

        try:
            # First try search for relevant images
            results = await self.search(topic, limit=10)

            if results:
                return random.choice(results)

            # Fallback to random photo endpoint
            url = f"{self.base_url}/photos/random"
            params = {
                "orientation": "landscape",
                "query": "technology",  # Generic fallback
            }

            async with session.get(url, params=params) as response:
                self._update_rate_limit(response)
                response.raise_for_status()
                data = await response.json()

            return MediaSearchResult(
                url=data["urls"]["regular"],
                photographer=data["user"]["name"],
                source="unsplash",
                width=data.get("width", 0),
                height=data.get("height", 0),
                alt_description=data.get("alt_description", ""),
            )

        except aiohttp.ClientError as e:
            logger.error(f"Unsplash get_random failed: {e}")
            return None

    async def health_check(self) -> bool:
        """
        Check if Unsplash API is accessible.

        Returns:
            True if API responds correctly
        """
        if not self.access_key:
            return False

        session = await self._get_session()

        try:
            url = f"{self.base_url}/me"
            async with session.get(url) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

    def _update_rate_limit(self, response: aiohttp.ClientResponse) -> None:
        """Update rate limit info from response headers."""
        used = response.headers.get("X-Ratelimit-Used")
        remaining = response.headers.get("X-Ratelimit-Remaining")

        if used and remaining:
            self.rate_limit = (int(used), int(remaining))

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
