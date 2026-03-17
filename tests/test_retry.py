"""
Tests for retry decorator and rate limiter.

Tests exponential backoff, retry logic, and token bucket rate limiting.
"""

import pytest

from utils.retry import (
    with_retry,
    calculate_backoff,
)
from utils.rate_limiter import (
    TokenBucket,
    RateLimiter,
    MultiServiceRateLimiter,
)


class TestCalculateBackoff:
    """Tests for backoff calculation."""

    def test_first_attempt(self):
        """Test first attempt backoff."""
        backoff = calculate_backoff(1, base=1.0, multiplier=2.0, max_backoff=60.0, jitter=False)
        assert backoff == 1.0

    def test_second_attempt(self):
        """Test second attempt backoff."""
        backoff = calculate_backoff(2, base=1.0, multiplier=2.0, max_backoff=60.0, jitter=False)
        assert backoff == 2.0

    def test_max_backoff(self):
        """Test maximum backoff cap."""
        backoff = calculate_backoff(10, base=1.0, multiplier=2.0, max_backoff=10.0, jitter=False)
        assert backoff <= 10.0

    def test_jitter(self):
        """Test jitter adds randomness."""
        backoffs = [
            calculate_backoff(3, base=1.0, multiplier=2.0, max_backoff=60.0, jitter=True)
            for _ in range(10)
        ]
        # With jitter, values should vary
        assert len(set(backoffs)) > 1  # Not all the same

    def test_no_jitter(self):
        """Test without jitter."""
        backoffs = [
            calculate_backoff(3, base=1.0, multiplier=2.0, max_backoff=60.0, jitter=False)
            for _ in range(10)
        ]
        # Without jitter, all values should be the same
        assert len(set(backoffs)) == 1


class TestWithRetry:
    """Tests for retry decorator."""

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        """Test function succeeds on first try."""
        call_count = 0

        @with_retry(max_attempts=3)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        """Test function succeeds after retry."""
        call_count = 0

        @with_retry(max_attempts=3, backoff_base=0.01)
        async def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Simulated failure")
            return "success"

        result = await retry_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self):
        """Test when all attempts fail."""
        @with_retry(max_attempts=2, backoff_base=0.01)
        async def fail_func():
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            await fail_func()

    @pytest.mark.asyncio
    async def test_specific_exceptions(self):
        """Test retry only on specific exceptions."""
        call_count = 0

        @with_retry(max_attempts=3, exceptions=(KeyError,))
        async def specific_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise KeyError("Key error")
            return "success"

        result = await specific_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_callback(self):
        """Test retry callback is called."""
        callback_calls = []

        def on_retry(attempt, exception):
            callback_calls.append((attempt, str(exception)))

        @with_retry(max_attempts=3, backoff_base=0.01, on_retry=on_retry)
        async def callback_func():
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            await callback_func()

        assert len(callback_calls) == 2


class TestTokenBucket:
    """Tests for TokenBucket."""

    def test_initial_tokens(self):
        """Test initial token count."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.tokens == 0.0

    @pytest.mark.asyncio
    async def test_consume_available_tokens(self):
        """Test consuming available tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=5.0)
        result = await bucket.consume(3.0)
        assert result is True
        # Use approximate comparison due to refill timing
        assert bucket.tokens == pytest.approx(2.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_consume_unavailable_tokens(self):
        """Test consuming unavailable tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=1.0)
        result = await bucket.consume(5.0)
        assert result is False

    @pytest.mark.asyncio
    async def test_refill(self):
        """Test token refill."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0, tokens=0.0)
        import time
        time.sleep(0.5)
        bucket._refill()
        assert bucket.tokens > 0

    @pytest.mark.asyncio
    async def test_wait_for_token(self):
        """Test waiting for token availability."""
        bucket = TokenBucket(capacity=10, refill_rate=100.0, tokens=0.0)
        import time
        start = time.time()
        await bucket.wait_for_token(1.0)
        elapsed = time.time() - start
        assert elapsed < 1.0  # Should be fast with high refill rate


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """Test acquiring within limits."""
        # Initialize with tokens so we can acquire immediately
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        # Manually add tokens to the bucket for testing
        for bucket in limiter.limiters.values():
            bucket.tokens = 10.0
        result = await limiter.acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_exceeds_burst(self):
        """Test acquiring when burst is exceeded."""
        limiter = RateLimiter(requests_per_minute=1, burst_size=1)
        # Manually add tokens to the bucket for testing
        for bucket in limiter.limiters.values():
            bucket.tokens = 1.0

        # First should succeed
        result1 = await limiter.acquire()
        assert result1 is True

        # Second should fail (burst exhausted)
        result2 = await limiter.acquire()
        assert result2 is False

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting status."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        # Manually add tokens to the bucket for testing
        for bucket in limiter.limiters.values():
            bucket.tokens = 10.0
        await limiter.acquire()
        status = limiter.get_status()
        assert status["total_requests"] == 1
        assert "per_minute" in status["limiters"]

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test resetting limiter."""
        limiter = RateLimiter(requests_per_minute=1, burst_size=1)
        # Manually add tokens to the bucket for testing
        for bucket in limiter.limiters.values():
            bucket.tokens = 1.0
        await limiter.acquire()
        await limiter.reset()
        status = limiter.get_status()
        assert status["total_requests"] == 0


class TestMultiServiceRateLimiter:
    """Tests for MultiServiceRateLimiter."""

    @pytest.mark.asyncio
    async def test_add_service(self):
        """Test adding service."""
        limiter = MultiServiceRateLimiter()
        limiter.add_service("openai", requests_per_minute=60)
        status = limiter.get_status()
        assert "openai" in status

    @pytest.mark.asyncio
    async def test_acquire_unknown_service(self):
        """Test acquiring for unknown service."""
        limiter = MultiServiceRateLimiter()
        result = await limiter.acquire("unknown")
        assert result is True  # Unknown services are allowed

    @pytest.mark.asyncio
    async def test_acquire_known_service(self):
        """Test acquiring for known service."""
        limiter = MultiServiceRateLimiter()
        limiter.add_service("openai", requests_per_minute=60, burst_size=10)
        # Add tokens to the bucket for testing
        for bucket in limiter._services["openai"].limiters.values():
            bucket.tokens = 10.0
        result = await limiter.acquire("openai")
        assert result is True

    @pytest.mark.asyncio
    async def test_multiple_services(self):
        """Test multiple services with different limits."""
        limiter = MultiServiceRateLimiter()
        limiter.add_service("openai", requests_per_minute=60, burst_size=10)
        limiter.add_service("telegram", requests_per_minute=20, burst_size=5)

        # Add tokens to the buckets for testing
        for service in ["openai", "telegram"]:
            for bucket in limiter._services[service].limiters.values():
                bucket.tokens = 10.0

        result1 = await limiter.acquire("openai")
        result2 = await limiter.acquire("telegram")

        assert result1 is True
        assert result2 is True

        status = limiter.get_status()
        assert "openai" in status
        assert "telegram" in status
