"""
Real-Time News Monitor - Continuous news monitoring system.

Monitors RSS feeds and news sources for breaking news and important updates,
automatically triggering post generation when significant news is detected.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from pipeline.source_collector import SourceCollector, Article
    from pipeline.orchestrator import PipelineOrchestrator
    from memory.topic_store import TopicStore

logger = get_logger(__name__)


@dataclass
class BreakingNewsCriteria:
    """Criteria for identifying breaking news."""

    # Keywords that indicate breaking news
    BREAKING_KEYWORDS = [
        "breaking", "urgent", "just in", "announced", "launched",
        "released", " unveiled", "revealed", "confirmed", "reported",
        "exclusive", "developing", "update", "alert",
        # Russian equivalents
        "срочно", "важно", "объявил", "запустил", "выпустил",
        "представил", "подтвердил", "эксклюзив",
    ]

    # Companies/subjects to prioritize
    PRIORITY_ENTITIES = [
        "openai", "anthropic", "google", "meta", "microsoft", "apple",
        "nvidia", "deepmind", "stability", "midjourney", "xai",
        "mistral", "cohere", "hugging face",
        # Russian tech
        "яндекс", "сбер", "тинькофф", "vk",
    ]

    # Topics that indicate high importance
    HIGH_IMPORTANCE_TOPICS = [
        "gpt-5", "gpt5", "claude", "gemini", "llama",
        "agi", "artificial general intelligence",
        "regulation", "ai safety", "ai act",
        "breakthrough", "milestone", "record",
    ]


@dataclass
class NewsAlert:
    """Represents a detected news alert."""

    article: "Article"
    priority: int  # 1-10, higher = more important
    reason: str
    detected_at: datetime = field(default_factory=datetime.now)
    keywords_matched: list[str] = field(default_factory=list)


class RealTimeMonitor:
    """
    Monitors news sources for breaking news and important updates.

    Features:
    - Continuous RSS feed monitoring
    - Breaking news detection
    - Automatic post generation for high-priority news
    - Deduplication with recent posts
    - Configurable polling interval
    """

    # Default polling interval in minutes
    DEFAULT_POLL_INTERVAL = 15  # Check every 15 minutes

    # Minimum time between auto-posts in minutes
    MIN_POST_INTERVAL = 30  # Don't spam posts

    def __init__(
        self,
        source_collector: "SourceCollector",
        orchestrator: "PipelineOrchestrator",
        topic_store: "TopicStore",
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        auto_post: bool = True,
        breaking_threshold: int = 7,  # Priority 7+ triggers auto-post
    ):
        """
        Initialize real-time monitor.

        Args:
            source_collector: Source collector for fetching articles
            orchestrator: Pipeline orchestrator for generating posts
            topic_store: Topic store for deduplication
            poll_interval: Minutes between checks
            auto_post: Whether to automatically generate posts for breaking news
            breaking_threshold: Minimum priority to trigger auto-post
        """
        self.source_collector = source_collector
        self.orchestrator = orchestrator
        self.topic_store = topic_store
        self.poll_interval = poll_interval
        self.auto_post = auto_post
        self.breaking_threshold = breaking_threshold

        self._is_running = False
        self._last_post_time: Optional[datetime] = None
        self._last_check_time: Optional[datetime] = None
        self._pending_alerts: list[NewsAlert] = []
        self._processed_urls: set[str] = set()

    async def start(self) -> None:
        """Start continuous monitoring."""
        if self._is_running:
            logger.warning("Real-time monitor is already running")
            return

        self._is_running = True
        logger.info(
            f"Starting real-time news monitor "
            f"(poll_interval={self.poll_interval}min, auto_post={self.auto_post})"
        )

        while self._is_running:
            try:
                await self._check_for_news()
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")

            # Wait for next cycle
            await asyncio.sleep(self.poll_interval * 60)

    def stop(self) -> None:
        """Stop continuous monitoring."""
        self._is_running = False
        logger.info("Real-time news monitor stopped")

    async def _check_for_news(self) -> list[NewsAlert]:
        """
        Check for new articles and identify breaking news.

        Returns:
            List of detected news alerts
        """
        self._last_check_time = datetime.now()
        logger.info("Checking for new articles...")

        # Fetch fresh articles
        articles = await self.source_collector.fetch_all()

        if not articles:
            logger.debug("No new articles found")
            return []

        # Filter out already processed articles
        new_articles = [
            a for a in articles
            if a.url not in self._processed_urls
        ]

        if not new_articles:
            logger.debug("No unprocessed articles found")
            return []

        logger.info(f"Found {len(new_articles)} new articles to analyze")

        # Analyze each article for breaking news potential
        alerts = []
        for article in new_articles:
            alert = self._analyze_article(article)
            if alert:
                alerts.append(alert)
                self._processed_urls.add(article.url)

        # Sort by priority (highest first)
        alerts.sort(key=lambda a: a.priority, reverse=True)

        # Store pending alerts
        self._pending_alerts.extend(alerts)

        # Keep only last 100 pending alerts
        self._pending_alerts = self._pending_alerts[-100:]

        # Keep only last 1000 processed URLs (memory management)
        if len(self._processed_urls) > 1000:
            self._processed_urls = set(list(self._processed_urls)[-1000:])

        # Log results
        if alerts:
            logger.info(
                f"Detected {len(alerts)} breaking news alerts: "
                f"top priority={alerts[0].priority}, "
                f"article='{alerts[0].article.title[:50]}...'"
            )

        # Trigger auto-post for high-priority news
        if self.auto_post and alerts:
            await self._maybe_auto_post(alerts)

        return alerts

    def _analyze_article(self, article: "Article") -> Optional[NewsAlert]:
        """
        Analyze an article for breaking news potential.

        Args:
            article: Article to analyze

        Returns:
            NewsAlert if article is newsworthy, None otherwise
        """
        title = article.title.lower()
        content = (article.content or "").lower()
        combined = f"{title} {content}"

        priority = 0
        keywords_matched = []
        reasons = []

        # Check for breaking news keywords
        for keyword in BreakingNewsCriteria.BREAKING_KEYWORDS:
            if keyword in combined:
                priority += 2
                keywords_matched.append(keyword)

        # Check for priority entities
        for entity in BreakingNewsCriteria.PRIORITY_ENTITIES:
            if entity in combined:
                priority += 3
                keywords_matched.append(entity)
                reasons.append(f"Mentions {entity}")

        # Check for high-importance topics
        for topic in BreakingNewsCriteria.HIGH_IMPORTANCE_TOPICS:
            if topic in combined:
                priority += 4
                keywords_matched.append(topic)
                reasons.append(f"Important topic: {topic}")

        # Bonus for very recent articles (published within last 2 hours)
        if article.published_at:
            age_hours = (datetime.now() - article.published_at).total_seconds() / 3600
            if age_hours < 2:
                priority += 3
                reasons.append("Very recent (< 2 hours)")
            elif age_hours < 6:
                priority += 1
                reasons.append("Recent (< 6 hours)")

        # Minimum threshold for alert
        if priority < 3:
            return None

        reason = "; ".join(reasons) if reasons else "Breaking news keywords detected"

        return NewsAlert(
            article=article,
            priority=min(priority, 10),  # Cap at 10
            reason=reason,
            keywords_matched=keywords_matched[:5],
        )

    async def _maybe_auto_post(self, alerts: list[NewsAlert]) -> None:
        """
        Check if we should auto-post based on alerts.

        Args:
            alerts: List of detected alerts
        """
        # Check if enough time has passed since last post
        if self._last_post_time:
            minutes_since = (
                datetime.now() - self._last_post_time
            ).total_seconds() / 60
            if minutes_since < self.MIN_POST_INTERVAL:
                logger.debug(
                    f"Skipping auto-post: only {minutes_since:.0f}min "
                    f"since last post (min: {self.MIN_POST_INTERVAL}min)"
                )
                return

        # Check for high-priority alerts
        high_priority = [a for a in alerts if a.priority >= self.breaking_threshold]

        if not high_priority:
            logger.debug(
                f"No alerts meet threshold (need {self.breaking_threshold}, "
                f"highest is {alerts[0].priority if alerts else 0})"
            )
            return

        # Check for duplicates with recent topics
        forbidden = await self.topic_store.get_forbidden_names(days=3)
        for alert in high_priority:
            is_duplicate = any(
                self._quick_similarity(alert.article.title, t)
                for t in forbidden
            )
            if is_duplicate:
                logger.debug(
                    f"Skipping duplicate topic: '{alert.article.title[:50]}...'"
                )
                continue

            # Found a good candidate - trigger post generation
            logger.info(
                f"Triggering auto-post for breaking news: "
                f"'{alert.article.title[:50]}...' (priority={alert.priority})"
            )

            try:
                # Run pipeline for this specific article
                result = await self.orchestrator.run(
                    topic_override=alert.article.title,
                    source_urls=[alert.article.url],
                )

                if result.success:
                    self._last_post_time = datetime.now()
                    logger.info(
                        f"Auto-post published successfully: "
                        f"post_id={result.post_id}, quality={result.quality_score}"
                    )
                else:
                    logger.warning(
                        f"Auto-post generation failed: {result.error}"
                    )
            except Exception as e:
                logger.error(f"Error generating auto-post: {e}")

            # Only post one at a time
            break

    def _quick_similarity(self, text1: str, text2: str) -> bool:
        """
        Quick similarity check for deduplication.

        Args:
            text1: First text
            text2: Second text

        Returns:
            True if texts are similar
        """
        words1 = set(text1.lower().split()[:10])
        words2 = set(text2.lower().split()[:10])

        if not words1 or not words2:
            return False

        common = words1 & words2
        similarity = len(common) / max(len(words1), len(words2))

        return similarity > 0.5

    def get_status(self) -> dict:
        """
        Get current monitor status.

        Returns:
            Dict with status information
        """
        return {
            "is_running": self._is_running,
            "poll_interval_minutes": self.poll_interval,
            "auto_post_enabled": self.auto_post,
            "breaking_threshold": self.breaking_threshold,
            "last_check": self._last_check_time.isoformat() if self._last_check_time else None,
            "last_post": self._last_post_time.isoformat() if self._last_post_time else None,
            "pending_alerts": len(self._pending_alerts),
            "processed_urls": len(self._processed_urls),
        }

    def get_pending_alerts(self, limit: int = 10) -> list[dict]:
        """
        Get pending alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of alert dicts
        """
        return [
            {
                "title": alert.article.title,
                "url": alert.article.url,
                "priority": alert.priority,
                "reason": alert.reason,
                "keywords": alert.keywords_matched,
                "detected_at": alert.detected_at.isoformat(),
            }
            for alert in self._pending_alerts[-limit:]
        ]
