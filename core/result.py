"""
Pipeline execution result.

Defines the standard result object returned by the pipeline coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PipelineResult:
    """Pipeline execution result."""

    success: bool
    post_id: Optional[int] = None
    content: Optional[str] = None
    topic: Optional[str] = None
    quality_score: float = 0.0
    editor_score: float = 0.0
    verification_score: float = 0.0
    media_url: Optional[str] = None
    sources: list[dict[str, Any]] = field(default_factory=dict)
    duration: float = 0.0
    error: Optional[str] = None
