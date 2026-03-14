# Phase 1 Features Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Draft System with versioning, Approval Workflow, and A/B Testing for post formats

**Architecture:** Three integrated systems - PostVersion model for version control, PostStatus enum with state transitions, and ABExperiment/ABVariant models for A/B testing. All integrated through PipelineOrchestrator.

**Tech Stack:** SQLAlchemy async models, Python dataclasses, asyncio, SQLite

---

## Chunk 1: Database Models

### Task 1.1: Add PostStatus Enum and Update Post Model

**Files:**
- Modify: `memory/models.py:1-200`

- [ ] **Step 1: Add PostStatus enum after imports**

```python
class PostStatus(str, Enum):
    """Post status lifecycle."""
    DRAFT = "draft"                    # Initial AI-generated
    PENDING_REVIEW = "pending_review"  # Awaiting quality check
    NEEDS_REVISION = "needs_revision"  # Failed quality check
    APPROVED = "approved"              # Passed all checks
    REJECTED = "rejected"              # Discarded
    SCHEDULED = "scheduled"            # Queued for publishing
    PUBLISHED = "published"            # Live on Telegram
    FAILED = "failed"                  # Publishing failed
```

- [ ] **Step 2: Add PostVersion model before Post class**

```python
class PostVersion(Base):
    """Version history for posts."""
    __tablename__ = "post_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Snapshot of post content at this version
    content: Mapped[str] = mapped_column(Text, nullable=False)
    post_title: Mapped[str | None] = mapped_column(String(200))
    post_hook: Mapped[str | None] = mapped_column(Text)
    post_body: Mapped[str | None] = mapped_column(Text)
    post_tldr: Mapped[str | None] = mapped_column(String(300))
    post_hashtags: Mapped[str | None] = mapped_column(Text)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    created_by: Mapped[str] = mapped_column(String(50), default="ai")
    change_reason: Mapped[str | None] = mapped_column(String(500))

    # Relationship
    post: Mapped["Post"] = relationship("Post", back_populates="versions")

    __table_args__ = (
        Index("ix_post_versions_post_id", "post_id"),
        Index("ix_post_versions_created", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "post_id": self.post_id,
            "version_number": self.version_number,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
            "change_reason": self.change_reason,
        }
```

- [ ] **Step 3: Add ABExperiment model after PostVersion**

```python
class ABExperiment(Base):
    """A/B test experiment configuration."""
    __tablename__ = "ab_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Configuration
    traffic_split: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Results
    winner_variant: Mapped[str | None] = mapped_column(String(10))
    confidence_level: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    variants: Mapped[list["ABVariant"]] = relationship(back_populates="experiment")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "traffic_split": self.traffic_split,
            "is_active": self.is_active,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "winner_variant": self.winner_variant,
            "confidence_level": self.confidence_level,
        }
```

- [ ] **Step 4: Add ABVariant model after ABExperiment**

```python
class ABVariant(Base):
    """Individual variant in an experiment."""
    __tablename__ = "ab_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(Integer, ForeignKey("ab_experiments.id"))
    variant_id: Mapped[str] = mapped_column(String(10), nullable=False)

    # Content reference
    post_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("posts.id"))

    # Metrics
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    total_engagement: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    experiment: Mapped["ABExperiment"] = relationship(back_populates="variants")
    post: Mapped["Post | None"] = relationship()

    __table_args__ = (
        Index("ix_ab_variants_experiment", "experiment_id"),
        UniqueConstraint("experiment_id", "variant_id", name="uq_experiment_variant"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "variant_id": self.variant_id,
            "post_id": self.post_id,
            "impressions": self.impressions,
            "total_engagement": self.total_engagement,
        }
```

- [ ] **Step 5: Add new fields to Post model (after pipeline_version field)**

```python
    # Version control fields
    version: Mapped[int] = mapped_column(Integer, default=1)
    current_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("post_versions.id"))

    # A/B testing fields
    ab_experiment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ab_experiments.id"))
    ab_variant_id: Mapped[str | None] = mapped_column(String(10))

    # Relationships
    versions: Mapped[list["PostVersion"]] = relationship(back_populates="post", order_by="PostVersion.version_number")
```

- [ ] **Step 6: Update Post.to_dict() method to include new fields**

Add to the return dict:
```python
            "version": self.version,
            "current_version_id": self.current_version_id,
            "ab_experiment_id": self.ab_experiment_id,
            "ab_variant_id": self.ab_variant_id,
```

---

