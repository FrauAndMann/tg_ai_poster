# Phase 1 Features Design

**Date:** 2025-03-14
**Status:** Approved
**Author:** Claude

---

## Overview

Three integrated features for content workflow management:

1. **Draft System** — Version control for posts
2. **Approval Workflow** — Automated status transitions
3. **A/B Testing** — Experiment variants with engagement tracking

---

## Architecture

```
Post Status Flow:
─────────────────────────────────────────────────────────────────

  draft ──► pending_review ──► approved ──► scheduled ──► published
               │                    │
               ▼                    ▼
          needs_revision       rejected

─────────────────────────────────────────────────────────────────
```

---

## 1. Draft System

### 1.1 Database Schema

```python
# memory/models.py - New model

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
    created_by: Mapped[str] = mapped_column(String(50), default="ai")  # ai or user_id
    change_reason: Mapped[str | None] = mapped_column(String(500))

    # Relationship
    post: Mapped["Post"] = relationship("Post", back_populates="versions")

    __table_args__ = (
        Index("ix_post_versions_post_id", "post_id"),
        Index("ix_post_versions_created", "created_at"),
    )
```

### 1.2 DraftManager

```python
# pipeline/draft_manager.py

class DraftManager:
    """Manages post versions and draft operations."""

    def __init__(self, db: Database):
        self.db = db

    async def create_version(
        self,
        post: Post,
        reason: str | None = None,
        created_by: str = "ai"
    ) -> PostVersion:
        """Create new version snapshot."""

    async def get_version(self, post_id: int, version: int) -> PostVersion | None:
        """Get specific version."""

    async def list_versions(self, post_id: int, limit: int = 10) -> list[PostVersion]:
        """List all versions of a post."""

    async def restore_version(self, post_id: int, version: int) -> Post:
        """Restore post to a previous version."""

    async def diff_versions(self, post_id: int, v1: int, v2: int) -> dict:
        """Compare two versions."""
```

---

## 2. Approval Workflow

### 2.1 Status Definitions

```python
# memory/models.py - Update Post.status

class PostStatus(str, Enum):
    DRAFT = "draft"                    # Initial AI-generated
    PENDING_REVIEW = "pending_review"  # Awaiting quality check
    NEEDS_REVISION = "needs_revision"  # Failed quality check
    APPROVED = "approved"              # Passed all checks
    REJECTED = "rejected"              # Discarded
    SCHEDULED = "scheduled"            # Queued for publishing
    PUBLISHED = "published"            # Live on Telegram
    FAILED = "failed"                  # Publishing failed
```

### 2.2 Transition Rules

```python
# pipeline/approval_workflow.py

TRANSITIONS = {
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
    PostStatus.PUBLISHED: [], # Terminal
    PostStatus.FAILED: [PostStatus.SCHEDULED],  # Retry
}

class ApprovalWorkflow:
    """Automated approval based on quality metrics."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def can_transition(self, current: PostStatus, target: PostStatus) -> bool:
        """Check if transition is valid."""

    async def auto_approve(self, post: Post) -> bool:
        """Auto-approve if quality metrics pass."""
        # Check: quality_score >= threshold, no needs_review flag
        return (
            post.quality_score >= self.settings.safety.quality_threshold
            and not post.needs_review
            and post.verification_score >= 0.7
        )

    async def process_post(self, post: Post) -> PostStatus:
        """Determine next status based on post metrics."""
```

### 2.3 Quality Thresholds

```yaml
# config.yaml additions
approval:
  auto_approve_enabled: true
  min_quality_score: 0.75
  min_verification_score: 0.70
  min_editor_score: 0.70
  max_regeneration_attempts: 3
```

---

## 3. A/B Testing

### 3.1 Database Schema

```python
# memory/models.py - New models

class ABExperiment(Base):
    """A/B test experiment configuration."""
    __tablename__ = "ab_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Configuration
    traffic_split: Mapped[float] = mapped_column(Float, default=0.5)  # 50/50
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Results
    winner_variant: Mapped[str | None] = mapped_column(String(10))  # 'A' or 'B'
    confidence_level: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    variants: Mapped[list["ABVariant"]] = relationship(back_populates="experiment")


class ABVariant(Base):
    """Individual variant in an experiment."""
    __tablename__ = "ab_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(Integer, ForeignKey("ab_experiments.id"))
    variant_id: Mapped[str] = mapped_column(String(10), nullable=False)  # 'A' or 'B'

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
```

### 3.2 ABTestManager

