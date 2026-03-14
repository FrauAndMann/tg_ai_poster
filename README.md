# TG AI Poster

[![Tests](https://github.com/FrauAndMann/tg_ai_poster/actions/workflows/test.yml/badge.svg)](https://github.com/FrauAndMann/tg_ai_poster/actions/workflows/test.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-orange.svg)](https://github.com/astral-sh/ruff)
[![Coverage](https://img.shields.io/badge/coverage-92%25-green.svg)](https://github.com/FrauAndMann/tg_ai_poster)

**Autonomous AI-powered Telegram channel management system that generates and publishes content 24/7 without human intervention.**

## Features

- **Multi-LLM Support** - OpenAI GPT-4o, Anthropic Claude, DeepSeek, GLM-5
- **Smart Content Generation** - AI-powered post creation with editorial review
- **Content Validation** - Strict validation prevents LLM artifacts and meta-text in posts
- **Semantic Deduplication** - ChromaDB-powered similarity detection ensures unique content
- **Multiple Sources** - RSS feeds, HackerNews, ProductHunt integration
- **Flexible Scheduling** - Fixed times, intervals, or random scheduling
- **Two Publishing Modes** - Bot API (safe) or Telethon (user account)
- **Learning System** - Improves based on engagement metrics
- **Docker Ready** - Full containerization support

## Quick Start

### Prerequisites

- Python 3.12+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- LLM API Key (OpenAI, Anthropic, or DeepSeek)

### Installation

```bash
# Clone the repository
git clone https://github.com/FrauAndMann/tg_ai_poster.git
cd tg_ai_poster

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

#### Option 1: Interactive Setup (Recommended)

```bash
python setup.py
```

The setup wizard will guide you through:
- Telegram bot configuration
- LLM provider selection
- Channel topic and style settings
- Schedule configuration

#### Option 2: Manual Configuration

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials:
```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHANNEL_ID=@your_channel

# LLM Provider
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...

# Admin notifications (optional)
ADMIN_TELEGRAM_ID=123456789
```

3. Configure `config.yaml`:
```yaml
telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  channel_id: "${TELEGRAM_CHANNEL_ID}"
  posting_mode: "bot"

llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.85
  max_tokens: 800

channel:
  topic: "AI technologies and automation"
  style: "Expert but accessible"
  language: "en"
  post_length_min: 200
  post_length_max: 900
  emojis_per_post: 3
  hashtags_count: 2

schedule:
  type: "fixed"
  fixed_times: ["09:30", "14:00", "20:00"]
  timezone: "Europe/London"

safety:
  max_daily_posts: 6
  min_interval_minutes: 60
  similarity_threshold: 0.85
```

### Running

```bash
# Initialize database (first time only)
python main.py --init-db

# Test run (no publishing)
python main.py --dry-run --once

# Single post and exit
python main.py --once

# Start scheduled posting
python main.py
```

## Publishing Modes

### Mode A: Bot API (Recommended)

The official Telegram Bot API approach.

**Setup:**
1. Create a bot via [@BotFather](https://t.me/botfather)
2. Get the bot token
3. Add the bot to your channel as administrator
4. Grant "Post Messages" permission

**Pros:**
- Official API, no ban risk
- Simple setup
- Reliable

**Cons:**
- Posts show "via @botname"
- Bot must be channel admin

### Mode B: Telethon (User Account)

Publishes through a user account session.

> **Warning:** Use ONLY on a separate account! May violate Telegram ToS.

**Setup:**
1. Get API ID and Hash from [my.telegram.org](https://my.telegram.org)
2. Enter SMS code on first run
3. Session is saved for subsequent runs

**Pros:**
- Posts appear as personal messages
- Full access to features

**Cons:**
- Risk of account ban
- Violates Telegram ToS
- More complex setup

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                         │
│              core/scheduler.py — APScheduler                │
└──────────────────────────┬──────────────────────────────────┘
                           │ triggers pipeline
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT PIPELINE                         │
│                                                             │
│  [1] SourceCollector   — RSS, HackerNews, ProductHunt      │
│  [2] ContentFilter     — Dedup, relevance scoring          │
│  [3] TopicSelector     — LLM-powered topic selection       │
│  [4] PromptBuilder     — Style, history, examples          │
│  [5] LLMGenerator      — Content generation                │
│  [6] ContentValidator  — LLM meta-text detection           │
│  [7] EditorReview      — AI editorial review               │
│  [8] QualityChecker    — Length, emoji, markdown, dedup    │
│  [9] Formatter         — Telegram MarkdownV2 formatting    │
│ [10] MediaGenerator    — Image prompt creation             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      PUBLISHER                              │
│                                                             │
│  BotPublisher         — python-telegram-bot (safe)          │
│  TelethonPublisher    — User account session (advanced)     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   MEMORY & LEARNING                         │
│                                                             │
│  SQLAlchemy DB        — Post history, topics, metrics       │
│  ChromaDB             — Vector embeddings for dedup         │
│  FeedbackLoop         — Learns from engagement              │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
tg_ai_poster/
├── main.py                 # Entry point
├── setup.py                # Interactive setup wizard
├── config.yaml             # Main configuration
│
├── core/                   # Core modules
│   ├── config.py           # Configuration management
│   ├── logger.py           # Logging utilities
│   ├── scheduler.py        # APScheduler integration
│   └── events.py           # Event system
│
├── pipeline/               # Content generation pipeline
│   ├── orchestrator.py     # Pipeline coordinator
│   ├── source_collector.py # RSS, HN, ProductHunt
│   ├── content_filter.py   # Relevance scoring
│   ├── content_validator.py# LLM artifact detection
│   ├── topic_selector.py   # LLM topic selection
│   ├── prompt_builder.py   # Prompt construction
│   ├── llm_generator.py    # LLM integration
│   ├── editor_review.py    # AI editorial review
│   ├── quality_checker.py  # Quality validation
│   └── formatter.py        # MarkdownV2 formatting
│
├── publisher/              # Publishing modules
│   ├── base.py             # Abstract publisher
│   ├── bot_publisher.py    # Bot API implementation
│   └── telethon_publisher.py
│
├── memory/                 # Data persistence
│   ├── models.py           # SQLAlchemy models
│   ├── database.py         # Database management
│   ├── post_store.py       # Post operations
│   ├── topic_store.py      # Topic operations
│   ├── vector_store.py     # ChromaDB integration
│   └── feedback_loop.py    # Learning system
│
├── llm/                    # LLM providers
│   ├── base.py             # Abstract adapter
│   ├── openai_adapter.py
│   ├── claude_adapter.py
│   ├── deepseek_adapter.py
│   └── prompts/            # Prompt templates
│
├── tests/                  # Test suite
│   ├── conftest.py         # Pytest fixtures
│   ├── test_memory.py
│   ├── test_pipeline.py
│   └── test_content_validator.py
│
└── utils/                  # Utilities
    ├── retry.py            # Retry logic
    ├── rate_limiter.py     # Rate limiting
    └── validators.py       # Content validation
```

## Content Validation

The system includes strict validation to prevent LLM artifacts from appearing in published posts:

**Automatically Rejected:**
- LLM meta-text ("Here's your post", "I created this for you")
- Thinking indicators ("Let me think", "As an AI")
- Incomplete content (placeholders, TBD markers)
- Generic questions at the start
- JSON parsing errors

**Quality Checks:**
- Minimum/maximum length
- Emoji count limits
- Hashtag formatting
- Telegram MarkdownV2 compliance
- Semantic similarity to recent posts

## Deployment

### Docker

```bash
# Build image
docker build -t tg-ai-poster .

# Run container
docker run -d \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.yaml:/app/config.yaml \
  tg-ai-poster
```

### Docker Compose

```bash
docker-compose up -d
docker-compose logs -f app
```

### Systemd (VPS)

Create `/etc/systemd/system/tg-ai-poster.service`:

```ini
[Unit]
Description=TG AI Poster
After=network.target

[Service]
Type=simple
User=tg-poster
WorkingDirectory=/opt/tg-ai-poster
ExecStart=/opt/tg-ai-poster/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tg-ai-poster
sudo systemctl start tg-ai-poster
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python main.py` | Start scheduled posting |
| `python main.py --dry-run` | Test mode (no publishing) |
| `python main.py --once` | Generate one post and exit |
| `python main.py --init-db` | Initialize database |
| `python main.py --debug` | Enable debug logging |

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_content_validator.py -v

# Run with verbose output
pytest -v
```

## Security

- **Never commit `.env` file** - Use `.env.example` as template
- Use Bot API mode for production
- Set reasonable `max_daily_posts` limits
- Enable `manual_approval` for sensitive content
- Keep API keys secure and rotate periodically

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Telethon](https://github.com/LonamiWebs/Telethon)
- [ChromaDB](https://www.trychroma.com/)
- [APScheduler](https://github.com/agronholm/apscheduler)
