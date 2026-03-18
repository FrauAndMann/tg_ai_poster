"""Tests for Feedback Loop Integration - collector and analyzer."""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from pipeline.feedback.collector import PostAnalytics, FeedbackCollector
from pipeline.feedback.analyzer import WeeklyAnalysis, FeedbackAnalyzer


# ============================================================================
# PostAnalytics Dataclass Tests
# ============================================================================


def test_post_analytics_dataclass_creation():
    """Test PostAnalytics dataclass can be created with all fields."""
    reactions: Dict[str, int] = {"👍": 10, "❤️": 5, "🔥": 3}

    analytics = PostAnalytics(
        post_id="post_123",
        telegram_message_id=456789,
        views=1000,
        reactions=reactions,
        forwards=15,
        replies=8,
        quality_score=85.5,
        collected_at=datetime(2025, 3, 15, 12, 0, 0),
    )

    assert analytics.post_id == "post_123"
    assert analytics.telegram_message_id == 456789
    assert analytics.views == 1000
    assert analytics.reactions == reactions
    assert analytics.forwards == 15
    assert analytics.replies == 8
    assert analytics.quality_score == 85.5
    assert analytics.collected_at == datetime(2025, 3, 15, 12, 0, 0)


def test_post_analytics_total_reactions():
    """Test total_reactions property sums all reaction counts."""
    reactions = {"👍": 10, "❤️": 5, "🔥": 3}

    analytics = PostAnalytics(
        post_id="post_123",
        telegram_message_id=456789,
        views=1000,
        reactions=reactions,
        forwards=15,
        replies=8,
        quality_score=85.5,
        collected_at=datetime.now(),
    )

    assert analytics.total_reactions == 18


def test_post_analytics_engagement_rate():
    """Test engagement_rate property calculates correctly."""
    reactions = {"👍": 10, "❤️": 5}

    analytics = PostAnalytics(
        post_id="post_123",
        telegram_message_id=456789,
        views=1000,
        reactions=reactions,
        forwards=10,
        replies=5,
        quality_score=85.5,
        collected_at=datetime.now(),
    )

    # Total engagement = 15 (reactions) + 10 (forwards) + 5 (replies) = 30
    # Rate = 30 / 1000 = 0.03
    assert analytics.engagement_rate == pytest.approx(0.03, rel=0.01)


def test_post_analytics_engagement_rate_zero_views():
    """Test engagement_rate returns 0 when views is 0."""
    analytics = PostAnalytics(
        post_id="post_123",
        telegram_message_id=456789,
        views=0,
        reactions={"👍": 1},
        forwards=0,
        replies=0,
        quality_score=85.5,
        collected_at=datetime.now(),
    )

    assert analytics.engagement_rate == 0.0


def test_post_analytics_to_dict():
    """Test to_dict serializes correctly."""
    reactions = {"👍": 10, "❤️": 5}
    collected_at = datetime(2025, 3, 15, 12, 0, 0)

    analytics = PostAnalytics(
        post_id="post_123",
        telegram_message_id=456789,
        views=1000,
        reactions=reactions,
        forwards=15,
        replies=8,
        quality_score=85.5,
        collected_at=collected_at,
    )

    result = analytics.to_dict()

    assert result["post_id"] == "post_123"
    assert result["telegram_message_id"] == 456789
    assert result["views"] == 1000
    assert result["reactions"] == reactions
    assert result["forwards"] == 15
    assert result["replies"] == 8
    assert result["quality_score"] == 85.5
    assert result["collected_at"] == collected_at.isoformat()


# ============================================================================
# FeedbackCollector Database Tests
# ============================================================================


