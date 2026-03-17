"""
Anthropic Claude LLM adapter implementation.

Supports Claude 3.5 Sonnet, Claude 3 Opus, and other Claude models.
"""

from __future__ import annotations

from typing import Any, Optional

from anthropic import AsyncAnthropic

from core.logger import get_logger
from llm.base import BaseLLMAdapter, LLMResponse, Message

logger = get_logger(__name__)


class ClaudeAdapter(BaseLLMAdapter):
    """
    Anthropic Claude API adapter.

    Supports Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Sonnet, and Haiku.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: Optional[str] = None,
        max_tokens: int = 800,
        temperature: float = 0.85,
        **kwargs,
    ) -> None:
        """
        Initialize Claude adapter.

        Args:
            api_key: Anthropic API key
            model: Model name (default: claude-sonnet-4-20250514)
            base_url: Optional base URL (for proxies)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0 for Claude)
            **kwargs: Additional options passed to AsyncAnthropic
        """
        super().__init__(api_key, model, base_url, max_tokens, temperature, **kwargs)

        # Initialize AsyncAnthropic client
        client_kwargs: dict[str, Any] = {"api_key": api_key}

        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncAnthropic(**client_kwargs)

        logger.info(f"Claude adapter initialized with model={model}")

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
            **kwargs: Additional options

        Returns:
            LLMResponse: Generated response
        """
        messages = self._build_messages(prompt, system_prompt)
        # Claude uses a separate system parameter, not system messages
        return await self.chat(messages, system_prompt=system_prompt, **kwargs)

    async def chat(
        self,
        messages: list[Message],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate response from chat messages.

        Args:
            messages: List of chat messages
            system_prompt: System prompt (Claude uses separate parameter)
            **kwargs: Additional options

        Returns:
            LLMResponse: Generated response
        """
        # Convert messages to Claude format (filter out system messages)
        claude_messages = []
        for msg in messages:
            if msg.role != "system":
                claude_messages.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                )

        # Build request options
        request_options: dict[str, Any] = {
            "model": self.model,
            "messages": claude_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        # Claude uses separate system parameter
        if system_prompt:
            request_options["system"] = system_prompt

        # Add temperature (Claude range is 0.0-1.0)
        temperature = kwargs.get("temperature", self.temperature)
        request_options["temperature"] = min(temperature, 1.0)

        # Add optional parameters
        optional_params = ["top_p", "top_k", "stop_sequences"]
        for param in optional_params:
            if param in kwargs:
                request_options[param] = kwargs[param]

        logger.debug(f"Sending request to Claude: model={self.model}")

        try:
            response = await self.client.messages.create(**request_options)

            # Extract response data
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            finish_reason = response.stop_reason or "stop"

            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            }

            logger.debug(
                f"Claude response: tokens={usage['total_tokens']}, "
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
            logger.error(f"Claude API error: {e}")
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
        claude_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.role != "system"
        ]

        request_options: dict[str, Any] = {
            "model": self.model,
            "messages": claude_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": True,
        }

        if system_prompt:
            request_options["system"] = system_prompt

        logger.debug(f"Starting streaming request to Claude: model={self.model}")

        async with self.client.messages.stream(**request_options) as stream:
            async for text in stream.text_stream:
                yield text

    async def close(self) -> None:
        """Close the Claude client."""
        await self.client.close()
        logger.info("Claude client closed")
