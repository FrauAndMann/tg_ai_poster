"""
Retry decorator with exponential backoff.

Provides configurable retry logic for async functions.
"""

from __future__ import annotations

import asyncio
import functools
import random
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional, Tuple, Type

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts
        backoff_base: Base for exponential backoff (seconds)
        backoff_multiplier: Multiplier for each retry
        max_backoff: Maximum backoff time (seconds)
        jitter: Whether to add random jitter to backoff
        exceptions: Tuple of exceptions to catch
        on_retry: Callback function called on each retry
    """

    max_attempts: int = 3
    backoff_base: float = 1.0
    backoff_multiplier: float = 2.0
    max_backoff: float = 60.0
    jitter: bool = True
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
    on_retry: Optional[Callable] = None


def calculate_backoff(
    attempt: int,
    base: float,
    multiplier: float,
    max_backoff: float,
    jitter: bool = True,
) -> float:
    """
    Calculate backoff time with exponential increase.

    Args:
        attempt: Current attempt number (1-based)
        base: Base backoff time
        multiplier: Multiplier for each attempt
        max_backoff: Maximum backoff time
        jitter: Whether to add random jitter

    Returns:
        float: Backoff time in seconds
    """
    backoff = base * (multiplier ** (attempt - 1))
    backoff = min(backoff, max_backoff)

    if jitter:
        # Add up to 25% jitter
        jitter_amount = backoff * 0.25 * random.random()
        backoff = backoff + jitter_amount

    return backoff


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_backoff: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator for automatic retry with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        backoff_base: Base backoff time in seconds
        backoff_multiplier: Multiplier for exponential backoff
        max_backoff: Maximum backoff time
        jitter: Add random jitter to backoff
        exceptions: Exceptions to catch and retry
        on_retry: Callback on each retry

    Returns:
        Decorated function

    Usage:
        @with_retry(max_attempts=3, backoff_base=2.0)
        async def my_function():
            ...

        # Or with specific exceptions
        @with_retry(max_attempts=5, exceptions=(ConnectionError, TimeoutError))
        async def fetch_data():
            ...
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts:
                        backoff = calculate_backoff(
                            attempt,
                            backoff_base,
                            backoff_multiplier,
                            max_backoff,
                            jitter,
                        )

                        logger.warning(
                            f"Retry {attempt}/{max_attempts} for {func.__name__}: {e}. "
                            f"Waiting {backoff:.2f}s before retry..."
                        )

                        if on_retry:
                            try:
                                if asyncio.iscoroutinefunction(on_retry):
                                    await on_retry(attempt, e)
                                else:
                                    on_retry(attempt, e)
                            except Exception as callback_error:
                                logger.error(f"Retry callback failed: {callback_error}")

                        await asyncio.sleep(backoff)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


def with_retry_sync(
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_backoff: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Synchronous version of retry decorator.

    Args:
        max_attempts: Maximum number of attempts
        backoff_base: Base backoff time in seconds
        backoff_multiplier: Multiplier for exponential backoff
        max_backoff: Maximum backoff time
        jitter: Add random jitter to backoff
        exceptions: Exceptions to catch and retry

    Returns:
        Decorated function
    """
    import time

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts:
                        backoff = calculate_backoff(
                            attempt,
                            backoff_base,
                            backoff_multiplier,
                            max_backoff,
                            jitter,
                        )

                        logger.warning(
                            f"Retry {attempt}/{max_attempts} for {func.__name__}: {e}. "
                            f"Waiting {backoff:.2f}s..."
                        )

                        time.sleep(backoff)

            raise last_exception

        return wrapper

    return decorator


class RetryContext:
    """
    Context manager for retry logic.

    Usage:
        async with RetryContext(max_attempts=3) as retry:
            while retry.should_continue():
                try:
                    result = await some_operation()
                    retry.success()
                    return result
                except Exception as e:
                    retry.failure(e)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_base: float = 1.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.exceptions = exceptions
        self.attempt = 0
        self._success = False
        self._last_exception: Optional[Exception] = None

    async def __aenter__(self) -> "RetryContext":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    def should_continue(self) -> bool:
        """Check if we should continue retrying."""
        return self.attempt < self.max_attempts and not self._success

    def success(self) -> None:
        """Mark operation as successful."""
        self._success = True

    def failure(self, exception: Exception) -> None:
        """Record a failure and wait if needed."""
        self._last_exception = exception
        self.attempt += 1

    async def wait(self) -> None:
        """Wait before next attempt."""
        if self.attempt > 0 and self.attempt < self.max_attempts:
            backoff = calculate_backoff(self.attempt, self.backoff_base, 2.0, 60.0, True)
            await asyncio.sleep(backoff)

    @property
    def last_exception(self) -> Optional[Exception]:
        """Get the last exception."""
        return self._last_exception
