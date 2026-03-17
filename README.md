<h1 align="center">TG AI Poster</h1>

<p align="center">
  <strong>Autonomous AI-powered Telegram channel management system</strong>
</p>

<p align="center">
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white" alt="Python">
  </a>
  <a href="https://github.com/FrauAndMann/tg_ai_poster/actions">
    <img src="https://github.com/FrauAndMann/tg_ai_poster/actions/workflows/CI.yml/badge.svg" alt="CI">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  </a>
</p>

---

## Overview

TG AI Poster is a fully autonomous system that generates and publishes high-quality content to Telegram channels 24/7. It collects news from multiple sources, filters by relevance, generates engaging posts using LLM, and publishes them on a configurable schedule.

## Features

| Category | Features |
|----------|----------|
| **LLM Support** | OpenAI GPT, Anthropic Claude, DeepSeek, GLM-5 |
| **Content Pipeline** | RSS/API collection, relevance filtering, topic selection, generation |
| **Quality Control** | Source verification, editorial review, 50+ validation rules |
| **Publishing** | Bot API & Telethon modes, MarkdownV2 formatting |
| **Scheduling** | Fixed times, intervals, random windows |
| **Management** | Admin Bot, A/B testing, draft system, approval workflow |
| **Reliability** | Circuit breaker, health monitoring, auto-backup |

## Quick Start

```bash
# Clone repository
git clone https://github.com/FrauAndMann/tg_ai_poster.git
cd tg_ai_poster

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run setup wizard
python setup.py

# Test run (no publishing)
python main.py --dry-run --once

# Start scheduled posting
python main.py
```

## Configuration

### config.yaml
```yaml
schedule:
  type: fixed
  fixed_times: ["09:30", "14:00", "20:00"]
  timezone: "Europe/Moscow"

llm:
  provider: openai      # openai, claude, deepseek, claude-cli
  model: gpt-4o-mini
  temperature: 0.7

telegram:
  channel_id: -1001234567890
  posting_mode: bot     # bot or telethon

content:
  language: ru
  post_length_min: 200
  post_length_max: 900
```

### .env
```env
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=sk-your-key
ADMIN_TELEGRAM_ID=your_telegram_id
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python main.py` | Start scheduled posting |
| `python main.py --dry-run` | Run without publishing |
| `python main.py --once` | Single post and exit |
| `python main.py --init-db` | Initialize database |
| `python main.py --debug` | Verbose logging |
| `python main.py --backup` | Create backup |
| `python main.py --restore file.tar.gz` | Restore from backup |

## Architecture

```
tg_ai_poster/
├── main.py                 # Entry point
├── config.yaml             # Configuration
├── .env                    # Secrets (gitignored)
│
├── core/                   # Core utilities
│   ├── config.py          # Configuration loader
│   ├── logger.py          # Logging setup
│   ├── scheduler.py       # APScheduler wrapper
│   └── events.py          # Event bus
│
├── pipeline/               # Content pipeline
│   ├── orchestrator.py    # Main coordinator
│   ├── source_collector.py
│   ├── content_filter.py
│   ├── topic_selector.py
│   ├── source_verification.py
│   ├── context_builder.py
│   ├── llm_generator.py
│   ├── editor_review.py
│   ├── quality_checker.py
│   └── telegram_formatter.py
│
├── llm/                    # LLM adapters
│   ├── base.py            # Abstract interface
│   ├── openai_adapter.py
│   ├── claude_adapter.py
│   ├── deepseek_adapter.py
│   └── claude_cli_adapter.py
│
├── memory/                 # Data layer
│   ├── models.py          # SQLAlchemy models
│   ├── database.py
│   ├── post_store.py
│   └── topic_store.py
│
├── publisher/              # Publishing
│   ├── base.py
│   ├── bot_publisher.py
│   └── telethon_publisher.py
│
├── admin_bot/              # Telegram admin bot
│   ├── bot.py
│   ├── commands.py
│   └── keyboards.py
│
└── tests/                  # Test suite
    ├── conftest.py
    └── test_*.py
```

## Pipeline Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Source         │───▶│  Content        │───▶│  Topic          │
│  Collection     │    │  Filter         │    │  Selection      │
│  (RSS/API)      │    │  (relevance)    │    │  (LLM)          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
┌─────────────────┐    ┌─────────────────┐           │
│  Quality        │◀───│  Editorial      │◀──┐       │
│  Check          │    │  Review         │   │       │
│  (50+ rules)    │    │  (AI editor)    │   │       │
└─────────────────┘    └─────────────────┘   │       │
         │                                    │       │
         ▼                           ┌─────────────────┐
┌─────────────────┐                  │  LLM            │◀──────┘
│  Telegram       │                  │  Generation     │
│  Formatter      │                  │  (JSON schema)  │
│  (MarkdownV2)   │                  └─────────────────┘
└─────────────────┘                           ▲
         │                                    │
         ▼                           ┌─────────────────┐
┌─────────────────┐                  │  Source         │
│  Publisher      │                  │  Verification   │
│  (Bot/Telethon) │                  │  (credibility)  │
└─────────────────┘                  └─────────────────┘
```

## Deployment

### Docker
```bash
docker build -t tg-ai-poster .
docker run -d --env-file .env -v ./data:/app/data tg-ai-poster
```

### Docker Compose
```bash
docker-compose up -d
```

### Systemd (VPS)
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

[Install]
WantedBy=multi-user.target
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Specific test
pytest tests/test_pipeline.py -v
```

## Security

- Never commit `.env` file
- Use Bot API mode for production
- Set `max_daily_posts` limits
- Enable `manual_approval` for sensitive content
- Rotate API keys periodically

## Tech Stack

- **Python 3.11+** - Main language
- **SQLAlchemy** - ORM and database
- **APScheduler** - Job scheduling
- **python-telegram-bot** - Bot API
- **Telethon** - User account mode
- **ChromaDB** - Vector storage for deduplication
- **Pydantic** - Configuration validation
- **Pytest** - Testing framework

## License

[MIT](LICENSE)

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Telethon](https://github.com/LonamiWebs/Telethon)
- [ChromaDB](https://www.trychroma.com/)
- [APScheduler](https://github.com/agronholm/apscheduler)
