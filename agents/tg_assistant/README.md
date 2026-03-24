# TG Assistant

Coding agent for the TG AI Poster project powered by Claude Agent SDK.

## What it does

- Code review and analysis
- Bug debugging and fixing
- Understanding project architecture
- Running tests and fixing failures
- Adding new features following project conventions

## Prerequisites

- Python 3.11+
- Claude Code CLI (bundled with SDK)
- ANTHROPIC_API_KEY environment variable

## Setup

1. Copy `.env.example` to `.env` and add your API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your key from https://console.anthropic.com/
   ```

2. Install dependencies:
   ```bash
   cd D:\tg_ai_poster
   pip install -r requirements.txt
   ```

## Usage

### Interactive Mode
```bash
python -m agents.tg_assistant
```

### Single Command Mode
```bash
python -m agents.tg_assistant "Review the pipeline orchestrator code"
python -m agents.tg_assistant "Find all uses of the LLM adapter"
python -m agents.tg_assistant "Debug why posts aren't being published"
```

### Example Commands

- "Review the pipeline orchestrator code"
- "Find all uses of the LLM adapter"
- "Add error handling to publisher.py"
- "Run tests and fix any failures"
- "Explain how the topic selector works"

## Architecture

The agent has access to these tools:
- **Read** - Read files from the project
- **Write** - Create new files
- **Edit** - Modify existing files
- **Glob** - Find files by pattern
- **Grep** - Search file contents
- **Bash** - Run commands (tests, linting, etc.)

All file edits are auto-accepted for a smooth workflow.

## Resources

- [Claude Agent SDK Documentation](https://docs.claude.com/en/api/agent-sdk/python)
- [TG AI Poster CLAUDE.md](../../CLAUDE.md)
