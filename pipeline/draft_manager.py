"""
Draft and Version Management Module.

Manages post versions, draft operations, and version history.
"""

from __future__ import annotations


from sqlalchemy import select, desc

from core.logger import get_logger
from memory.models import Post, PostVersion
from memory.database import get_database

logger = get_logger(__name__)


class DraftManager:
    """Manages post versions and draft operations."""

    def __init__(self):
        pass

    async def create_version(
        self, post: Post, reason: str | None = None, created_by: str = "ai"
    ) -> PostVersion:
        """
        Create new version snapshot.

        Args:
            post: Post to version
            reason: Optional change reason
            created_by: Creator identifier (ai or user_id)

        Returns:
            PostVersion: Created version
        """
        async with get_database().session() as session:
            # Get next version number
            result = await session.execute(
                select(PostVersion.version_number)
                .where(PostVersion.post_id == post.id)
                .order_by(desc(PostVersion.version_number))
                .limit(1)
            )
            last_version = result.scalar() or 0
            version_number = last_version + 1

            # Create version snapshot
            version = PostVersion(
                post_id=post.id,
                version_number=version_number,
                content=post.content,
                post_title=post.post_title,
                post_hook=post.post_hook,
                post_body=post.post_body,
                post_tldr=post.post_tldr,
                post_hashtags=post.post_hashtags,
                created_by=created_by,
                change_reason=reason,
            )

            session.add(version)
            await session.flush()

            # Update post version - get fresh post from this session
            result = await session.execute(select(Post).where(Post.id == post.id))
            db_post = result.scalar_one_or_none()
            if db_post:
                db_post.version = version_number
                db_post.current_version_id = version.id

            await session.commit()
            await session.refresh(version)

            logger.info(f"Created version {version_number} for post {post.id}")
            return version

    async def get_version(self, post_id: int, version: int) -> PostVersion | None:
        """
        Get specific version.

        Args:
            post_id: Post ID
            version: Version number

        Returns:
            PostVersion | None: Version if found
        """
        async with get_database().session() as session:
            result = await session.execute(
                select(PostVersion)
                .where(PostVersion.post_id == post_id)
                .where(PostVersion.version_number == version)
            )
            return result.scalar_one_or_none()

    async def list_versions(self, post_id: int, limit: int = 10) -> list[PostVersion]:
        """
        List all versions of a post.

        Args:
            post_id: Post ID
            limit: Maximum versions to return

        Returns:
            list[PostVersion]: List of versions (newest first)
        """
        async with get_database().session() as session:
            result = await session.execute(
                select(PostVersion)
                .where(PostVersion.post_id == post_id)
                .order_by(desc(PostVersion.version_number))
                .limit(limit)
            )
            return list(result.scalars().all())

    async def restore_version(self, post_id: int, version: int) -> Post | None:
        """
        Restore post to a previous version.

        Args:
            post_id: Post ID
            version: Version number to restore

        Returns:
            Post | None: Updated post if successful
        """
        # Get the version to restore
        version_obj = await self.get_version(post_id, version)
        if not version_obj:
            logger.warning(f"Version {version} not found for post {post_id}")
            return None

        async with get_database().session() as session:
            # Get the post
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            if not post:
                return None

            # Create a version snapshot of current state before restore
            await self.create_version(
                post, reason=f"Before restore to version {version}", created_by="system"
            )

            # Restore content from version
            post.content = version_obj.content
            post.post_title = version_obj.post_title
            post.post_hook = version_obj.post_hook
            post.post_body = version_obj.post_body
            post.post_tldr = version_obj.post_tldr
            post.post_hashtags = version_obj.post_hashtags

            session.add(post)
            await session.commit()
            await session.refresh(post)

            logger.info(f"Restored post {post_id} to version {version}")
            return post

    async def diff_versions(self, post_id: int, v1: int, v2: int) -> dict:
        """
        Compare two versions.

        Args:
            post_id: Post ID
            v1: First version number
            v2: Second version number

        Returns:
            dict: Diff information
        """
        version1 = await self.get_version(post_id, v1)
        version2 = await self.get_version(post_id, v2)

        if not version1 or not version2:
            return {"error": "One or both versions not found"}

        return {
            "post_id": post_id,
            "version_1": v1,
            "version_2": v2,
            "content_changed": version1.content != version2.content,
            "title_changed": version1.post_title != version2.post_title,
            "v1_created_at": version1.created_at.isoformat()
            if version1.created_at
            else None,
            "v2_created_at": version2.created_at.isoformat()
            if version2.created_at
            else None,
            "v1_reason": version1.change_reason,
            "v2_reason": version2.change_reason,
        }

    async def get_latest_version(self, post_id: int) -> PostVersion | None:
        """Get the latest version of a post."""
        async with get_database().session() as session:
            result = await session.execute(
                select(PostVersion)
                .where(PostVersion.post_id == post_id)
                .order_by(desc(PostVersion.version_number))
                .limit(1)
            )
            return result.scalar_one_or_none()
