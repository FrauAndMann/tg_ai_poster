# TG AI Poster

Production-oriented platform for autonomous Telegram publishing with AI generation, editorial validation, source collection, real-time news monitoring, and multi-provider LLM support.

## Why this project exists

`TG AI Poster` is built for teams that want more than a simple "LLM -> Telegram" script. The repository already contains a broad pipeline for:

- collecting signals from RSS and external tech sources;
- selecting relevant topics for a Telegram channel;
- generating structured posts via LLM;
- validating factuality, readability, anti-water quality, and formatting;
- scheduling or auto-publishing content;
- monitoring breaking news in near real time.

This update hardens the project toward production usage with stronger validation, better source freshness handling, smarter ranking, improved deduplication, and significantly better documentation.

---

## What is included

### Core capabilities

- Multi-provider LLM support: OpenAI, Claude, DeepSeek, GLM, Claude CLI.
- Telegram publishing via Bot API or Telethon.
- Source collection from RSS, Hacker News, Product Hunt, ArXiv, and NewsAPI integrations.
- Topic selection and content generation pipeline.
- Editorial review and quality scoring.
- Breaking-news monitoring and automatic triggering.
- Admin bot and operational tooling.
- Backups, health checks, scheduler, circuit breaker, retry helpers.

### Production hardening added in this revision

- Dynamic CJK glitch detection in generated content.
- Noise-pattern validation for repeated punctuation and invisible characters.
- Stronger raw-response sanitation before publication.
- RSS feed caching to reduce redundant network work.
- Conditional feed fetching with `ETag` / `Last-Modified`.
- Threaded RSS parsing so feed parsing does not block the event loop.
- Concurrent-fetch control via semaphore.
- Feed retries with backoff and temporary auto-disable for broken sources.
- URL normalization for stronger deduplication.
- Persistent source-health telemetry and per-feed state.
- Article ranking based on freshness, source signal, metadata richness, language heuristics, and launch/breakthrough cues.
- Safer compatibility for monitors expecting `article.content`.
- Better breaking-news prioritization from source trust, corroboration, entity cooldowns, and summary richness.
- YAML loading for `realtime` and `media` sections in `Settings.create()`.

---

## Architecture

```text
sources -> collector -> filter -> topic selector -> prompt builder -> LLM generator
        -> validator/editor/quality gates -> formatter -> publisher -> feedback/memory
                                  \
                                   -> real-time monitor / breaking-news autopost
```

### Main subsystems

| Area | Responsibility |
| --- | --- |
| `core/` | Config, logging, scheduler, events, health, watchdog |
| `pipeline/` | Content collection, filtering, generation, review, quality, formatting |
| `llm/` | Provider adapters |
| `memory/` | Database, stores, vector memory |
| `publisher/` | Telegram delivery backends |
| `admin_bot/` | Operational bot for administration |
| `backup/` | Backup and restore workflows |
| `tests/` | Unit and integration validation |

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/FrauAndMann/tg_ai_poster.git
cd tg_ai_poster
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure secrets

Create `.env` and fill the required variables:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=...
LLM_API_KEY=...
ADMIN_TELEGRAM_ID=123456789
```

### 3. Edit `config.yaml`

Minimal example:

```yaml
telegram:
  posting_mode: bot
  channel_id: "@your_channel"

llm:
  provider: openai
  model: gpt-4o-mini
  temperature: 0.6

channel:
  topic: "AI products, models, releases, benchmarks and market analysis"
  style: "Crisp, analytical, useful, no hype"
  language: ru
  post_length_min: 250
  post_length_max: 1100

schedule:
  type: fixed
  fixed_times: ["09:30", "14:00", "20:00"]
  timezone: "Europe/Moscow"

sources:
  rss_feeds:
    - "https://openai.com/news/rss.xml"
    - "https://feeds.feedburner.com/oreilly/radar"
    - "https://hnrss.org/frontpage"
  max_articles_per_feed: 15
  feed_cache_ttl_minutes: 15
  max_concurrent_fetches: 10
  max_article_age_days: 7
  source_weights:
    openai.com: 1.0
    anthropic.com: 0.9
    arxiv.org: 0.8

realtime:
  enabled: true
  poll_interval_minutes: 15
  auto_post: true
  breaking_threshold: 7