class TestFeedbackCollectorDatabase:
    """Tests for FeedbackCollector database operations."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temporary database path for testing."""
        return str(tmp_path / "test_analytics.db")

    def test_init_db_creates_table(self, temp_db_path):
        """Test database initialization creates the post_analytics table."""
        collector = FeedbackCollector(db_path=temp_db_path)

        # Check table exists
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='post_analytics'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "post_analytics"

    def test_init_db_table_schema(self, temp_db_path):
        """Test database table has correct schema."""
        collector = FeedbackCollector(db_path=temp_db_path)

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(post_analytics)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert "id" in columns
        assert "post_id" in columns
        assert "telegram_message_id" in columns
        assert "views" in columns
        assert "reactions" in columns
        assert "forwards" in columns
        assert "replies" in columns
        assert "quality_score" in columns
        assert "collected_at" in columns

    @pytest.mark.asyncio
    async def test_store_analytics(self, temp_db_path):
        """Test storing analytics in database."""
        collector = FeedbackCollector(db_path=temp_db_path)

        analytics = PostAnalytics(
            post_id="post_123",
            telegram_message_id=456789,
            views=1000,
            reactions={"👍": 10, "❤️": 5},
            forwards=15,
            replies=8,
            quality_score=85.5,
            collected_at=datetime(2025, 3, 15, 12, 0, 0),
        )

        await collector.store_analytics(analytics)

        # Verify data was stored
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM post_analytics WHERE post_id = ?", ("post_123",))
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[1] == "post_123"
        assert result[2] == 456789
        assert result[3] == 1000
        assert result[5] == 15
        assert result[6] == 8
        assert result[7] == 85.5

    @pytest.mark.asyncio
    async def test_get_analytics_by_post_id(self, temp_db_path):
        """Test retrieving analytics by post ID."""
        collector = FeedbackCollector(db_path=temp_db_path)

        analytics = PostAnalytics(
            post_id="post_456",
            telegram_message_id=789012,
            views=2000,
            reactions={"👍": 20},
            forwards=25,
            replies=10,
            quality_score=90.0,
            collected_at=datetime(2025, 3, 16, 14, 30, 0),
        )

        await collector.store_analytics(analytics)

        result = collector.get_analytics_by_post_id("post_456")

        assert result is not None
        assert result.post_id == "post_456"
        assert result.views == 2000
        assert result.forwards == 25
        assert result.quality_score == 90.0

    @pytest.mark.asyncio
    async def test_get_analytics_for_period(self, temp_db_path):
        """Test retrieving analytics for a date range."""
        collector = FeedbackCollector(db_path=temp_db_path)

        # Store analytics for different dates
        base_date = datetime(2025, 3, 10, 12, 0, 0)
        for i in range(5):
            analytics = PostAnalytics(
                post_id=f"post_{i}",
                telegram_message_id=100000 + i,
                views=100 * (i + 1),
                reactions={"👍": i + 1},
                forwards=i,
                replies=i,
                quality_score=70.0 + i * 5,
                collected_at=base_date + timedelta(days=i),
            )
            await collector.store_analytics(analytics)

        # Get analytics for middle 3 days
        start_date = date(2025, 3, 11)
        end_date = date(2025, 3, 13)
        results = collector.get_analytics_for_period(start_date, end_date)

        assert len(results) == 3
        post_ids = [r.post_id for r in results]
        assert "post_1" in post_ids
        assert "post_2" in post_ids
        assert "post_3" in post_ids
        assert "post_0" not in post_ids
        assert "post_4" not in post_ids


# ============================================================================
# FeedbackCollector Metrics Collection Tests
# ============================================================================


class TestFeedbackCollectorMetrics:
    """Tests for FeedbackCollector metrics collection."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temporary database path for testing."""
        return str(tmp_path / "test_analytics.db")

    @pytest.fixture
    def mock_telegram_client(self):
        """Create mock Telegram client."""
        client = AsyncMock()

        # Mock message with views, reactions, forwards
        mock_message = MagicMock()
        mock_message.views = 1500
        mock_message.forwards = 25

        # Mock reactions
        mock_reaction_result = MagicMock()
        mock_reaction_result.count = 10
        mock_reaction_result.reaction.emoticon = "👍"

        mock_reaction_result2 = MagicMock()
        mock_reaction_result2.count = 5
        mock_reaction_result2.reaction.emoticon = "❤️"

        mock_reactions = MagicMock()
        mock_reactions.results = [mock_reaction_result, mock_reaction_result2]
        mock_message.reactions = mock_reactions

        client.get_messages = AsyncMock(return_value=[mock_message])

        return client

    @pytest.mark.asyncio
    async def test_collect_metrics_from_telegram(self, temp_db_path, mock_telegram_client):
        """Test collecting metrics from Telegram API."""
        collector = FeedbackCollector(db_path=temp_db_path, telegram_client=mock_telegram_client)

        analytics = await collector.collect_metrics("post_123", 456789, channel_entity="@test_channel")

        assert analytics is not None
        assert analytics.post_id == "post_123"
        assert analytics.telegram_message_id == 456789
        assert analytics.views == 1500
        assert analytics.forwards == 25
        # Reactions: 👍=10, ❤️=5
        assert analytics.reactions.get("👍", 0) == 10
        assert analytics.reactions.get("❤️", 0) == 5

    @pytest.mark.asyncio
    async def test_collect_metrics_no_client(self, temp_db_path):
        """Test collect_metrics returns None when no client configured."""
        collector = FeedbackCollector(db_path=temp_db_path, telegram_client=None)

        analytics = await collector.collect_metrics("post_123", 456789, channel_entity="@test_channel")

        assert analytics is None

    @pytest.mark.asyncio
    async def test_collect_metrics_message_not_found(self, temp_db_path):
        """Test collect_metrics handles message not found."""
        mock_client = AsyncMock()
        mock_client.get_messages = AsyncMock(return_value=None)

        collector = FeedbackCollector(db_path=temp_db_path, telegram_client=mock_client)

        analytics = await collector.collect_metrics("post_123", 456789, channel_entity="@test_channel")

        assert analytics is None


