"""
Circuit Breaker pattern implementation.

Protects against cascade failures by temporarily blocking requests
to failing services and allowing them time to recover.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Requests blocked, waiting for recovery timeout
- HALF_OPEN: Testing if service recovered, limited requests allowed
"""

from __future__ import annotations

import asyncio
import functools
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional, Type

from core.logger import get_logger
from utils.exceptions import should_trigger_circuit_breaker

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStats:
    """Statistics for circuit breaker monitoring."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: int = 0


@dataclass
class CircuitBreaker:
    """
    Circuit Breaker implementation.

    Protects services from cascade failures by temporarily blocking
    requests when failure threshold is exceeded.

    Attributes:
        name: Circuit breaker identifier
        failure_threshold: Number of failures before opening
        recovery_timeout: Seconds to wait before attempting recovery
        success_threshold: Successes in half-open to close (default: 1)
        exceptions: Tuple of exceptions that trigger the breaker
    """

    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 1
    exceptions: tuple[Type[Exception], ...] = (Exception,)

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _failure_count: int = field(default=0, repr=False)
    _success_count: int = field(default=0, repr=False)
    _last_failure_time: Optional[float] = field(default=None, repr=False)
    _stats: CircuitStats = field(default_factory=CircuitStats, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def state(self) -> CircuitState:
        """Get current state (may transition if recovery timeout passed)."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to_half_open()
        return self._state

    @property
    def stats(self) -> CircuitStats:
        """Get circuit breaker statistics."""
        return self._stats

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (requests blocked)."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.recovery_timeout

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        if self._state != CircuitState.OPEN:
            old_state = self._state
            self._state = CircuitState.OPEN
            self._stats.state_changes += 1
            logger.warning(
                f"Circuit '{self.name}' OPENED after {self._failure_count} failures. "
                f"Will retry after {self.recovery_timeout}s."
            )

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._stats.state_changes += 1
        logger.info(f"Circuit '{self.name}' HALF_OPEN - testing recovery...")

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        if self._state != CircuitState.CLOSED:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._stats.state_changes += 1
            logger.info(f"Circuit '{self.name}' CLOSED - service recovered")

    def record_success(self) -> None:
        """Record a successful call."""
        self._stats.total_calls += 1
        self._stats.successful_calls += 1
        self._stats.last_success_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._transition_to_closed()
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        self._stats.total_calls += 1
        self._stats.failed_calls += 1
        self._stats.last_failure_time = time.time()
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Failure in half-open immediately opens
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            # Check if this exception should trigger the breaker
            if should_trigger_circuit_breaker(error) or isinstance(error, self.exceptions):
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._transition_to_open()

    def record_rejection(self) -> None:
        """Record a rejected call (circuit open)."""
        self._stats.rejected_calls += 1

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        state = self.state  # This may trigger state transition
        return state != CircuitState.OPEN

    async def call(self, func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            Exception: Original exception from function
        """
        async with self._lock:
            if not self.can_execute():
                self.record_rejection()
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is OPEN. Retry after {self.recovery_timeout}s.",
                    circuit_name=self.name,
                    recovery_timeout=self.recovery_timeout,
                )

        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                self.record_success()
            return result

        except Exception as e:
            async with self._lock:
                self.record_failure(e)
            raise

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        logger.info(f"Circuit '{self.name}' RESET to CLOSED")

    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "stats": {
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "rejected_calls": self._stats.rejected_calls,
                "state_changes": self._stats.state_changes,
            },
        }


class CircuitOpenError(Exception):
    """Exception raised when circuit is open."""

    def __init__(self, message: str, circuit_name: str, recovery_timeout: float):
        super().__init__(message)
        self.circuit_name = circuit_name
        self.recovery_timeout = recovery_timeout


# =============================================================================
# Circuit Breaker Registry
# =============================================================================

class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Allows centralized management and monitoring of all circuit breakers.
    """

    _instance: Optional["CircuitBreakerRegistry"] = None
    _circuit_breakers: dict[str, CircuitBreaker] = {}

    def __new__(cls) -> "CircuitBreakerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_or_create(
        cls,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        exceptions: tuple[Type[Exception], ...] = (Exception,),
    ) -> CircuitBreaker:
        """
        Get existing circuit breaker or create new one.

        Args:
            name: Circuit breaker name
            failure_threshold: Failures before opening
            recovery_timeout: Recovery timeout in seconds
            exceptions: Exceptions to catch

        Returns:
            CircuitBreaker instance
        """
        if name not in cls._circuit_breakers:
            cls._circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                exceptions=exceptions,
            )
        return cls._circuit_breakers[name]

    @classmethod
    def get(cls, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return cls._circuit_breakers.get(name)

    @classmethod
    def get_all(cls) -> dict[str, CircuitBreaker]:
        """Get all circuit breakers."""
        return cls._circuit_breakers.copy()

    @classmethod
    def get_all_status(cls) -> dict[str, dict]:
        """Get status of all circuit breakers."""
        return {name: cb.get_status() for name, cb in cls._circuit_breakers.items()}

    @classmethod
    def reset_all(cls) -> None:
        """Reset all circuit breakers."""
        for cb in cls._circuit_breakers.values():
            cb.reset()

    @classmethod
    def clear(cls) -> None:
        """Clear all circuit breakers."""
        cls._circuit_breakers.clear()


# =============================================================================
# Decorator for Circuit Breaker
# =============================================================================

def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator to protect a function with circuit breaker.

    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening
        recovery_timeout: Recovery timeout in seconds
        exceptions: Exceptions to catch

    Returns:
        Decorated function

    Usage:
        @with_circuit_breaker("llm_service", failure_threshold=3)
        async def call_llm():
            ...
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
        circuit = CircuitBreakerRegistry.get_or_create(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            exceptions=exceptions,
        )

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await circuit.call(func, *args, **kwargs)

        # Attach circuit breaker for testing/monitoring
        wrapper.circuit_breaker = circuit  # type: ignore

        return wrapper

    return decorator
