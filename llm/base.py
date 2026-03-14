"""
Base LLM adapter interface.

Defines the abstract interface that all LLM adapters must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LLMResponse:
    """
    Standardized response from LLM providers.

    Attributes:
        content: Generated text content
        model: Model used for generation
        usage: Token usage statistics
        finish_reason: Why generation finished
        raw_response: Original response from provider
    """

    content: str
    model: str
    usage: dict[str, int]
    finish_reason: str = "stop"
    raw_response: Optional[dict[str, Any]] = None

    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return self.usage.get("total_tokens", 0)

    @property
    def prompt_tokens(self) -> int:
        """Get prompt tokens used."""
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        """Get completion tokens used."""
        return self.usage.get("completion_tokens", 0)


@dataclass
class Message:
    """
    Chat message structure.

    Attributes:
        role: Message role (system, user, assistant)
        content: Message content
    """

    role: str  # system, user, assistant
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary format."""
        return {"role": self.role, "content": self.content}


class BaseLLMAdapter(ABC):
    """
    Abstract base class for LLM adapters.

    All LLM providers must implement this interface to ensure
    consistent behavior across different providers.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        max_tokens: int = 800,
        temperature: float = 0.85,
        **kwargs,
    ) -> None:
        """
        Initialize the LLM adapter.

        Args:
            api_key: API key for the provider
            model: Model name to use
            base_url: Optional base URL for API
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            **kwargs: Additional provider-specific options
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.extra_options = kwargs

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate text from a prompt.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional generation options

        Returns:
            LLMResponse: Generated response
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        **kwargs,
    ) -> LLMResponse:
        """
        Generate response from a chat conversation.

        Args:
            messages: List of chat messages
            **kwargs: Additional generation options

        Returns:
            LLMResponse: Generated response
        """
        pass

    async def generate_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate with automatic retry on failure.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_retries: Maximum retry attempts
            **kwargs: Additional generation options

        Returns:
            LLMResponse: Generated response

        Raises:
            Exception: If all retries fail
        """
        import asyncio

        from core.logger import get_logger

        logger = get_logger(__name__)

        last_error = None
        for attempt in range(max_retries):
            try:
                return await self.generate(prompt, system_prompt, **kwargs)
            except Exception as e:
                last_error = e
                wait_time = 2**attempt  # Exponential backoff
                logger.warning(
                    f"LLM generation failed (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

        logger.error(f"All {max_retries} attempts failed")
        raise last_error

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> list[Message]:
        """
        Build message list from prompt and system prompt.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            list[Message]: List of messages
        """
        messages = []

        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))

        messages.append(Message(role="user", content=prompt))

        return messages

    def get_model_info(self) -> dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            dict: Model information
        """
        return {
            "provider": self.__class__.__name__.replace("Adapter", "").lower(),
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