## Chunk 2: Draft Manager

### Task 2.1: Create DraftManager Class

**Files:**
- Create: `pipeline/draft_manager.py`
- Test: `tests/test_draft_manager.py`

- [ ] **Step 1: Create draft_manager.py with DraftManager class**

```python
"""
Draft and Version Management Module.

Manages post versions, draft operations, and version history.
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import get_logger
from memory.models import Post, PostVersion
from memory.database import get_session

logger = get_logger(__name__)


class DraftManager:
    """Manages post versions and draft operations."""

    def __init__(self):
        pass

    async def create_version(
        self,
        post: Post,
        reason: str | None = None,
        created_by: str = "ai"
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
        async with get_session() as session:
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

            # Update post version
            post.version = version_number
            post.current_version_id = version.id
            session.add(post)

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
        async with get_session() as session:
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
        async with get_session() as session:
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
        async with get_session() as session:
            # Get the version to restore
            version_obj = await self.get_version(post_id, version)
            if not version_obj:
                logger.warning(f"Version {version} not found for post {post_id}")
                return None

            # Get the post
            result = await session.execute(
                select(Post).where(Post.id == post_id)
            )
            post = result.scalar_one_or_none()
            if not post:
                return None

            # Create a version snapshot of current state before restore
            await self.create_version(
                post,
                reason=f"Before restore to version {version}",
                created_by="system"
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
            "v1_created_at": version1.created_at.isoformat() if version1.created_at else None,
            "v2_created_at": version2.created_at.isoformat() if version2.created_at else None,
            "v1_reason": version1.change_reason,
            "v2_reason": version2.change_reason,
        }

    async def get_latest_version(self, post_id: int) -> PostVersion | None:
        """Get the latest version of a post."""
        async with get_session() as session:
            result = await session.execute(
                select(PostVersion)
                .where(PostVersion.post_id == post_id)
                .order_by(desc(PostVersion.version_number))
                .limit(1)
            )
            return result.scalar_one_or_none()
```

- [ ] **Step 2: Write tests for DraftManager**

```python
# tests/test_draft_manager.py
"""Tests for DraftManager."""
import pytest
from datetime import datetime

from pipeline.draft_manager import DraftManager
from memory.models import Post, PostVersion
from memory.database import init_db, get_session


@pytest.fixture
async def setup_db():
    """Setup test database."""
    await init_db()
    yield
    # Cleanup handled by in-memory DB


@pytest.fixture
def draft_manager():
    return DraftManager()


@pytest.fixture
async def test_post():
    """Create a test post."""
    async with get_session() as session:
        post = Post(
            content="Test content",
            post_title="Test Title",
            status="draft",
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post


@pytest.mark.asyncio
async def test_create_version(setup_db, draft_manager, test_post):
    """Test version creation."""
    version = await draft_manager.create_version(
        test_post,
        reason="Initial version",
        created_by="ai"
    )

    assert version is not None
    assert version.post_id == test_post.id
    assert version.version_number == 1
    assert version.content == "Test content"
    assert version.change_reason == "Initial version"


@pytest.mark.asyncio
async def test_list_versions(setup_db, draft_manager, test_post):
    """Test listing versions."""
    # Create multiple versions
    await draft_manager.create_version(test_post, reason="v1")
    await draft_manager.create_version(test_post, reason="v2")
    await draft_manager.create_version(test_post, reason="v3")

    versions = await draft_manager.list_versions(test_post.id)

    assert len(versions) == 3
    # Should be newest first
    assert versions[0].version_number == 3
    assert versions[2].version_number == 1


@pytest.mark.asyncio
async def test_get_specific_version(setup_db, draft_manager, test_post):
    """Test getting specific version."""
    await draft_manager.create_version(test_post, reason="v1")

    version = await draft_manager.get_version(test_post.id, 1)

    assert version is not None
    assert version.version_number == 1


@pytest.mark.asyncio
async def test_restore_version(setup_db, draft_manager, test_post):
    """Test restoring to previous version."""
    # Create initial version
    await draft_manager.create_version(test_post, reason="v1")

    # Modify post and create new version
    async with get_session() as session:
        test_post.content = "Modified content"
        session.add(test_post)
        await session.commit()

    await draft_manager.create_version(test_post, reason="v2")

    # Restore to v1
    restored = await draft_manager.restore_version(test_post.id, 1)

    assert restored is not None
    assert restored.content == "Test content"
```

---

## Chunk 3: Approval Workflow

