"""
OpenAI LLM adapter implementation.

Supports GPT-4o, GPT-4-turbo, and other OpenAI models.
"""

from __future__ import annotations

from typing import Any, Optional

from openai import AsyncOpenAI

from core.logger import get_logger
from llm.base import BaseLLMAdapter, LLMResponse, Message

logger = get_logger(__name__)


class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI API adapter.

    Supports all OpenAI chat models including GPT-4o, GPT-4-turbo, etc.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        max_tokens: int = 800,
        temperature: float = 0.85,
        **kwargs,
    ) -> None:
        """
        Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key
            model: Model name (default: gpt-4o)
            base_url: Optional base URL (for proxies or Azure)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-2.0)
            **kwargs: Additional options passed to AsyncOpenAI
        """
        super().__init__(api_key, model, base_url, max_tokens, temperature, **kwargs)

        # Initialize AsyncOpenAI client
        client_kwargs: dict[str, Any] = {"api_key": api_key}

        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncOpenAI(**client_kwargs)

        logger.info(f"OpenAI adapter initialized with model={model}")

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
            **kwargs: Additional options (top_p, presence_penalty, etc.)

        Returns:
            LLMResponse: Generated response
        """
        messages = self._build_messages(prompt, system_prompt)
        return await self.chat(messages, **kwargs)

    async def chat(
        self,
        messages: list[Message],
        **kwargs,
    ) -> LLMResponse:
        """
        Generate response from chat messages.

        Args:
            messages: List of chat messages
            **kwargs: Additional options

        Returns:
            LLMResponse: Generated response
        """
        # Convert messages to OpenAI format
        openai_messages = [msg.to_dict() for msg in messages]

        # Build request options
        request_options: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        # Add optional parameters
        optional_params = ["top_p", "presence_penalty", "frequency_penalty", "stop"]
        for param in optional_params:
            if param in kwargs:
                request_options[param] = kwargs[param]

        logger.debug(f"Sending request to OpenAI: model={self.model}")

        try:
            response = await self.client.chat.completions.create(**request_options)

            # Extract response data
            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason

            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            logger.debug(
                f"OpenAI response: tokens={usage['total_tokens']}, "
                f"finish_reason={finish_reason}"
            )

            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=finish_reason,
                raw_response=response.model_dump(),
            )

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def generate_streaming(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ):
        """
        Generate text with streaming (async generator).

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional options

        Yields:
            str: Text chunks
        """
        messages = self._build_messages(prompt, system_prompt)
        openai_messages = [msg.to_dict() for msg in messages]

        request_options: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }

        logger.debug(f"Starting streaming request to OpenAI: model={self.model}")

        stream = await self.client.chat.completions.create(**request_options)

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Note: This is an approximation. For exact counts, use tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            int: Estimated token count
        """
        # Simple approximation: ~4 characters per token for English
        # For Russian, it's roughly similar
        return len(text) // 4

    async def close(self) -> None:
        """Close the OpenAI client."""
        await self.client.close()
        logger.info("OpenAI client closed")