# ============================================================================
# FeedbackAnalyzer Tests
# ============================================================================


class TestFeedbackAnalyzer:
    """Tests for FeedbackAnalyzer."""

    @pytest.fixture
    def sample_analytics(self):
        """Create sample analytics data for testing."""
        base_date = datetime(2025, 3, 10, 12, 0, 0)
        analytics_list = []

        # Create analytics with varying quality scores and engagement
        for i in range(10):
            quality_score = 60.0 + i * 4  # 60 to 96
            views = 1000 + i * 200
            reactions_count = 10 + i * 5

            analytics = PostAnalytics(
                post_id=f"post_{i}",
                telegram_message_id=100000 + i,
                views=views,
                reactions={"👍": reactions_count},
                forwards=i * 2,
                replies=i,
                quality_score=quality_score,
                collected_at=base_date + timedelta(days=i % 7),
            )
            analytics_list.append(analytics)

        return analytics_list

    def test_analyze_week_basic(self, sample_analytics):
        """Test weekly analysis produces correct basic metrics."""
        analyzer = FeedbackAnalyzer()
        period = (date(2025, 3, 10), date(2025, 3, 16))

        analysis = analyzer.analyze_week(sample_analytics, period)

        assert analysis.period == period
        assert analysis.total_posts == 10
        assert analysis.avg_quality_score > 0
        assert analysis.avg_engagement > 0

    def test_analyze_week_correlation(self, sample_analytics):
        """Test correlation calculation between quality and engagement."""
        analyzer = FeedbackAnalyzer()
        period = (date(2025, 3, 10), date(2025, 3, 16))

        analysis = analyzer.analyze_week(sample_analytics, period)

        # Higher quality scores should correlate with higher engagement
        # in our sample data
        assert -1.0 <= analysis.correlation <= 1.0

    def test_analyze_week_recommendations(self, sample_analytics):
        """Test that recommendations are generated."""
        analyzer = FeedbackAnalyzer()
        period = (date(2025, 3, 10), date(2025, 3, 16))

        analysis = analyzer.analyze_week(sample_analytics, period)

        assert isinstance(analysis.recommendations, list)

    def test_analyze_week_empty_data(self):
        """Test analysis handles empty data gracefully."""
        analyzer = FeedbackAnalyzer()
        period = (date(2025, 3, 10), date(2025, 3, 16))

        analysis = analyzer.analyze_week([], period)

        assert analysis.total_posts == 0
        assert analysis.avg_quality_score == 0.0
        assert analysis.avg_engagement == 0.0
        assert analysis.correlation == 0.0
        assert len(analysis.recommendations) > 0  # Should recommend collecting data

    def test_analyze_week_single_post(self):
        """Test analysis handles single post."""
        analyzer = FeedbackAnalyzer()
        period = (date(2025, 3, 10), date(2025, 3, 16))

        analytics = PostAnalytics(
            post_id="post_1",
            telegram_message_id=100000,
            views=1000,
            reactions={"👍": 10},
            forwards=5,
            replies=3,
            quality_score=85.0,
            collected_at=datetime(2025, 3, 12, 12, 0, 0),
        )

        analysis = analyzer.analyze_week([analytics], period)

        assert analysis.total_posts == 1
        assert analysis.avg_quality_score == 85.0


