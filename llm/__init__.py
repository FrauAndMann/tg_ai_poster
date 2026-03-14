"""
LLM module for TG AI Poster.

Contains abstract base class and provider-specific adapters.
"""

from .base import BaseLLMAdapter, LLMResponse
from .openai_adapter import OpenAIAdapter
from .claude_adapter import ClaudeAdapter
from .deepseek_adapter import DeepSeekAdapter
from .glm_adapter import GLMAdapter
from .claude_cli_adapter import ClaudeCLIAdapter

__all__ = [
    "BaseLLMAdapter",
    "LLMResponse",
    "OpenAIAdapter",
    "ClaudeAdapter",
    "DeepSeekAdapter",
    "GLMAdapter",
    "ClaudeCLIAdapter",
]


def get_llm_adapter(provider: str, **kwargs) -> BaseLLMAdapter:
    """
    Factory function to get the appropriate LLM adapter.

    Args:
        provider: Provider name (openai, claude, deepseek, glm, claude-cli)
        **kwargs: Adapter-specific configuration

    Returns:
        BaseLLMAdapter: Configured adapter instance
    """
    adapters = {
        "openai": OpenAIAdapter,
        "claude": ClaudeAdapter,
        "deepseek": DeepSeekAdapter,
        "glm": GLMAdapter,
        "claude-cli": ClaudeCLIAdapter,
    }

    adapter_class = adapters.get(provider)
    if adapter_class is None:
        raise ValueError(f"Unknown LLM provider: {provider}")

    return adapter_class(**kwargs)