### Task 3.1: Create ApprovalWorkflow Class

**Files:**
- Create: `pipeline/approval_workflow.py`
- Test: `tests/test_approval_workflow.py`

- [ ] **Step 1: Create approval_workflow.py**

```python
"""
Approval Workflow Module.

Handles post status transitions and automated approval based on quality metrics.
"""
from __future__ import annotations

from typing import Optional
from enum import Enum

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
        current_status = PostStatus(post.status)

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
        current_status = PostStatus(post.status)

        if not self.can_transition(current_status, target_status):
            logger.warning(
                f"Invalid transition: {current_status} -> {target_status} "
                f"for post {post.id}"
            )
            return False

        async with get_session() as session:
            post.status = target_status.value
            session.add(post)
            await session.commit()

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
            current = PostStatus(post.status)
            if self.can_transition(current, recommended):
                await self.transition_status(post, recommended, "batch_process")

        return results

    def get_valid_transitions(self, current: PostStatus) -> list[PostStatus]:
        """Get list of valid transitions from current status."""
        return TRANSITIONS.get(current, [])
```

- [ ] **Step 2: Write tests for ApprovalWorkflow**

```python
# tests/test_approval_workflow.py
"""Tests for ApprovalWorkflow."""
import pytest

from pipeline.approval_workflow import ApprovalWorkflow, TRANSITIONS, PostStatus
from memory.models import Post
from memory.database import init_db, get_session


@pytest.fixture
async def setup_db():
    """Setup test database."""
    await init_db()
    yield


@pytest.fixture
def workflow():
    return ApprovalWorkflow(
        min_quality_score=0.75,
        min_verification_score=0.70,
        min_editor_score=0.70,
    )


@pytest.fixture
async def test_post():
    """Create a test post."""
    async with get_session() as session:
        post = Post(
            content="Test content",
            status="draft",
            quality_score=0.8,
            verification_score=0.8,
            editor_score=0.8,
            needs_review=False,
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post


def test_can_transition_valid(workflow):
    """Test valid transitions."""
    assert workflow.can_transition(PostStatus.DRAFT, PostStatus.PENDING_REVIEW)
    assert workflow.can_transition(PostStatus.PENDING_REVIEW, PostStatus.APPROVED)
    assert workflow.can_transition(PostStatus.APPROVED, PostStatus.SCHEDULED)


def test_can_transition_invalid(workflow):
    """Test invalid transitions."""
    assert not workflow.can_transition(PostStatus.DRAFT, PostStatus.APPROVED)
    assert not workflow.can_transition(PostStatus.PUBLISHED, PostStatus.DRAFT)
    assert not workflow.can_transition(PostStatus.REJECTED, PostStatus.APPROVED)


@pytest.mark.asyncio
async def test_auto_approve_passing(setup_db, workflow, test_post):
    """Test auto-approval with passing scores."""
    result = await workflow.auto_approve(test_post)
    assert result is True


@pytest.mark.asyncio
async def test_auto_approve_failing_quality(setup_db, workflow, test_post):
    """Test auto-approval with failing quality score."""
    test_post.quality_score = 0.5  # Below threshold

    result = await workflow.auto_approve(test_post)
    assert result is False


@pytest.mark.asyncio
async def test_auto_approve_needs_review(setup_db, workflow, test_post):
    """Test auto-approval when needs_review is True."""
    test_post.needs_review = True

    result = await workflow.auto_approve(test_post)
    assert result is False


@pytest.mark.asyncio
async def test_process_post_draft(setup_db, workflow, test_post):
    """Test processing draft post."""
    test_post.status = "draft"
    result = await workflow.process_post(test_post)
    assert result == PostStatus.PENDING_REVIEW


@pytest.mark.asyncio
async def test_transition_status(setup_db, workflow, test_post):
    """Test status transition."""
    test_post.status = "draft"

    result = await workflow.transition_status(test_post, PostStatus.PENDING_REVIEW)
    assert result is True
    assert test_post.status == "pending_review"


@pytest.mark.asyncio
async def test_transition_status_invalid(setup_db, workflow, test_post):
    """Test invalid status transition."""
    test_post.status = "draft"

    result = await workflow.transition_status(test_post, PostStatus.APPROVED)
    assert result is False
    assert test_post.status == "draft"  # Unchanged
```

---

## Chunk 4: A/B Test Manager

### Task 4.1: Create ABTestManager Class

**Files:**
- Create: `pipeline/ab_test_manager.py`
- Test: `tests/test_ab_manager.py`

