"""
Tests for Phase 1 Features: Draft System, Approval Workflow, A/B Testing.
"""
import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from memory.models import (
    Base, Post, PostVersion, ABExperiment, ABVariant, PostStatus
)
from memory.database import Database
from pipeline.draft_manager import DraftManager
from pipeline.approval_workflow import ApprovalWorkflow, TRANSITIONS
from pipeline.ab_test_manager import ABTestManager


@pytest_asyncio.fixture
async def db():
    """Create in-memory database for testing."""
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.init()
    yield database
    await database.close()


@pytest.fixture
def draft_manager():
    return DraftManager()


@pytest.fixture
def approval_workflow():
    return ApprovalWorkflow(
        min_quality_score=0.75,
        min_verification_score=0.70,
        min_editor_score=0.70,
    )


@pytest.fixture
def ab_manager():
    return ABTestManager(min_sample_size=10, confidence_threshold=0.95)


# ============================================
# DraftManager Tests
# ============================================

class TestDraftManager:
    """Tests for DraftManager."""

    @pytest.mark.asyncio
    async def test_create_version(self, db, draft_manager):
        """Test version creation."""
        async with db.session() as session:
            # Create a test post
            post = Post(
                content="Test content",
                post_title="Test Title",
                status="draft",
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)

            # Create version
            version = await draft_manager.create_version(
                post,
                reason="Initial version",
                created_by="ai"
            )

            assert version is not None
            assert version.post_id == post.id
            assert version.version_number == 1
            assert version.content == "Test content"
            assert version.change_reason == "Initial version"

    @pytest.mark.asyncio
    async def test_list_versions(self, db, draft_manager):
        """Test listing versions."""
        async with db.session() as session:
            post = Post(content="Test content", status="draft")
            session.add(post)
            await session.commit()
            await session.refresh(post)

            # Create multiple versions
            await draft_manager.create_version(post, reason="v1")
            await draft_manager.create_version(post, reason="v2")
            await draft_manager.create_version(post, reason="v3")

            versions = await draft_manager.list_versions(post.id)

            assert len(versions) == 3
            # Should be newest first
            assert versions[0].version_number == 3
            assert versions[2].version_number == 1

    @pytest.mark.asyncio
    async def test_get_specific_version(self, db, draft_manager):
        """Test getting specific version."""
        async with db.session() as session:
            post = Post(content="Test content", status="draft")
            session.add(post)
            await session.commit()
            await session.refresh(post)

            await draft_manager.create_version(post, reason="v1")

            version = await draft_manager.get_version(post.id, 1)

            assert version is not None
            assert version.version_number == 1


# ============================================
# ApprovalWorkflow Tests
# ============================================