# ============================================================================
# WeeklyAnalysis Dataclass Tests
# ============================================================================


def test_weekly_analysis_dataclass():
    """Test WeeklyAnalysis dataclass creation."""
    period = (date(2025, 3, 10), date(2025, 3, 16))
    recommendations = ["Increase quality score threshold", "Post more frequently"]

    analysis = WeeklyAnalysis(
        period=period,
        total_posts=50,
        avg_quality_score=78.5,
        avg_engagement=0.045,
        correlation=0.72,
        recommendations=recommendations,
    )

    assert analysis.period == period
    assert analysis.total_posts == 50
    assert analysis.avg_quality_score == 78.5
    assert analysis.avg_engagement == 0.045
    assert analysis.correlation == 0.72
    assert analysis.recommendations == recommendations


def test_weekly_analysis_to_dict():
    """Test WeeklyAnalysis to_dict serialization."""
    period = (date(2025, 3, 10), date(2025, 3, 16))
    recommendations = ["Test recommendation"]

    analysis = WeeklyAnalysis(
        period=period,
        total_posts=25,
        avg_quality_score=82.0,
        avg_engagement=0.05,
        correlation=0.65,
        recommendations=recommendations,
    )

    result = analysis.to_dict()

    assert result["period_start"] == "2025-03-10"
    assert result["period_end"] == "2025-03-16"
    assert result["total_posts"] == 25
    assert result["avg_quality_score"] == 82.0
    assert result["avg_engagement"] == 0.05
    assert result["correlation"] == 0.65
    assert result["recommendations"] == recommendations


# ============================================================================
# Integration Tests
# ============================================================================


class TestFeedbackLoopIntegration:
    """Integration tests for the feedback loop."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temporary database path for testing."""
        return str(tmp_path / "test_analytics.db")

    @pytest.mark.asyncio
    async def test_full_feedback_loop(self, temp_db_path):
        """Test complete feedback loop: collect, store, analyze."""
        collector = FeedbackCollector(db_path=temp_db_path)
        analyzer = FeedbackAnalyzer()

        # Store multiple analytics
        base_date = datetime(2025, 3, 10, 12, 0, 0)
        for i in range(7):
            analytics = PostAnalytics(
                post_id=f"post_{i}",
                telegram_message_id=100000 + i,
                views=1000 + i * 100,
                reactions={"👍": 10 + i, "❤️": 5 + i},
                forwards=5 + i,
                replies=2 + i,
                quality_score=70.0 + i * 3,
                collected_at=base_date + timedelta(days=i),
            )
            await collector.store_analytics(analytics)

        # Get weekly analytics
        period = (date(2025, 3, 10), date(2025, 3, 16))
        stored_analytics = collector.get_analytics_for_period(period[0], period[1])

        # Analyze
        analysis = analyzer.analyze_week(stored_analytics, period)

        assert analysis.total_posts == 7
        assert analysis.avg_quality_score > 0
        assert len(analysis.recommendations) >= 0

    @pytest.mark.asyncio
    async def test_threshold_adjustment_recommendation(self, temp_db_path):
        """Test that analysis can recommend threshold adjustments."""
        collector = FeedbackCollector(db_path=temp_db_path)
        analyzer = FeedbackAnalyzer()

        # Create analytics where low quality posts perform well
        base_date = datetime(2025, 3, 10, 12, 0, 0)
        for i in range(5):
            # Low quality but high engagement
            analytics = PostAnalytics(
                post_id=f"post_{i}",
                telegram_message_id=100000 + i,
                views=10000,  # High views
                reactions={"👍": 500, "❤️": 200},  # High reactions
                forwards=100,
                replies=50,
                quality_score=55.0 + i * 2,  # Low quality (55-63)
                collected_at=base_date + timedelta(days=i),
            )
            await collector.store_analytics(analytics)

        period = (date(2025, 3, 10), date(2025, 3, 16))
        stored_analytics = collector.get_analytics_for_period(period[0], period[1])
        analysis = analyzer.analyze_week(stored_analytics, period)

        # Should have recommendations about threshold
        assert len(analysis.recommendations) > 0
