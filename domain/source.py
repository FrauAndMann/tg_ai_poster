"""
Source value object.

Represents a content source with credibility information.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """
    Source value object.

    Represents a content source with its credibility score.
    """

    name: str
    url: str
    title: str = ""
    credibility: int = 70  # 0-100 scale