- [ ] **Step 1: Create ab_test_manager.py**

```python
"""
A/B Testing Module.

Manages experiments for testing different post formats and content variants.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from scipy import stats
import numpy as np

from core.logger import get_logger
from memory.models import Post, ABExperiment, ABVariant
from memory.database import get_session

logger = get_logger(__name__)


class ABTestManager:
    """Manages A/B experiments for post variants."""

    def __init__(
        self,
        min_sample_size: int = 100,
        confidence_threshold: float = 0.95,
    ):
        """
        Initialize A/B test manager.

        Args:
            min_sample_size: Minimum impressions before analysis
            confidence_threshold: Statistical significance threshold
        """
        self.min_sample_size = min_sample_size
        self.confidence_threshold = confidence_threshold

    async def create_experiment(
        self,
        name: str,
        post_a: Post,
        post_b: Post,
        traffic_split: float = 0.5,
        description: str | None = None,
    ) -> ABExperiment:
        """
        Create new A/B experiment with two variants.

        Args:
            name: Experiment name
            post_a: Variant A post
            post_b: Variant B post
            traffic_split: Traffic split for variant A (0.0-1.0)
            description: Optional description

        Returns:
            ABExperiment: Created experiment
        """
        async with get_session() as session:
            experiment = ABExperiment(
                name=name,
                description=description,
                traffic_split=traffic_split,
                is_active=True,
            )
            session.add(experiment)
            await session.flush()

            # Create variant A
            variant_a = ABVariant(
                experiment_id=experiment.id,
                variant_id="A",
                post_id=post_a.id,
            )
            session.add(variant_a)

            # Create variant B
            variant_b = ABVariant(
                experiment_id=experiment.id,
                variant_id="B",
                post_id=post_b.id,
            )
            session.add(variant_b)

            # Update posts with experiment info
            post_a.ab_experiment_id = experiment.id
            post_a.ab_variant_id = "A"
            session.add(post_a)

            post_b.ab_experiment_id = experiment.id
            post_b.ab_variant_id = "B"
            session.add(post_b)

            await session.commit()
            await session.refresh(experiment)

            logger.info(f"Created A/B experiment '{name}' (ID: {experiment.id})")
            return experiment

    async def select_variant(self, experiment: ABExperiment) -> ABVariant:
        """
        Select variant based on traffic split.

        Args:
            experiment: Active experiment

        Returns:
            ABVariant: Selected variant
        """
        async with get_session() as session:
            # Get variants
            result = await session.execute(
                select(ABVariant)
                .where(ABVariant.experiment_id == experiment.id)
                .order_by(ABVariant.variant_id)
            )
            variants = list(result.scalars().all())

            if len(variants) != 2:
                raise ValueError(f"Expected 2 variants, got {len(variants)}")

            # Select based on traffic split
            if random.random() < experiment.traffic_split:
                selected = variants[0]  # Variant A
            else:
                selected = variants[1]  # Variant B

            logger.debug(
                f"Selected variant {selected.variant_id} for experiment {experiment.id}"
            )
            return selected

    async def record_impression(self, variant: ABVariant) -> None:
        """
        Record that variant was shown.

        Args:
            variant: Variant shown
        """
        async with get_session() as session:
            result = await session.execute(
                select(ABVariant).where(ABVariant.id == variant.id)
            )
            db_variant = result.scalar_one()
            db_variant.impressions += 1
            session.add(db_variant)
            await session.commit()

            logger.debug(
                f"Recorded impression for variant {variant.variant_id} "
                f"(total: {db_variant.impressions})"
            )

    async def record_engagement(
        self,
        variant: ABVariant,
        engagement_score: float
    ) -> None:
        """
        Record engagement metric.

        Args:
            variant: Variant that received engagement
            engagement_score: Engagement score
        """
        async with get_session() as session:
            result = await session.execute(
                select(ABVariant).where(ABVariant.id == variant.id)
            )
            db_variant = result.scalar_one()
            db_variant.total_engagement += engagement_score
            session.add(db_variant)
            await session.commit()

            logger.debug(
                f"Recorded engagement {engagement_score:.2f} for variant {variant.variant_id}"
            )

    async def analyze_experiment(self, experiment_id: int) -> dict:
        """
        Analyze results and determine winner if significant.

        Args:
            experiment_id: Experiment to analyze

        Returns:
            dict: Analysis results
        """
        async with get_session() as session:
            # Get experiment
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            experiment = result.scalar_one_or_none()
            if not experiment:
                return {"error": "Experiment not found"}

            # Get variants
            result = await session.execute(
                select(ABVariant)
                .where(ABVariant.experiment_id == experiment_id)
                .order_by(ABVariant.variant_id)
            )
            variants = list(result.scalars().all())

            if len(variants) != 2:
                return {"error": "Expected 2 variants"}

            variant_a, variant_b = variants

            # Check sample size
            if variant_a.impressions < self.min_sample_size or variant_b.impressions < self.min_sample_size:
                return {
                    "status": "insufficient_data",
                    "variant_a_impressions": variant_a.impressions,
                    "variant_b_impressions": variant_b.impressions,
                    "min_required": self.min_sample_size,
                }

            # Calculate average engagement
            avg_a = variant_a.total_engagement / variant_a.impressions if variant_a.impressions > 0 else 0
            avg_b = variant_b.total_engagement / variant_b.impressions if variant_b.impressions > 0 else 0

            # Perform t-test (simplified - in production would use raw data)
            # For simplicity, we'll use a comparison based on averages
            improvement = (avg_b - avg_a) / avg_a if avg_a > 0 else 0

            # Determine if significant (simplified)
            # In production, would store individual measurements for proper t-test
            if abs(improvement) > 0.1:  # 10% improvement threshold
                winner = "B" if avg_b > avg_a else "A"
                confidence = min(0.99, 0.85 + abs(improvement))
            else:
                winner = None
                confidence = 0.5

            result_data = {
                "experiment_id": experiment_id,
                "experiment_name": experiment.name,
                "variant_a": {
                    "impressions": variant_a.impressions,
                    "total_engagement": variant_a.total_engagement,
                    "avg_engagement": avg_a,
                },
                "variant_b": {
                    "impressions": variant_b.impressions,
                    "total_engagement": variant_b.total_engagement,
                    "avg_engagement": avg_b,
                },
                "improvement": f"{improvement:.1%}",
                "winner": winner,
                "confidence": confidence,
                "significant": confidence >= self.confidence_threshold,
            }

            # Update experiment if winner determined
            if winner and confidence >= self.confidence_threshold:
                experiment.winner_variant = winner
                experiment.confidence_level = confidence
                experiment.is_active = False
                experiment.ended_at = datetime.utcnow()
                session.add(experiment)
                await session.commit()

                logger.info(
                    f"Experiment {experiment_id} concluded: winner={winner}, "
                    f"confidence={confidence:.1%}"
                )

            return result_data

    async def get_active_experiments(self) -> list[ABExperiment]:
        """Get all active experiments."""
        async with get_session() as session:
            result = await session.execute(
                select(ABExperiment)
                .where(ABExperiment.is_active == True)
                .order_by(ABExperiment.started_at.desc())
            )
            return list(result.scalars().all())

    async def get_experiment(self, experiment_id: int) -> ABExperiment | None:
        """Get experiment by ID."""
        async with get_session() as session:
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            return result.scalar_one_or_none()

    async def end_experiment(self, experiment_id: int) -> bool:
        """End an active experiment."""
        async with get_session() as session:
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            experiment = result.scalar_one_or_none()
            if not experiment:
                return False

            experiment.is_active = False
            experiment.ended_at = datetime.utcnow()
            session.add(experiment)
            await session.commit()

            logger.info(f"Ended experiment {experiment_id}")
            return True
```

