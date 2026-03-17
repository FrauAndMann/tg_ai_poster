<p align="center">
  <img src="https://img.shields.io/badge.svg?style=display: inline-block;" alt="TG AI Poster"/>
</p>

<h1 align="center">TG AI Poster</h1>

<p align="center">
  <em>Autonomous AI-powered Telegram channel management system</em>
</p>

<p align="center">
  <a href="https://github.com/FrauAndMann/tg_ai_poster/actions/workflows/CI/badge.svg?branch=main" alt="CI Status">
  <a href="https://github.com/FrauAndMann/tg_ai_poster/actions/workflows/CI/badge.svg?branch=main"><style="display: inline-block;" alt="Build status">
  <a href="https://github.com/FrauAndMann/tg_ai_poster/actions/workflows/CI/badge.svg?branch=main"><style="display: inline-block;" alt="Coverage">
  <a href="https://codecov.io/gh/FrauAndMann/tg_ai_poster">
  <img src="https://img.shields.io/badge.svg?style=display: inline-block;" alt="Coverage">
</p>

<p align="center">
  <a href="https://www.python.org/" alt="Python">
  <img src="https://img.shields.io/badge.svg?style=display: inline-block;" alt="Python 3.11+" style="display: inline-block;" alt="Python 3.11">
  <img src="https://img.shields.io/badge.svg?style=display: inline-block;" alt="License">
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT" alt="License">
  <img src="https://img.shields.io/badge.svg?style="display: inline-block;" alt="License: MIT">
</p>

---

## Features

- **Multi-LLM Support** - OpenAI, Claude, DeepSeek, GLM-5
- **Smart Content Pipeline** - Source collection, filtering, topic selection, generation
- **Source Verification** - Domain trust tiers, credibility scoring
- **Editorial Review** - AI-powered content review and quality checks
- **Multiple Posting Modes** - Bot API & Telethon
- **Flexible Scheduling** - Fixed times, interval, random windows
- **A/B Testing** - Experiment variants with statistical analysis
- **Draft System** - Post versioning with approval workflow
- **Admin Bot** - Telegram-based remote control
- **Backup & Recovery** - Automated database backups
- **Health Monitoring** - Watchdog with auto-recovery
- **Circuit Breaker** - Resilience pattern for- **Analytics & Reports** - Engagement metrics, quality scores
- **Security** - Input validation, API key protection

---

## Quick Start

```bash
# Setup
python setup.py
cp . .env.example . .

# Run
python main.py                    # Start scheduled posting
python main.py --dry-run          # Test without publishing
python main.py --once             # Generate one post and exit
python main.py --config my.yaml   # Use custom config
```

</details>

<details>
<summary>Usage</summary>

| Command | Description |
|---------|-------------|
| `python main.py` | Start scheduled posting |
| `python main.py --dry-run` | Run without publishing |
| `python main.py --once` | Run pipeline once and exit |
| `python main.py --init-db` | Initialize database |
| `python main.py --debug` | Enable debug logging |

| `python main.py --backup` | Create backup |
| `python main.py --restore file.tar.gz` | Restore from backup |
```
</details>

<details>
<summary>Content Validation</summary>

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

---

## Installation

### Prerequisites

- Python 3.11+
- Telegram Bot Token (from @BotFather)
- LLM API Key (OpenAI or Anthropic)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/FrauAndMann/tg_ai_poster.git
   cd tg_ai_poster
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example . .env
   # Edit .env with your credentials
   ```

4. **Run setup wizard**
   ```bash
   python setup.py
   ```

---

## Configuration

Configuration is split into two files:

### config.yaml (Non-sensitive)
```yaml
schedule:
  type: fixed          # fixed, interval, or random
  fixed_times: ["09:30", "14:00", "20:00"]
  timezone: "Europe/Moscow"

llm:
  provider: openai
  model: gpt-4o-mini
  temperature: 0.7

telegram:
  channel_id: -1001234567890
  posting_mode: bot
```

### .env (Secrets)
```env
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=sk-api-key
ADMIN_TELEGRAM_ID=your_telegram_id
```

---

## Architecture

```
pipeline/
├── source_collector.py    # RSS/API collection
├── content_filter.py     # Relevance scoring
├── topic_selector.py      # LLM topic selection
├── source_verification.py # Credibility checks
├── context_builder.py    # Context assembly
├── llm_generator.py      # LLM generation
├── editor_review.py      # Editorial review
├── quality_checker.py    # Quality validation
├── media_prompt_gen.py   # Image prompts
├── telegram_formatter.py # Formatting
└── orchestrator.py       # Pipeline coordination

core/
├── config.py             # Configuration
├── logger.py            # Logging
├── scheduler.py          # Scheduling
└── watchdog.py           # Health monitoring

memory/
├── models.py            # SQLAlchemy models
├── database.py          # Database management
├── post_store.py        # Post operations
├── topic_store.py       # Topic operations
└── feedback_loop.py     # Learning system

tests/
├── conftest.py           # Pytest fixtures
├── test_memory.py
├── test_pipeline.py
└── test_content_validator.py
```

---

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

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `python main.py` | Start scheduled posting |
| `python main.py --dry-run` | Test mode (no publishing) |
| `python main.py --once` | Generate one post and exit |
| `python main.py --init-db` | Initialize database |
| `python main.py --debug` | Enable debug logging |

---

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

---

## Security

- **Never commit `.env` file** - Use `.env.example` as template
- Use Bot API mode for production
- Set reasonable `max_daily_posts` limits
- Enable `manual_approval` for sensitive content
- Keep API keys secure and rotate periodically

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Telethon](https://github.com/LonamiWebs/Telethon)
- [ChromaDB](https://www.trychroma.com/)
- [APScheduler](https://github.com/agronholm/apscheduler)
