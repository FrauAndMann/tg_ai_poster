"""
Claude Code CLI LLM Adapter.

Uses Claude Code CLI (with GLM Coding Plan) for LLM calls.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from typing import Optional

from loguru import logger

from llm.base import BaseLLMAdapter, LLMResponse, Message


class ClaudeCLIAdapter(BaseLLMAdapter):
    """LLM adapter that uses Claude Code CLI with GLM Coding Plan."""

    def __init__(
        self,
        model: str = "glm-4.7",
        max_tokens: int = 2000,
        temperature: float = 0.9,
        timeout: float = 180.0,
        claude_path: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            api_key="cli-mode",
            model=model,
            base_url="cli",
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        self.timeout = timeout
        self.claude_path = claude_path or self._find_claude_cli()
        self._verify_cli()

    def _find_claude_cli(self) -> str:
        claude_path = shutil.which("claude")
        return claude_path if claude_path else "claude"

    def _verify_cli(self) -> None:
        if not shutil.which("claude"):
            logger.warning("Claude CLI not found in PATH.")

    def _build_full_prompt(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        parts = []
        if system_prompt:
            parts.append(f"[SYSTEM]\n{system_prompt}\n[/SYSTEM]\n")
        parts.append(prompt)
        return "\n".join(parts)

    def _clean_response(self, content: str) -> str:
        ansi_escape = re.compile(r'\x1B(?:[@-Z\-_]|\[[0-?]*[ -/]*[@-~])')
        content = ansi_escape.sub('', content)
        for prefix in ["Here's the response:", "Response:", "Output:", "Result:"]:
            if content.startswith(prefix):
                content = content[len(prefix):].strip()
        return content.strip()

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        full_prompt = self._build_full_prompt(prompt, system_prompt)

        # Get temperature from kwargs or use default
        temperature = kwargs.get("temperature", self.temperature)

        logger.debug(f"Calling Claude CLI, prompt length: {len(full_prompt)}, temp={temperature}")

        try:
            # Build CLI arguments
            cli_args = [
                self.claude_path,
                "--print",
                "--tools", "",
                "--no-session-persistence",
            ]

            # Add temperature if different from default
            # Note: Claude CLI may not support --temperature flag directly
            # Instead, we include it in the prompt for GLM models
            if temperature is not None and temperature != self.temperature:
                full_prompt = f"[Temperature: {temperature}]\n\n{full_prompt}"

            # Use stdin to pass prompt - this avoids CLI treating it as a coding task
            process = await asyncio.create_subprocess_exec(
                *cli_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=full_prompt.encode("utf-8")),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                raise TimeoutError(f"CLI call timed out after {self.timeout}s")

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace").strip()
                logger.error(f"Claude CLI error: {error_msg}")
                raise RuntimeError(f"CLI failed: {error_msg}")

            content = stdout.decode("utf-8", errors="replace").strip()
            content = self._clean_response(content)

            logger.debug(f"Claude CLI response: {len(content)} chars")

            return LLMResponse(
                content=content,
                model=self.model,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                finish_reason="stop",
                raw_response={"content": content},
            )

        except FileNotFoundError:
            raise RuntimeError("Claude CLI not found. Install Claude Code first.")
        except Exception as e:
            logger.error(f"Claude CLI error: {e}")
            raise

    async def chat(
        self,
        messages: list[Message],
        **kwargs,
    ) -> LLMResponse:
        prompt_parts = []
        system_prompt = None

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")

        prompt = prompt_parts[-1].replace("User: ", "") if prompt_parts else ""

        if len(prompt_parts) > 1:
            history = "\n".join(prompt_parts[:-1])
            prompt = f"Conversation:\n{history}\n\nCurrent request: {prompt}"

        return await self.generate(prompt, system_prompt=system_prompt, **kwargs)

    async def close(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"ClaudeCLIAdapter(model={self.model})"
