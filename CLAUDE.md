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

# Use custom config file
python main.py --config my.yaml
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

### Code Quality

```bash
# Lint with ruff
ruff check .

# Format with ruff
ruff format .

# Type checking with mypy
mypy .
```

## Architecture

### Pipeline Flow

The content generation pipeline is orchestrated by `PipelineOrchestrator` (`pipeline/orchestrator.py`) and runs through these stages:

1. **Source Collection** (`pipeline/source_collector.py`) - RSS feeds, HackerNews, ProductHunt
2. **Content Filtering** (`pipeline/content_filter.py`) - Relevance scoring and deduplication
3. **Topic Selection** (`pipeline/topic_selector.py`) - LLM-powered topic selection
4. **Source Verification** (`pipeline/source_verification.py`) - Domain trust tiers, credibility scoring (requires min 2 sources)
5. **Context Building** (`pipeline/context_builder.py`) - Structured context with verified facts and entities
6. **Post Generation** (`pipeline/llm_generator.py`) - LLM content creation with JSON schema output
7. **Editorial Review** (`pipeline/editor_review.py`) - AI editor review, AI-phrase removal
8. **Quality Check** (`pipeline/quality_checker.py`, `pipeline/quality_rules.py`) - 50 quality rules validation, semantic dedup
9. **Media Generation** (`pipeline/media_prompt_generator.py`) - Cinematic image prompt generation
10. **Formatting** (`pipeline/telegram_formatter.py`) - Telegram MarkdownV2 with block validation
11. **Publishing** - Via Bot API or Telethon

### Key Modules

- **`core/`** - Configuration (`config.py`), logging (`logger.py`), scheduling (`scheduler.py`), events (`events.py`)
- **`llm/`** - LLM adapters with common interface (`base.py`). Implementations: OpenAI, Claude, Claude CLI (for GLM-5), DeepSeek, GLM
- **`memory/`** - SQLAlchemy models (`models.py`), database (`database.py`), post/topic stores, vector store (ChromaDB), feedback loop
- **`publisher/`** - Abstract publisher (`base.py`), Bot API (`bot_publisher.py`), Telethon publisher
- **`pipeline/`** - All content generation stages, A/B testing (`ab_test_manager.py`), draft management (`draft_manager.py`)

### Configuration

Two-level configuration:
- **`config.yaml`** - Non-secret settings (schedule, channel topic, sources, etc.)
- **`.env`** - Secrets (API keys, tokens) - NEVER commit this file
- **`config/domain_trust.json`** - Source trust tiers (tier 1/2/3)
- **`config/banned_words.json`** - Banned phrases and AI cliches

Environment variables in config.yaml use `${VAR_NAME}` syntax for substitution.

### LLM Provider Selection

Configured in `config.yaml` under `llm.provider`:
- `openai` - OpenAI GPT models
- `claude` - Anthropic Claude via API
- `claude-cli` - GLM-5 via Claude Code CLI
- `deepseek` - DeepSeek models
- `glm` - GLM models via API

Temperature varies by post type:
- `breaking` / `tool_roundup`: 0.15 (factual, precise)
- `deep_dive` / `analysis`: 0.4 (creative, analytical)

### Posting Modes

- **Bot API** (`posting_mode: "bot"`) - Official Telegram Bot API, safe, requires bot as channel admin
- **Telethon** (`posting_mode: "telethon"`) - User account mode, higher risk, no bot label

### Schedule Types

Configured in `config.yaml` under `schedule.type`:
- `fixed` - Post at specific times (e.g., `["09:30", "14:00", "20:00"]`)
- `interval` - Post every N hours
- `random` - Random times within a time window

## Phase 1 Features

### A/B Testing (`pipeline/ab_test_manager.py`)
- Create experiments with two post variants
- Track impressions and engagement per variant
- Statistical analysis with confidence thresholds
- Config: `ab_testing.enabled`, `ab_testing.min_sample_size`, `ab_testing.confidence_threshold`

### Draft System (`pipeline/draft_manager.py`)
- Version history for posts (`PostVersion` model)
- Create, list, restore versions
- Config: `draft.max_versions`, `draft.auto_cleanup_days`

### Approval Workflow
- Post status lifecycle: draft → pending_review → approved → scheduled → published
- Auto-approve based on quality/verification/editor scores
- Config: `approval.auto_approve_enabled`, `approval.min_quality_score`

### Quick Wins (Implemented)
- Health monitoring (`health.check_on_startup`, `health.check_before_post`)
- Audit logging (`audit.enabled`, `audit.retention_days`)
- Weekly reports (`reporting.enabled`, `reporting.schedule`)
- Post templates (`templates.enabled`, `templates.path`)
- Poll generation (`polls.enabled`, `polls.probability`)

## Database Models

Key SQLAlchemy models in `memory/models.py`:
- **Post** - Published content with engagement metrics, quality scores, source tracking, media prompts, A/B testing fields
- **PostVersion** - Version history snapshots
- **ABExperiment** / **ABVariant** - A/B testing configuration
- **Topic** - Topic tracking for deduplication
- **Source** - RSS/API source management
- **StyleProfile** - Learned writing style characteristics

## Important Files

- `main.py` - Entry point with CLI argument parsing
- `setup.py` - Interactive first-run configuration wizard
- `config.yaml` - Main configuration file
- `.env.example` - Template for environment variables
- `data/tg_poster.db` - SQLite database (default)
- `docs/ROADMAP.md` - Full feature roadmap (50 planned features)

## Post Structure (v2.0)

Generated posts follow this structure:
```
{title} - max 120 chars with 1-2 emojis

{hook} - 1-2 sentences explaining what + why care

{body} - 800-1500 chars, short paragraphs

🔍 Что важно знать:
- {key_facts[0-3]} - exactly 4 standalone verifiable claims

🧠 Почему это важно
{analysis} - 2-4 sentences with industry trend + question

🔗 Источники:
- {sources[].name} — {sources[].url}

⚡ Полезные ссылки:
- {useful_links[].label} — {useful_links[].url}

💡 TL;DR: {tldr} - single self-contained sentence

#hashtags
```

## Development Notes

- All async code uses `async/await` pattern
- Type hints are used throughout the codebase
- LLM adapters implement `BaseLLMAdapter` interface from `llm/base.py`
- Pipeline stages are designed to be independent and testable
- The system uses ChromaDB for semantic deduplication of posts
- Rate limiting and retry logic is handled via `tenacity` library
- Posts require minimum 2 verified sources for generation
- Quality checker runs 50 validation rules before publishing
- Source URL deduplication prevents reposting from same URL
