"""
DeepSeek LLM adapter implementation.

DeepSeek uses OpenAI-compatible API, so this extends OpenAI adapter.
"""

from __future__ import annotations

from typing import Optional

from core.logger import get_logger
from llm.base import LLMResponse
from llm.openai_adapter import OpenAIAdapter

logger = get_logger(__name__)


class DeepSeekAdapter(OpenAIAdapter):
    """
    DeepSeek API adapter.

    Uses OpenAI-compatible API format with DeepSeek's base URL.
    Supports DeepSeek-V3, DeepSeek-Chat, and DeepSeek-Coder models.
    """

    # DeepSeek API base URL
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"

    # Available models
    MODELS = {
        "deepseek-chat": "General purpose chat model",
        "deepseek-coder": "Code-specialized model",
        "deepseek-reasoner": "Reasoning model (R1)",
    }

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: Optional[str] = None,
        max_tokens: int = 800,
        temperature: float = 0.85,
        **kwargs,
    ) -> None:
        """
        Initialize DeepSeek adapter.

        Args:
            api_key: DeepSeek API key
            model: Model name (default: deepseek-chat)
            base_url: Optional base URL (default: DeepSeek API URL)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-2.0)
            **kwargs: Additional options
        """
        # Use DeepSeek base URL if not specified
        if base_url is None:
            base_url = self.DEFAULT_BASE_URL

        super().__init__(api_key, model, base_url, max_tokens, temperature, **kwargs)

        logger.info(f"DeepSeek adapter initialized with model={model}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate text from a prompt.

        DeepSeek supports reasoning models that output thinking process.
        This is handled automatically.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional options

        Returns:
            LLMResponse: Generated response
        """
        # DeepSeek reasoner model has special handling
        if "reasoner" in self.model.lower():
            return await self._generate_with_reasoning(prompt, system_prompt, **kwargs)

        return await super().generate(prompt, system_prompt, **kwargs)

    async def _generate_with_reasoning(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate with reasoning model (R1).

        Reasoning models include a thinking process before the answer.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional options

        Returns:
            LLMResponse: Generated response with reasoning stripped
        """
        messages = self._build_messages(prompt, system_prompt)
        response = await self.chat(messages, **kwargs)

        # DeepSeek R1 includes <think/> tags for reasoning
        content = response.content

        # Extract content after </think/> tag if present
        if "</think/>" in content:
            content = content.split("</think/>")[-1].strip()
        elif "<think/>" in content:
            # Handle self-closing tag case
            parts = content.split("<think/>")
            if len(parts) > 1:
                content = parts[-1].strip()

        response.content = content
        return response

    def get_model_info(self) -> dict:
        """
        Get information about the current model.

        Returns:
            dict: Model information
        """
        info = super().get_model_info()
        info["provider"] = "deepseek"
        info["description"] = self.MODELS.get(self.model, "Unknown model")
        return info
