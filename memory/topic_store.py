"""
Topic storage and management operations.

Provides CRUD operations for topics with embedding support for deduplication.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import get_logger
from memory.database import Database
from memory.models import Topic

logger = get_logger(__name__)


class TopicStore:
    """
    Store for managing topics in the database.

    Provides methods for topic tracking, deduplication, and selection.
    """

    def __init__(self, db: Database) -> None:
        """
        Initialize topic store.

        Args:
            db: Database instance
        """
        self.db = db

    async def create(
        self,
        name: str,
        description: str | None = None,
        source_type: str = "manual",
        source_url: str | None = None,
        embedding_vector: list[float] | None = None,
    ) -> Topic:
        """
        Create a new topic.

        Args:
            name: Topic name/title
            description: Topic description
            source_type: Source type (manual, rss, api, generated)
            source_url: Source URL
            embedding_vector: Topic embedding for similarity

        Returns:
            Topic: Created topic instance
        """
        async with self.db.session() as session:
            # Check if topic already exists
            existing = await self.get_by_name(name)
            if existing:
                logger.debug(f"Topic already exists: {name[:50]}...")
                return existing

            topic = Topic(
                name=name,
                description=description,
                source_type=source_type,
                source_url=source_url,
                embedding_vector=(
                    json.dumps(embedding_vector) if embedding_vector else None
                ),
            )
            session.add(topic)
            await session.flush()
            await session.refresh(topic)
            logger.info(f"Created topic id={topic.id}, name={name[:50]}...")
            return topic

    async def get_by_id(self, topic_id: int) -> Topic | None:
        """
        Get topic by ID.

        Args:
            topic_id: Topic ID

        Returns:
            Topic | None: Topic instance or None
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(Topic).where(Topic.id == topic_id)
            )
            return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Topic | None:
        """
        Get topic by name.

        Args:
            name: Topic name

        Returns:
            Topic | None: Topic instance or None
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(Topic).where(Topic.name == name)
            )
            return result.scalar_one_or_none()

    async def update(
        self,
        topic_id: int,
        **kwargs,
    ) -> Topic | None:
        """
        Update topic fields.

        Args:
            topic_id: Topic ID
            **kwargs: Fields to update

        Returns:
            Topic | None: Updated topic or None
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(Topic).where(Topic.id == topic_id)
            )
            topic = result.scalar_one_or_none()

            if topic is None:
                return None

            for key, value in kwargs.items():
                if hasattr(topic, key):
                    setattr(topic, key, value)

            await session.flush()
            await session.refresh(topic)
            logger.debug(f"Updated topic id={topic_id}")
            return topic

    async def delete(self, topic_id: int) -> bool:
        """
        Delete topic by ID.

        Args:
            topic_id: Topic ID

        Returns:
            bool: True if deleted
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(Topic).where(Topic.id == topic_id)
            )
            topic = result.scalar_one_or_none()

            if topic is None:
                return False

            await session.delete(topic)
            logger.info(f"Deleted topic id={topic_id}")
            return True

    async def mark_used(self, topic_id: int) -> Topic | None:
        """
        Mark topic as used (increment use count and update timestamp).

        Args:
            topic_id: Topic ID

        Returns:
            Topic | None: Updated topic
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(Topic).where(Topic.id == topic_id)
            )
            topic = result.scalar_one_or_none()

            if topic is None:
                return None

            topic.use_count += 1
            topic.last_used = datetime.utcnow()

            await session.flush()
            await session.refresh(topic)
            return topic

    async def get_unused(self, limit: int = 10) -> list[Topic]:
        """
        Get topics that haven't been used recently.

        Args:
            limit: Maximum number of topics to return

        Returns:
            list[Topic]: List of unused/recently unused topics
        """
        async with self.db.session() as session:
            # Get topics ordered by last_used (oldest first), then by use_count
            query = (
                select(Topic)
                .order_by(Topic.last_used.asc().nulls_first(), Topic.use_count.asc())
                .limit(limit)
            )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def has_used_source_url(self, source_url: str | None) -> bool:
        """
        Check if a topic with the given source URL has already been used.

        This is used to prevent publishing duplicate news from the same source URL.

        Args:
            source_url: Source URL to check.

        Returns:
            bool: True if the URL was already used for a published topic.
        """
        if not source_url:
            return False

        async with self.db.session() as session:
            result = await session.execute(
                select(Topic.id)
                .where(
                    and_(
                        Topic.source_url == source_url,
                        Topic.use_count > 0,
                    )
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def get_recently_used(
        self,
        days: int = 7,
        limit: int = 20,
    ) -> list[Topic]:
        """
        Get topics used within the last N days.

        Args:
            days: Number of days to look back
            limit: Maximum number of topics

        Returns:
            list[Topic]: List of recently used topics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with self.db.session() as session:
            query = (
                select(Topic)
                .where(Topic.last_used >= cutoff)
                .order_by(desc(Topic.last_used))
                .limit(limit)
            )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_forbidden_names(self, days: int = 7) -> list[str]:
        """
        Get topic names that were used recently (for deduplication).

        Args:
            days: Number of days to look back

        Returns:
            list[str]: List of topic names to avoid
        """
        topics = await self.get_recently_used(days=days)
        return [t.name for t in topics]

    async def get_embedding(self, topic_id: int) -> list[float] | None:
        """
        Get embedding vector for a topic.

        Args:
            topic_id: Topic ID

        Returns:
            list[float] | None: Embedding vector or None
        """
        topic = await self.get_by_id(topic_id)
        if topic and topic.embedding_vector:
            return json.loads(topic.embedding_vector)
        return None

    async def set_embedding(
        self,
        topic_id: int,
        embedding: list[float],
    ) -> Topic | None:
        """
        Set embedding vector for a topic.

        Args:
            topic_id: Topic ID
            embedding: Embedding vector

        Returns:
            Topic | None: Updated topic
        """
        return await self.update(
            topic_id,
            embedding_vector=json.dumps(embedding),
        )

    async def find_similar(
        self,
        embedding: list[float],
        threshold: float = 0.85,
        limit: int = 5,
    ) -> list[tuple[Topic, float]]:
        """
        Find topics with similar embeddings.

        Args:
            embedding: Query embedding vector
            threshold: Minimum similarity threshold
            limit: Maximum number of results

        Returns:
            list[tuple[Topic, float]]: List of (topic, similarity) tuples
        """
        import numpy as np

        async with self.db.session() as session:
            # Get all topics with embeddings
            result = await session.execute(
                select(Topic).where(Topic.embedding_vector.isnot(None))
            )
            topics = list(result.scalars().all())

        if not topics:
            return []

        query_embedding = np.array(embedding)
        similarities = []

        for topic in topics:
            topic_embedding = np.array(json.loads(topic.embedding_vector))

            # Cosine similarity
            similarity = np.dot(query_embedding, topic_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(topic_embedding)
            )

            if similarity >= threshold:
                similarities.append((topic, float(similarity)))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:limit]

    async def update_success_rate(
        self,
        topic_id: int,
        success: bool,
        engagement: float = 0.0,
    ) -> Topic | None:
        """
        Update topic success rate and engagement metrics.

        Args:
            topic_id: Topic ID
            success: Whether the post was successful
            engagement: Engagement score of the post

        Returns:
            Topic | None: Updated topic
        """
        topic = await self.get_by_id(topic_id)
        if topic is None:
            return None

        # Simple exponential moving average
        alpha = 0.1  # Weight for new value

        if success:
            new_success_rate = topic.success_rate * (1 - alpha) + 1.0 * alpha
        else:
            new_success_rate = topic.success_rate * (1 - alpha) + 0.0 * alpha

        new_engagement = topic.avg_engagement * (1 - alpha) + engagement * alpha

        return await self.update(
            topic_id,
            success_rate=new_success_rate,
            avg_engagement=new_engagement,
        )

    async def get_top_performing(self, limit: int = 10) -> list[Topic]:
        """
        Get topics with highest engagement scores.

        Args:
            limit: Maximum number of topics

        Returns:
            list[Topic]: List of top performing topics
        """
        async with self.db.session() as session:
            query = (
                select(Topic)
                .where(Topic.use_count > 0)
                .order_by(desc(Topic.avg_engagement))
                .limit(limit)
            )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def bulk_create_from_rss(
        self,
        articles: list[dict],
    ) -> list[Topic]:
        """
        Bulk create topics from RSS articles.

        Args:
            articles: List of article dictionaries with 'title', 'summary', 'url'

        Returns:
            list[Topic]: List of created topics
        """
        created = []

        for article in articles:
            try:
                topic = await self.create(
                    name=article.get("title", ""),
                    description=article.get("summary", ""),
                    source_type="rss",
                    source_url=article.get("url", ""),
                )
                if topic:
                    created.append(topic)
            except Exception as e:
                logger.warning(f"Failed to create topic from article: {e}")

        logger.info(f"Created {len(created)} topics from RSS")
        return created

    async def cleanup_old(self, days: int = 90, min_use_count: int = 0) -> int:
        """
        Remove old unused topics.

        Args:
            days: Remove topics older than this
            min_use_count: Only remove if use_count <= this

        Returns:
            int: Number of topics removed
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with self.db.session() as session:
            result = await session.execute(
                select(Topic).where(
                    and_(
                        Topic.created_at < cutoff,
                        Topic.use_count <= min_use_count,
                    )
                )
            )
            topics = list(result.scalars().all())

            count = 0
            for topic in topics:
                await session.delete(topic)
                count += 1

            logger.info(f"Cleaned up {count} old topics")
            return count

    async def get_stats(self) -> dict:
        """
        Get topic statistics.

        Returns:
            dict: Statistics dictionary
        """
        async with self.db.session() as session:
            # Total topics
            total_result = await session.execute(
                select(func.count(Topic.id))
            )
            total = total_result.scalar() or 0

            # Topics by source type
            by_type_result = await session.execute(
                select(Topic.source_type, func.count(Topic.id))
                .group_by(Topic.source_type)
            )
            by_type = dict(by_type_result.all())

            # Average use count
            avg_result = await session.execute(
                select(func.avg(Topic.use_count))
            )
            avg_use = avg_result.scalar() or 0.0

            # Unused topics
            unused_result = await session.execute(
                select(func.count(Topic.id)).where(Topic.use_count == 0)
            )
            unused = unused_result.scalar() or 0

            return {
                "total_topics": total,
                "by_source_type": by_type,
                "avg_use_count": round(avg_use, 2),
                "unused_topics": unused,
            }
