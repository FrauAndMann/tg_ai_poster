"""
Tests for pipeline components.

Tests source collector, content filter, formatter, and orchestrator.
"""

from datetime import datetime, timedelta
import pytest

from pipeline.source_collector import SourceCollector, Article
from pipeline.content_filter import ContentFilter, ScoredArticle
from pipeline.formatter import PostFormatter


class TestSourceCollector:
    """Tests for SourceCollector."""

    def test_article_creation(self):
        """Test Article dataclass."""
        article = Article(
            title="Test Article",
            summary="Test summary",
            url="https://example.com/test",
            source="Test Source",
        )

        assert article.title == "Test Article"
        assert article.content_hash  # Should have auto-generated hash

    def test_article_to_dict(self):
        """Test Article serialization."""
        article = Article(
            title="Test",
            summary="Summary",
            url="https://example.com",
        )

        data = article.to_dict()
        assert data["title"] == "Test"
        assert data["url"] == "https://example.com"

    def test_article_normalized_url_and_content_alias(self):
        """Test article URL normalization and content alias."""
        article = Article(
            title="Test",
            summary="Summary body",
            url="https://Example.com/path/?utm_source=test&b=2&a=1",
        )

        assert article.content == "Summary body"
        assert article.normalized_url == "https://example.com/path?a=1&b=2"

    def test_deduplicate(self):
        """Test deduplication."""
        collector = SourceCollector(rss_feeds=[])

        articles = [
            Article(title="Article 1", summary="Summary", url="url1"),
            Article(title="Article 1", summary="Summary", url="url1"),  # Duplicate
            Article(title="Article 2", summary="Summary", url="url2"),
        ]

        unique = collector.deduplicate(articles)
        assert len(unique) == 2

    def test_deduplicate_uses_normalized_url(self):
        """Test deduplication by normalized URL, not only hash."""
        collector = SourceCollector(rss_feeds=[])

        articles = [
            Article(title="Article 1", summary="Summary", url="https://example.com/post?utm_source=x&id=1"),
            Article(title="Article 1 copy", summary="Summary", url="https://example.com/post?id=1"),
        ]

        unique = collector.deduplicate(articles)
        assert len(unique) == 1

    def test_filter_by_date(self):
        """Test date filtering."""
        collector = SourceCollector(rss_feeds=[])

        now = datetime.utcnow()
        articles = [
            Article(
                title="Old",
                summary="",
                url="url1",
                published_at=now - timedelta(days=10),
            ),
            Article(
                title="New",
                summary="",
                url="url2",
                published_at=now - timedelta(days=1),
            ),
        ]

        filtered = collector.filter_by_date(articles, max_age_days=7)
        assert len(filtered) == 1
        assert filtered[0].title == "New"

    def test_filter_by_keywords(self):
        """Test keyword filtering."""
        collector = SourceCollector(rss_feeds=[])

        articles = [
            Article(
                title="AI News", summary="About artificial intelligence", url="url1"
            ),
            Article(title="Sports", summary="Football results", url="url2"),
            Article(title="Tech AI", summary="Machine learning update", url="url3"),
        ]

        filtered = collector.filter_by_keywords(articles, keywords=["AI", "tech"])
        assert len(filtered) == 2

    def test_sort_by_date(self):
        """Test date sorting."""
        collector = SourceCollector(rss_feeds=[])

        now = datetime.utcnow()
        articles = [
            Article(
                title="Old",
                summary="",
                url="url1",
                published_at=now - timedelta(days=2),
            ),
            Article(title="New", summary="", url="url2", published_at=now),
            Article(
                title="Middle",
                summary="",
                url="url3",
                published_at=now - timedelta(days=1),
            ),
        ]

        sorted_articles = collector.sort_by_date(articles, descending=True)
        assert sorted_articles[0].title == "New"
        assert sorted_articles[-1].title == "Old"

    def test_rank_articles_prefers_fresh_authoritative_sources(self):
        """Test ranking prefers fresher and higher-signal articles."""
        now = datetime.utcnow()
        collector = SourceCollector(
            rss_feeds=[],
            source_weights={"openai.com": 1.0},
        )
        articles = [
            Article(
                title="Older generic tech post",
                summary="A small update from a generic blog.",
                url="https://example.com/post",
                published_at=now - timedelta(hours=24),
            ),
            Article(
                title="OpenAI announces new release",
                summary="A detailed product and API launch note.",
                url="https://openai.com/blog/post",
                published_at=now - timedelta(hours=1),
            ),
        ]

        ranked = collector.rank_articles(articles)
        assert ranked[0].url == "https://openai.com/blog/post"

    def test_deduplicate_clusters_similar_titles(self):
        """Test duplicate-title clustering across feeds."""
        now = datetime.utcnow()
        collector = SourceCollector(rss_feeds=[])
        articles = [
            Article(
                title="OpenAI releases GPT-5 for developers",
                summary="Short note",
                url="https://example.com/1",
                published_at=now - timedelta(hours=5),
            ),
            Article(
                title="OpenAI releases GPT-5 for developers!",
                summary="Longer and richer launch note for developers.",
                url="https://openai.com/blog/gpt-5",
                published_at=now - timedelta(hours=1),
            ),
        ]

        unique = collector.deduplicate(articles)
        assert len(unique) == 1
        assert unique[0].url == "https://openai.com/blog/gpt-5"

    @pytest.mark.asyncio
    async def test_fetch_rss_uses_cached_articles_on_not_modified(self, monkeypatch, tmp_path):
        """Test HTTP 304 path reuses cached articles and updates health report."""
        state_path = tmp_path / "collector_state.json"
        collector = SourceCollector(
            rss_feeds=["https://example.com/feed.xml"],
            state_path=str(state_path),
        )
        cached = [
            Article(
                title="Cached article",
                summary="Cached summary",
                url="https://example.com/a",
            )
        ]
        collector._cache_articles("https://example.com/feed.xml", cached)
        stats = collector._get_feed_stats("https://example.com/feed.xml")
        stats.etag = "etag-1"

        async def fake_fetch(url):
            return 304, "", "etag-1", "", 12.5

        monkeypatch.setattr(collector, "_fetch_feed_response", fake_fetch)

        articles = await collector.fetch_rss("https://example.com/feed.xml")
        report = collector.get_feed_health_report()["https://example.com/feed.xml"]

        assert len(articles) == 1
        assert articles[0].title == "Cached article"
        assert report["cache_hits"] >= 1

    @pytest.mark.asyncio
    async def test_fetch_rss_disables_feed_after_repeated_failures(self, monkeypatch, tmp_path):
        """Test failing feeds are temporarily disabled."""
        collector = SourceCollector(
            rss_feeds=["https://example.com/feed.xml"],
            request_retries=0,
            disable_after_failures=1,
            state_path=str(tmp_path / "collector_state.json"),
        )

        async def failing_fetch(url):
            raise RuntimeError("boom")

        monkeypatch.setattr(collector, "_fetch_feed_response", failing_fetch)

        articles = await collector.fetch_rss("https://example.com/feed.xml")
        report = collector.get_feed_health_report()["https://example.com/feed.xml"]

        assert articles == []
        assert report["is_disabled"] is True

    @pytest.mark.asyncio
    async def test_close_closes_underlying_session(self, tmp_path):
        """Test explicit collector close lifecycle."""
        collector = SourceCollector(
            rss_feeds=[],
            state_path=str(tmp_path / "collector_state.json"),
        )

        class DummySession:
            def __init__(self):
                self.closed = False

            async def close(self):
                self.closed = True

        session = DummySession()
        collector._session = session
        await collector.close()

        assert session.closed is True


