"""
Audit logging for TG AI Poster
Provides comprehensive audit logging for all system actions with:
- Action tracking (create, update, delete)
- State changes (pending -> published)
- Error logging with context
- Query logging with performance metrics
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional

from loguru import logger


class AuditEventType(str, Enum):
    """Types of audit events."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    PUBLISH = "publish"
    ERROR = "error"
    QUERY = "query"
    LOGIN = "login"
    CONFIG_CHANGE = "config_change"


@dataclass
class AuditLog:
    """Audit log entry."""

    event_type: AuditEventType
    action: str
    resource_type: str
    resource_id: str
    details: dict = field(default_factory=dict)
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        self.timestamp = self.timestamp or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "action": self.action,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat(),
        }


class _AuditLogger:
    """Comprehensive audit logging system."""

    def __init__(self, retention_days: int = 90):
        self.retention_days = retention_days
        self._logs: list[AuditLog] = []
        self._handlers: list[Callable] = []

    def add_handler(self, handler: Callable[[AuditLog], None]) -> None:
        """Add a custom audit handler."""
        self._handlers.append(handler)

    def log(
        self,
        event_type: AuditEventType,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[dict] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log an audit event."""
        entry = AuditLog(
            event_type=event_type,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
        )

        self._logs.append(entry)
        logger.info(
            f"AUDIT: {event_type.value} - {action} - {resource_type}/{resource_id}",
            extra={"details": details, "user_id": user_id},
        )

        # Call custom handlers
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception as e:
                logger.error(f"Audit handler error: {e}")

    def get_logs(
        self,
        event_type: Optional[AuditEventType] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Get logs with optional filtering."""
        logs = self._logs

        if event_type:
            logs = [log for log in logs if log.event_type == event_type]

        if resource_type:
            logs = [log for log in logs if log.resource_type == resource_type]

        return logs[-limit:]

    def clear_old_logs(self) -> int:
        """Clear logs older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        initial_count = len(self._logs)
        self._logs = [log for log in self._logs if log.timestamp > cutoff]
        cleared = initial_count - len(self._logs)
        logger.info(f"Cleared {cleared} old audit logs")
        return cleared


def audit_action(event_type: AuditEventType, action: str, resource_type: str):
    """Decorator to audit async function calls."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get resource_id from first argument or kwargs
            resource_id = str(args[0]) if args else "unknown"
            user_id = kwargs.get("user_id")
            ip_address = kwargs.get("ip_address")

            try:
                result = await func(*args, **kwargs)

                # Log successful action
                _audit_logger.log(
                    event_type=event_type,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details={"result": "success"},
                    user_id=user_id,
                    ip_address=ip_address,
                )

                return result

            except Exception as e:
                # Log failed action
                _audit_logger.log(
                    event_type=AuditEventType.ERROR,
                    action=f"{action}_failed",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details={"error": str(e)},
                    user_id=user_id,
                    ip_address=ip_address,
                )
                raise

        return wrapper

    return decorator


# Type alias for backward compatibility
AuditLogger = _AuditLogger

# Global audit logger instance
_audit_logger: _AuditLogger = _AuditLogger()


def get_audit_logger() -> _AuditLogger:
    """Get global audit logger instance."""
    return _audit_logger


def init_audit_logger(retention_days: int = 90) -> None:
    """Initialize global audit logger."""
    global _audit_logger
    _audit_logger = AuditLogger(retention_days=retention_days)
