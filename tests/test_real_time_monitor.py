"""Tests for Real-Time News Monitor."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.real_time_monitor import (
    RealTimeMonitor,
    BreakingNewsCriteria,
    NewsAlert,
)


class TestBreakingNewsCriteria:
    """Test breaking news detection criteria."""

    def test_breaking_keywords_exist(self):
        """Test that breaking keywords are defined."""
        assert len(BreakingNewsCriteria.BREAKING_KEYWORDS) > 0
        assert "breaking" in BreakingNewsCriteria.BREAKING_KEYWORDS
        assert "announced" in BreakingNewsCriteria.BREAKING_KEYWORDS

    def test_priority_entities_exist(self):
        """Test that priority entities are defined."""
        assert len(BreakingNewsCriteria.PRIORITY_ENTITIES) > 0
        assert "openai" in BreakingNewsCriteria.PRIORITY_ENTITIES
        assert "google" in BreakingNewsCriteria.PRIORITY_ENTITIES

    def test_high_importance_topics_exist(self):
        """Test that high importance topics are defined."""
        assert len(BreakingNewsCriteria.HIGH_IMPORTANCE_TOPICS) > 0
        assert "gpt-5" in BreakingNewsCriteria.HIGH_IMPORTANCE_TOPICS
        assert "agi" in BreakingNewsCriteria.HIGH_IMPORTANCE_TOPICS


class TestNewsAlert:
    """Test NewsAlert dataclass."""

    def test_news_alert_creation(self):
        """Test creating a news alert."""
        article = MagicMock()
        article.title = "Test Article"
        article.url = "https://example.com/test"

        alert = NewsAlert(
            article=article,
            priority=7,
            reason="Breaking news detected",
            keywords_matched=["breaking", "openai"],
        )

        assert alert.article == article
        assert alert.priority == 7
        assert alert.reason == "Breaking news detected"
        assert len(alert.keywords_matched) == 2


class TestRealTimeMonitor:
    """Test RealTimeMonitor class."""

    @pytest.fixture
    def mock_source_collector(self):
        """Create mock source collector."""
        collector = AsyncMock()
        collector.fetch_all = AsyncMock(return_value=[])
        return collector

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = AsyncMock()
        result = MagicMock()
        result.success = True
        result.post_id = 123
        result.quality_score = 85
        orchestrator.run = AsyncMock(return_value=result)
        return orchestrator

    @pytest.fixture
    def mock_topic_store(self):
        """Create mock topic store."""
        store = AsyncMock()
        store.get_forbidden_names = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def monitor(self, mock_source_collector, mock_orchestrator, mock_topic_store):
        """Create monitor instance."""
        return RealTimeMonitor(
            source_collector=mock_source_collector,
            orchestrator=mock_orchestrator,
            topic_store=mock_topic_store,
            poll_interval=15,
            auto_post=False,
            breaking_threshold=7,
        )

    def test_monitor_initialization(self, monitor):
        """Test monitor initialization."""
        assert monitor.poll_interval == 15
        assert monitor.auto_post is False
        assert monitor.breaking_threshold == 7
        assert monitor._is_running is False
        assert len(monitor._pending_alerts) == 0

    def test_analyze_article_breaking_news(self, monitor):
        """Test analyzing breaking news article."""
        article = MagicMock()
        article.title = "Breaking: OpenAI announces GPT-5"
        article.content = "OpenAI has just announced their latest model."
        article.url = "https://example.com/breaking"
        article.published_at = datetime.now() - timedelta(minutes=30)

        alert = monitor._analyze_article(article)

        assert alert is not None
        assert alert.priority >= 5
        assert "openai" in alert.keywords_matched

    def test_analyze_article_regular_news(self, monitor):
        """Test analyzing regular (non-breaking) article."""
        article = MagicMock()
        article.title = "Weekly tech roundup"
        article.content = "Here are some tech news from this week."
        article.url = "https://example.com/weekly"
        article.published_at = datetime.now() - timedelta(hours=24)

        alert = monitor._analyze_article(article)

        # Should be low priority or None
        if alert:
            assert alert.priority < 5

    def test_analyze_article_priority_entity(self, monitor):
        """Test article with priority entity gets high score."""
        article = MagicMock()
        article.title = "Google DeepMind releases new model"
        article.content = "DeepMind has released a breakthrough."
        article.url = "https://example.com/google"
        article.published_at = datetime.now() - timedelta(minutes=10)

        alert = monitor._analyze_article(article)

        assert alert is not None
        assert alert.priority >= 5
        assert any("google" in kw or "deepmind" in kw for kw in alert.keywords_matched)

    def test_quick_similarity_same_text(self, monitor):
        """Test similarity check with identical texts."""
        text = "OpenAI announces new GPT model"

        assert monitor._quick_similarity(text, text) is True

    def test_quick_similarity_different_text(self, monitor):
        """Test similarity check with different texts."""
        text1 = "OpenAI announces new model"
        text2 = "Weather forecast for tomorrow"

        assert monitor._quick_similarity(text1, text2) is False

    def test_quick_similarity_similar_text(self, monitor):
        """Test similarity check with similar texts."""
        text1 = "OpenAI announces GPT-5 release"
        text2 = "OpenAI announces GPT-5 model launch"

        assert monitor._quick_similarity(text1, text2) is True

    def test_get_status(self, monitor):
        """Test getting monitor status."""
        status = monitor.get_status()

        assert "is_running" in status
        assert "poll_interval_minutes" in status
        assert "auto_post_enabled" in status
        assert "breaking_threshold" in status
        assert status["is_running"] is False
        assert status["poll_interval_minutes"] == 15

    def test_get_pending_alerts_empty(self, monitor):
        """Test getting pending alerts when empty."""
        alerts = monitor.get_pending_alerts()

        assert alerts == []

    def test_get_pending_alerts_with_alerts(self, monitor):
        """Test getting pending alerts with data."""
        article = MagicMock()
        article.title = "Test"
        article.url = "https://test.com"

        alert = NewsAlert(
            article=article,
            priority=8,
            reason="Test alert",
            keywords_matched=["test"],
        )
        monitor._pending_alerts.append(alert)

        alerts = monitor.get_pending_alerts()

        assert len(alerts) == 1
        assert alerts[0]["priority"] == 8
        assert alerts[0]["title"] == "Test"

    @pytest.mark.asyncio
    async def test_check_for_news_no_articles(self, monitor, mock_source_collector):
        """Test checking for news when no articles found."""
        mock_source_collector.fetch_all = AsyncMock(return_value=[])

        alerts = await monitor._check_for_news()

        assert alerts == []

    @pytest.mark.asyncio
    async def test_check_for_news_with_articles(self, monitor, mock_source_collector):
        """Test checking for news with articles."""
        article = MagicMock()
        article.title = "Breaking: Major AI breakthrough"
        article.content = "Scientists announce major breakthrough in AI."
        article.url = "https://example.com/breakthrough"
        article.published_at = datetime.now() - timedelta(minutes=30)

        mock_source_collector.fetch_all = AsyncMock(return_value=[article])

        alerts = await monitor._check_for_news()

        # Should detect as breaking news
        assert len(alerts) >= 1
        assert alerts[0].priority >= 3


class TestRealTimeMonitorAutoPost:
    """Test auto-post functionality."""

    @pytest.fixture
    def mock_source_collector(self):
        """Create mock source collector."""
        return AsyncMock()

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = AsyncMock()
        result = MagicMock()
        result.success = True
        result.post_id = 123
        result.quality_score = 85
        orchestrator.run = AsyncMock(return_value=result)
        return orchestrator

    @pytest.fixture
    def mock_topic_store(self):
        """Create mock topic store."""
        store = AsyncMock()
        store.get_forbidden_names = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def auto_post_monitor(
        self, mock_source_collector, mock_orchestrator, mock_topic_store
    ):
        """Create monitor with auto-post enabled."""
        return RealTimeMonitor(
            source_collector=mock_source_collector,
            orchestrator=mock_orchestrator,
            topic_store=mock_topic_store,
            poll_interval=15,
            auto_post=True,
            breaking_threshold=7,
        )

    @pytest.mark.asyncio
    async def test_maybe_auto_post_skips_low_priority(
        self, auto_post_monitor, mock_orchestrator
    ):
        """Test that low priority alerts don't trigger auto-post."""
        article = MagicMock()
        article.title = "Weekly roundup"
        article.url = "https://example.com/weekly"

        alert = NewsAlert(
            article=article,
            priority=3,  # Below threshold
            reason="Low priority",
        )

        await auto_post_monitor._maybe_auto_post([alert])

        mock_orchestrator.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_maybe_auto_post_respects_min_interval(
        self, auto_post_monitor, mock_orchestrator
    ):
        """Test that auto-post respects minimum interval."""
        auto_post_monitor._last_post_time = datetime.now() - timedelta(minutes=10)

        article = MagicMock()
        article.title = "Breaking: Major news"
        article.url = "https://example.com/breaking"

        alert = NewsAlert(
            article=article,
            priority=9,
            reason="High priority",
        )

        await auto_post_monitor._maybe_auto_post([alert])

        # Should not post due to min interval
        mock_orchestrator.run.assert_not_called()