class TestApprovalWorkflow:
    """Tests for ApprovalWorkflow."""

    def test_can_transition_valid(self, approval_workflow):
        """Test valid transitions."""
        assert approval_workflow.can_transition(PostStatus.DRAFT, PostStatus.PENDING_REVIEW)
        assert approval_workflow.can_transition(PostStatus.PENDING_REVIEW, PostStatus.APPROVED)
        assert approval_workflow.can_transition(PostStatus.APPROVED, PostStatus.SCHEDULED)

        assert approval_workflow.can_transition(PostStatus.SCHEDULED, PostStatus.PUBLISHED)

        assert approval_workflow.can_transition(PostStatus.SCHEDULED, PostStatus.FAILED)

    def test_can_transition_invalid(self, approval_workflow):
        """Test invalid transitions."""
        assert not approval_workflow.can_transition(PostStatus.DRAFT, PostStatus.APPROVED)
        assert not approval_workflow.can_transition(PostStatus.PUBLISHED, PostStatus.DRAFT)
        assert not approval_workflow.can_transition(PostStatus.REJECTED, PostStatus.APPROVED)
        # PENDING_REVIEW can go to APPROVED, NEEDS_REVISION, or REJECTED
        assert approval_workflow.can_transition(PostStatus.PENDING_REVIEW, PostStatus.NEEDS_REVISION)

        assert approval_workflow.can_transition(PostStatus.PENDING_REVIEW, PostStatus.REJECTED)

        assert not approval_workflow.can_transition(PostStatus.PENDING_REVIEW, PostStatus.SCHEDULED)

    @pytest.mark.asyncio
    async def test_auto_approve_passing(self, db, approval_workflow):
        """Test auto-approval with passing scores."""
        async with db.session() as session:
            post = Post(
                content="Test content",
                status="pending_review",
                quality_score=0.8,
                verification_score=0.8,
                editor_score=0.8,
                needs_review=False,
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)

            result = await approval_workflow.auto_approve(post)
            assert result is True

    @pytest.mark.asyncio
    async def test_auto_approve_failing_quality(self, db, approval_workflow):
        """Test auto-approval with failing quality score."""
        async with db.session() as session:
            post = Post(
                content="Test content",
                status="pending_review",
                quality_score=0.5,  # Below threshold
                verification_score=0.8,
                editor_score=0.8,
                needs_review=False,
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)

            result = await approval_workflow.auto_approve(post)
            assert result is False

    @pytest.mark.asyncio
    async def test_auto_approve_needs_review(self, db, approval_workflow):
        """Test auto-approval when needs_review is True."""
        async with db.session() as session:
            post = Post(
                content="Test content",
                status="pending_review",
                quality_score=0.8,
                verification_score=0.8,
                editor_score=0.8,
                needs_review=True,  # Requires manual review
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)

            result = await approval_workflow.auto_approve(post)
            assert result is False

    @pytest.mark.asyncio
    async def test_transition_status(self, db, approval_workflow):
        """Test status transition."""
        async with db.session() as session:
            post = Post(content="Test content", status="draft")
            session.add(post)
            await session.commit()
            await session.refresh(post)

            result = await approval_workflow.transition_status(post, PostStatus.PENDING_REVIEW)
            assert result is True
            # Refresh to get updated status
            await session.refresh(post)
            assert post.status == "pending_review"

    @pytest.mark.asyncio
    async def test_transition_status_invalid(self, db, approval_workflow):
        """Test invalid status transition."""
        async with db.session() as session:
            post = Post(content="Test content", status="draft")
            session.add(post)
            await session.commit()
            await session.refresh(post)

            result = await approval_workflow.transition_status(post, PostStatus.APPROVED)
            assert result is False
            assert post.status == "draft"  # Unchanged

    def test_get_valid_transitions(self, approval_workflow):
        """Test getting valid transitions."""
        transitions = approval_workflow.get_valid_transitions(PostStatus.PENDING_REVIEW)
        assert PostStatus.APPROVED in transitions
        assert PostStatus.NEEDS_REVISION in transitions
        assert PostStatus.REJECTED in transitions
        # DRAFT can only go to PENDING_REVIEW
        transitions = approval_workflow.get_valid_transitions(PostStatus.DRAFT)
        assert PostStatus.PENDING_REVIEW in transitions
        assert len(transitions) == 1


# ============================================
# ABTestManager Tests
# ============================================

