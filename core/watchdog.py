"""
Self-Monitoring & Auto-Recovery Watchdog - System health guardian.

Monitors system health, detects anomalies, and automatically recovers
from common failure scenarios without human intervention.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from memory.database import PostStore

logger = get_logger(__name__)


class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(slots=True)
class HealthCheck:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Alert:
    """System alert."""

    severity: AlertSeverity
    component: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass(slots=True)
class RecoveryAction:
    """Auto-recovery action."""

    name: str
    trigger_condition: str
    action: Callable[[], bool]
    max_attempts: int = 3
    cooldown_minutes: int = 5
    last_attempt: Optional[datetime] = None
    attempt_count: int = 0


class Watchdog:
    """
    Self-monitoring and auto-recovery system.

    Features:
    - Continuous health monitoring
    - Anomaly detection
    - Automatic recovery from common failures
    - Alert management
    - Resource monitoring
    """

    # Health check thresholds
    DISK_SPACE_THRESHOLD_PCT = 90
    MEMORY_THRESHOLD_PCT = 85
    MAX_CONSECUTIVE_FAILURES = 3
    MAX_POST_GAP_HOURS = 48
    DB_SLOW_QUERY_SECONDS = 5.0

    def __init__(
        self,
        post_store: Optional["PostStore"] = None,
        check_interval_seconds: int = 300,  # 5 minutes
        enable_auto_recovery: bool = True,
    ) -> None:
        self.post_store = post_store
        self.check_interval = check_interval_seconds
        self.enable_auto_recovery = enable_auto_recovery

        self._health_checks: dict[str, HealthCheck] = {}
        self._alerts: list[Alert] = []
        self._recovery_actions: list[RecoveryAction] = []
        self._consecutive_failures: dict[str, int] = {}
        self._running = False
        self._last_post_time: Optional[datetime] = None

        # Register default health checks
        self._register_default_checks()
        self._register_default_recovery_actions()

    def _register_default_checks(self) -> None:
        """Register default health checks."""
        self.register_health_check("disk_space", self._check_disk_space)
        self.register_health_check("memory_usage", self._check_memory_usage)
        self.register_health_check("database", self._check_database)
        self.register_health_check("posting_frequency", self._check_posting_frequency)
        self.register_health_check("pipeline_health", self._check_pipeline_health)

    def _register_default_recovery_actions(self) -> None:
        """Register default recovery actions."""
        self.register_recovery_action(
            "restart_scheduler",
            "posting_frequency_low",
            self._restart_scheduler,
            max_attempts=2,
            cooldown_minutes=10,
        )
        self.register_recovery_action(
            "clear_cache",
            "memory_high",
            self._clear_caches,
            max_attempts=3,
            cooldown_minutes=5,
        )
        self.register_recovery_action(
            "reconnect_database",
            "database_unresponsive",
            self._reconnect_database,
            max_attempts=3,
            cooldown_minutes=2,
        )

    def register_health_check(
        self,
        name: str,
        check_func: Callable[[], HealthCheck],
    ) -> None:
        """Register a health check function."""
        # Store the function for later execution
        self._health_checks[name] = HealthCheck(
            name=name,
            status=HealthStatus.HEALTHY,
            message="Not yet checked",
        )
        setattr(self, f"_check_func_{name}", check_func)

    def register_recovery_action(
        self,
        name: str,
        trigger_condition: str,
        action: Callable[[], bool],
        max_attempts: int = 3,
        cooldown_minutes: int = 5,
    ) -> None:
        """Register a recovery action."""
        self._recovery_actions.append(RecoveryAction(
            name=name,
            trigger_condition=trigger_condition,
            action=action,
            max_attempts=max_attempts,
            cooldown_minutes=cooldown_minutes,
        ))

    async def run_health_checks(self) -> dict[str, HealthCheck]:
        """Run all registered health checks."""
        results = {}

        for name in self._health_checks:
            try:
                check_func = getattr(self, f"_check_func_{name}", None)
                if check_func:
                    result = check_func()
                    results[name] = result
                    self._health_checks[name] = result

                    # Generate alerts for unhealthy checks
                    if result.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
                        self._create_alert(
                            AlertSeverity.ERROR if result.status == HealthStatus.UNHEALTHY
                            else AlertSeverity.CRITICAL,
                            name,
                            result.message,
                        )

            except Exception as e:
                logger.error("Health check %s failed: %s", name, e)
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {e}",
                )

        return results

    def _check_disk_space(self) -> HealthCheck:
        """Check available disk space."""
        try:
            total, used, free = shutil.disk_usage("/")
            used_pct = (used / total) * 100

            if used_pct >= self.DISK_SPACE_THRESHOLD_PCT:
                return HealthCheck(
                    name="disk_space",
                    status=HealthStatus.CRITICAL,
                    message=f"Disk space critically low: {used_pct:.1f}% used",
                    details={"used_pct": used_pct, "free_gb": free / (1024**3)},
                )
            elif used_pct >= self.DISK_SPACE_THRESHOLD_PCT - 10:
                return HealthCheck(
                    name="disk_space",
                    status=HealthStatus.DEGRADED,
                    message=f"Disk space getting low: {used_pct:.1f}% used",
                    details={"used_pct": used_pct, "free_gb": free / (1024**3)},
                )

            return HealthCheck(
                name="disk_space",
                status=HealthStatus.HEALTHY,
                message=f"Disk space OK: {used_pct:.1f}% used",
                details={"used_pct": used_pct, "free_gb": free / (1024**3)},
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check disk space: {e}",
            )

    def _check_memory_usage(self) -> HealthCheck:
        """Check memory usage."""
        try:
            # Cross-platform memory check
            import psutil
            memory = psutil.virtual_memory()
            used_pct = memory.percent

            if used_pct >= self.MEMORY_THRESHOLD_PCT:
                return HealthCheck(
                    name="memory_usage",
                    status=HealthStatus.CRITICAL,
                    message=f"Memory critically high: {used_pct:.1f}% used",
                    details={"used_pct": used_pct, "available_gb": memory.available / (1024**3)},
                )
            elif used_pct >= self.MEMORY_THRESHOLD_PCT - 10:
                return HealthCheck(
                    name="memory_usage",
                    status=HealthStatus.DEGRADED,
                    message=f"Memory usage high: {used_pct:.1f}% used",
                    details={"used_pct": used_pct, "available_gb": memory.available / (1024**3)},
                )

            return HealthCheck(
                name="memory_usage",
                status=HealthStatus.HEALTHY,
                message=f"Memory OK: {used_pct:.1f}% used",
                details={"used_pct": used_pct, "available_gb": memory.available / (1024**3)},
            )
        except ImportError:
            return HealthCheck(
                name="memory_usage",
                status=HealthStatus.HEALTHY,
                message="Memory check skipped (psutil not installed)",
            )
        except Exception as e:
            return HealthCheck(
                name="memory_usage",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check memory: {e}",
            )

    def _check_database(self) -> HealthCheck:
        """Check database connectivity and performance."""
        if not self.post_store:
            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database not configured",
            )

        try:
            start = datetime.now()
            # Simple connectivity test
            asyncio.get_event_loop().run_until_complete(self.post_store.count())
            elapsed = (datetime.now() - start).total_seconds()

            if elapsed > self.DB_SLOW_QUERY_SECONDS:
                return HealthCheck(
                    name="database",
                    status=HealthStatus.DEGRADED,
                    message=f"Database slow: {elapsed:.2f}s response time",
                    details={"response_time_seconds": elapsed},
                )

            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY,
                message=f"Database OK: {elapsed:.2f}s response time",
                details={"response_time_seconds": elapsed},
            )
        except Exception as e:
            return HealthCheck(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {e}",
            )

    def _check_posting_frequency(self) -> HealthCheck:
        """Check if posting frequency is normal."""
        if not self.post_store:
            return HealthCheck(
                name="posting_frequency",
                status=HealthStatus.HEALTHY,
                message="Post store not configured",
            )

        try:
            # Get last post time
            posts = asyncio.get_event_loop().run_until_complete(
                self.post_store.list(limit=1)
            )

            if not posts:
                return HealthCheck(
                    name="posting_frequency",
                    status=HealthStatus.DEGRADED,
                    message="No posts found",
                )

            last_post = posts[0]
            last_post_time = last_post.published_at or datetime.min
            hours_since = (datetime.now() - last_post_time).total_seconds() / 3600

            if hours_since >= self.MAX_POST_GAP_HOURS:
                return HealthCheck(
                    name="posting_frequency",
                    status=HealthStatus.CRITICAL,
                    message=f"No posts for {hours_since:.1f} hours",
                    details={"hours_since_last_post": hours_since},
                )
            elif hours_since >= self.MAX_POST_GAP_HOURS / 2:
                return HealthCheck(
                    name="posting_frequency",
                    status=HealthStatus.DEGRADED,
                    message=f"Posting delayed: {hours_since:.1f} hours since last post",
                    details={"hours_since_last_post": hours_since},
                )

            return HealthCheck(
                name="posting_frequency",
                status=HealthStatus.HEALTHY,
                message=f"Posting OK: last post {hours_since:.1f} hours ago",
                details={"hours_since_last_post": hours_since},
            )
        except Exception as e:
            return HealthCheck(
                name="posting_frequency",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check posting frequency: {e}",
            )

    def _check_pipeline_health(self) -> HealthCheck:
        """Check overall pipeline health."""
        failures = sum(self._consecutive_failures.values())

        if failures >= self.MAX_CONSECUTIVE_FAILURES:
            return HealthCheck(
                name="pipeline_health",
                status=HealthStatus.CRITICAL,
                message=f"Pipeline has {failures} consecutive failures",
                details={"failures": self._consecutive_failures},
            )
        elif failures > 0:
            return HealthCheck(
                name="pipeline_health",
                status=HealthStatus.DEGRADED,
                message=f"Pipeline has some failures: {self._consecutive_failures}",
                details={"failures": self._consecutive_failures},
            )

        return HealthCheck(
            name="pipeline_health",
            status=HealthStatus.HEALTHY,
            message="Pipeline operating normally",
        )

    def _create_alert(
        self,
        severity: AlertSeverity,
        component: str,
        message: str,
    ) -> None:
        """Create a new alert."""
        alert = Alert(
            severity=severity,
            component=component,
            message=message,
        )
        self._alerts.append(alert)
        logger.warning(
            "Alert created [%s] %s: %s",
            severity.value.upper(),
            component,
            message,
        )

    def record_failure(self, component: str) -> None:
        """Record a failure for tracking."""
        self._consecutive_failures[component] = self._consecutive_failures.get(component, 0) + 1

    def record_success(self, component: str) -> None:
        """Record a success, resetting failure counter."""
        self._consecutive_failures[component] = 0

    async def attempt_recovery(self, condition: str) -> bool:
        """Attempt automatic recovery for a condition."""
        if not self.enable_auto_recovery:
            logger.info("Auto-recovery disabled, skipping recovery for: %s", condition)
            return False

        for action in self._recovery_actions:
            if action.trigger_condition == condition:
                # Check cooldown
                if action.last_attempt:
                    cooldown = timedelta(minutes=action.cooldown_minutes)
                    if datetime.now() - action.last_attempt < cooldown:
                        logger.debug(
                            "Recovery action %s on cooldown",
                            action.name,
                        )
                        return False

                # Check max attempts
                if action.attempt_count >= action.max_attempts:
                    logger.warning(
                        "Recovery action %s exceeded max attempts",
                        action.name,
                    )
                    return False

                # Attempt recovery
                logger.info("Attempting recovery action: %s", action.name)
                try:
                    success = action.action()
                    action.last_attempt = datetime.now()
                    action.attempt_count += 1

                    if success:
                        logger.info("Recovery action %s succeeded", action.name)
                        action.attempt_count = 0
                        return True
                    else:
                        logger.warning("Recovery action %s failed", action.name)
                        return False

                except Exception as e:
                    logger.error("Recovery action %s raised exception: %s", action.name, e)
                    action.last_attempt = datetime.now()
                    action.attempt_count += 1
                    return False

        return False

    def _restart_scheduler(self) -> bool:
        """Attempt to restart the scheduler."""
        try:
            # This would integrate with the actual scheduler
            logger.info("Attempting scheduler restart...")
            # Placeholder - actual implementation would restart APScheduler
            return True
        except Exception as e:
            logger.error("Scheduler restart failed: %s", e)
            return False

    def _clear_caches(self) -> bool:
        """Attempt to clear caches."""
        try:
            logger.info("Attempting cache cleanup...")
            # Clear any in-memory caches
            import gc
            gc.collect()
            return True
        except Exception as e:
            logger.error("Cache cleanup failed: %s", e)
            return False

    def _reconnect_database(self) -> bool:
        """Attempt to reconnect to database."""
        try:
            logger.info("Attempting database reconnection...")
            # Placeholder - actual implementation would reconnect
            return True
        except Exception as e:
            logger.error("Database reconnection failed: %s", e)
            return False

    async def start_monitoring(self) -> None:
        """Start continuous monitoring loop."""
        self._running = True
        logger.info("Watchdog monitoring started")

        while self._running:
            try:
                # Run health checks
                results = await self.run_health_checks()

                # Check for conditions requiring recovery
                for name, check in results.items():
                    if check.status == HealthStatus.CRITICAL:
                        # Map check name to recovery condition
                        condition_map = {
                            "disk_space": "disk_full",
                            "memory_usage": "memory_high",
                            "database": "database_unresponsive",
                            "posting_frequency": "posting_frequency_low",
                        }
                        condition = condition_map.get(name)
                        if condition:
                            await self.attempt_recovery(condition)

                # Clean up old alerts (keep last 100)
                if len(self._alerts) > 100:
                    self._alerts = self._alerts[-100:]

                # Wait for next check
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Watchdog monitoring error: %s", e)
                await asyncio.sleep(self.check_interval)

    def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        logger.info("Watchdog monitoring stopped")

    def get_status(self) -> dict[str, Any]:
        """Get current system status."""
        overall_status = HealthStatus.HEALTHY
        for check in self._health_checks.values():
            if check.status.value > overall_status.value:
                overall_status = check.status

        return {
            "overall_status": overall_status.value,
            "last_check": max(
                (c.timestamp for c in self._health_checks.values()),
                default=datetime.now(),
            ).isoformat(),
            "health_checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                }
                for name, check in self._health_checks.items()
            },
            "active_alerts": len([a for a in self._alerts if not a.resolved]),
            "recent_alerts": [
                {
                    "severity": a.severity.value,
                    "component": a.component,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in self._alerts[-10:]
            ],
        }


# Configuration schema
WATCHDOG_CONFIG_SCHEMA = {
    "watchdog": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable watchdog monitoring",
        },
        "check_interval_seconds": {
            "type": "int",
            "default": 300,
            "description": "Seconds between health checks",
        },
        "enable_auto_recovery": {
            "type": "bool",
            "default": True,
            "description": "Enable automatic recovery actions",
        },
        "disk_threshold_pct": {
            "type": "int",
            "default": 90,
            "description": "Disk usage percentage threshold",
        },
        "memory_threshold_pct": {
            "type": "int",
            "default": 85,
            "description": "Memory usage percentage threshold",
        },
        "max_post_gap_hours": {
            "type": "int",
            "default": 48,
            "description": "Maximum hours without a post before alert",
        },
    }
}
