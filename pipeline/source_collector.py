"""
Source collector for gathering content from RSS feeds and APIs.

Fetches, parses, and deduplicates articles from configured sources.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import html

import feedparser
from aiohttp import ClientSession, ClientTimeout

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Article:
    """
    Represents a collected article.

    Attributes:
        title: Article title
        summary: Article summary/description
        url: Article URL
        published_at: Publication date
        source: Source name/URL
        content_hash: Hash for deduplication
        tags: Optional tags/categories
    """

    title: str
    summary: str
    url: str
    published_at: Optional[datetime] = None
    source: str = ""
    content_hash: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Generate content hash after initialization."""
        if not self.content_hash:
            self.content_hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate hash for deduplication."""
        content = f"{self.title}:{self.url}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "published_at": self.published_at.isoformat()
            if self.published_at
            else None,
            "source": self.source,
            "content_hash": self.content_hash,
            "tags": self.tags,
        }


class SourceCollector:
    """
    Collects content from RSS feeds and external APIs.

    Handles feed parsing, deduplication, and content extraction.
    Supports RSS, HackerNews, and ProductHunt sources.
    """

    # HackerNews API endpoints
    HN_TOPSTORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
    HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

    # ProductHunt RSS feed
    PRODUCTHUNT_RSS = "https://www.producthunt.com/feed"

    def __init__(
        self,
        rss_feeds: list[str],
        fetch_timeout: int = 30,
        max_articles_per_feed: int = 10,
        user_agent: str = "TG-AI-Poster/1.0",
        enable_hackernews: bool = True,
        enable_producthunt: bool = True,
        hackernews_limit: int = 20,
    ) -> None:
        """
        Initialize source collector.

        Args:
            rss_feeds: List of RSS feed URLs
            fetch_timeout: Timeout for HTTP requests
            max_articles_per_feed: Maximum articles to collect per feed
            user_agent: User agent for requests
            enable_hackernews: Enable HackerNews collection
            enable_producthunt: Enable ProductHunt collection
            hackernews_limit: Maximum HackerNews stories to fetch
        """
        self.rss_feeds = rss_feeds
        self.fetch_timeout = fetch_timeout
        self.max_articles_per_feed = max_articles_per_feed
        self.user_agent = user_agent
        self.enable_hackernews = enable_hackernews
        self.enable_producthunt = enable_producthunt
        self.hackernews_limit = hackernews_limit
        self._seen_hashes: set[str] = set()
        self._session: Optional[ClientSession] = None

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """
        Parse publication date from RSS entry.

        Args:
            entry: RSS feed entry

        Returns:
            datetime | None: Parsed date or None
        """
        date_fields = ["published_parsed", "updated_parsed"]

        for date_field in date_fields:
            if hasattr(entry, date_field):
                time_struct = getattr(entry, date_field)
                if time_struct:
                    try:
                        return datetime(*time_struct[:6])
                    except (TypeError, ValueError):
                        pass

        return None

    def _clean_text(self, text: str) -> str:
        """
        Clean HTML and whitespace from text.

        Args:
            text: Raw text

        Returns:
            str: Cleaned text
        """
        if not text:
            return ""

        # Decode HTML entities
        text = html.unescape(text)

        # Remove HTML tags (simple approach)
        import re

        text = re.sub(r"<[^>]+>", "", text)

        # Normalize whitespace
        text = " ".join(text.split())

        return text.strip()

    async def _fetch_rss_with_fallback(self, url: str):
        """
        Fallback method to fetch and clean broken RSS feeds.

        Some feeds have invalid XML characters that feedparser can't handle.
        This method fetches the raw content, cleans common XML issues,
        and then parses it.

        Args:
            url: RSS feed URL

        Returns:
            Parsed feed object or empty feed
        """
        import re

        try:
            async with ClientSession(
                timeout=ClientTimeout(total=self.fetch_timeout)
            ) as session:
                headers = {"User-Agent": self.user_agent}
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Fallback fetch failed: HTTP {response.status}")
                        return feedparser.parse("")  # Empty feed

                    content = await response.text()

            # Clean common XML issues
            # Remove invalid XML characters (control chars except \t, \n, \r)
            content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", content)

            # Fix common entity issues
            content = content.replace("&nbsp;", " ")
            content = content.replace("&mdash;", "—")
            content = content.replace("&ndash;", "–")
            content = content.replace("&rsquo;", "'")
            content = content.replace("&lsquo;", "'")
            content = content.replace("&rdquo;", '"')
            content = content.replace("&ldquo;", '"')

            # Fix unescaped ampersands in URLs
            content = re.sub(
                r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", content
            )

            # Try parsing cleaned content
            feed = feedparser.parse(content)

            if len(feed.entries) > 0:
                logger.info(
                    f"Fallback parsing succeeded for {url}: {len(feed.entries)} entries"
                )

            return feed

        except Exception as e:
            logger.error(f"Fallback fetch failed for {url}: {e}")
            return feedparser.parse("")  # Empty feed

    async def fetch_rss(self, url: str) -> list[Article]:
        """
        Fetch and parse an RSS feed.

        Args:
            url: RSS feed URL

        Returns:
            list[Article]: List of parsed articles
        """
        logger.debug(f"Fetching RSS feed: {url}")

        articles = []

        try:
            # First try: direct feedparser parse
            feed = feedparser.parse(
                url,
                agent=self.user_agent,
            )

            # Check for severe XML issues that resulted in 0 entries
            if feed.bozo and feed.bozo_exception and len(feed.entries) == 0:
                logger.warning(
                    f"RSS feed has severe issues, trying fallback: {url}. Error: {feed.bozo_exception}"
                )
                # Fallback: fetch raw content and try to clean it
                feed = await self._fetch_rss_with_fallback(url)

            if feed.bozo and feed.bozo_exception:
                logger.warning(
                    f"RSS feed has issues: {url}. Error: {feed.bozo_exception}"
                )

            feed_title = feed.feed.get("title", url)

            for entry in feed.entries[: self.max_articles_per_feed]:
                try:
                    title = self._clean_text(entry.get("title", ""))
                    summary = self._clean_text(
                        entry.get("summary") or entry.get("description", "")
                    )
                    article_url = entry.get("link", "")

                    if not title or not article_url:
                        continue

                    published_at = self._parse_date(entry)

                    # Get tags/categories
                    tags = []
                    if hasattr(entry, "tags"):
                        tags = [tag.term for tag in entry.tags if hasattr(tag, "term")]

                    article = Article(
                        title=title,
                        summary=summary[:500]
                        if summary
                        else "",  # Limit summary length
                        url=article_url,
                        published_at=published_at,
                        source=feed_title,
                        tags=tags,
                    )

                    articles.append(article)

                except Exception as e:
                    logger.warning(f"Failed to parse RSS entry: {e}")
                    continue

            logger.info(f"Fetched {len(articles)} articles from {url}")

        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {url}: {e}")

        return articles

    async def fetch_all(self) -> list[Article]:
        """
        Fetch articles from all configured sources.

        Returns:
            list[Article]: Combined list of articles from all feeds
        """
        import asyncio

        logger.info(f"Fetching from {len(self.rss_feeds)} RSS feeds")

        tasks = [self.fetch_rss(url) for url in self.rss_feeds]

        # Add HackerNews if enabled
        if self.enable_hackernews:
            tasks.append(self.fetch_hackernews())

        # Add ProductHunt if enabled
        if self.enable_producthunt:
            tasks.append(self.fetch_producthunt())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Feed fetch error: {result}")

        logger.info(f"Total articles fetched: {len(all_articles)}")
        return all_articles

    async def _get_http_session(self) -> ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=self.fetch_timeout)
            self._session = ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.user_agent},
            )
        return self._session

    async def fetch_hackernews(self, limit: Optional[int] = None) -> list[Article]:
        """
        Fetch top stories from HackerNews.

        Args:
            limit: Maximum number of stories to fetch

        Returns:
            list[Article]: List of HackerNews stories as articles
        """
        limit = limit or self.hackernews_limit
        logger.debug(f"Fetching {limit} stories from HackerNews")

        articles = []

        try:
            session = await self._get_http_session()

            # Get top story IDs
            async with session.get(self.HN_TOPSTORIES_URL) as response:
                if response.status != 200:
                    logger.error(f"HackerNews API error: {response.status}")
                    return []
                story_ids = await response.json()

            # Fetch details for each story
            story_ids = story_ids[:limit]

            import asyncio

            fetch_tasks = [
                self._fetch_hn_item(session, story_id) for story_id in story_ids
            ]

            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Article):
                    articles.append(result)
                elif isinstance(result, Exception):
                    logger.debug(f"Failed to fetch HN item: {result}")

            logger.info(f"Fetched {len(articles)} stories from HackerNews")

        except Exception as e:
            logger.error(f"Failed to fetch HackerNews: {e}")

        return articles

    async def _fetch_hn_item(
        self,
        session: ClientSession,
        item_id: int,
    ) -> Optional[Article]:
        """Fetch a single HackerNews item."""
        try:
            url = self.HN_ITEM_URL.format(item_id)
            async with session.get(url) as response:
                if response.status != 200:
                    return None

                data = await response.json()

                if not data or data.get("type") != "story":
                    return None

                # Skip items without URLs (Ask HN, etc.)
                if not data.get("url"):
                    return None

                published_at = None
                if data.get("time"):
                    published_at = datetime.fromtimestamp(data["time"])

                return Article(
                    title=data.get("title", ""),
                    summary=f"Score: {data.get('score', 0)} | Comments: {data.get('descendants', 0)}",
                    url=data.get("url", ""),
                    published_at=published_at,
                    source="HackerNews",
                    tags=["tech", "hn"],
                )

        except Exception as e:
            logger.debug(f"Failed to fetch HN item {item_id}: {e}")
            return None

    async def fetch_producthunt(self) -> list[Article]:
        """
        Fetch today's posts from ProductHunt via RSS.

        Returns:
            list[Article]: List of ProductHunt posts as articles
        """
        logger.debug("Fetching from ProductHunt")

        # ProductHunt has an RSS feed
        return await self.fetch_rss(self.PRODUCTHUNT_RSS)

    def deduplicate(
        self,
        articles: list[Article],
        seen_hashes: Optional[set[str]] = None,
    ) -> list[Article]:
        """
        Remove duplicate articles.

        Args:
            articles: List of articles
            seen_hashes: Set of already seen content hashes

        Returns:
            list[Article]: Deduplicated articles
        """
        if seen_hashes:
            self._seen_hashes.update(seen_hashes)

        unique_articles = []

        for article in articles:
            if article.content_hash not in self._seen_hashes:
                unique_articles.append(article)
                self._seen_hashes.add(article.content_hash)

        logger.info(
            f"Deduplication: {len(articles)} -> {len(unique_articles)} articles"
        )
        return unique_articles

    def filter_by_date(
        self,
        articles: list[Article],
        max_age_days: int = 7,
    ) -> list[Article]:
        """
        Filter articles by publication date.

        Args:
            articles: List of articles
            max_age_days: Maximum age in days

        Returns:
            list[Article]: Filtered articles
        """
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)

        filtered = [
            article
            for article in articles
            if article.published_at is None or article.published_at >= cutoff
        ]

        logger.info(
            f"Date filter: {len(articles)} -> {len(filtered)} articles "
            f"(max age: {max_age_days} days)"
        )
        return filtered

    def filter_by_keywords(
        self,
        articles: list[Article],
        keywords: list[str],
        require_all: bool = False,
    ) -> list[Article]:
        """
        Filter articles by keywords.

        Args:
            articles: List of articles
            keywords: Keywords to search for
            require_all: Whether all keywords must be present

        Returns:
            list[Article]: Filtered articles
        """
        if not keywords:
            return articles

        keywords_lower = [kw.lower() for kw in keywords]
        filtered = []

        for article in articles:
            text = f"{article.title} {article.summary}".lower()

            if require_all:
                if all(kw in text for kw in keywords_lower):
                    filtered.append(article)
            else:
                if any(kw in text for kw in keywords_lower):
                    filtered.append(article)

        logger.info(f"Keyword filter: {len(articles)} -> {len(filtered)} articles")
        return filtered

    def sort_by_date(
        self, articles: list[Article], descending: bool = True
    ) -> list[Article]:
        """
        Sort articles by publication date.

        Args:
            articles: List of articles
            descending: Sort in descending order (newest first)

        Returns:
            list[Article]: Sorted articles
        """
        return sorted(
            articles,
            key=lambda a: a.published_at or datetime.min,
            reverse=descending,
        )

    async def collect(
        self,
        max_age_days: int = 7,
        keywords: Optional[list[str]] = None,
    ) -> list[Article]:
        """
        Full collection pipeline: fetch, deduplicate, filter, sort.

        Args:
            max_age_days: Maximum article age
            keywords: Optional keywords to filter by

        Returns:
            list[Article]: Processed articles ready for use
        """
        # Fetch from all sources
        articles = await self.fetch_all()

        # Deduplicate
        articles = self.deduplicate(articles)

        # Filter by date
        articles = self.filter_by_date(articles, max_age_days)

        # Filter by keywords if provided
        if keywords:
            articles = self.filter_by_keywords(articles, keywords)

        # Sort by date (newest first)
        articles = self.sort_by_date(articles)

        return articles

    def get_seen_hashes(self) -> set[str]:
        """Get set of seen content hashes."""
        return self._seen_hashes.copy()

    def clear_seen_hashes(self) -> None:
        """Clear seen hashes cache."""
        self._seen_hashes.clear()
        logger.info("Cleared seen hashes cache")

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("SourceCollector session closed")