```

### 4. Validate configuration / dry run

```bash
python main.py --dry-run --once
```

### 5. Run scheduled mode

```bash
python main.py
```

---

## CLI

| Command | Purpose |
| --- | --- |
| `python main.py` | Start scheduled posting |
| `python main.py --once` | Run one pipeline cycle |
| `python main.py --dry-run` | Skip publishing but run the logic |
| `python main.py --debug` | Verbose logging |
| `python main.py --init-db` | Initialize database |
| `python main.py --backup` | Create a backup |
| `python main.py --restore backups/file.tar.gz` | Restore backup |
| `python setup.py` | Project setup workflow |

---

## Configuration guide

### `telegram`

- `posting_mode`: `bot` or `telethon`
- `channel_id`: target channel ID or username
- `bot_token`: Bot API token
- `proxy`: optional HTTP/SOCKS proxy

### `llm`

- `provider`: `openai`, `claude`, `deepseek`, `glm`, `claude-cli`
- `model`: provider-specific model name
- `api_key`: secret key if required
- `base_url`: override API endpoint
- `max_tokens`, `temperature`: generation settings

### `channel`

- `topic`: editorial niche
- `style`: channel voice and tone
- `language`: output language
- `post_length_min` / `post_length_max`: content boundaries
- `emojis_per_post`, `hashtags_count`: stylistic constraints

### `sources`

- `rss_feeds`: source list
- `max_articles_per_feed`: hard cap per feed
- `feed_cache_ttl_minutes`: cache TTL to reduce fetch waste
- `max_concurrent_fetches`: fetch parallelism control
- `max_article_age_days`: freshness filter
- `source_weights`: per-domain ranking boost
- `request_retries`, `retry_base_delay_ms`: retry/backoff control
- `disable_after_failures`, `disable_duration_minutes`: failing-feed circuit breaker
- `state_path`: persistent source-health state

### `realtime`

- `enabled`: enable news monitor
- `poll_interval_minutes`: polling frequency
- `auto_post`: whether breaking news triggers generation
- `breaking_threshold`: minimum score for autopost
- `min_post_interval_minutes`: cooldown between autoposts
- `entity_cooldown_minutes`: throttle repeated alerts about the same entity
- `duplicate_collapse_hours`: collapse repeated title signatures
- `state_path`: persistent monitor dedup state

### `safety`

- manual approval toggle;
- maximum daily posts;
- minimum posting interval;
- duplicate similarity threshold;
- forbidden words;
- regeneration attempts.

---

## Content-quality system

The repository already contains multiple content-quality layers. In practice, production quality here is a composition of many smaller gates:

- raw LLM response validation;
- JSON schema and structure validation;
- body-length and sentence-density checks;
- filler/water detection;
- density scoring;
- grammar checking;
- voice consistency;
- hook analysis;
- paragraph structure checks;
- fact/claim extraction;
- hallucination detection;
- source mapping and verification;
- formatting validation before Telegram publish.

### New validation improvements

This revision adds:

1. Dynamic detection of CJK leakage in RU/EN posts.
2. Repeated punctuation warnings.
3. Invisible-character warnings.
4. Repetition warnings for duplicated sections.
5. Better pre-publication raw-response diagnostics.

---

## News-quality and freshness improvements

This revision improves source handling with:

1. RSS feed response caching.
2. Conditional requests via `ETag` and `Last-Modified`.
3. Event-loop friendly threaded parsing.
4. Concurrency limits to avoid burst overload.
5. Retries with jitter and temporary feed disable on repeated failures.
6. URL normalization and canonical-link extraction for deduplication.
7. Freshness-aware ranking.
8. Domain-weight ranking with aggregator penalty.
9. Lightweight language heuristics before ranking.
10. Summary-richness ranking.
11. Breaking-news keyword reinforcement.
12. Compatibility fallback from `content` to `summary`.
13. Title-signature deduplication plus corroboration-aware real-time scoring.

---

## Running tests

```bash
pytest -q
```

For targeted tests:

```bash
pytest tests/test_content_validator.py -q
pytest tests/test_pipeline.py -q
pytest tests/test_config.py -q
pytest tests/test_real_time_monitor.py -q
```

---

## Deployment

### Docker

```bash
docker build -t tg-ai-poster .
docker run -d --env-file .env -v $(pwd)/data:/app/data tg-ai-poster
```

### Docker Compose

```bash
docker-compose up -d
```

### VPS / systemd sketch

```ini
[Unit]
Description=TG AI Poster
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/tg_ai_poster
ExecStart=/opt/tg_ai_poster/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Recommended production checklist

- Run in `--dry-run` first.
- Use a dedicated Telegram test channel before production.
- Keep `manual_approval=true` while tuning prompts.
- Add trusted domains in `sources.source_weights`.
- Monitor duplicates and forbidden topics in stores.
- Review generated posts for formatting edge cases.
- Back up database and vector state.
- Keep API keys only in `.env`, never in YAML or code.
- Use conservative autopost thresholds until source quality is proven.

---

## Documentation map

- `USER_GUIDE.md` — user-level usage.
- `docs/INDEX.md` — document index.
- `docs/ROADMAP.md` — roadmap.
- `docs/SECURITY.md` — security notes.
- `docs/PRODUCTION_AUDIT_100.md` — 100-point production audit and improvement backlog.

---

## License

MIT.