class TestContentFilter:
    """Tests for ContentFilter."""

    def test_filter_initialization(self):
        """Test ContentFilter initialization."""
        filter = ContentFilter(
            channel_topic="AI and Technology",
            min_score=30.0,
        )

        assert filter.channel_topic == "ai and technology"
        assert filter.min_score == 30.0

    def test_score_article(self):
        """Test article scoring."""
        filter = ContentFilter(
            channel_topic="AI Technology",
            min_score=0.0,
        )

        article = Article(
            title="New AI Breakthrough in Machine Learning",
            summary="A new breakthrough in artificial intelligence has been announced. This could change everything.",
            url="https://example.com/ai-news",
        )

        scored = filter.score_article(article)
        assert scored.score > 0

    def test_filter_and_score(self):
        """Test filtering and scoring."""
        filter = ContentFilter(
            channel_topic="AI",
            min_score=20.0,
        )

        articles = [
            Article(
                title="AI News", summary="Good summary about AI technology", url="url1"
            ),
            Article(title="Sports", summary="Short", url="url2"),  # Too short summary
        ]

        scored = filter.filter_and_score(articles)
        assert all(s.score >= 20.0 for s in scored)

    def test_get_top_articles(self):
        """Test getting top articles."""
        filter = ContentFilter(
            channel_topic="AI",
            min_score=0.0,
        )

        articles = [
            Article(title="AI", summary="About AI", url="url1"),
            Article(title="Sports", summary="About sports", url="url2"),
        ]

        top = filter.get_top_articles(articles, n=1)
        assert len(top) == 1

    def test_get_topics_from_articles(self):
        """Test extracting topics from articles."""
        filter = ContentFilter(
            channel_topic="AI",
            min_score=0.0,
        )

        articles = [
            Article(title="AI Topic", summary="Summary", url="url1", source="Source1"),
        ]

        topics = filter.get_topics_from_articles(articles)
        assert len(topics) == 1
        assert topics[0]["title"] == "AI Topic"


