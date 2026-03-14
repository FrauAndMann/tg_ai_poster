"""
Post formatter base interface.

Defines the contract for formatter implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FormattedPost:
    """Result of post formatting."""

    text: str
    character_count: int
    is_valid: bool
    validation_errors: list[str] = field(default_factory=list)
    missing_blocks: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    media_prompt: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "character_count": self.character_count,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "missing_blocks": self.missing_blocks,
            "hashtags": self.hashtags,
            "media_prompt": self.media_prompt,
        }


class PostFormatter(ABC):
    """Abstract base class for post formatters."""

    @abstractmethod
    def format(self, post: Any) -> FormattedPost:
        """
        Format a post for publishing.

        Args:
            post: Post object or dict with post data

        Returns:
            FormattedPost ready for publishing
        """
        pass

    @abstractmethod
    def validate(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Validate formatted text.

        Args:
            text: Formatted text to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
