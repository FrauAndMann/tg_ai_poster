"""
Tests for Circuit Breaker module.
"""

import asyncio
import time

import pytest

from utils.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    CircuitBreakerRegistry,
)


class TestCircuitBreakerStateTransitions:
    """Test CircuitBreaker state transitions."""

    def test_initial_state(self):
        """Circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=10.0,
        )
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        assert not cb.is_open
        assert not cb.is_half_open

    def test_record_success_resets_failure_count(self):
        """Recording success in CLOSED state resets failure count."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=10.0,
        )

        # Record some failures
        cb.record_failure(Exception("Error 1"))
        cb.record_failure(Exception("Error 2"))
        assert cb._failure_count == 2

        # Success should reset failure count
        cb.record_success()
        assert cb._failure_count == 0

    def test_record_failure_opens_circuit(self):
        """Recording failures opens the circuit after threshold."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=10.0,
        )

        # Record failures
        for i in range(3):
            cb.record_failure(Exception(f"Error {i+1}"))

        assert cb.state == CircuitState.OPEN
        assert cb.is_open is True

    def test_circuit_recovery_after_timeout(self):
        """Circuit recovers after timeout."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,  # Short timeout for test
        )

        # Open the circuit
        cb.record_failure(Exception("Error 1"))
        cb.record_failure(Exception("Error 2"))
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # State should transition to HALF_OPEN on next call
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes_circuit(self):
        """Success in HALF_OPEN closes the circuit after success_threshold successes."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=10.0,
            success_threshold=2,
        )

        # Open the circuit
        cb.record_failure(Exception("Error 1"))
        cb.record_failure(Exception("Error 2"))
        assert cb.state == CircuitState.OPEN

        # Force transition to HALF_OPEN for testing
        cb._transition_to_half_open()

        # Now in HALF_OPEN - record 2 successes to close
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN  # Still half-open after 1 success
        cb.record_success()
        assert cb.state == CircuitState.CLOSED  # Closed after 2 successes

    def test_failure_in_half_open_reopens(self):
        """Failure in HALF_OPEN reopens the circuit immediately."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=10.0,
        )

        # Open the circuit
        cb.record_failure(Exception("Error 1"))
        assert cb.state == CircuitState.OPEN

        # Wait for recovery (manually set time)
        cb._last_failure_time = time.time() - 20

        # Now in HALF_OPEN
        cb.record_failure(Exception("Error in half-open"))
        assert cb.state == CircuitState.OPEN

    def test_rejected_calls_counted(self):
        """Rejected calls are counted when circuit is open."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=10.0,
        )

        cb.record_failure(Exception("Error"))
        assert cb.state == CircuitState.OPEN

        cb.record_rejection()
        assert cb.stats.rejected_calls == 1


class TestCircuitBreakerRegistry:
    """Test CircuitBreakerRegistry singleton."""

    def setup_method(self):
        """Clear registry before each test."""
        CircuitBreakerRegistry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        CircuitBreakerRegistry.clear()

    def test_registry_singleton(self):
        """Registry is a singleton."""
        cb1 = CircuitBreakerRegistry.get_or_create("test1")
        cb2 = CircuitBreakerRegistry.get_or_create("test1")
        assert cb1 is cb2

    def test_registry_get_all_status(self):
        """Registry returns status of all circuit breakers."""
        cb1 = CircuitBreakerRegistry.get_or_create("test1", failure_threshold=3)
        cb2 = CircuitBreakerRegistry.get_or_create("test2", failure_threshold=5)

        status = CircuitBreakerRegistry.get_all_status()
        assert "test1" in status
        assert "test2" in status
        assert status["test1"]["failure_threshold"] == 3
        assert status["test2"]["failure_threshold"] == 5

    def test_registry_reset_all(self):
        """Registry can reset all circuit breakers."""
        cb1 = CircuitBreakerRegistry.get_or_create("test1", failure_threshold=3)
        cb2 = CircuitBreakerRegistry.get_or_create("test2", failure_threshold=5)

        # Open both circuits
        for _ in range(3):
            cb1.record_failure(Exception(f"Error {_}"))

        for _ in range(5):
            cb2.record_failure(Exception(f"Error {_}"))

        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.OPEN

        # Reset all
        CircuitBreakerRegistry.reset_all()

        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED


class TestCircuitBreakerAsync:
    """Test CircuitBreaker async operations."""

    @pytest.mark.asyncio
    async def test_async_call_success(self):
        """Async call succeeds through circuit breaker."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=10.0,
        )

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_async_call_failure(self):
        """Async call failure is recorded."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=10.0,
        )

        async def failing_func():
            raise ValueError("This should fail")

        with pytest.raises(ValueError):
            await cb.call(failing_func)

        assert cb.stats.failed_calls == 1

    @pytest.mark.asyncio
    async def test_async_call_rejected_when_open(self):
        """Async call is rejected when circuit is open."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=10.0,
        )
        async def success_func():
            return "success"

        # Open the circuit
        cb.record_failure(Exception("Error"))

        with pytest.raises(CircuitOpenError):
            await cb.call(success_func)


class TestCircuitBreakerStats:
    """Test CircuitBreaker statistics."""

    def test_stats_tracking(self):
        """Stats are properly tracked."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=5,
            recovery_timeout=60.0,
        )

        assert cb.stats.total_calls == 0
        assert cb.stats.successful_calls == 0
        assert cb.stats.failed_calls == 0
        assert cb.stats.rejected_calls == 0
        assert cb.stats.state_changes == 0

        # Record some activity
        cb.record_success()
        assert cb.stats.total_calls == 1
        assert cb.stats.successful_calls == 1
        assert cb.stats.state_changes == 0

        cb.record_failure(Exception("Error"))
        assert cb.stats.total_calls == 2
        assert cb.stats.failed_calls == 1
        assert cb.stats.state_changes == 0

        cb._transition_to_open()
        assert cb.stats.state_changes == 1

        cb.record_rejection()
        assert cb.stats.rejected_calls == 1

    def test_get_status(self):
        """Get status returns complete information."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=5,
            recovery_timeout=60.0,
        )
        status = cb.get_status()
        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert status["failure_threshold"] == 5
        assert status["recovery_timeout"] == 60.0
        assert "stats" in status
        assert "total_calls" in status["stats"]
        assert "state_changes" in status["stats"]
