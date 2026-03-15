"""
Utility module for TG AI Poster.

Contains helper functions, retry logic, rate limiting, validators,
circuit breaker, and exception handling.
"""

from .retry import with_retry, RetryConfig
from .rate_limiter import RateLimiter, TokenBucket
from .validators import (
    check_duplicate,
    check_forbidden_words,
    check_length,
    check_telegram_markdown,
    validate_post,
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    CircuitBreakerRegistry,
    with_circuit_breaker,
)
from .exceptions import (
    TgPosterException,
    # LLM exceptions
    LLMException,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMQuotaExceededError,
    # Telegram exceptions
    TelegramException,
    TelegramRateLimitError,
    TelegramServiceUnavailableError,
    TelegramChatNotFoundError,
    TelegramForbiddenError,
    # Source exceptions
    SourceException,
    SourceRateLimitError,
    SourceUnavailableError,
    SourceParseError,
    # Classification functions
    is_transient_error,
    is_permanent_error,
    should_trigger_circuit_breaker,
    classify_http_error,
)

__all__ = [
    # Retry
    "with_retry",
    "RetryConfig",
    # Rate limiting
    "RateLimiter",
    "TokenBucket",
    # Validators
    "check_duplicate",
    "check_forbidden_words",
    "check_length",
    "check_telegram_markdown",
    "validate_post",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitOpenError",
    "CircuitBreakerRegistry",
    "with_circuit_breaker",
    # Exceptions
    "TgPosterException",
    "LLMException",
    "LLMRateLimitError",
    "LLMServiceUnavailableError",
    "LLMAuthenticationError",
    "LLMContentFilterError",
    "LLMQuotaExceededError",
    "TelegramException",
    "TelegramRateLimitError",
    "TelegramServiceUnavailableError",
    "TelegramChatNotFoundError",
    "TelegramForbiddenError",
    "SourceException",
    "SourceRateLimitError",
    "SourceUnavailableError",
    "SourceParseError",
    # Classification
    "is_transient_error",
    "is_permanent_error",
    "should_trigger_circuit_breaker",
    "classify_http_error",
]
