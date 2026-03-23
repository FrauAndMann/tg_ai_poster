"""
Tests for duplicate checker module.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from pipeline.duplicate_checker import ChannelDuplicateChecker, DuplicateCheckStats
from pipeline.source_collector import Article


@pytest.fixture
def checker():
    """Create duplicate checker with mocked stores."""
    post_store = MagicMock()
    topic_store = MagicMock()

    # Setup async methods - return empty by default
    post_store.get_recent = AsyncMock(return_value=[])
    post_store.get_by_id = AsyncMock(return_value=None)
    topic_store.get_recently_used = AsyncMock(return_value=[])
    topic_store.has_used_source_url = AsyncMock(return_value=False)

    c = ChannelDuplicateChecker(
        post_store=post_store,
        topic_store=topic_store,
    )
    return c


class TestChannelDuplicateChecker:
    """Tests for ChannelDuplicateChecker."""

    @pytest.mark.asyncio
    async def test_check_articles_empty(self, checker):
        """Test with empty article list."""
        result, stats = await checker.check_articles([])

        assert result == []
        assert stats.total_checked == 0
        assert stats.total_duplicates == 0

    @pytest.mark.asyncio
    async def test_check_articles_no_duplicates(self, checker):
        """Test with no duplicates found."""
        article = Article(
            title="Test Article",
            url="https://example.com/test",
            source="Test Source",
            summary="Test summary",
        )

        result, stats = await checker.check_articles([article])

        assert len(result) == 1
        assert stats.total_checked == 1
        assert stats.total_duplicates == 0

    @pytest.mark.asyncio
    async def test_check_articles_url_duplicate(self, checker):
        """Test URL duplicate detection against published posts."""
        article1 = Article(
            title="New Article",
            url="https://example.com/new",
            source="Source A",
            summary="Test summary",
        )

        article2 = Article(
            title="Test Article",
            url="https://example.com/duplicate",  # This URL was already used
            source="Source B",
            summary="Test summary"
        )

        # Mock topic_store to return topics with the duplicate URL
        mock_topic = MagicMock()
        mock_topic.source_url = "https://example.com/duplicate"
        checker.topic_store.get_recently_used = AsyncMock(return_value=[mock_topic])

        result, stats = await checker.check_articles([article1, article2])

        assert len(result) == 1  # Only first article should pass
        assert stats.total_checked == 2
        assert stats.total_duplicates == 1
        assert stats.url_duplicates == 1

    @pytest.mark.asyncio
    async def test_check_articles_title_duplicate(self, checker):
        """Test title duplicate detection against published posts."""
        article1 = Article(
            title="Unique Article Title",
            url="https://example.com/unique1",
            source="Test Source",
            summary="Unique summary",
        )

        article2 = Article(
            title="Already Published Title",  # This title was already published
            url="https://example.com/unique2",
            source="Test Source",
            summary="Unique summary",
        )

        # Mock post_store to return a post with the duplicate title
        mock_post = MagicMock()
        mock_post.id = 1
        mock_post.topic = "Already Published Title"
        checker.post_store.get_recent = AsyncMock(return_value=[mock_post])

        result, stats = await checker.check_articles([article1, article2])

        assert len(result) == 1  # Only unique article should pass
        assert stats.total_duplicates == 1
        assert stats.title_duplicates == 1

    @pytest.mark.asyncio
    async def test_check_articles_url_via_topic_store(self, checker):
        """Test URL duplicate detection via topic_store.has_used_source_url."""
        article = Article(
            title="Test Article",
            url="https://example.com/used-url",
            source="Test Source",
            summary="Test summary",
        )

        # Mock topic_store to report URL as used
        checker.topic_store.has_used_source_url = AsyncMock(return_value=True)

        result, stats = await checker.check_articles([article])

        assert len(result) == 0
        assert stats.total_duplicates == 1
        assert stats.url_duplicates == 1
