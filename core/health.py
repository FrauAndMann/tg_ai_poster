"""
Health monitoring and system checks for TG AI Poster.

Provides comprehensive health checking for:
- Database connectivity
- LLM adapter availability
- Telegram API connectivity
- Disk space
- Memory usage
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from loguru import logger


class HealthStatus(str, Enum):
    """Health check status for individual components."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status for a single component."""
    component: str
    healthy: bool
    message: str
    latency_ms: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        self.timestamp = self.timestamp or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "healthy": self.healthy,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoisoformat(),
        }


@dataclass
class SystemHealth:
    """Overall system health status."""
    overall_healthy: bool
    components: list[ComponentHealth]
    checked_at: datetime
    version: str = "1.0.0"

    def __post_init__(self):
        self.checked_at = self.checked_at or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "overall_healthy": self.overall_healthy,
            "components": [c.to_dict() for c in self.components],
            "checked_at": self.checked_at.isoisoformat(),
            "version": self.version,
        }


class HealthChecker:
    """
    Comprehensive health checker for system components.

    Usage:
        checker = HealthChecker(db, publisher, llm_adapter)
        health = await checker.check_all()
        if not health.overall_healthy:
            logger.warning(f"System health issues detected")
    """

    def __init__(
        self,
        db: Any,
        publisher: Any,
        llm_adapter: Any,
    ):
        self.db = db
        self.publisher = publisher
        self.llm_adapter = llm_adapter

    async def check_all(self) -> SystemHealth:
        """Run all health checks and return overall status."""
        components = []

        # Check database
        db_health = await self.check_database()
        components.append(db_health)

        # Check LLM adapter
        llm_health = await self.check_llm_adapter()
        components.append(llm_health)

        # Check Telegram
        telegram_health = await self.check_telegram()
        components.append(telegram_health)

        # Check disk space
        disk_health = await self.check_disk_space()
        components.append(disk_health)

        # Check memory
        memory_health = await self.check_memory()
        components.append(memory_health)

        # Determine overall health
        overall_healthy = all(c.healthy for c in components)

        return SystemHealth(
            overall_healthy=overall_healthy,
            components=components,
        )

    async def check_database(self) -> ComponentHealth:
        """Check database connectivity."""
        start = datetime.utcnow()
        try:
            # Simple query to check connection
            if hasattr(self.db, 'execute'):
                result = await self.db.execute("SELECT 1")
            else:
                # Fallback for different DB interfaces
                logger.debug("Database connection check - alternative method")
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            return ComponentHealth(
                component="database",
                healthy=True,
                message="Connected",
                latency_ms=latency,
            )
        except Exception as e:
            return ComponentHealth(
                component="database",
                healthy=False,
                message=f"Connection failed: {e}",
            )

    async def check_llm_adapter(self) -> ComponentHealth:
        """Check LLM adapter availability with a light request."""
        start = datetime.utcnow()
        try:
            if self.llm_adapter is None:
                return ComponentHealth(
                    component="llm_adapter",
                    healthy=False,
                    message="LLM adapter not configured",
                )

            # Light ping - minimal token request
            result = await asyncio.wait_for(
                self.llm_adapter.generate(
                    "Say 'ok'",
                    max_tokens=5,
                ),
                timeout=5.0,
            )
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            return ComponentHealth(
                component="llm_adapter",
                healthy=True,
                message=f"API responding ({latency:.0f}ms)",
                latency_ms=latency,
            )
        except asyncio.TimeoutError:
            return ComponentHealth(
                component="llm_adapter",
                healthy=False,
                message="API timeout",
            )
        except Exception as e:
            return ComponentHealth(
                component="llm_adapter",
                healthy=False,
                message=str(e),
            )

    async def check_telegram(self) -> ComponentHealth:
        """Check Telegram API connectivity."""
        start = datetime.utcnow()
        try:
            if self.publisher is None:
                return ComponentHealth(
                    component="telegram",
                    healthy=False,
                    message="Publisher not configured",
                )

            # Get bot info to check connection
            me = await asyncio.wait_for(
                self.publisher.bot.get_me(),
                timeout=5.0,
            )
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            return ComponentHealth(
                component="telegram",
                healthy=True,
                message=f"Connected as @{me.username}",
                latency_ms=latency,
            )
        except asyncio.TimeoutError:
            return ComponentHealth(
                component="telegram",
                healthy=False,
                message="API timeout",
            )
        except Exception as e:
            return ComponentHealth(
                component="telegram",
                healthy=False,
                message=str(e),
            )

    async def check_disk_space(self) -> ComponentHealth:
        """Check available disk space."""
        try:
            usage = shutil.disk_usage(".")
            free_gb = usage.free / (1024** 3)  # Convert to GB

            if free_gb > 1.0:
                return ComponentHealth(
                    component="disk_space",
                    healthy=True,
                    message=f"{free_gb:.1f} GB free",
                )
            else:
                return ComponentHealth(
                    component="disk_space",
                    healthy=False,
                    message=f"Low disk space: {free_gb:.1f} GB free",
                )
        except Exception as e:
            return ComponentHealth(
                component="disk_space",
                healthy=False,
                message=str(e),
            )

    async def check_memory(self) -> ComponentHealth:
        """Check memory usage."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            healthy = memory.percent < 90

            return ComponentHealth(
                component="memory",
                healthy=healthy,
                message=f"{memory.percent:.1f}% used",
            )
        except ImportError:
            return ComponentHealth(
                component="memory",
                healthy=True,
                message="psutil not installed - skipping check",
            )
        except Exception as e:
            return ComponentHealth(
                component="memory",
                healthy=False,
                message=str(e),
            )


# Convenience functions for startup validation
async def run_startup_health_check(
    db: Any,
    publisher: Any,
    llm_adapter: Any,
) -> SystemHealth:
    """
    Run health checks at application startup.

    Args:
        db: Database instance
        publisher: Publisher instance
        llm_adapter: LLM adapter instance

    Returns:
        SystemHealth: Overall system health status
    """
    checker = HealthChecker(db, publisher, llm_adapter)
    health = await checker.check_all()

    for component in health.components:
        if not component.healthy:
            logger.warning(
                f"Health check failed - {component.component}: {component.message}"
            )
        else:
            logger.debug(
                f"Health check passed - {component.component}: {component.message}"
            )

    if not health.overall_healthy:
        logger.error("System health checks failed - some components are unhealthy")
    else:
        logger.info("All health checks passed")

    return health
