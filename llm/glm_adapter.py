"""
GLM-5 LLM Adapter for Z.AI API.

OpenAI-compatible API implementation for GLM-5 model.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx
from loguru import logger

from llm.base import BaseLLMAdapter, LLMResponse, Message


class GLMAdapter(BaseLLMAdapter):
    """
    LLM adapter for GLM-5 from Z.AI.

    Uses OpenAI-compatible API format.

    Example:
        adapter = GLMAdapter(
            api_key="your-api-key",
            model="glm-5"
        )
        response = await adapter.generate("Write a post about AI")
        print(response.content)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "glm-5",
        base_url: str = "https://api.z.ai/api/paas/v4",
        max_tokens: int = 2000,
        temperature: float = 0.9,
        timeout: float = 120.0,
        max_retries: int = 3,
        **kwargs,
    ):
        """
        Initialize GLM adapter.

        Args:
            api_key: Z.AI API key
            model: Model name (default: glm-5)
            base_url: API base URL
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for rate limits
        """
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate text using GLM-5.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional options (temperature, max_tokens)

        Returns:
            LLMResponse: Generated response
        """
        client = await self._get_client()

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request body
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        try:
            # Retry logic for rate limits
            for attempt in range(self.max_retries):
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=body,
                )

                if response.status_code == 429:
                    # Rate limit - wait and retry
                    wait_time = 2 ** (attempt + 1)  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}")
                    await asyncio.sleep(wait_time)
                    continue

                if response.status_code != 200:
                    logger.error(f"GLM API error: {response.status_code} - {response.text}")

                response.raise_for_status()
                break
            else:
                raise httpx.HTTPStatusError("Max retries exceeded", request=None, response=response)

            data = response.json()

            # Extract response text
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Extract usage info
            usage = data.get("usage", {})

            return LLMResponse(
                content=content,
                model=data.get("model", self.model),
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                finish_reason=data.get("choices", [{}])[0].get("finish_reason", "stop"),
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"GLM API HTTP error: {e}")
            logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"GLM API error: {e}")
            raise

    async def chat(
        self,
        messages: list[Message],
        **kwargs,
    ) -> LLMResponse:
        """
        Generate response from a chat conversation.

        Args:
            messages: List of chat messages
            **kwargs: Additional options

        Returns:
            LLMResponse: Generated response
        """
        client = await self._get_client()

        # Convert Message objects to dict format
        formatted_messages = [msg.to_dict() for msg in messages]

        # Build request body
        body = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=body,
            )
            response.raise_for_status()
            data = response.json()

            # Extract response text
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Extract usage info
            usage = data.get("usage", {})

            return LLMResponse(
                content=content,
                model=data.get("model", self.model),
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                finish_reason=data.get("choices", [{}])[0].get("finish_reason", "stop"),
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"GLM API HTTP error: {e}")
            logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"GLM API error: {e}")
            raise

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def __repr__(self) -> str:
        return f"GLMAdapter(model={self.model})"
