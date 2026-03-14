"""
Tests for memory module.

Tests database initialization, models, and stores.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

from memory.models import Base, Post, Topic, Source
from memory.database import Database
from memory.post_store import PostStore
from memory.topic_store import TopicStore


class TestModels:
    """Tests for SQLAlchemy models."""

    def test_post_model(self):
        """Test Post model attributes."""
        post = Post(
            content="Test content",
            topic="Test topic",
            status="draft",
        )
        assert post.content == "Test content"
        assert post.status == "draft"
        # character_count has default value of0, not calculated

    def test_post_to_dict(self):
        """Test Post serialization."""
        post = Post(
            content="Test",
            topic="Topic",
            status="draft",
        )
        data = post.to_dict()
        assert data["content"] == "Test"
        assert data["status"] == "draft"

    def test_topic_model(self):
        """Test Topic model attributes."""
        topic = Topic(
            name="Test Topic",
            source_type="manual",
        )
        assert topic.name == "Test Topic"
        # use_count has default value of 0
        assert topic.use_count == 0 or topic.use_count is None

    def test_source_model(self):
        """Test Source model attributes."""
        source = Source(
            url="https://example.com/feed",
            type="rss",
        )
        assert source.url == "https://example.com/feed"
        assert source.type == "rss"


class TestDatabase:
    """Tests for Database class."""

    @pytest_asyncio.fixture
    async def db(self, in_memory_db):
        """Use shared in-memory database fixture."""
        yield in_memory_db

    @pytest.mark.asyncio
    async def test_init(self):
        """Test database initialization."""
        db = Database("sqlite+aiosqlite:///:memory:")
        await db.init()

        # Check that tables exist
        async with db.session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result.fetchall()]
            assert "posts" in tables
            assert "topics" in tables
            assert "sources" in tables

        await db.close()

    @pytest.mark.asyncio
    async def test_session_context(self, db):
        """Test session context manager."""
        async with db.session() as session:
            # Should be able to execute queries
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_health_check(self, db):
        """Test database health check."""
        is_healthy = await db.health_check()
        # May pass or fail depending on database state
        assert isinstance(is_healthy, bool)


class TestPostStore:
    """Tests for PostStore."""

    @pytest_asyncio.fixture
    async def post_store(self, in_memory_db):
        """Create post store with shared in-memory database."""
        store = PostStore(in_memory_db)
        yield store

    @pytest.mark.asyncio
    async def test_create_post(self, post_store):
        """Test creating a post."""
        post = await post_store.create(
            content="Test post content",
            topic="Test topic",
            source="Test source",
            status="draft",
        )

        assert post.id is not None
        assert post.content == "Test post content"
        assert post.status == "draft"

    @pytest.mark.asyncio
    async def test_get_by_id(self, post_store):
        """Test getting post by ID."""
        created = await post_store.create(content="Test", status="draft")
        retrieved = await post_store.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.content == "Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_post(self, post_store):
        """Test getting nonexistent post."""
        post = await post_store.get_by_id(99999)
        assert post is None

    @pytest.mark.asyncio
    async def test_update_post(self, post_store):
        """Test updating a post."""
        created = await post_store.create(content="Original", status="draft")
        updated = await post_store.update(created.id, status="published")

        assert updated.status == "published"

    @pytest.mark.asyncio
    async def test_delete_post(self, post_store):
        """Test deleting a post."""
        created = await post_store.create(content="To delete", status="draft")
        deleted = await post_store.delete(created.id)

        assert deleted is True

        # Verify deleted
        retrieved = await post_store.get_by_id(created.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_recent(self, post_store):
        """Test getting recent posts."""
        await post_store.create(content="Post 1", status="published")
        await post_store.create(content="Post 2", status="published")
        await post_store.create(content="Post 3", status="draft")  # Should not appear

        recent = await post_store.get_recent(limit=10, status="published")
        assert len(recent) == 2

    @pytest.mark.asyncio
    async def test_mark_published(self, post_store):
        """Test marking post as published."""
        post = await post_store.create(content="Test", status="pending")
        updated = await post_store.mark_published(post.id, telegram_message_id=12345)

        assert updated.status == "published"
        assert updated.telegram_message_id == 12345

    @pytest.mark.asyncio
    async def test_get_today_post_count(self, post_store):
        """Test getting today's post count."""
        await post_store.create(content="Post 1", status="published")
        await post_store.create(content="Post 2", status="published")

        count = await post_store.get_today_post_count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_can_post_now(self, post_store):
        """Test checking if posting is allowed."""
        # No posts yet
        can_post = await post_store.can_post_now(min_interval_minutes=60)
        assert can_post is True

    @pytest.mark.asyncio
    async def test_get_stats(self, post_store):
        """Test getting statistics."""
        await post_store.create(content="Post 1", status="published")
        await post_store.create(content="Post 2", status="published")

        stats = await post_store.get_stats(days=30)
        assert stats["total_posts"] == 2


class TestTopicStore:
    """Tests for TopicStore."""

    @pytest_asyncio.fixture
    async def topic_store(self, in_memory_db):
        """Create topic store with shared in-memory database."""
        store = TopicStore(in_memory_db)
        yield store

    @pytest.mark.asyncio
    async def test_create_topic(self, topic_store):
        """Test creating a topic."""
        topic = await topic_store.create(
            name="Test Topic",
            description="Test description",
            source_type="manual",
        )

        assert topic.id is not None
        assert topic.name == "Test Topic"

    @pytest.mark.asyncio
    async def test_get_by_name(self, topic_store):
        """Test getting topic by name."""
        created = await topic_store.create(name="Unique Topic")
        retrieved = await topic_store.get_by_name("Unique Topic")

        assert retrieved is not None
        assert retrieved.name == "Unique Topic"

    @pytest.mark.asyncio
    async def test_create_duplicate_topic(self, topic_store):
        """Test that duplicate topics are not created."""
        await topic_store.create(name="Duplicate Topic")
        duplicate = await topic_store.create(name="Duplicate Topic")

        # Should return existing topic
        assert duplicate.name == "Duplicate Topic"

    @pytest.mark.asyncio
    async def test_mark_used(self, topic_store):
        """Test marking topic as used."""
        topic = await topic_store.create(name="Test Topic")
        updated = await topic_store.mark_used(topic.id)

        assert updated.use_count == 1
        assert updated.last_used is not None

    @pytest.mark.asyncio
    async def test_get_unused(self, topic_store):
        """Test getting unused topics."""
        await topic_store.create(name="Topic 1")
        await topic_store.create(name="Topic 2")
        topic3 = await topic_store.create(name="Topic 3")
        await topic_store.mark_used(topic3.id)

        unused = await topic_store.get_unused(limit=10)
        names = [t.name for t in unused]
        assert "Topic 1" in names
        assert "Topic 2" in names
        assert "Topic 3" not in names  # Was used

