"""
Telegram channel duplicate checker for preventing reposting.

Checks newly generated content against already published posts
in the Telegram channel to prevent duplicate content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger
from pipeline.source_collector import Article

if TYPE_CHECKING:
    from memory.post_store import PostStore
    from memory.topic_store import TopicStore
    from memory.vector_store import VectorStore

logger = get_logger(__name__)


@dataclass
class DuplicateCheckResult:
    """Result of duplicate check."""

    is_duplicate: bool
    duplicate_type: Optional[str] = None  # 'title', 'url', 'semantic', 'content'
    similar_post_id: Optional[int] = None
    similarity_score: float = 0.0
    message: str = ""
    details: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "is_duplicate": self.is_duplicate,
            "duplicate_type": self.duplicate_type,
            "similar_post_id": self.similar_post_id,
            "similarity_score": self.similarity_score,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class ArticleDuplicateInfo:
    """Information about an article duplicate check."""

    article: Optional[Article] = None
    title_match: bool = False
    url_match: bool = False
    content_similarity: float = 0.0
    is_duplicate: bool = False
    duplicate_type: Optional[str] = None
    similar_post_id: Optional[int] = None
    similarity_score: float = 0.0
    details: Optional[dict] = None


@dataclass
class DuplicateCheckStats:
    """Statistics about duplicate checking."""

    total_checked: int = 0
    total_duplicates: int = 0
    url_duplicates: int = 0
    title_duplicates: int = 0
    semantic_duplicates: int = 0
    content_duplicates: int = 0


class ChannelDuplicateChecker:
    """
    Checks for duplicate content against published Telegram posts.

    Performs multiple checks:
    1. URL matching - exact match with source URLs
    2. Title similarity - normalized title comparison
    3. Semantic similarity - vector-based comparison (if available)
    4. Content similarity - text overlap comparison
    """

    def __init__(
        self,
        post_store: PostStore,
        topic_store: TopicStore,
        vector_store: Optional[VectorStore] = None,
        similarity_threshold: float = 0.80,
        title_similarity_threshold: float = 0.85,
        url_check_days: int = 30,
        content_check_limit: int = 50,
    ) -> None:
        """
        Initialize duplicate checker.

        Args:
            post_store: Post store for accessing published posts
            topic_store: Topic store for checking source URLs
            vector_store: Optional vector store for semantic similarity
            similarity_threshold: Threshold for semantic similarity (0-1)
            title_similarity_threshold: Threshold for title matching (0-1)
            url_check_days: How many days back to check for URL duplicates
            content_check_limit: How many recent posts to check for content similarity
        """
        self.post_store = post_store
        self.topic_store = topic_store
        self.vector_store = vector_store
        self.similarity_threshold = similarity_threshold
        self.title_similarity_threshold = title_similarity_threshold
        self.url_check_days = url_check_days
        self.content_check_limit = content_check_limit

        # Caches for faster duplicate checking
        self._normalized_title_cache: dict[str, tuple[int, float]] = {}
        self._source_url_cache: dict[str, tuple[int, float]] = {}
        self._published_post_ids: set[int] = set()

        self._stats = DuplicateCheckStats()

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        # Remove special characters and keep only alphanumeric and spaces
        title = re.sub(r"[^\w\s]", " ", title.lower())
        # Remove common prefixes
        for prefix in ["breaking:", "update:", "news:", "just in:", "alert:"]:
            title = re.sub(f"^{re.escape(prefix)}\\s*", "", title)
        return title.strip()

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        # Remove protocol and common tracking parameters
        url = url.lower().strip()
        # Remove common tracking parameters
        url = re.sub(r"[?&](utm_|ref|source|)=.*", "", url)
        url = re.sub(r"^https?://", "", url)
        url = re.sub(r"/$", "", url)
        url = re.sub(r"www\.", "", url)
        return url.rstrip("/").strip()

    async def _build_caches(self) -> None:
        """Build caches for faster duplicate checking."""
        # Build normalized title cache
        self._normalized_title_cache: dict[str, tuple[int, float]] = {}
        posts = await self.post_store.get_recent(
            limit=self.content_check_limit, status="published"
        )
        for post in posts:
            normalized_title = self._normalize_title(post.topic or "")
            if normalized_title:
                self._normalized_title_cache[normalized_title] = (post.id, 1.0)

        # Build source URL cache from topic store
        topics = await self.topic_store.get_recently_used(
            days=self.url_check_days, limit=self.content_check_limit
        )
        for topic in topics:
            if topic.source_url:
                normalized_url = self._normalize_url(topic.source_url)
                if normalized_url:
                    self._source_url_cache[normalized_url] = (topic.id, 0.0)

        logger.debug(
            f"Built duplicate caches: {len(self._normalized_title_cache)} titles, "
            f"{len(self._source_url_cache)} URLs"
        )

    async def check_article(self, article: Article) -> ArticleDuplicateInfo:
        """
        Check if an article is a duplicate of already published posts.

        Args:
            article: Article to check

        Returns:
            ArticleDuplicateInfo: Result of duplicate check
        """
        self._stats.total_checked += 1

        info = ArticleDuplicateInfo(article=article)

        # Check 1: URL exact match
        if article.url:
            normalized_url = self._normalize_url(article.url)
            if normalized_url in self._source_url_cache:
                info.is_duplicate = True
                info.url_match = True
                info.duplicate_type = "url"
                info.similar_post_id = self._source_url_cache[normalized_url][0]
                self._stats.url_duplicates += 1
                logger.info(f"URL duplicate found: {article.url}")
                return info

            # Also check via topic store for safety
            if await self.topic_store.has_used_source_url(article.url):
                info.is_duplicate = True
                info.url_match = True
                info.duplicate_type = "url"
                self._stats.url_duplicates += 1
                logger.info(f"URL duplicate (via topic_store): {article.url}")
                return info

        # Check 2: Title similarity
        normalized_title = self._normalize_title(article.title)
        if normalized_title in self._normalized_title_cache:
            post_id, score = self._normalized_title_cache[normalized_title]
            info.is_duplicate = True
            info.title_match = True
            info.duplicate_type = "title"
            info.similarity_score = score
            info.similar_post_id = post_id
            info.details = {
                "article_title": article.title,
                "similarity": score,
            }
            self._stats.title_duplicates += 1
            logger.info(f"Title duplicate found: {article.title[:50]}...")
            return info

        # Check 3: Semantic similarity (if vector store available)
        if self.vector_store:
            try:
                article_text = f"{article.title}\n{article.summary}"
                is_duplicate, similar_post = await self.vector_store.check_similarity(
                    article_text,
                    threshold=self.similarity_threshold,
                    n_results=3,
                )
                if is_duplicate and similar_post:
                    info.is_duplicate = True
                    info.duplicate_type = "semantic"
                    info.similarity_score = similar_post.similarity
                    info.similar_post_id = similar_post.post_id
                    info.details = {
                        "similar_post_id": similar_post.post_id,
                        "similarity": similar_post.similarity,
                    }
                    self._stats.semantic_duplicates += 1
                    logger.info(
                        f"Semantic duplicate found: {article.title[:50]}... "
                        f"(similarity: {similar_post.similarity:.0%})"
                    )
                    return info
            except Exception as e:
                logger.warning(f"Semantic similarity check failed: {e}")

        # Check 4: Content similarity (fallback using word overlap)
        try:
            article_words = set(article.summary.lower().split())
            article_words = {w for w in article_words if len(w) > 3}  # Filter short words

            for cached_title, (post_id, _) in self._normalized_title_cache.items():
                post = await self.post_store.get_by_id(post_id)
                if not post:
                    continue
                post_words = set((post.content or "").lower().split())
                post_words = {w for w in post_words if len(w) > 3}

                if not article_words or not post_words:
                    continue

                intersection = len(article_words & post_words)
                union = len(article_words | post_words)

                if union > 0:
                    similarity = intersection / union
                    if similarity >= self.similarity_threshold:
                        info.is_duplicate = True
                        info.duplicate_type = "content"
                        info.similarity_score = similarity
                        info.similar_post_id = post_id
                        info.details = {
                            "word_overlap": similarity,
                        }
                        self._stats.content_duplicates += 1
                        logger.info(
                            f"Content duplicate found: {article.title[:50]}... "
                            f"(overlap: {similarity:.0%})"
                        )
                        return info
        except Exception as e:
            logger.warning(f"Content similarity check failed: {e}")

        return info

    async def check_articles(
        self,
        articles: list[Article],
    ) -> tuple[list[Article], DuplicateCheckStats]:
        """
        Check multiple articles for duplicates.

        Args:
            articles: Articles to check

        Returns:
            tuple[list[Article], DuplicateCheckStats]: Filtered articles and statistics
        """
        if not articles:
            return [], DuplicateCheckStats()

        # Build caches if needed
        await self._build_caches()

        filtered = []
        stats = DuplicateCheckStats()

        for article in articles:
            result = await self.check_article(article)
            stats.total_checked += 1

            if not result.is_duplicate:
                filtered.append(article)
            else:
                stats.total_duplicates += 1
                if result.duplicate_type == "url":
                    stats.url_duplicates += 1
                elif result.duplicate_type == "title":
                    stats.title_duplicates += 1
                elif result.duplicate_type == "semantic":
                    stats.semantic_duplicates += 1
                elif result.duplicate_type == "content":
                    stats.content_duplicates += 1
                logger.info(
                    f"Skipping duplicate article: {article.title[:50]}... "
                    f"(type: {result.duplicate_type}, similarity: {result.similarity_score:.0%})"
                )

        logger.info(
            f"Duplicate check: {stats.total_duplicates}/{stats.total_checked} articles filtered"
        )
        return filtered, stats

    def get_stats(self) -> DuplicateCheckStats:
        """Get duplicate checking statistics."""
        return self._stats