- [ ] **Step 2: Write tests for ABTestManager**

```python
# tests/test_ab_manager.py
"""Tests for ABTestManager."""
import pytest
from datetime import datetime

from pipeline.ab_test_manager import ABTestManager
from memory.models import Post, ABExperiment, ABVariant
from memory.database import init_db, get_session


@pytest.fixture
async def setup_db():
    """Setup test database."""
    await init_db()
    yield


@pytest.fixture
def ab_manager():
    return ABTestManager(min_sample_size=10, confidence_threshold=0.95)


@pytest.fixture
async def test_posts():
    """Create test posts."""
    async with get_session() as session:
        post_a = Post(content="Variant A content", status="approved")
        post_b = Post(content="Variant B content", status="approved")
        session.add(post_a)
        session.add(post_b)
        await session.commit()
        await session.refresh(post_a)
        await session.refresh(post_b)
        return post_a, post_b


@pytest.mark.asyncio
async def test_create_experiment(setup_db, ab_manager, test_posts):
    """Test experiment creation."""
    post_a, post_b = test_posts

    experiment = await ab_manager.create_experiment(
        name="test_experiment",
        post_a=post_a,
        post_b=post_b,
        traffic_split=0.5,
        description="Test description",
    )

    assert experiment is not None
    assert experiment.name == "test_experiment"
    assert experiment.traffic_split == 0.5
    assert experiment.is_active is True


@pytest.mark.asyncio
async def test_select_variant(setup_db, ab_manager, test_posts):
    """Test variant selection."""
    post_a, post_b = test_posts
    experiment = await ab_manager.create_experiment(
        name="test_selection",
        post_a=post_a,
        post_b=post_b,
    )

    # Select multiple times to verify distribution
    selections = {"A": 0, "B": 0}
    for _ in range(100):
        variant = await ab_manager.select_variant(experiment)
        selections[variant.variant_id] += 1

    # Both variants should be selected (roughly 50/50)
    assert selections["A"] > 20
    assert selections["B"] > 20


@pytest.mark.asyncio
async def test_record_impression(setup_db, ab_manager, test_posts):
    """Test impression recording."""
    post_a, post_b = test_posts
    experiment = await ab_manager.create_experiment(
        name="test_impressions",
        post_a=post_a,
        post_b=post_b,
    )

    variant = await ab_manager.select_variant(experiment)
    await ab_manager.record_impression(variant)

    # Get updated variant
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(ABVariant).where(ABVariant.id == variant.id)
        )
        updated = result.scalar_one()
        assert updated.impressions == 1


@pytest.mark.asyncio
async def test_analyze_experiment(setup_db, ab_manager, test_posts):
    """Test experiment analysis."""
    post_a, post_b = test_posts
    experiment = await ab_manager.create_experiment(
        name="test_analysis",
        post_a=post_a,
        post_b=post_b,
    )

    # Record impressions and engagement
    variant = await ab_manager.select_variant(experiment)
    for _ in range(15):
        await ab_manager.record_impression(variant)
        await ab_manager.record_engagement(variant, 5.0)

    # Select other variant and record less engagement
    variant2 = await ab_manager.select_variant(experiment)
    while variant2.id == variant.id:
        variant2 = await ab_manager.select_variant(experiment)

    for _ in range(15):
        await ab_manager.record_impression(variant2)
        await ab_manager.record_engagement(variant2, 2.0)

    analysis = await ab_manager.analyze_experiment(experiment.id)

    assert "experiment_id" in analysis
    assert "variant_a" in analysis
    assert "variant_b" in analysis


@pytest.mark.asyncio
async def test_get_active_experiments(setup_db, ab_manager, test_posts):
    """Test getting active experiments."""
    post_a, post_b = test_posts

    # Create two experiments
    await ab_manager.create_experiment("exp1", post_a, post_b)
    await ab_manager.create_experiment("exp2", post_a, post_b)

    active = await ab_manager.get_active_experiments()

    assert len(active) == 2
```

