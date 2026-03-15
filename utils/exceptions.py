"""
Exception classification for Circuit Breaker and error handling.

Categorizes exceptions to determine appropriate responses:
- Retryable vs non-retryable
- Transient vs permanent failures
- Service-specific error types
"""

from __future__ import annotations

from typing import Optional, Type


class TgPosterException(Exception):
    """Base exception for TG AI Poster application."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - {self.details}"
        return self.message


# =============================================================================
# LLM Exceptions
# =============================================================================

class LLMException(TgPosterException):
    """Base exception for LLM-related errors."""
    pass


class LLMRateLimitError(LLMException):
    """
    Rate limit exceeded.

    Triggered when API returns 429 or similar rate limiting response.
    Should trigger circuit breaker after multiple occurrences.
    """
    pass


class LLMServiceUnavailableError(LLMException):
    """
    LLM service is temporarily unavailable.

    Triggered by 503, timeouts, or connection errors.
    Transient error - should retry with backoff.
    """
    pass


class LLMAuthenticationError(LLMException):
    """
    Authentication failed.

    Triggered by 401 or 403 responses.
    Permanent error - should NOT retry.
    """
    pass


class LLMContentFilterError(LLMException):
    """
    Content filter triggered.

    Triggered when request is blocked by content safety filters.
    Should NOT retry with same content.
    """
    pass


class LLMQuotaExceededError(LLMException):
    """
    API quota exceeded.

    Triggered when account quota/balance is depleted.
    Should fallback to alternative provider.
    """
    pass


# =============================================================================
# Telegram Exceptions
# =============================================================================

class TelegramException(TgPosterException):
    """Base exception for Telegram-related errors."""
    pass


class TelegramRateLimitError(TelegramException):
    """
    Telegram API rate limit exceeded.

    Triggered by FloodWait or similar rate limiting.
    Should wait and retry.
    """
    pass


class TelegramServiceUnavailableError(TelegramException):
    """
    Telegram service is temporarily unavailable.

    Transient error - should retry with backoff.
    """
    pass


class TelegramChatNotFoundError(TelegramException):
    """
    Chat/channel not found.

    Permanent error - check channel_id configuration.
    """
    pass


class TelegramForbiddenError(TelegramException):
    """
    Bot lacks permission.

    Permanent error - check bot permissions in channel.
    """
    pass


# =============================================================================
# Source Collection Exceptions
# =============================================================================

class SourceException(TgPosterException):
    """Base exception for source collection errors."""
    pass


class SourceRateLimitError(SourceException):
    """
    Source rate limit exceeded.

    Should back off and retry later.
    """
    pass


class SourceUnavailableError(SourceException):
    """
    Source is temporarily unavailable.

    Transient error - should retry.
    """
    pass


class SourceParseError(SourceException):
    """
    Failed to parse source content.

    May indicate changed format or corrupt data.
    """
    pass


# =============================================================================
# Exception Classification
# =============================================================================

# Exceptions that indicate temporary failures (should retry)
TRANSIENT_EXCEPTIONS: tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    LLMServiceUnavailableError,
    LLMRateLimitError,
    TelegramServiceUnavailableError,
    TelegramRateLimitError,
    SourceUnavailableError,
    SourceRateLimitError,
)

# Exceptions that indicate permanent failures (should NOT retry)
PERMANENT_EXCEPTIONS: tuple[Type[Exception], ...] = (
    LLMAuthenticationError,
    LLMContentFilterError,
    TelegramChatNotFoundError,
    TelegramForbiddenError,
)

# Exceptions that should trigger circuit breaker
CIRCUIT_BREAKER_EXCEPTIONS: tuple[Type[Exception], ...] = (
    LLMServiceUnavailableError,
    LLMRateLimitError,
    LLMQuotaExceededError,
    TelegramServiceUnavailableError,
    TelegramRateLimitError,
    SourceUnavailableError,
    SourceRateLimitError,
    ConnectionError,
    TimeoutError,
)


def is_transient_error(error: Exception) -> bool:
    """
    Check if error is transient and should be retried.

    Args:
        error: Exception to check

    Returns:
        bool: True if error is transient
    """
    return isinstance(error, TRANSIENT_EXCEPTIONS)


def is_permanent_error(error: Exception) -> bool:
    """
    Check if error is permanent and should NOT be retried.

    Args:
        error: Exception to check

    Returns:
        bool: True if error is permanent
    """
    return isinstance(error, PERMANENT_EXCEPTIONS)


def should_trigger_circuit_breaker(error: Exception) -> bool:
    """
    Check if error should trigger circuit breaker.

    Args:
        error: Exception to check

    Returns:
        bool: True if error should trigger circuit breaker
    """
    return isinstance(error, CIRCUIT_BREAKER_EXCEPTIONS)


def classify_http_error(status_code: int, service: str = "unknown") -> TgPosterException:
    """
    Classify HTTP error by status code.

    Args:
        status_code: HTTP status code
        service: Service name for context

    Returns:
        Appropriate exception type
    """
    details = {"status_code": status_code, "service": service}

    if status_code == 401:
        return LLMAuthenticationError("Authentication failed", details)
    elif status_code == 403:
        if "telegram" in service.lower():
            return TelegramForbiddenError("Permission denied", details)
        return LLMAuthenticationError("Access forbidden", details)
    elif status_code == 404:
        if "telegram" in service.lower():
            return TelegramChatNotFoundError("Chat not found", details)
        return TgPosterException("Resource not found", details)
    elif status_code == 429:
        if "telegram" in service.lower():
            return TelegramRateLimitError("Rate limit exceeded", details)
        return LLMRateLimitError("Rate limit exceeded", details)
    elif status_code == 503:
        if "telegram" in service.lower():
            return TelegramServiceUnavailableError("Service unavailable", details)
        return LLMServiceUnavailableError("Service unavailable", details)
    elif status_code >= 500:
        if "telegram" in service.lower():
            return TelegramServiceUnavailableError("Server error", details)
        return LLMServiceUnavailableError("Server error", details)
    else:
        return TgPosterException(f"HTTP error {status_code}", details)
