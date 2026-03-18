"""
Source collector for gathering content from RSS feeds and APIs.

Fetches, parses, and deduplicates articles from configured sources.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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

    @property
    def content(self) -> str:
        """Compatibility alias for systems expecting full article content."""
        return self.summary

    @property
    def normalized_url(self) -> str:
        """Normalize URL for stronger deduplication."""
        parsed = urlparse(self.url)
        normalized_query = urlencode(
            sorted(
                (key, value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                if not key.lower().startswith("utm_")
            )
        )
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                "",
                normalized_query,
                "",
            )
        )

    @property
    def source_domain(self) -> str:
        """Get canonical domain for article URL."""
        return urlparse(self.url).netloc.lower().replace("www.", "")

    @property
    def age_hours(self) -> Optional[float]:
        """Get article age in hours."""
        if not self.published_at:
            return None
        return max(0.0, (datetime.utcnow() - self.published_at).total_seconds() / 3600)

    @property
    def title_signature(self) -> str:
        """Normalized title signature for cross-feed duplicate clustering."""
        import re

        normalized = re.sub(r"[^a-zа-я0-9\s]+", " ", self.title.lower())
        tokens = [
            token
            for token in normalized.split()
            if len(token) > 2 or any(char.isdigit() for char in token)
        ]
        return " ".join(tokens[:12])


@dataclass
class FeedStats:
    """Operational stats for a single feed."""

    url: str
    success_count: int = 0
    error_count: int = 0
    consecutive_failures: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    last_status: str = "never"
    last_fetch_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error_at: Optional[str] = None
    last_error: str = ""
    last_latency_ms: float = 0.0
    disabled_until: Optional[str] = None
    etag: str = ""
    last_modified: str = ""

    def to_dict(self) -> dict:
        """Serialize stats to dict."""
        return {
            "url": self.url,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "consecutive_failures": self.consecutive_failures,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "last_status": self.last_status,
            "last_fetch_at": self.last_fetch_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_error": self.last_error,
            "last_latency_ms": self.last_latency_ms,
            "disabled_until": self.disabled_until,
            "etag": self.etag,
            "last_modified": self.last_modified,
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
        feed_cache_ttl_minutes: int = 15,
        max_concurrent_fetches: int = 10,
        max_article_age_days: int = 7,
        source_weights: Optional[dict[str, float]] = None,
        request_retries: int = 2,
        retry_base_delay_ms: int = 250,
        disable_after_failures: int = 3,
        disable_duration_minutes: int = 30,
        state_path: str = "data/source_collector_state.json",
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
        self.feed_cache_ttl = timedelta(minutes=feed_cache_ttl_minutes)
        self.max_article_age_days = max_article_age_days
        self.request_retries = max(0, request_retries)
        self.retry_base_delay_ms = max(1, retry_base_delay_ms)
        self.disable_after_failures = max(1, disable_after_failures)
        self.disable_duration = timedelta(minutes=max(1, disable_duration_minutes))
        self.state_path = Path(state_path)
        self.source_weights = {
            (domain.lower().replace("www.", "")): weight
            for domain, weight in (source_weights or {}).items()
        }
        self._seen_hashes: set[str] = set()
        self._session: Optional[ClientSession] = None
        self._feed_cache: dict[str, tuple[datetime, list[Article]]] = {}
        self._fetch_semaphore = asyncio.Semaphore(max(1, max_concurrent_fetches))
        self._feed_stats: dict[str, FeedStats] = {}
        self._load_state()

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

    def _is_cache_valid(self, url: str) -> bool:
        """Check whether a feed cache entry is still valid."""
        if url not in self._feed_cache:
            return False
        cached_at, _ = self._feed_cache[url]
        return datetime.utcnow() - cached_at < self.feed_cache_ttl

    def _cache_articles(self, url: str, articles: list[Article]) -> None:
        """Cache articles for a feed URL."""
        self._feed_cache[url] = (datetime.utcnow(), list(articles))

    def _get_feed_stats(self, url: str) -> FeedStats:
        """Get or create feed stats."""
        if url not in self._feed_stats:
            self._feed_stats[url] = FeedStats(url=url)
        return self._feed_stats[url]

    def _load_state(self) -> None:
        """Load persisted feed stats/state if available."""
        try:
            if not self.state_path.exists():
                return
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            for url, raw in data.get("feed_stats", {}).items():
                self._feed_stats[url] = FeedStats(**raw)
        except Exception as e:
            logger.warning("Failed to load source collector state: %s", e)

    def _persist_state(self) -> None:
        """Persist feed stats/state for future runs."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "feed_stats": {
                    url: stats.to_dict() for url, stats in self._feed_stats.items()
                }
            }
            self.state_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to persist source collector state: %s", e)

    def _parse_iso_datetime(self, value: str | None) -> Optional[datetime]:
        """Parse ISO datetime safely."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _is_feed_disabled(self, url: str) -> bool:
        """Check whether a feed is temporarily disabled after repeated failures."""
        stats = self._get_feed_stats(url)
        disabled_until = self._parse_iso_datetime(stats.disabled_until)
        if not disabled_until:
            return False
        if datetime.utcnow() >= disabled_until:
            stats.disabled_until = None
            return False
        return True

    def _mark_cache_hit(self, url: str) -> None:
        """Track cache hit metric."""
        stats = self._get_feed_stats(url)
        stats.cache_hits += 1
        stats.last_status = "cache_hit"
        self._persist_state()

    def _mark_cache_miss(self, url: str) -> None:
        """Track cache miss metric."""
        stats = self._get_feed_stats(url)
        stats.cache_misses += 1

    def _record_feed_success(
        self,
        url: str,
        latency_ms: float,
        etag: str = "",
        last_modified: str = "",
    ) -> None:
        """Record successful feed fetch."""
        stats = self._get_feed_stats(url)
        now = datetime.utcnow().isoformat()
        stats.success_count += 1
        stats.consecutive_failures = 0
        stats.last_status = "success"
        stats.last_fetch_at = now
        stats.last_success_at = now
        stats.last_error = ""
        stats.last_latency_ms = latency_ms
        if etag:
            stats.etag = etag
        if last_modified:
            stats.last_modified = last_modified
        stats.disabled_until = None
        self._persist_state()

    def _record_feed_not_modified(self, url: str, latency_ms: float) -> None:
        """Record HTTP 304 feed response."""
        stats = self._get_feed_stats(url)
        now = datetime.utcnow().isoformat()
        stats.success_count += 1
        stats.consecutive_failures = 0
        stats.last_status = "not_modified"
        stats.last_fetch_at = now
        stats.last_success_at = now
        stats.last_latency_ms = latency_ms
        self._persist_state()

    def _record_feed_error(self, url: str, error: Exception | str, latency_ms: float) -> None:
        """Record failed feed fetch and apply temporary disable if needed."""
        stats = self._get_feed_stats(url)
        now = datetime.utcnow().isoformat()
        stats.error_count += 1
        stats.consecutive_failures += 1
        stats.last_status = "error"
        stats.last_fetch_at = now
        stats.last_error_at = now
        stats.last_error = str(error)
        stats.last_latency_ms = latency_ms

        if stats.consecutive_failures >= self.disable_after_failures:
            stats.disabled_until = (
                datetime.utcnow() + self.disable_duration
            ).isoformat()
            logger.warning(
                "Temporarily disabling feed %s until %s after %s consecutive failures",
                url,
                stats.disabled_until,
                stats.consecutive_failures,
            )

        self._persist_state()

    def _extract_canonical_url(self, entry: dict) -> str:
        """Extract the best canonical/original URL from feed entry."""
        preferred_fields = [
            "feedburner_origlink",
            "origlink",
            "original_link",
            "link",
            "id",
        ]
        for field_name in preferred_fields:
            value = entry.get(field_name)
            if value:
                return value
        return ""

    def _detect_language(self, text: str) -> str:
        """Very lightweight language/script detection for ranking heuristics."""
        if not text:
            return "unknown"
        cyrillic = sum(1 for char in text if "а" <= char.lower() <= "я" or char.lower() == "ё")
        latin = sum(1 for char in text if "a" <= char.lower() <= "z")
        cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")

        if cjk > max(cyrillic, latin):
            return "cjk"
        if cyrillic and latin:
            return "mixed"
        if cyrillic:
            return "ru"
        if latin:
            return "en"
        return "unknown"

    def _parse_feed_entries(self, feed, url: str) -> list[Article]:
        """Parse feedparser output into Article objects."""
        articles: list[Article] = []
        feed_title = feed.feed.get("title", url)

        for entry in feed.entries[: self.max_articles_per_feed]:
            try:
                title = self._clean_text(entry.get("title", ""))
                summary = self._clean_text(
                    entry.get("summary") or entry.get("description", "")
                )
                article_url = self._extract_canonical_url(entry)

                if not title or not article_url:
                    continue

                published_at = self._parse_date(entry)

                tags = []
                if hasattr(entry, "tags"):
                    tags = [tag.term for tag in entry.tags if hasattr(tag, "term")]

                articles.append(
                    Article(
                        title=title,
                        summary=summary[:500] if summary else "",
                        url=article_url,
                        published_at=published_at,
                        source=feed_title,
                        tags=tags,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse RSS entry: {e}")

        return articles

    def _score_article(self, article: Article) -> float:
        """Compute a lightweight priority score for ranking fetched articles."""
        score = 0.0

        if article.published_at:
            age_hours = article.age_hours or 0.0
            score += max(0.0, 72.0 - min(age_hours, 72.0))
        else:
            score += 12.0

        score += min(len(article.tags) * 1.5, 6.0)
        score += min(len(article.summary) / 140.0, 5.0)

        domain = article.source_domain
        source_weight = self.source_weights.get(domain)
        if source_weight is not None:
            score += source_weight * 10
        elif domain.endswith("openai.com") or domain.endswith("anthropic.com"):
            score += 8.0
        elif domain.endswith("github.com") or domain.endswith("arxiv.org"):
            score += 6.0
        elif "news.ycombinator.com" in domain:
            score += 3.0

        if any(aggregator in domain for aggregator in ("reddit.com", "medium.com", "producthunt.com")):
            score -= 2.5

        language = self._detect_language(f"{article.title} {article.summary}")
        if language == "cjk":
            score -= 5.0
        elif language in {"ru", "en", "mixed"}:
            score += 1.0

        text = f"{article.title} {article.summary}".lower()
        if any(
            keyword in text
            for keyword in ("release", "launch", "announce", "breakthrough", "gpt")
        ):
            score += 4.0

        return score

    def rank_articles(self, articles: list[Article]) -> list[Article]:
        """Rank articles by freshness and source priority."""
        return sorted(
            articles,
            key=lambda article: (
                self._score_article(article),
                article.published_at or datetime.min,
            ),
            reverse=True,
        )

    async def _fetch_feed_response(
        self, url: str
    ) -> tuple[int, str, str, str, float]:
        """Fetch raw feed content with conditional request headers."""
        stats = self._get_feed_stats(url)
        session = await self._get_http_session()

        headers = {"User-Agent": self.user_agent}
        if stats.etag:
            headers["If-None-Match"] = stats.etag
        if stats.last_modified:
            headers["If-Modified-Since"] = stats.last_modified

        start = time.perf_counter()
        async with session.get(url, headers=headers) as response:
            latency_ms = (time.perf_counter() - start) * 1000
            if response.status == 304:
                return 304, "", response.headers.get("ETag", ""), response.headers.get(
                    "Last-Modified", ""
                ), latency_ms
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            content = await response.text()
            return (
                response.status,
                content,
                response.headers.get("ETag", ""),
                response.headers.get("Last-Modified", ""),
                latency_ms,
            )

    async def _parse_feed_content(self, content: str, url: str):
        """Parse raw feed content with XML cleaning fallback."""
        import re

        feed = await asyncio.to_thread(feedparser.parse, content)
        if not (feed.bozo and feed.bozo_exception and len(feed.entries) == 0):
            return feed

        logger.warning(
            "RSS feed has severe issues, trying cleanup fallback: %s. Error: %s",
            url,
            feed.bozo_exception,
        )
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", content)
        cleaned = cleaned.replace("&nbsp;", " ")
        cleaned = cleaned.replace("&mdash;", "—")
        cleaned = cleaned.replace("&ndash;", "–")
        cleaned = cleaned.replace("&rsquo;", "'")
        cleaned = cleaned.replace("&lsquo;", "'")
        cleaned = cleaned.replace("&rdquo;", '"')
        cleaned = cleaned.replace("&ldquo;", '"')
        cleaned = re.sub(
            r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", cleaned
        )
        return await asyncio.to_thread(feedparser.parse, cleaned)

    async def fetch_rss(self, url: str) -> list[Article]:
        """
        Fetch and parse an RSS feed.

        Args:
            url: RSS feed URL

        Returns:
            list[Article]: List of parsed articles
        """
        logger.debug(f"Fetching RSS feed: {url}")

        if self._is_cache_valid(url):
            logger.debug("Using cached RSS feed for %s", url)
            self._mark_cache_hit(url)
            return list(self._feed_cache[url][1])

        if self._is_feed_disabled(url):
            logger.warning("Skipping temporarily disabled feed: %s", url)
            if url in self._feed_cache:
                self._mark_cache_hit(url)
                return list(self._feed_cache[url][1])
            return []

        self._mark_cache_miss(url)

        articles: list[Article] = []

        last_error: Exception | str | None = None
        for attempt in range(self.request_retries + 1):
            try:
                async with self._fetch_semaphore:
                    status, content, etag, last_modified, latency_ms = (
                        await self._fetch_feed_response(url)
                    )

                    if status == 304:
                        self._record_feed_not_modified(url, latency_ms)
                        if url in self._feed_cache:
                            self._mark_cache_hit(url)
                            return list(self._feed_cache[url][1])
                        return []

                    feed = await self._parse_feed_content(content, url)
                    if feed.bozo and feed.bozo_exception:
                        logger.warning(
                            "RSS feed has parse issues: %s. Error: %s",
                            url,
                            feed.bozo_exception,
                        )

                    articles = self._parse_feed_entries(feed, url)
                    self._record_feed_success(
                        url,
                        latency_ms,
                        etag=etag,
                        last_modified=last_modified,
                    )
                    self._cache_articles(url, articles)
                    logger.info(f"Fetched {len(articles)} articles from {url}")
                    return articles

            except Exception as e:
                last_error = e
                latency_ms = 0.0
                self._record_feed_error(url, e, latency_ms)
                if attempt >= self.request_retries:
                    break
                delay = (self.retry_base_delay_ms * (2**attempt)) / 1000
                delay += random.uniform(0, self.retry_base_delay_ms / 1000)
                logger.warning(
                    "Retrying feed %s in %.2fs after error: %s",
                    url,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)

        logger.error("Failed to fetch RSS feed %s: %s", url, last_error)

        return articles

    async def fetch_all(self) -> list[Article]:
        """
        Fetch articles from all configured sources.

        Returns:
            list[Article]: Combined list of articles from all feeds
        """
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

        deduplicated = self.deduplicate(all_articles)
        filtered = self.filter_by_date(deduplicated, self.max_article_age_days)
        ranked = self.rank_articles(filtered)

        logger.info(
            "Total articles fetched: %s, after processing: %s",
            len(all_articles),
            len(ranked),
        )
        return ranked

    async def _get_http_session(self) -> ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=self.fetch_timeout)
            self._session = ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.user_agent},
            )
        return self._session

    async def close(self) -> None:
        """Close owned HTTP resources and persist state."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._persist_state()

    def get_feed_health_report(self) -> dict[str, dict]:
        """Return operational health report for all tracked feeds."""
        report = {}
        for url, stats in self._feed_stats.items():
            report[url] = {
                **stats.to_dict(),
                "is_disabled": self._is_feed_disabled(url),
            }
        return report

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
        seen_urls = {article.normalized_url for article in unique_articles}
        seen_titles: dict[str, Article] = {}

        for article in articles:
            normalized_url = article.normalized_url
            title_signature = article.title_signature
            existing_by_title = seen_titles.get(title_signature)

            if (
                article.content_hash in self._seen_hashes
                or normalized_url in seen_urls
            ):
                continue

            if existing_by_title:
                if self._score_article(article) > self._score_article(existing_by_title):
                    replace_idx = unique_articles.index(existing_by_title)
                    unique_articles[replace_idx] = article
                    seen_titles[title_signature] = article
                    seen_urls.add(normalized_url)
                    self._seen_hashes.add(article.content_hash)
                continue

            unique_articles.append(article)
            seen_titles[title_signature] = article
            self._seen_hashes.add(article.content_hash)
            seen_urls.add(normalized_url)

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

        # Rank by freshness, trust, and content richness
        articles = self.rank_articles(articles)

        return articles

    def get_seen_hashes(self) -> set[str]:
        """Get set of seen content hashes."""
        return self._seen_hashes.copy()

    def clear_seen_hashes(self) -> None:
        """Clear seen hashes cache."""
        self._seen_hashes.clear()
        logger.info("Cleared seen hashes cache")

    async def fetch_arxiv(
        self,
        categories: Optional[list[str]] = None,
        max_results: int = 15,
    ) -> list[Article]:
        """
        Fetch recent papers from ArXiv.

        Args:
            categories: ArXiv categories (e.g., cs.AI, cs.LG)
            max_results: Maximum papers to fetch

        Returns:
            list[Article]: List of ArXiv papers as articles
        """
        import xml.etree.ElementTree as ET

        categories = categories or ["cs.AI", "cs.LG", "cs.CL"]
        logger.debug(f"Fetching ArXiv papers from {categories}")

        articles = []

        try:
            session = await self._get_http_session()

            # Build query URL
            # ArXiv API: http://export.arxiv.org/api/query
            base_url = "http://export.arxiv.org/api/query"
            query = " OR ".join(f"cat:{cat}" for cat in categories)
            params = {
                "search_query": query,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": max_results,
            }

            async with session.get(base_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"ArXiv API error: {response.status}")
                    return []
                xml_content = await response.text()

            # Parse XML response
            root = ET.fromstring(xml_content)

            # Define namespace
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                summary_elem = entry.find("atom:summary", ns)
                link_elem = entry.find("atom:id", ns)
                published_elem = entry.find("atom:published", ns)

                if title_elem is None or link_elem is None:
                    continue

                title = self._clean_text(title_elem.text or "")
                summary = self._clean_text(summary_elem.text or "")[:500] if summary_elem is not None else ""
                url = link_elem.text or ""

                published_at = None
                if published_elem is not None and published_elem.text:
                    try:
                        published_at = datetime.fromisoformat(
                            published_elem.text.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                articles.append(Article(
                    title=title,
                    summary=summary,
                    url=url,
                    published_at=published_at,
                    source="arxiv.org",
                    tags=["research", "arxiv"],
                ))

            logger.info(f"Fetched {len(articles)} papers from ArXiv")

        except Exception as e:
            logger.error(f"Failed to fetch ArXiv: {e}")

        return articles

    async def fetch_newsapi(
        self,
        api_key: str,
        query: str = "artificial intelligence",
        language: str = "en",
        page_size: int = 20,
    ) -> list[Article]:
        """
        Fetch news from NewsAPI.

        Args:
            api_key: NewsAPI API key
            query: Search query
            language: Language code
            page_size: Number of results

        Returns:
            list[Article]: List of news articles
        """
        if not api_key:
            logger.warning("NewsAPI key not provided, skipping")
            return []

        logger.debug(f"Fetching from NewsAPI: {query}")

        articles = []

        try:
            session = await self._get_http_session()

            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "language": language,
                "pageSize": page_size,
                "sortBy": "publishedAt",
                "apiKey": api_key,
            }

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"NewsAPI error: {response.status}")
                    return []
                data = await response.json()

            for item in data.get("articles", []):
                title = item.get("title", "")
                summary = item.get("description", "") or ""
                url = item.get("url", "")
                source_name = item.get("source", {}).get("name", "NewsAPI")

                published_at = None
                if item.get("publishedAt"):
                    try:
                        published_at = datetime.fromisoformat(
                            item["publishedAt"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                if title and url:
                    articles.append(Article(
                        title=self._clean_text(title),
                        summary=self._clean_text(summary)[:500],
                        url=url,
                        published_at=published_at,
                        source=source_name,
                        tags=["newsapi"],
                    ))

            logger.info(f"Fetched {len(articles)} articles from NewsAPI")

        except Exception as e:
            logger.error(f"Failed to fetch NewsAPI: {e}")

        return articles

    async def fetch_all_extended(
        self,
        arxiv_categories: Optional[list[str]] = None,
        arxiv_max: int = 15,
        newsapi_key: Optional[str] = None,
        newsapi_query: str = "artificial intelligence",
    ) -> list[Article]:
        """
        Fetch from all sources including extended APIs.

        Args:
            arxiv_categories: ArXiv categories
            arxiv_max: Max ArXiv results
            newsapi_key: NewsAPI key
            newsapi_query: NewsAPI query

        Returns:
            list[Article]: Combined articles
        """
        import asyncio

        # Base sources
        tasks = [self.fetch_rss(url) for url in self.rss_feeds]

        # HackerNews
        if self.enable_hackernews:
            tasks.append(self.fetch_hackernews())

        # ProductHunt
        if self.enable_producthunt:
            tasks.append(self.fetch_producthunt())

        # ArXiv
        tasks.append(self.fetch_arxiv(arxiv_categories, arxiv_max))

        # NewsAPI (if key provided)
        if newsapi_key:
            tasks.append(self.fetch_newsapi(newsapi_key, newsapi_query))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Extended fetch error: {result}")

        logger.info(f"Total articles fetched (extended): {len(all_articles)}")
        return all_articles

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("SourceCollector session closed")