---

## Chunk 5: Config and Integration

### Task 5.1: Update config.yaml

**Files:**
- Modify: `config.yaml:107-150`

- [ ] **Step 1: Add new feature sections to config.yaml**

Add after line 137 (after polls section):

```yaml
# ===================================
# Phase 1 Features
# ===================================

# Approval Workflow
approval:
  auto_approve_enabled: true
  min_quality_score: 0.75
  min_verification_score: 0.70
  min_editor_score: 0.70
  max_regeneration_attempts: 3

# A/B Testing
ab_testing:
  enabled: true
  default_traffic_split: 0.5
  min_sample_size: 100
  confidence_threshold: 0.95
  auto_select_winner: true

# Draft System
draft:
  max_versions: 50
  auto_cleanup_days: 30
```

### Task 5.2: Run Database Migration

**Files:**
- Modify: `memory/database.py`

- [ ] **Step 1: Ensure models are registered**

The database should automatically create tables for new models when `create_all()` is called. Verify the models are imported in database.py.

- [ ] **Step 2: Test migration**

```bash
# Re-initialize database to create new tables
python main.py --init-db
```

---

## Implementation Order Summary

1. `memory/models.py` — Add PostStatus enum, PostVersion, ABExperiment, ABVariant models + Post fields
2. `pipeline/draft_manager.py` — Version management
3. `pipeline/approval_workflow.py` — Status transitions
4. `pipeline/ab_test_manager.py` — A/B experiment logic
5. `config.yaml` — Add feature flags
6. `tests/` — Unit tests for all components

---

*Plan created: 2025-03-14*
