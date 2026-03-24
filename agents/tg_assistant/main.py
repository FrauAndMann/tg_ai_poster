#!/usr/bin/env python3
"""
TG Assistant - Coding agent for TG AI Poster project.

This agent helps with code review, debugging, and development tasks
for the autonomous Telegram publishing system.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    query,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ClaudeSDKError,
    CLINotFoundError,
    ProcessError,
)

# Project root directory (parent of agents/tg_assistant)
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# System prompt for the coding agent
SYSTEM_PROMPT = """You are TG Assistant, an expert coding agent for the TG AI Poster project.

TG AI Poster is an autonomous Telegram publishing system with:
- RSS feed collection and content filtering
- LLM-powered content generation (supports OpenAI, Claude, DeepSeek, GLM)
- Editorial validation and quality scoring
- Telegram channel publishing (Bot API or Telethon)
- Vector-based deduplication using ChromaDB
- Async pipeline architecture with event-driven design

Your role is to help with:
1. Code review and quality improvements
2. Debugging pipeline issues
3. Adding new features following existing patterns
4. Explaining code architecture
5. Running tests and fixing failures

Guidelines:
- Follow existing code patterns and conventions
- Use async/await throughout (project uses asyncio)
- Maintain type hints with Pydantic models
- Keep functions focused and modular
- Write tests for new functionality

The project uses:
- Python 3.11+
- SQLAlchemy async with SQLite/PostgreSQL
- loguru for logging
- APScheduler for scheduling
- pytest for testing

Always explain your reasoning before making changes."""


async def run_assistant(prompt: str, cwd: Path | None = None) -> None:
    """
    Run the TG Assistant with a given prompt (single command mode).

    Args:
        prompt: The user's request/question
        cwd: Working directory (defaults to project root)
    """
    work_dir = cwd or PROJECT_ROOT

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        cwd=str(work_dir),
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "Glob",
            "Grep",
            "Bash",
        ],
        permission_mode="acceptEdits",  # Auto-accept file edits
        max_turns=50,
    )

    print(f"\n{'='*60}")
    print(f"TG Assistant - Working in: {work_dir}")
    print(f"{'='*60}\n")
    print(f"Request: {prompt}\n")
    print("-" * 60, "\n")

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"\n[Using tool: {block.name}]")
            elif isinstance(message, ResultMessage):
                print(f"\n{'-'*60}")
                if message.is_error:
                    print(f"Task completed with errors after {message.num_turns} turns")
                else:
                    print(f"Task completed successfully in {message.num_turns} turns")
                    if message.total_cost_usd:
                        print(f"Cost: {message.total_cost_usd:.4f}")
                    if message.duration_ms:
                        print(f"Duration: {message.duration_ms / 1000:.1f}s")

    except CLINotFoundError:
        print("ERROR: Claude Code CLI not found.")
        print("Please install it: https://docs.claude.com/en/docs/installation")
        sys.exit(1)
    except ProcessError as e:
        print(f"ERROR: Process failed with exit code {e.exit_code}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        sys.exit(1)
    except ClaudeSDKError as e:
        print(f"ERROR: SDK error - {e}")
        sys.exit(1)


async def interactive_mode() -> None:
    """Run TG Assistant in interactive REPL mode with conversation context.

    Uses ClaudeSDKClient to maintain conversation context across multiple
    exchanges, so Claude remembers previous messages in the session.
    """
    print("\n" + "=" * 60)
    print("TG Assistant - Interactive Mode")
    print("=" * 60)
    print(f"Project: {PROJECT_ROOT}")
    print("\nCommands:")
    print("  - Type your request and press Enter")
    print("  - 'quit' or 'exit' to stop")
    print("  - 'new' to start a fresh session")
    print("  - 'help' for usage tips")
    print("-" * 60 + "\n")

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        cwd=str(PROJECT_ROOT),
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "Glob",
            "Grep",
            "Bash",
        ],
        permission_mode="acceptEdits",
        max_turns=50,
    )

    turn_count = 0

    try:
        async with ClaudeSDKClient(options=options) as client:
            while True:
                try:
                    user_input = input("\n> ").strip()

                    if not user_input:
                        continue

                    if user_input.lower() in ("quit", "exit", "q"):
                        print("\nGoodbye!")
                        break

                    if user_input.lower() == "new":
                        # Disconnect and reconnect for a fresh session
                        await client.disconnect()
                        await client.connect()
                        turn_count = 0
                        print("Started new conversation session (previous context cleared)")
                        continue

                    if user_input.lower() == "help":
                        print("""
Usage Tips:
- "Review the pipeline orchestrator code"
- "Find all uses of the LLM adapter"
- "Add error handling to publisher.py"
- "Run tests and fix any failures"
- "Explain how the topic selector works"
- "Debug why posts aren't being published"
- "new" - Start a fresh conversation session
""")
                        continue

                    # Send message - Claude remembers all previous messages in this session
                    await client.query(user_input)
                    turn_count += 1

                    # Process response
                    print()
                    async for message in client.receive_response():
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    print(block.text)
                                elif isinstance(block, ToolUseBlock):
                                    print(f"[Using tool: {block.name}]")
                        elif isinstance(message, ResultMessage):
                            if message.is_error:
                                print(f"\n[Task completed with errors after {message.num_turns} turns]")
                            else:
                                print(f"\n[Turn {turn_count} completed]")
                                if message.total_cost_usd:
                                    print(f"[Cost: ${message.total_cost_usd:.4f}]")
                                if message.duration_ms:
                                    print(f"[Duration: {message.duration_ms / 1000:.1f}s]")

                except KeyboardInterrupt:
                    print("\n\nInterrupted. Type 'quit' to exit or 'new' for fresh session.")
                except EOFError:
                    break

    except CLINotFoundError:
        print("ERROR: Claude Code CLI not found.")
        print("Please install it: https://docs.claude.com/en/docs/installation")
        sys.exit(1)
    except ProcessError as e:
        print(f"ERROR: Process failed with exit code {e.exit_code}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        sys.exit(1)
    except ClaudeSDKError as e:
        print(f"ERROR: SDK error - {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("Get your API key from: https://console.anthropic.com/")
        print("\nSet it with:")
        print("  export ANTHROPIC_API_KEY='your-key-here'  # Linux/Mac")
        print("  set ANTHROPIC_API_KEY=your-key-here       # Windows")
        sys.exit(1)

    if len(sys.argv) > 1:
        # Single command mode
        prompt = " ".join(sys.argv[1:])
        asyncio.run(run_assistant(prompt))
    else:
        # Interactive mode
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
