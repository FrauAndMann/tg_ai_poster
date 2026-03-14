# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TG AI Poster is an autonomous AI-powered Telegram channel management system that generates and publishes content 24/7 using LLM providers (OpenAI, Claude, DeepSeek, GLM-5 via Claude CLI).

## Commands

### Running the Application

```bash
# Initialize database (first time setup)
python main.py --init-db

# Run once for testing (no publishing)
python main.py --dry-run --once

# Run once and publish
python main.py --once

# Start scheduled posting
python main.py

# Debug mode
python main.py --debug --dry-run --once
```

### Setup

```bash
# Interactive setup wizard
python setup.py
```

### Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_pipeline.py

# Run with coverage
pytest --cov=. --cov-report=html
```

## Architecture

### Pipeline Flow

The content generation pipeline is orchestrated by `PipelineOrchestrator` (`pipeline/orchestrator.py`) and runs through these stages:

1. **Source Collection** (`pipeline/source_collector.py`) - RSS feeds, HackerNews, ProductHunt
2. **Content Filtering** (`pipeline/content_filter.py`) - Relevance scoring and deduplication
3. **Topic Selection** (`pipeline/topic_selector.py`) - LLM-powered topic selection
4. **Source Verification** (`pipeline/source_verification.py`) - Credibility checking
5. **Post Generation** (`pipeline/llm_generator.py`) - LLM content creation
6. **Editorial Review** (`pipeline/editor_review.py`) - AI editor review
7. **Quality Check** (`pipeline/quality_checker.py`) - Validation and semantic dedup
8. **Formatting** (`pipeline/formatter.py`, `pipeline/telegram_formatter.py`) - Telegram MarkdownV2
9. **Media Generation** (`pipeline/media_prompt_generator.py`) - Image prompt generation
10. **Publishing** - Via Bot API or Telethon

### Key Modules

- **`core/`** - Configuration (`config.py`), logging (`logger.py`), scheduling (`scheduler.py`)
- **`llm/`** - LLM adapters with common interface (`base.py`). Implementations: OpenAI, Claude, Claude CLI (for GLM-5), DeepSeek
- **`memory/`** - SQLAlchemy models (`models.py`), database (`database.py`), post/topic stores, vector store (ChromaDB), feedback loop
- **`publisher/`** - Abstract publisher (`base.py`), Bot API (`bot_publisher.py`), Telethon mode
- **`pipeline/`** - All content generation stages

### Configuration

Two-level configuration:
- **`config.yaml`** - Non-secret settings (schedule, channel topic, sources, etc.)
- **`.env`** - Secrets (API keys, tokens) - NEVER commit this file

Environment variables in config.yaml use `${VAR_NAME}` syntax for substitution.

### LLM Provider Selection

Configured in `config.yaml` under `llm.provider`:
- `openai` - OpenAI GPT models
- `claude` - Anthropic Claude via API
- `claude-cli` - GLM-5 via Claude Code CLI
- `deepseek` - DeepSeek models

### Posting Modes

- **Bot API** (`posting_mode: "bot"`) - Official Telegram Bot API, safe, requires bot as channel admin
- **Telethon** (`posting_mode: "telethon"`) - User account mode, higher risk, no bot label

### Schedule Types

Configured in `config.yaml` under `schedule.type`:
- `fixed` - Post at specific times (e.g., `["09:30", "14:00", "20:00"]`)
- `interval` - Post every N hours
- `random` - Random times within a time window

## Database Models

Key SQLAlchemy models in `memory/models.py`:
- **Post** - Published content with engagement metrics, quality scores, source tracking
- **Topic** - Topic tracking for deduplication
- **Source** - RSS/API source management
- **StyleProfile** - Learned writing style characteristics

## Important Files

- `main.py` - Entry point with CLI argument parsing
- `setup.py` - Interactive first-run configuration wizard
- `config.yaml` - Main configuration file
- `.env.example` - Template for environment variables
- `data/tg_poster.db` - SQLite database (default)

## Development Notes

- All async code uses `async/await` pattern
- Type hints are used throughout the codebase
- LLM adapters implement `BaseLLMAdapter` interface from `llm/base.py`
- Pipeline stages are designed to be independent and testable
- The system uses ChromaDB for semantic deduplication of posts
- Rate limiting and retry logic is handled via `tenacity` library
