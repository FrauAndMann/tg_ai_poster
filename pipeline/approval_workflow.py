"""
Approval Workflow Module.

Handles post status transitions and automated approval based on quality metrics.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from core.logger import get_logger
from memory.models import Post, PostStatus
from memory.database import get_session

logger = get_logger(__name__)


# Valid state transitions
TRANSITIONS: dict[PostStatus, list[PostStatus]] = {
    PostStatus.DRAFT: [PostStatus.PENDING_REVIEW],
    PostStatus.PENDING_REVIEW: [
        PostStatus.APPROVED,
        PostStatus.NEEDS_REVISION,
        PostStatus.REJECTED
    ],
    PostStatus.NEEDS_REVISION: [PostStatus.PENDING_REVIEW],
    PostStatus.APPROVED: [PostStatus.SCHEDULED],
    PostStatus.SCHEDULED: [PostStatus.PUBLISHED, PostStatus.FAILED],
    PostStatus.REJECTED: [],  # Terminal
    PostStatus.PUBLISHED: [],  # Terminal
    PostStatus.FAILED: [PostStatus.SCHEDULED],  # Retry
}


class ApprovalWorkflow:
    """Automated approval based on quality metrics."""

    def __init__(
        self,
        min_quality_score: float = 0.75,
        min_verification_score: float = 0.70,
        min_editor_score: float = 0.70,
    ):
        """
        Initialize workflow.

        Args:
            min_quality_score: Minimum quality score for auto-approval
            min_verification_score: Minimum verification score
            min_editor_score: Minimum editor score
        """
        self.min_quality_score = min_quality_score
        self.min_verification_score = min_verification_score
        self.min_editor_score = min_editor_score

    def can_transition(self, current: PostStatus, target: PostStatus) -> bool:
        """
        Check if transition is valid.

        Args:
            current: Current status
            target: Target status

        Returns:
            bool: True if transition is valid
        """
        valid_targets = TRANSITIONS.get(current, [])
        return target in valid_targets

    async def auto_approve(self, post: Post) -> bool:
        """
        Auto-approve if quality metrics pass.

        Args:
            post: Post to evaluate

        Returns:
            bool: True if auto-approved
        """
        # Check all quality thresholds
        quality_passed = post.quality_score >= self.min_quality_score
        verification_passed = post.verification_score >= self.min_verification_score
        editor_passed = post.editor_score >= self.min_editor_score
        no_manual_review = not post.needs_review

        approved = (
            quality_passed
            and verification_passed
            and editor_passed
            and no_manual_review
        )

        if approved:
            logger.info(
                f"Post {post.id} auto-approved: "
                f"quality={post.quality_score:.2f}, "
                f"verification={post.verification_score:.2f}, "
                f"editor={post.editor_score:.2f}"
            )
        else:
            logger.debug(
                f"Post {post.id} not auto-approved: "
                f"quality={quality_passed}, "
                f"verification={verification_passed}, "
                f"editor={editor_passed}, "
                f"no_review={no_manual_review}"
            )

        return approved

    async def process_post(self, post: Post) -> PostStatus:
        """
        Determine next status based on post metrics.

        Args:
            post: Post to process

        Returns:
            PostStatus: Recommended next status
        """
        try:
            current_status = PostStatus(post.status)
        except ValueError:
            # Unknown status, return as-is
            logger.warning(f"Unknown status '{post.status}' for post {post.id}")
            return PostStatus.DRAFT

        if current_status == PostStatus.DRAFT:
            return PostStatus.PENDING_REVIEW

        if current_status == PostStatus.PENDING_REVIEW:
            if await self.auto_approve(post):
                return PostStatus.APPROVED
            elif post.needs_review:
                return PostStatus.NEEDS_REVISION
            else:
                return PostStatus.NEEDS_REVISION

        if current_status == PostStatus.NEEDS_REVISION:
            return PostStatus.PENDING_REVIEW

        return current_status

    async def transition_status(
        self,
        post: Post,
        target_status: PostStatus,
        reason: str | None = None
    ) -> bool:
        """
        Transition post to new status.

        Args:
            post: Post to update
            target_status: Target status
            reason: Optional reason for transition

        Returns:
            bool: True if transition successful
        """
        try:
            current_status = PostStatus(post.status)
        except ValueError:
            logger.warning(f"Unknown status '{post.status}' for post {post.id}")
            return False

        if not self.can_transition(current_status, target_status):
            logger.warning(
                f"Invalid transition: {current_status} -> {target_status} "
                f"for post {post.id}"
            )
            return False

        async with get_session() as session:
            # Get fresh post from DB
            result = await session.execute(
                select(Post).where(Post.id == post.id)
            )
            db_post = result.scalar_one_or_none()
            if not db_post:
                return False

            db_post.status = target_status.value
            session.add(db_post)
            await session.commit()

            # Update local object
            post.status = target_status.value

            logger.info(
                f"Post {post.id} status changed: {current_status} -> {target_status}"
                f"{f' ({reason})' if reason else ''}"
            )
            return True

    async def batch_process(self, posts: list[Post]) -> dict[str, int]:
        """
        Process multiple posts and return status counts.

        Args:
            posts: Posts to process

        Returns:
            dict: Status -> count mapping
        """
        results: dict[str, int] = {}

        for post in posts:
            recommended = await self.process_post(post)
            status_key = recommended.value
            results[status_key] = results.get(status_key, 0) + 1

            # Auto-transition if valid
            try:
                current = PostStatus(post.status)
                if self.can_transition(current, recommended):
                    await self.transition_status(post, recommended, "batch_process")
            except ValueError:
                pass

        return results

    def get_valid_transitions(self, current: PostStatus) -> list[PostStatus]:
        """Get list of valid transitions from current status."""
        return TRANSITIONS.get(current, [])

    async def get_posts_by_status(
        self,
        status: PostStatus,
        limit: int = 100
    ) -> list[Post]:
        """
        Get all posts with a specific status.

        Args:
            status: Status to filter by
            limit: Maximum posts to return

        Returns:
            list[Post]: Posts with the specified status
        """
        async with get_session() as session:
            result = await session.execute(
                select(Post)
                .where(Post.status == status.value)
                .order_by(Post.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
