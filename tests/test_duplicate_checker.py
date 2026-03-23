"""
Tests for duplicate checker module.
"""
import pytest

from pipeline.duplicate_checker import ChannelDuplicateChecker, DuplicateCheckStats


@pytest.fixture
def checker():
    """Create duplicate checker with mocked stores."""
    post_store = pytest.Asyncio.Mock.Mock()
    topic_store = pytest.asyncio.mock.mock()

    c = ChannelDuplicateChecker(
        post_store=post_store,
        topic_store=topic_store,
    )
    return checker


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
        from pipeline.source_collector import Article

        article = Article(
            title="Test Article",
            url="https://example.com/test",
            source="Test Source",
            summary="Test summary",
        )

        checker._source_url_cache = {}
        checker._normalized_title_cache = {}
        checker._normalized_title_cache = {}

        checker.post_store.get_recent = AsyncMock()
        checker.topic_store.get_recently_used = AsyncMock()
        checker.topic_store.has_used_source_url = AsyncMock()

        result, stats = await checker.check_articles([article])

        assert len(result) == 1
        assert stats.total_checked == 1
        assert stats.total_duplicates == 0

    @pytest.mark.asyncio
    async def test_check_articles_url_duplicate(self, checker):
        """Test URL duplicate detection."""
        from pipeline.source_collector import Article

        article1 = Article(
            title="New Article",
            url="https://example.com/new",
            source="Source A",
            summary="Test summary",
        )

        article2 = Article(
            title="Test Article",
            url="https://example.com/test",  # Duplicate URL
            source="Source B",
            summary="Test summary"
        )

        # Mock the stores
        checker.post_store.get_recent = AsyncMock()
        checker.topic_store.get_recently_used = AsyncMock()
        checker.topic_store.has_used_source_url = AsyncMock()

        result, stats = await checker.check_articles([article1, article2])

        assert len(result) == 1  # Only first article should pass
        assert stats.total_checked == 2
        assert stats.total_duplicates == 1
        assert stats.url_duplicates == 1

    @pytest.mark.asyncio
    async def test_check_articles_title_duplicate(self, checker):
        """Test title duplicate detection."""
        from pipeline.source_collector import Article

        article = Article(
            title="Test Article Title",
            url="https://example.com/unique1",
            source="Test Source",
            summary="Unique summary",
        )

        # Mock normalized title cache with existing title
        checker._normalized_title_cache = {
            "test article title": (1, 1.0)
        }

        # Mock stores
        checker.post_store.get_recent = AsyncMock()
        checker.topic_store.get_recently_used = AsyncMock()
        checker.topic_store.has_used_source_url = AsyncMock()

        result, stats = await checker.check_articles([article])

        assert len(result) == 0  # All should be filtered
        assert stats.total_duplicates == 1
        assert stats.title_duplicates == 1


