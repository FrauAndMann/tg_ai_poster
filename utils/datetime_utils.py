"""
DateTime utilities for timezone-aware datetime operations.

This module provides timezone-aware alternatives to datetime.utcnow()
to ensure consistent timezone handling across the codebase.
"""

from datetime import datetime, timezone

# Use UTC timezone constant
UTC = timezone.utc


def utcnow() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.

    This is the recommended replacement for datetime.utcnow()
    which returns a naive datetime object.

    Returns:
        datetime: Current UTC time with timezone info
    """
    return datetime.now(UTC)


def make_aware(dt: datetime | None) -> datetime | None:
    """
    Ensure datetime is timezone-aware (assume UTC if naive).

    Args:
        dt: Datetime to make aware (or None)

    Returns:
        datetime | None: Timezone-aware datetime or None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def to_utc(dt: datetime | None) -> datetime | None:
    """
    Convert datetime to UTC.

    Args:
        dt: Datetime to convert (or None)

    Returns:
        datetime | None: UTC datetime or None
    """
    if dt is None:
        return None
    aware = make_aware(dt)
    return aware.astimezone(UTC)