class TestPostFormatter:
    """Tests for PostFormatter."""

    def test_escape_markdown_v2(self):
        """Test MarkdownV2 escaping."""
        formatter = PostFormatter(parse_mode="MarkdownV2")

        text = "Hello *World*!"
        escaped = formatter.escape_markdown_v2(text)

        assert "\\!" in escaped

    def test_format_bold(self):
        """Test bold formatting."""
        formatter = PostFormatter(parse_mode="MarkdownV2")

        bold = formatter.format_bold("text")
        assert bold == "*text*"

    def test_format_italic(self):
        """Test italic formatting."""
        formatter = PostFormatter(parse_mode="MarkdownV2")

        italic = formatter.format_italic("text")
        assert italic == "_text_"

    def test_truncate(self):
        """Test truncation."""
        formatter = PostFormatter(max_length=100)

        long_text = "x" * 200
        truncated = formatter.truncate(long_text)

        assert len(truncated) <= 100

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        formatter = PostFormatter()

        text = "Hello   World\n\n\n\nNew Paragraph"
        normalized = formatter.normalize_whitespace(text)

        assert "   " not in normalized
        assert "\n\n\n\n" not in normalized

    def test_extract_hashtags(self):
        """Test hashtag extraction."""
        formatter = PostFormatter()

        text = "Post with #AI and #Technology hashtags"
        hashtags = formatter.extract_hashtags(text)

        assert "AI" in hashtags
        assert "Technology" in hashtags

    def test_remove_hashtags(self):
        """Test hashtag removal."""
        formatter = PostFormatter()

        text = "Post #AI #Tech"
        without_hashtags = formatter.remove_hashtags(text)

        assert "#AI" not in without_hashtags
        assert "#Tech" not in without_hashtags

    def test_validate_format(self):
        """Test format validation."""
        formatter = PostFormatter(parse_mode="MarkdownV2")

        # Valid content
        is_valid, error = formatter.validate_format("Valid content")
        assert is_valid is True

        # Long content is still valid (will be truncated, not rejected)
        is_valid, error = formatter.validate_format("x" * 5000)
        assert is_valid is True  # Long content is valid, just gets truncated

    def test_preview(self):
        """Test preview generation."""
        formatter = PostFormatter()

        text = "x" * 200
        preview = formatter.preview(text, max_preview_length=50)

        assert len(preview) <= 53  # 50 + "..."

    def test_ensure_hashtags_at_end(self):
        """Test hashtag placement."""
        formatter = PostFormatter()

        content = "Post content #existing"
        hashtags = ["new1", "new2"]

        result = formatter.ensure_hashtags_at_end(content, hashtags)
        assert "#new1" in result
        assert "#new2" in result
        assert "#existing" not in result


class TestArticle:
    """Tests for Article dataclass."""

    def test_hash_generation(self):
        """Test automatic hash generation."""
        article1 = Article(title="Test", summary="", url="url")
        article2 = Article(title="Test", summary="", url="url")

        assert article1.content_hash == article2.content_hash

    def test_different_urls_different_hashes(self):
        """Test that different URLs produce different hashes."""
        article1 = Article(title="Test", summary="", url="url1")
        article2 = Article(title="Test", summary="", url="url2")

        assert article1.content_hash != article2.content_hash


class TestScoredArticle:
    """Tests for ScoredArticle dataclass."""

    def test_creation(self):
        """Test ScoredArticle creation."""
        article = Article(title="Test", summary="", url="url")
        scored = ScoredArticle(
            article=article,
            score=75.0,
            score_reasons=["+10: keyword match"],
        )

        assert scored.score == 75.0
        assert len(scored.score_reasons) == 1

    def test_to_dict(self):
        """Test ScoredArticle serialization."""
        article = Article(title="Test", summary="", url="url")
        scored = ScoredArticle(
            article=article,
            score=75.0,
            score_reasons=["reason"],
        )

        data = scored.to_dict()
        assert data["score"] == 75.0
        assert "article" in data
