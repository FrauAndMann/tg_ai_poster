"""
Media value object.

Represents media attached to a post.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Media:
    """
    Media value object.

    Represents an image attached to a post with attribution.
    """

    url: str
    source: str  # "unsplash" | "pexels" | "generated"
    photographer: Optional[str] = None
    prompt: Optional[str] = None  # For AI-generated images
