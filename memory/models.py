"""
SQLAlchemy database models.

Defines the schema for posts, topics, and sources.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


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

    def __repr__(self) -> str:
        return f"<PostVersion(id={self.id}, post_id={self.post_id}, v{self.version_number})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "post_id": self.post_id,
            "version_number": self.version_number,
            "content": self.content,
            "post_title": self.post_title,
            "post_hook": self.post_hook,
            "post_body": self.post_body,
            "post_tldr": self.post_tldr,
            "post_hashtags": self.post_hashtags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
            "change_reason": self.change_reason,
        }


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

    def __repr__(self) -> str:
        return f"<ABExperiment(id={self.id}, name='{self.name}', active={self.is_active})>"

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
    post: Mapped[Optional["Post"]] = relationship()

    __table_args__ = (
        Index("ix_ab_variants_experiment", "experiment_id"),
        UniqueConstraint("experiment_id", "variant_id", name="uq_experiment_variant"),
    )

    def __repr__(self) -> str:
        return f"<ABVariant(id={self.id}, experiment={self.experiment_id}, variant={self.variant_id})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "variant_id": self.variant_id,
            "post_id": self.post_id,
            "impressions": self.impressions,
            "total_engagement": self.total_engagement,
        }


class Post(Base):
    """
    Model for storing published posts and their metadata.

    Tracks post content, engagement metrics, and generation details.
    """

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Metadata
    published_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        nullable=False,
    )  # draft, published, failed, pending

    # Content metrics
    character_count: Mapped[int] = mapped_column(Integer, default=0)
    has_emoji: Mapped[bool] = mapped_column(Boolean, default=False)
    emoji_count: Mapped[int] = mapped_column(Integer, default=0)
    hashtag_count: Mapped[int] = mapped_column(Integer, default=0)

    # Engagement metrics (updated after publishing)
    views: Mapped[int] = mapped_column(Integer, default=0)
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Generation info
    llm_model: Mapped[str] = mapped_column(String(100), nullable=True)
    generation_attempts: Mapped[int] = mapped_column(Integer, default=1)
    telegram_message_id: Mapped[int] = mapped_column(Integer, nullable=True)

    # New fields for v2.0 pipeline
    post_type: Mapped[str] = mapped_column(
        String(50),
        default="breaking",
        nullable=True,
    )  # breaking, deep_dive, tool_roundup, analysis

    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    editor_score: Mapped[float] = mapped_column(Float, default=0.0)
    verification_score: Mapped[float] = mapped_column(Float, default=0.0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    # Structured post data (JSON)
    post_title: Mapped[str] = mapped_column(String(200), nullable=True)
    post_hook: Mapped[str] = mapped_column(Text, nullable=True)
    post_body: Mapped[str] = mapped_column(Text, nullable=True)
    post_tldr: Mapped[str] = mapped_column(String(300), nullable=True)
    post_analysis: Mapped[str] = mapped_column(Text, nullable=True)
    post_key_facts: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array
    post_sources: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array
    post_hashtags: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array
    media_prompt: Mapped[str] = mapped_column(Text, nullable=True)

    # Source tracking
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    source_tiers: Mapped[str] = mapped_column(String(100), nullable=True)  # JSON array of tiers

    # Media fields
    media_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    media_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # unsplash, pexels, generated
    media_photographer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Pipeline version tracking
    pipeline_version: Mapped[str] = mapped_column(String(50), default="1.0")

    # Version control fields
    version: Mapped[int] = mapped_column(Integer, default=1)
    current_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("post_versions.id"), nullable=True)

    # A/B testing fields
    ab_experiment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ab_experiments.id"), nullable=True)
    ab_variant_id: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Relationships
    versions: Mapped[list["PostVersion"]] = relationship(
        back_populates="post", order_by="PostVersion.version_number"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_posts_published_at", published_at),
        Index("ix_posts_status", status),
        Index("ix_posts_engagement_score", engagement_score),
    )

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, status='{self.status}', published_at={self.published_at})>"

    def to_dict(self) -> dict:
        """Convert post to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "topic": self.topic,
            "source": self.source,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "status": self.status,
            "character_count": self.character_count,
            "has_emoji": self.has_emoji,
            "emoji_count": self.emoji_count,
            "hashtag_count": self.hashtag_count,
            "views": self.views,
            "reactions": self.reactions,
            "shares": self.shares,
            "comments": self.comments,
            "engagement_score": self.engagement_score,
            "llm_model": self.llm_model,
            "generation_attempts": self.generation_attempts,
            "telegram_message_id": self.telegram_message_id,
            # New v2.0 fields
            "post_type": self.post_type,
            "confidence_score": self.confidence_score,
            "quality_score": self.quality_score,
            "editor_score": self.editor_score,
            "verification_score": self.verification_score,
            "needs_review": self.needs_review,
            "post_title": self.post_title,
            "post_hook": self.post_hook,
            "post_body": self.post_body,
            "post_tldr": self.post_tldr,
            "post_analysis": self.post_analysis,
            "post_key_facts": self.post_key_facts,
            "post_sources": self.post_sources,
            "post_hashtags": self.post_hashtags,
            "media_prompt": self.media_prompt,
            "source_count": self.source_count,
            "source_tiers": self.source_tiers,
            "media_url": self.media_url,
            "media_source": self.media_source,
            "media_photographer": self.media_photographer,
            "pipeline_version": self.pipeline_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # Version control fields
            "version": self.version,
            "current_version_id": self.current_version_id,
            # A/B testing fields
            "ab_experiment_id": self.ab_experiment_id,
            "ab_variant_id": self.ab_variant_id,
        }


