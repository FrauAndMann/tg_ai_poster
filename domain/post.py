"""
Post domain models.

Defines the Post aggregate root, PostType enum, and related value objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List

from .source import Source
from .media import Media


class PostType(Enum):
    """Types of posts in the pipeline."""

    BREAKING = "breaking"
    DEEP_DIVE = "deep_dive"
    ANALYSIS = "analysis"
    TOOL_ROUNDUP = "tool_roundup"


@dataclass(frozen=True)
class PostTypeConfig:
    """Configuration for each post type."""

    min_length: int
    max_length: int
    temperature: float
    require_sources: bool
    require_media: bool
    emoji_range: tuple[int, int]  # (min, max)


# Default configurations for each post type
POST_TYPE_CONFIGS: dict[PostType, PostTypeConfig] = {
    PostType.BREAKING: PostTypeConfig(
        min_length=800,
        max_length=1500,
        temperature=0.15,
        require_sources=True,
        require_media=True,
        emoji_range=(2, 4),
    ),
    PostType.DEEP_DIVE: PostTypeConfig(
        min_length=2000,
        max_length=3500,
        temperature=0.4,
        require_sources=True,
        require_media=True,
        emoji_range=(1, 3),
    ),
    PostType.ANALYSIS: PostTypeConfig(
        min_length=1500,
        max_length=3000,
        temperature=0.35,
        require_sources=False,
        require_media=False,
        emoji_range=(1, 2),
    ),
    PostType.TOOL_ROUNDUP: PostTypeConfig(
        min_length=1000,
        max_length=2000,
        temperature=0.2,
        require_sources=True,
        require_media=True,
        emoji_range=(3, 5),
    ),
}


@dataclass
class PostContent:
    """Content components of a post."""

    title: str
    body: str
    hook: Optional[str] = None
    tldr: Optional[str] = None
    analysis: Optional[str] = None
    key_facts: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)


@dataclass
class PostMetadata:
    """Metadata for a generated post."""

    created_at: datetime = field(default_factory=datetime.now)
    llm_model: str = ""
    generation_time: float = 0.0
    tokens_used: int = 0


@dataclass
class Post:
    """
    Post aggregate root.

    Represents a complete post with all its components.
    """

    topic: str
    post_type: PostType
    content: PostContent
    sources: list[Source] = field(default_factory=list)
    media: Optional[Media] = None
    metadata: PostMetadata = field(default_factory=PostMetadata)
    id: Optional[int] = None

    def format_sources_block(self) -> str:
        """Generate clickable sources block for Telegram."""
        lines = ["🔗 Источники:"]
        for src in self.sources[:3]:
            lines.append(f"• [{src.name}]({src.url})")
        return "\n".join(lines)

    def validate_length(self) -> tuple[bool, str]:
        """
        Validate post length against type-specific limits.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        config = POST_TYPE_CONFIGS[self.post_type]
        length = len(self.full_text())

        if length < config.min_length:
            return False, f"Too short: {length} < {config.min_length}"
        if length > config.max_length:
            return False, f"Too long: {length} > {config.max_length}"
        return True, "OK"

    def full_text(self) -> str:
        """Get full post text for length calculation."""
        parts = [self.content.title]
        if self.content.hook:
            parts.append(self.content.hook)
        parts.append(self.content.body)
        if self.content.key_facts:
            parts.extend(self.content.key_facts)
        if self.content.analysis:
            parts.append(self.content.analysis)
        if self.content.tldr:
            parts.append(self.content.tldr)
        return "\n".join(parts)

    def get_config(self) -> PostTypeConfig:
        """Get configuration for this post's type."""
        return POST_TYPE_CONFIGS[self.post_type]
