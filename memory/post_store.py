"""
Post storage and retrieval operations.

Provides CRUD operations for posts with analytics support.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from utils.datetime_utils import utcnow, make_aware
from typing import TYPE_CHECKING

from sqlalchemy import and_, desc, func, select

from core.logger import get_logger
from memory.database import Database
from memory.models import Post as PostModel

if TYPE_CHECKING:
    from domain.post import Post as DomainPost

logger = get_logger(__name__)


class PostStore:
    """
    Store for managing posts in the database.

    Provides methods for creating, retrieving, and analyzing posts.
    """

    def __init__(self, db: Database) -> None:
        """
        Initialize post store.

        Args:
            db: Database instance
        """
        self.db = db

    async def create(
        self,
        content: str,
        topic: str | None = None,
        source: str | None = None,
        source_url: str | None = None,
        status: str = "draft",
        llm_model: str | None = None,
    ) -> PostModel:
        """
        Create a new post.

        Args:
            content: Post content
            topic: Post topic
            source: Content source name
            source_url: Source URL
            status: Post status
            llm_model: LLM model used for generation

        Returns:
            PostModel: Created post instance
        """
        async with self.db.session() as session:
            post = PostModel(
                content=content,
                topic=topic,
                source=source,
                source_url=source_url,
                status=status,
                llm_model=llm_model,
                character_count=len(content),
            )
            session.add(post)
            await session.flush()
            await session.refresh(post)
            logger.info(f"Created post id={post.id}, status={status}")
            return post

    async def create_from_domain(
        self,
        domain_post: "DomainPost",
        formatted_content: str,
        status: str = "draft",
        llm_model: str | None = None,
    ) -> PostModel:
        """
        Create a post from domain Post object.

        Args:
            domain_post: Domain Post object
            formatted_content: Formatted content for publishing
            status: Post status
            llm_model: LLM model used for generation

        Returns:
            PostModel: Created post instance
        """
        async with self.db.session() as session:
            # Convert sources to JSON
            sources_data = [
                {
                    "name": s.name,
                    "url": s.url,
                    "title": s.title,
                    "credibility": s.credibility,
                }
                for s in domain_post.sources
            ]

            post = PostModel(
                content=formatted_content,
                topic=domain_post.topic,
                post_type=domain_post.post_type.value,
                status=status,
                llm_model=llm_model,
                character_count=len(formatted_content),
                # Structured content
                post_title=domain_post.content.title,
                post_hook=domain_post.content.hook,
                post_body=domain_post.content.body,
                post_tldr=domain_post.content.tldr,
                post_analysis=domain_post.content.analysis,
                post_key_facts=json.dumps(
                    domain_post.content.key_facts, ensure_ascii=False
                ),
                post_sources=json.dumps(sources_data, ensure_ascii=False),
                post_hashtags=json.dumps(
                    domain_post.content.hashtags, ensure_ascii=False
                ),
                media_prompt=domain_post.content.media_prompt,
                # Metadata
                quality_score=domain_post.metadata.quality_score,
                editor_score=domain_post.metadata.editor_score,
                confidence_score=domain_post.metadata.confidence_score,
                # Source tracking
                source_count=len(domain_post.sources),
                # Media
                media_url=domain_post.media.url if domain_post.media else None,
                media_source=domain_post.media.source if domain_post.media else None,
                media_photographer=domain_post.media.photographer
                if domain_post.media
                else None,
                # Pipeline version
                pipeline_version="2.0",
            )
            session.add(post)
            await session.flush()
            await session.refresh(post)
            logger.info(
                f"Created post id={post.id}, type={domain_post.post_type.value}"
            )
            return post

    async def get_by_id(self, post_id: int) -> PostModel | None:
        """
        Get post by ID.

        Args:
            post_id: Post ID

        Returns:
            PostModel | None: Post instance or None
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(PostModel).where(PostModel.id == post_id)
            )
            return result.scalar_one_or_none()

    async def update(
        self,
        post_id: int,
        **kwargs,
    ) -> PostModel | None:
        """
        Update post fields.

        Args:
            post_id: Post ID
            **kwargs: Fields to update

        Returns:
            PostModel | None: Updated post or None
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(PostModel).where(PostModel.id == post_id)
            )
            post = result.scalar_one_or_none()

            if post is None:
                return None

            for key, value in kwargs.items():
                if hasattr(post, key):
                    setattr(post, key, value)

            await session.flush()
            await session.refresh(post)
            logger.debug(f"Updated post id={post_id}")
            return post

    async def delete(self, post_id: int) -> bool:
        """
        Delete post by ID.

        Args:
            post_id: Post ID

        Returns:
            bool: True if deleted
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(PostModel).where(PostModel.id == post_id)
            )
            post = result.scalar_one_or_none()

            if post is None:
                return False

            await session.delete(post)
            logger.info(f"Deleted post id={post_id}")
            return True

    async def get_recent(
        self,
        limit: int = 10,
        status: str | None = "published",
    ) -> list[PostModel]:
        """
        Get recent posts.

        Args:
            limit: Maximum number of posts to return
            status: Filter by status (None for all)

        Returns:
            list[PostModel]: List of recent posts
        """
        async with self.db.session() as session:
            query = select(PostModel)

            if status:
                query = query.where(PostModel.status == status)

            query = query.order_by(desc(PostModel.created_at)).limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: str | None = "published",
    ) -> list[PostModel]:
        """
        Get posts within a date range.

        Args:
            start_date: Start date
            end_date: End date
            status: Filter by status

        Returns:
            list[PostModel]: List of posts
        """
        async with self.db.session() as session:
            query = select(PostModel).where(
                and_(
                    PostModel.published_at >= start_date,
                    PostModel.published_at <= end_date,
                )
            )

            if status:
                query = query.where(PostModel.status == status)

            query = query.order_by(desc(PostModel.published_at))

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_for_style_training(self, limit: int = 50) -> list[PostModel]:
        """
        Get successful posts for style training.

        Args:
            limit: Maximum number of posts

        Returns:
            list[PostModel]: List of successful posts
        """
        async with self.db.session() as session:
            query = (
                select(PostModel)
                .where(PostModel.status == "published")
                .where(PostModel.engagement_score > 0)
                .order_by(desc(PostModel.engagement_score))
                .limit(limit)
            )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def mark_published(
        self,
        post_id: int,
        telegram_message_id: int,
    ) -> PostModel | None:
        """
        Mark post as published with Telegram message ID.

        Args:
            post_id: Post ID
            telegram_message_id: Telegram message ID

        Returns:
            PostModel | None: Updated post
        """
        return await self.update(
            post_id,
            status="published",
            telegram_message_id=telegram_message_id,
            published_at=utcnow(),
        )

    async def mark_failed(
        self, post_id: int, error: str | None = None
    ) -> PostModel | None:
        """
        Mark post as failed.

        Args:
            post_id: Post ID
            error: Error message

        Returns:
            PostModel | None: Updated post
        """
        return await self.update(post_id, status="failed")

    async def update_engagement(
        self,
        post_id: int,
        views: int = 0,
        reactions: int = 0,
        shares: int = 0,
        comments: int = 0,
    ) -> PostModel | None:
        """
        Update engagement metrics for a post.

        Args:
            post_id: Post ID
            views: View count
            reactions: Reaction count
            shares: Share count
            comments: Comment count

        Returns:
            PostModel | None: Updated post
        """
        # Calculate engagement score (weighted)
        engagement_score = views * 0.1 + reactions * 1.0 + shares * 2.0 + comments * 1.5

        return await self.update(
            post_id,
            views=views,
            reactions=reactions,
            shares=shares,
            comments=comments,
            engagement_score=engagement_score,
        )

    async def get_today_post_count(self) -> int:
        """
        Get count of posts published today.

        Returns:
            int: Number of posts today
        """
        today = utcnow().date()
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())

        async with self.db.session() as session:
            result = await session.execute(
                select(func.count(PostModel.id)).where(
                    and_(
                        PostModel.status == "published",
                        PostModel.published_at >= start,
                        PostModel.published_at <= end,
                    )
                )
            )
            return result.scalar() or 0

    async def get_last_post_time(self) -> datetime | None:
        """
        Get the time of the last published post.

        Returns:
            datetime | None: Last post time or None
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(PostModel.published_at)
                .where(PostModel.status == "published")
                .order_by(desc(PostModel.published_at))
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return row

    async def can_post_now(self, min_interval_minutes: int) -> bool:
        """
        Check if enough time has passed since the last post.

        Args:
            min_interval_minutes: Minimum minutes between posts

        Returns:
            bool: True if posting is allowed
        """
        last_post = await self.get_last_post_time()

        if last_post is None:
            return True

        # Ensure last_post is timezone-aware (assume UTC if naive from DB)
        last_post_aware = make_aware(last_post)
        min_interval = timedelta(minutes=min_interval_minutes)
        return utcnow() - last_post_aware >= min_interval

    async def get_content_for_dedup(self, limit: int = 10) -> list[str]:
        """
        Get recent post content for deduplication checks.

        Args:
            limit: Number of posts to retrieve

        Returns:
            list[str]: List of post contents
        """
        posts = await self.get_recent(limit=limit, status="published")
        return [p.content for p in posts]

    async def get_stats(self, days: int = 30) -> dict:
        """
        Get posting statistics for the last N days.

        Args:
            days: Number of days to analyze

        Returns:
            dict: Statistics dictionary
        """
        start_date = utcnow() - timedelta(days=days)

        async with self.db.session() as session:
            # Total posts
            total_result = await session.execute(
                select(func.count(PostModel.id)).where(
                    PostModel.published_at >= start_date
                )
            )
            total_posts = total_result.scalar() or 0

            # Average engagement
            avg_result = await session.execute(
                select(func.avg(PostModel.engagement_score)).where(
                    and_(
                        PostModel.published_at >= start_date,
                        PostModel.status == "published",
                    )
                )
            )
            avg_engagement = avg_result.scalar() or 0.0

            # Total views
            views_result = await session.execute(
                select(func.sum(PostModel.views)).where(
                    PostModel.published_at >= start_date
                )
            )
            total_views = views_result.scalar() or 0

            # Failed posts
            failed_result = await session.execute(
                select(func.count(PostModel.id)).where(
                    and_(
                        PostModel.created_at >= start_date,
                        PostModel.status == "failed",
                    )
                )
            )
            failed_posts = failed_result.scalar() or 0

            return {
                "period_days": days,
                "total_posts": total_posts,
                "failed_posts": failed_posts,
                "success_rate": (
                    (total_posts - failed_posts) / total_posts * 100
                    if total_posts > 0
                    else 100
                ),
                "avg_engagement_score": round(avg_engagement, 2),
                "total_views": total_views,
                "posts_per_day": round(total_posts / days, 1),
            }
