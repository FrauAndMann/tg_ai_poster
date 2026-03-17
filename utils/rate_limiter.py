"""
Rate limiter implementations.

Provides token bucket and sliding window rate limiters.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TokenBucket:
    """
    Token bucket rate limiter.

    Allows bursts up to bucket size, then rate-limits to refill rate.

    Attributes:
        capacity: Maximum tokens in bucket
        refill_rate: Tokens added per second
        tokens: Current token count
        last_refill: Last refill timestamp
    """

    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.time)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens for elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    async def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            bool: True if tokens were consumed
        """
        async with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    async def wait_for_token(self, tokens: float = 1.0) -> None:
        """
        Wait until tokens are available, then consume.

        Args:
            tokens: Number of tokens to consume
        """
        while True:
            if await self.consume(tokens):
                return

            # Calculate wait time
            async with self._lock:
                needed = tokens - self.tokens
                wait_time = needed / self.refill_rate

            await asyncio.sleep(min(wait_time, 0.1))

    def get_wait_time(self, tokens: float = 1.0) -> float:
        """
        Get estimated wait time for tokens.

        Args:
            tokens: Number of tokens needed

        Returns:
            float: Estimated wait time in seconds
        """
        self._refill()

        if self.tokens >= tokens:
            return 0.0

        needed = tokens - self.tokens
        return needed / self.refill_rate


class RateLimiter:
    """
    Configurable rate limiter with multiple algorithms.

    Supports per-minute and per-day limits.
    """

    def __init__(
        self,
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
        requests_per_day: Optional[int] = None,
        burst_size: Optional[int] = None,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
            requests_per_day: Max requests per day
            burst_size: Allow burst up to this size
        """
        self.limiters: dict[str, TokenBucket] = {}

        if requests_per_minute:
            self.limiters["per_minute"] = TokenBucket(
                capacity=burst_size or requests_per_minute,
                refill_rate=requests_per_minute / 60.0,
            )

        if requests_per_hour:
            self.limiters["per_hour"] = TokenBucket(
                capacity=burst_size or requests_per_hour,
                refill_rate=requests_per_hour / 3600.0,
            )

        if requests_per_day:
            self.limiters["per_day"] = TokenBucket(
                capacity=burst_size or requests_per_day,
                refill_rate=requests_per_day / 86400.0,
            )

        self._request_count = 0
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> bool:
        """
        Try to acquire permission to proceed.

        Args:
            tokens: Number of tokens to consume

        Returns:
            bool: True if allowed, False if rate limited
        """
        async with self._lock:
            for name, limiter in self.limiters.items():
                if not await limiter.consume(tokens):
                    logger.debug(f"Rate limited by {name}")
                    return False

            self._request_count += 1
            return True

    async def wait_and_acquire(self, tokens: float = 1.0) -> None:
        """
        Wait until rate limit allows, then proceed.

        Args:
            tokens: Number of tokens to consume
        """
        while True:
            if await self.acquire(tokens):
                return

            # Find minimum wait time
            wait_time = min(
                (limiter.get_wait_time(tokens) for limiter in self.limiters.values()),
                default=0.1,
            )

            await asyncio.sleep(max(wait_time, 0.1))

    def get_status(self) -> dict:
        """
        Get current rate limiter status.

        Returns:
            dict: Status information
        """
        status = {
            "total_requests": self._request_count,
            "limiters": {},
        }

        for name, limiter in self.limiters.items():
            limiter._refill()
            status["limiters"][name] = {
                "tokens": limiter.tokens,
                "capacity": limiter.capacity,
                "refill_rate": limiter.refill_rate,
            }

        return status

    async def reset(self) -> None:
        """Reset all limiters."""
        async with self._lock:
            for limiter in self.limiters.values():
                limiter.tokens = limiter.capacity
                limiter.last_refill = time.time()

            self._request_count = 0


class MultiServiceRateLimiter:
    """
    Rate limiter for multiple services with different limits.

    Useful when calling multiple APIs with different rate limits.
    """

    def __init__(self) -> None:
        """Initialize multi-service rate limiter."""
        self._services: dict[str, RateLimiter] = {}
        self._lock = asyncio.Lock()

    def add_service(
        self,
        name: str,
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
        requests_per_day: Optional[int] = None,
        burst_size: Optional[int] = None,
    ) -> None:
        """
        Add a service with its rate limits.

        Args:
            name: Service name
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
            requests_per_day: Max requests per day
            burst_size: Burst size
        """
        self._services[name] = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            requests_per_day=requests_per_day,
            burst_size=burst_size,
        )

        logger.info(
            f"Added rate limiter for '{name}': "
            f"{requests_per_minute}/min, {requests_per_hour}/hour, {requests_per_day}/day"
        )

    async def acquire(self, service: str, tokens: float = 1.0) -> bool:
        """
        Try to acquire for a specific service.

        Args:
            service: Service name
            tokens: Tokens to consume

        Returns:
            bool: True if allowed
        """
        if service not in self._services:
            logger.warning(f"Unknown service: {service}")
            return True

        return await self._services[service].acquire(tokens)

    async def wait_and_acquire(self, service: str, tokens: float = 1.0) -> None:
        """
        Wait and acquire for a specific service.

        Args:
            service: Service name
            tokens: Tokens to consume
        """
        if service not in self._services:
            return

        await self._services[service].wait_and_acquire(tokens)

    def get_status(self, service: Optional[str] = None) -> dict:
        """
        Get status for one or all services.

        Args:
            service: Optional service name

        Returns:
            dict: Status information
        """
        if service:
            if service in self._services:
                return self._services[service].get_status()
            return {}

        return {name: limiter.get_status() for name, limiter in self._services.items()}


# Pre-configured limiters for common use cases
def create_openai_limiter() -> RateLimiter:
    """Create rate limiter for OpenAI API (typical tier limits)."""
    return RateLimiter(
        requests_per_minute=500,
        requests_per_hour=30000,
        burst_size=10,
    )


def create_telegram_limiter() -> RateLimiter:
    """Create rate limiter for Telegram Bot API."""
    # Telegram limits: ~30 messages/sec to same group,
    # ~1 message/sec to same user in private
    return RateLimiter(
        requests_per_minute=20,
        requests_per_hour=500,
        burst_size=5,
    )


def create_default_limiter() -> RateLimiter:
    """Create a conservative default rate limiter."""
    return RateLimiter(
        requests_per_minute=30,
        requests_per_hour=500,
        requests_per_day=5000,
    )