```python
# pipeline/ab_test_manager.py

class ABTestManager:
    """Manages A/B experiments for post variants."""

    def __init__(self, db: Database, post_store: PostStore):
        self.db = db
        self.post_store = post_store

    async def create_experiment(
        self,
        name: str,
        post_a: Post,
        post_b: Post,
        traffic_split: float = 0.5
    ) -> ABExperiment:
        """Create new A/B experiment with two variants."""

    async def select_variant(self, experiment: ABExperiment) -> ABVariant:
        """Select variant based on traffic split."""

    async def record_impression(self, variant: ABVariant) -> None:
        """Record that variant was shown."""

    async def record_engagement(
        self,
        variant: ABVariant,
        engagement_score: float
    ) -> None:
        """Record engagement metric."""

    async def analyze_experiment(self, experiment_id: int) -> dict:
        """Analyze results and determine winner if significant."""
        # Use t-test or chi-square for significance

    async def get_active_experiments(self) -> list[ABExperiment]:
        """Get all active experiments."""
```

### 3.3 Integration Points

```python
# In orchestrator.py

class PipelineOrchestrator:
    async def run(self, dry_run: bool = False) -> PipelineResult:
        # ... existing pipeline ...

        # NEW: A/B Testing integration
        if self._should_ab_test():
            experiment = await self.ab_manager.create_experiment(
                name=f"format_test_{datetime.now():%Y%m%d}",
                post_a=post_variant_a,
                post_b=post_variant_b
            )
            variant = await self.ab_manager.select_variant(experiment)
            final_post = variant.post
```

---

## 4. Integration Summary

### 4.1 Updated Post Model

```python
# Add to existing Post model
class Post(Base):
    # ... existing fields ...

    # New fields for features
    version: Mapped[int] = mapped_column(Integer, default=1)
    current_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("post_versions.id"))

    # A/B testing
    ab_experiment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ab_experiments.id"))
    ab_variant_id: Mapped[str | None] = mapped_column(String(10))  # 'A' or 'B'

    # Relationships
    versions: Mapped[list["PostVersion"]] = relationship(back_populates="post")
```

### 4.2 Config Updates

```yaml
# config.yaml - All new sections

approval:
  auto_approve_enabled: true
  min_quality_score: 0.75
  min_verification_score: 0.70
  min_editor_score: 0.70
  max_regeneration_attempts: 3

ab_testing:
  enabled: true
  default_traffic_split: 0.5
  min_sample_size: 100  # Min impressions before analysis
  confidence_threshold: 0.95
  auto_select_winner: true

draft:
  max_versions: 50
  auto_cleanup_days: 30
```

---

## 5. Testing Strategy

### 5.1 Unit Tests

- `tests/test_draft_manager.py` — version CRUD, restore
- `tests/test_approval_workflow.py` — transitions, auto-approve
- `tests/test_ab_manager.py` — variant selection, analysis

### 5.2 Integration Tests

- `tests/test_pipeline_with_features.py` — full flow with all features

---

## 6. Migration

```sql
-- Create post_versions table
CREATE TABLE post_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES posts(id),
    version_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    post_title VARCHAR(200),
    post_hook TEXT,
    post_body TEXT,
    post_tldr VARCHAR(300),
    post_hashtags TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) DEFAULT 'ai',
    change_reason VARCHAR(500)
);

CREATE INDEX ix_post_versions_post_id ON post_versions(post_id);
CREATE INDEX ix_post_versions_created ON post_versions(created_at);

-- Create ab_experiments table
CREATE TABLE ab_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    traffic_split FLOAT DEFAULT 0.5,
    is_active BOOLEAN DEFAULT TRUE,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    winner_variant VARCHAR(10),
    confidence_level FLOAT DEFAULT 0.0
);

-- Create ab_variants table
CREATE TABLE ab_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL REFERENCES ab_experiments(id),
    variant_id VARCHAR(10) NOT NULL,
    post_id INTEGER REFERENCES posts(id),
    impressions INTEGER DEFAULT 0,
    total_engagement FLOAT DEFAULT 0.0,
    UNIQUE(experiment_id, variant_id)
);

CREATE INDEX ix_ab_variants_experiment ON ab_variants(experiment_id);

-- Add new columns to posts table
ALTER TABLE posts ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE posts ADD COLUMN current_version_id INTEGER REFERENCES post_versions(id);
ALTER TABLE posts ADD COLUMN ab_experiment_id INTEGER REFERENCES ab_experiments(id);
ALTER TABLE posts ADD COLUMN ab_variant_id VARCHAR(10);
```

---

## 7. Implementation Order

1. `memory/models.py` — Add PostVersion, ABExperiment, ABVariant models + Post fields
2. `pipeline/draft_manager.py` — Version management
3. `pipeline/approval_workflow.py` — Status transitions
4. `pipeline/ab_test_manager.py` — A/B experiment logic
5. `memory/database.py` — Run migrations
6. `pipeline/orchestrator.py` — Integrate all components
7. `config.yaml` — Add feature flags
8. `tests/` — Unit + integration tests

---

*Design approved by user: 2025-03-14*