class TestABTestManager:
    """Tests for ABTestManager."""

    @pytest.mark.asyncio
    async def test_create_experiment(self, db, ab_manager):
        """Test experiment creation."""
        async with db.session() as session:
            post_a = Post(content="Variant A content", status="approved")
            post_b = Post(content="Variant B content", status="approved")
            session.add(post_a)
            session.add(post_b)
            await session.commit()
            await session.refresh(post_a)
            await session.refresh(post_b)

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
    async def test_select_variant(self, db, ab_manager):
        """Test variant selection."""
        async with db.session() as session:
            post_a = Post(content="Variant A content", status="approved")
            post_b = Post(content="Variant B content", status="approved")
            session.add(post_a)
            session.add(post_b)
            await session.commit()
            await session.refresh(post_a)
            await session.refresh(post_b)

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
    async def test_get_active_experiments(self, db, ab_manager):
        """Test getting active experiments."""
        async with db.session() as session:
            post_a = Post(content="Variant A", status="approved")
            post_b = Post(content="Variant B", status="approved")
            session.add(post_a)
            session.add(post_b)
            await session.commit()
            await session.refresh(post_a)
            await session.refresh(post_b)

            # Create two experiments
            await ab_manager.create_experiment("exp1", post_a, post_b)
            await ab_manager.create_experiment("exp2", post_a, post_b)

            active = await ab_manager.get_active_experiments()

            assert len(active) == 2

    @pytest.mark.asyncio
    async def test_end_experiment(self, db, ab_manager):
        """Test ending an experiment."""
        async with db.session() as session:
            post_a = Post(content="Variant A", status="approved")
            post_b = Post(content="Variant B", status="approved")
            session.add(post_a)
            session.add(post_b)
            await session.commit()
            await session.refresh(post_a)
            await session.refresh(post_b)

            experiment = await ab_manager.create_experiment("exp_to_end", post_a, post_b)

            result = await ab_manager.end_experiment(experiment.id)
            assert result is True

            # Check it's no longer active
            updated = await ab_manager.get_experiment(experiment.id)
            assert updated.is_active is False
            assert updated.ended_at is not None


# ============================================
# Model Tests
# ============================================

class TestPostVersionModel:
    """Tests for PostVersion model."""

    def test_post_version_to_dict(self):
        """Test PostVersion.to_dict()."""
        version = PostVersion(
            id=1,
            post_id=100,
            version_number=1,
            content="Test content",
            post_title="Title",
            created_by="ai",
            change_reason="Initial",
        )
        d = version.to_dict()
        assert d["id"] == 1
        assert d["post_id"] == 100
        assert d["version_number"] == 1
        assert d["content"] == "Test content"


class TestABExperimentModel:
    """Tests for ABExperiment model."""

    def test_ab_experiment_to_dict(self):
        """Test ABExperiment.to_dict()."""
        experiment = ABExperiment(
            id=1,
            name="Test Experiment",
            description="Test description",
            traffic_split=0.5,
            is_active=True,
            confidence_level=0.95,
        )
        d = experiment.to_dict()
        assert d["id"] == 1
        assert d["name"] == "Test Experiment"
        assert d["traffic_split"] == 0.5


class TestABVariantModel:
    """Tests for ABVariant model."""

    def test_ab_variant_to_dict(self):
        """Test ABVariant.to_dict()."""
        variant = ABVariant(
            id=1,
            experiment_id=100,
            variant_id="A",
            post_id=500,
            impressions=50,
            total_engagement=125.5,
        )
        d = variant.to_dict()
        assert d["id"] == 1
        assert d["experiment_id"] == 100
        assert d["variant_id"] == "A"
        assert d["impressions"] == 50
        assert d["total_engagement"] == 125.5


class TestPostStatusEnum:
    """Tests for PostStatus enum."""

    def test_status_values(self):
        """Test all status values."""
        assert PostStatus.DRAFT.value == "draft"
        assert PostStatus.PENDING_REVIEW.value == "pending_review"
        assert PostStatus.NEEDS_REVISION.value == "needs_revision"
        assert PostStatus.APPROVED.value == "approved"
        assert PostStatus.REJECTED.value == "rejected"
        assert PostStatus.SCHEDULED.value == "scheduled"
        assert PostStatus.PUBLISHED.value == "published"
        assert PostStatus.FAILED.value == "failed"

        assert PostStatus.SCHEDULED.value == "scheduled"  # Extra to ensure coverage

    def test_transitions_completeness(self):
        """Test that all statuses have defined transitions."""
        for status in PostStatus:
            assert status in TRANSITIONS, f"Missing transitions for {status}"