class Topic(Base):
    """
    Model for tracking topics and their embeddings.

    Used for deduplication and style consistency.
    """

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Topic info
    name: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Usage tracking
    last_used: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)

    # Embedding for similarity comparison (stored as JSON string)
    embedding_vector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Quality metrics
    avg_engagement: Mapped[float] = mapped_column(Float, default=0.0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # Source info
    source_type: Mapped[str] = mapped_column(
        String(50),
        default="manual",
    )  # manual, rss, api, generated
    source_url: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Indexes
    __table_args__ = (
        Index("ix_topics_name", name),
        Index("ix_topics_last_used", last_used),
        Index("ix_topics_use_count", use_count),
    )

    def __repr__(self) -> str:
        return f"<Topic(id={self.id}, name='{self.name[:50]}...', use_count={self.use_count})>"

    def to_dict(self) -> dict:
        """Convert topic to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "use_count": self.use_count,
            "avg_engagement": self.avg_engagement,
            "success_rate": self.success_rate,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Source(Base):
    """
    Model for tracking content sources (RSS feeds, APIs).

    Monitors fetch history and item counts.
    """

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source info
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=True)
    type: Mapped[str] = mapped_column(
        String(50),
        default="rss",
    )  # rss, api, manual

    # Fetch tracking
    last_fetched: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    fetch_count: Mapped[int] = mapped_column(Integer, default=0)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    new_items_count: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Indexes
    __table_args__ = (
        Index("ix_sources_url", url),
        Index("ix_sources_type", type),
        Index("ix_sources_is_active", is_active),
    )

    def __repr__(self) -> str:
        return f"<Source(id={self.id}, url='{self.url[:50]}...', type='{self.type}')>"

    def to_dict(self) -> dict:
        """Convert source to dictionary."""
        return {
            "id": self.id,
            "url": self.url,
            "name": self.name,
            "type": self.type,
            "last_fetched": self.last_fetched.isoformat() if self.last_fetched else None,
            "fetch_count": self.fetch_count,
            "item_count": self.item_count,
            "new_items_count": self.new_items_count,
            "is_active": self.is_active,
            "last_error": self.last_error,
            "consecutive_errors": self.consecutive_errors,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class StyleProfile(Base):
    """
    Model for storing channel style profile.

    Contains learned style characteristics for consistent content generation.
    """

    __tablename__ = "style_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Style characteristics
    avg_sentence_length: Mapped[float] = mapped_column(Float, default=0.0)
    avg_paragraph_count: Mapped[float] = mapped_column(Float, default=0.0)
    common_phrases: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string
    vocabulary_richness: Mapped[float] = mapped_column(Float, default=0.0)
    emoji_patterns: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string
    hashtag_patterns: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string

    # Tone analysis
    formality_score: Mapped[float] = mapped_column(Float, default=0.5)
    enthusiasm_score: Mapped[float] = mapped_column(Float, default=0.5)
    technicality_score: Mapped[float] = mapped_column(Float, default=0.5)

    # Training info
    posts_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<StyleProfile(id={self.id}, posts_analyzed={self.posts_analyzed})>"

    def to_dict(self) -> dict:
        """Convert style profile to dictionary."""
        import json

        return {
            "id": self.id,
            "avg_sentence_length": self.avg_sentence_length,
            "avg_paragraph_count": self.avg_paragraph_count,
            "common_phrases": json.loads(self.common_phrases) if self.common_phrases else [],
            "vocabulary_richness": self.vocabulary_richness,
            "emoji_patterns": json.loads(self.emoji_patterns) if self.emoji_patterns else {},
            "hashtag_patterns": json.loads(self.hashtag_patterns) if self.hashtag_patterns else {},
            "formality_score": self.formality_score,
            "enthusiasm_score": self.enthusiasm_score,
            "technicality_score": self.technicality_score,
            "posts_analyzed": self.posts_analyzed,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
