"""
Real-Time Trend Detection - Detects trending topics from multiple sources.

Queries Google Trends RSS, Twitter/X trending topics, and GitHub Trending
to identify hot topics for prioritization in content selection.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

import aiohttp

from core.constants import (
    HN_TOPSTORIES_URL,
)
from core.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@dataclass(slots=True)
class TrendSignal:
    """Represents a trend signal from a single source."""

    source: str  # "google_trends", "github", "hackernews"
    topic: str
    score: float  # 0.0 to 1.0
    velocity: float  # Rate of change (positive = trending up)
    timestamp: datetime = field(default_factory=datetime.now)
    url: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class TrendScore:
    """Aggregated trend score for a topic."""

    topic: str
    total_score: float
    velocity: float
    sources: list[str] = field(default_factory=list)
    signals: list[TrendSignal] = field(default_factory=list)
    recommendation: str = "neutral"  # "hot", "warm", "neutral", "cold"

    @property
    def is_hot(self) -> bool:
        """Check if topic is trending hot."""
        return self.total_score >= 0.7 and self.velocity > 0.1


class TrendDetector:
    """
    Detects trending topics from multiple sources.

    Sources:
    - Google Trends RSS (free, no API key)
    - GitHub Trending (via API)
    - Hacker News (via Firebase API)
    """

    # Google Trends RSS feed URL
    GOOGLE_TRENDS_RSS = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"

    # GitHub Trending API (unofficial but works)
    GITHUB_TRENDING_URL = "https://api.gitterapp.com/repositories"

    # Cache duration
    CACHE_DURATION_MINUTES = 30

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        cache_duration_minutes: int = 30,
    ) -> None:
        """
        Initialize trend detector.

        Args:
            session: Optional aiohttp session
            cache_duration_minutes: How long to cache results
        """
        self._session = session
        self._own_session = session is None
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self._cache: dict[str, tuple[datetime, Any]] = {}
        self._last_fetch: Optional[datetime] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "TG-AI-Poster/1.0"},
            )
        return self._session

    async def close(self) -> None:
        """Close HTTP session if we own it."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache:
            return False
        timestamp, _ = self._cache[key]
        return datetime.now() - timestamp < self.cache_duration

    async def fetch_google_trends(self) -> list[TrendSignal]:
        """
        Fetch trending topics from Google Trends RSS.

        Returns:
            List of trend signals from Google Trends
        """
        if self._is_cache_valid("google_trends"):
            return self._cache["google_trends"][1]

        session = await self._get_session()
        signals = []

        try:
            async with session.get(self.GOOGLE_TRENDS_RSS) as response:
                if response.status != 200:
                    logger.warning("Google Trends returned status %d", response.status)
                    return []

                content = await response.text()

            # Parse RSS feed (simple regex-based parsing)
            # Look for <title> and <ht:approx_traffic> tags
            items = re.findall(
                r"<item>.*?<title><!\[CDATA\[(.*?)\]\]></title>.*?"
                r"<ht:approx_traffic>(.*?)</ht:approx_traffic>.*?</item>",
                content,
                re.DOTALL,
            )

            for i, (title, traffic) in enumerate(items[:20]):
                # Parse traffic (e.g., "200K+" -> 200000)
                traffic_num = 0
                if traffic:
                    match = re.search(r"(\d+(?:\.\d+)?)[KM]?\+?", traffic)
                    if match:
                        traffic_num = float(match.group(1))
                        if "M" in traffic:
                            traffic_num *= 1_000_000
                        elif "K" in traffic:
                            traffic_num *= 1_000

                # Normalize score (top result = 1.0, decreasing)
                score = max(0.1, 1.0 - (i * 0.05))

                signals.append(TrendSignal(
                    source="google_trends",
                    topic=title.strip(),
                    score=score,
                    velocity=traffic_num / 1_000_000,  # Normalize to millions
                    metadata={"traffic": traffic, "rank": i + 1},
                ))

            self._cache["google_trends"] = (datetime.now(), signals)
            logger.info("Fetched %d Google Trends signals", len(signals))

        except Exception as e:
            logger.warning("Failed to fetch Google Trends: %s", e)

        return signals

    async def fetch_github_trending(self) -> list[TrendSignal]:
        """
        Fetch trending repositories from GitHub.

        Returns:
            List of trend signals from GitHub Trending
        """
        if self._is_cache_valid("github_trending"):
            return self._cache["github_trending"][1]

        session = await self._get_session()
        signals = []

        try:
            # Use GitHub's search API for trending (stars in last 24h)
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            url = f"https://api.github.com/search/repositories?q=stars:>100+created:>{yesterday}&sort=stars&order=desc&per_page=20"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning("GitHub returned status %d", response.status)
                    return []

                data = await response.json()

            for i, repo in enumerate(data.get("items", [])[:20]):
                # Extract AI/ML related topics
                description = repo.get("description", "") or ""
                name = repo.get("full_name", "")
                topics = repo.get("topics", [])

                # Check if AI-related
                ai_keywords = ["ai", "ml", "machine-learning", "llm", "gpt", "neural", "deep-learning", "nlp", "transformer"]
                is_ai_related = any(kw in " ".join(topics).lower() or kw in description.lower() for kw in ai_keywords)

                if not is_ai_related:
                    continue

                score = max(0.1, 0.9 - (i * 0.04))
                stars = repo.get("stargazers_count", 0)

                signals.append(TrendSignal(
                    source="github",
                    topic=f"{name}: {description[:50]}",
                    score=score,
                    velocity=stars / 1000,  # Normalize stars
                    url=repo.get("html_url"),
                    metadata={"stars": stars, "language": repo.get("language"), "topics": topics},
                ))

            self._cache["github_trending"] = (datetime.now(), signals)
            logger.info("Fetched %d GitHub Trending signals", len(signals))

        except Exception as e:
            logger.warning("Failed to fetch GitHub Trending: %s", e)

        return signals

    async def fetch_hackernews_trending(self) -> list[TrendSignal]:
        """
        Fetch trending stories from Hacker News.

        Returns:
            List of trend signals from HN
        """
        if self._is_cache_valid("hackernews"):
            return self._cache["hackernews"][1]

        session = await self._get_session()
        signals = []

        try:
            # Get top stories
            async with session.get(HN_TOPSTORIES_URL) as response:
                story_ids = await response.json()

            # Fetch top 20 stories
            for i, story_id in enumerate(story_ids[:20]):
                try:
                    url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    async with session.get(url) as story_response:
                        story = await story_response.json()

                    if not story:
                        continue

                    title = story.get("title", "")
                    score = story.get("score", 0)
                    url_link = story.get("url", "")

                    # Check if tech/AI related
                    tech_keywords = ["ai", "ml", "llm", "gpt", "neural", "algorithm", "model", "openai", "anthropic"]
                    is_tech = any(kw in title.lower() for kw in tech_keywords)

                    trend_score = max(0.1, 0.85 - (i * 0.04)) if is_tech else max(0.05, 0.5 - (i * 0.025))

                    signals.append(TrendSignal(
                        source="hackernews",
                        topic=title,
                        score=trend_score,
                        velocity=score / 100,  # Normalize score
                        url=url_link,
                        metadata={"hn_score": score, "comments": story.get("descendants", 0)},
                    ))

                except Exception as e:
                    logger.debug("Failed to fetch HN story %d: %s", story_id, e)
                    continue

            self._cache["hackernews"] = (datetime.now(), signals)
            logger.info("Fetched %d Hacker News signals", len(signals))

        except Exception as e:
            logger.warning("Failed to fetch Hacker News: %s", e)

        return signals

    async def detect_trends(self) -> list[TrendScore]:
        """
        Aggregate trend signals from all sources.

        Returns:
            List of aggregated trend scores
        """
        # Fetch all sources in parallel
        results = await asyncio.gather(
            self.fetch_google_trends(),
            self.fetch_github_trending(),
            self.fetch_hackernews_trending(),
            return_exceptions=True,
        )

        all_signals: list[TrendSignal] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Trend source fetch failed: %s", result)
            elif isinstance(result, list):
                all_signals.extend(result)

        # Aggregate by topic (normalized)
        topic_scores: dict[str, TrendScore] = {}

        for signal in all_signals:
            # Normalize topic (lowercase, remove special chars)
            normalized = re.sub(r"[^\w\s]", "", signal.topic.lower())[:50]

            if normalized not in topic_scores:
                topic_scores[normalized] = TrendScore(
                    topic=signal.topic,
                    total_score=0.0,
                    velocity=0.0,
                    sources=[],
                    signals=[],
                )

            score = topic_scores[normalized]
            score.total_score += signal.score * 0.33  # Weight per source
            score.velocity += signal.velocity * 0.33
            if signal.source not in score.sources:
                score.sources.append(signal.source)
            score.signals.append(signal)

        # Calculate recommendations
        for score in topic_scores.values():
            if score.total_score >= 0.7:
                score.recommendation = "hot"
            elif score.total_score >= 0.5:
                score.recommendation = "warm"
            elif score.total_score >= 0.3:
                score.recommendation = "neutral"
            else:
                score.recommendation = "cold"

        # Sort by total score
        sorted_scores = sorted(
            topic_scores.values(),
            key=lambda x: x.total_score,
            reverse=True,
        )

        self._last_fetch = datetime.now()
        logger.info("Detected %d trending topics", len(sorted_scores))

        return sorted_scores[:30]  # Top 30

    def get_hot_topics(self, min_score: float = 0.6) -> list[str]:
        """
        Get list of hot topics for content prioritization.

        Args:
            min_score: Minimum score threshold

        Returns:
            List of hot topic strings
        """
        # This would be called after detect_trends()
        # For now, return cached hot topics
        hot_topics = []
        for key, (timestamp, data) in self._cache.items():
            if isinstance(data, list):
                for signal in data:
                    if isinstance(signal, TrendSignal) and signal.score >= min_score:
                                hot_topics.append(signal.topic)
        return list(set(hot_topics))[:10]


# Configuration schema
TREND_DETECTOR_CONFIG_SCHEMA = {
    "trends": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable trend detection",
        },
        "cache_duration_minutes": {
            "type": "int",
            "default": 30,
            "description": "How long to cache trend data",
        },
        "min_score_threshold": {
            "type": "float",
            "default": 0.5,
            "description": "Minimum score for topic prioritization",
        },
    }
}
