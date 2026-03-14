# AGENT TASK: Build Autonomous AI Telegram Channel Manager
# ============================================================
# Feed this entire file to your CLI agent (Claude Code, Aider, etc.)
# Command example: claude < AGENT_DESIGN_DOC.md
# ============================================================

## ROLE & MISSION

You are a senior Python engineer. Your task is to build a **complete, 
production-ready, autonomous AI system** that manages a Telegram channel 
24/7 without human intervention.

The system uses an LLM to generate high-quality posts, automatically 
publishes them on a schedule, learns from engagement feedback, and never 
repeats itself semantically.

**Do not ask clarifying questions. Build everything described below.**  
**Do not leave TODO placeholders. Write working code for every module.**  
**Use async/await throughout. Add type hints everywhere.**

---

## TECH STACK

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Telegram (Mode A) | python-telegram-bot 20.x |
| Telegram (Mode B) | Telethon 1.x |
| LLM | OpenAI API (gpt-4o) — adapter pattern |
| Vector store | ChromaDB (semantic dedup) |
| Database | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy 2.x |
| Scheduler | APScheduler 3.x |
| Queue | Redis + rq (optional) |
| Config | Pydantic BaseSettings v2 + config.yaml |
| Logging | loguru |
| HTTP | httpx (async) |
| RSS | feedparser |
| Retry | tenacity |
| Container | Docker + docker-compose |
| Env | python-dotenv |

---

## SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                         │
│              core/scheduler.py — APScheduler                │
└──────────────────────────┬──────────────────────────────────┘
                           │ triggers pipeline every N hours
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT PIPELINE                         │
│                                                             │
│  [1] SourceCollector   — RSS, HackerNews, ProductHunt API  │
│         ↓                                                   │
│  [2] ContentFilter     — dedup, relevance scoring          │
│         ↓                                                   │
│  [3] TopicSelector     — Agent picks best topic via LLM    │
│         ↓                                                   │
│  [4] PromptBuilder     — injects style, history, examples  │
│         ↓                                                   │
│  [5] LLMGenerator      — Agent-Editor writes draft         │
│         ↓                                                   │
│  [6] AgentCritic       — Agent-Critic improves draft       │
│         ↓                                                   │
│  [7] QualityChecker    — length, emoji, markdown, dedup    │
│         ↓                                                   │
│  [8] Formatter         — Telegram MarkdownV2 formatting    │
│         ↓                                                   │
│  [9] ApprovalGate      — auto or manual (Telegram DM)      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      PUBLISHER                              │
│                                                             │
│  Mode A: BotPublisher    — python-telegram-bot              │
│  Mode B: TelethonPublisher — user account session           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   MEMORY & LEARNING                         │
│                                                             │
│  SQLAlchemy DB  — post history, topics, engagement          │
│  ChromaDB       — vector embeddings for semantic dedup      │
│  FeedbackLoop   — learns from reactions, updates style      │
└─────────────────────────────────────────────────────────────┘
```

---

## PROJECT STRUCTURE

Create exactly this directory and file layout:

```
tg_ai_poster/
│
├── main.py                          # Entry point, starts scheduler
├── setup.py                         # First-run setup wizard
├── config.yaml                      # All non-secret settings
├── .env.example                     # Template for secrets
├── requirements.txt                 # Pinned versions
├── Dockerfile                       # Multi-stage, non-root user
├── docker-compose.yml               # app + redis services
├── README.md                        # Quick start guide
│
├── core/
│   ├── __init__.py
│   ├── config.py                    # Pydantic BaseSettings loader
│   ├── logger.py                    # loguru configuration
│   └── scheduler.py                 # APScheduler, 3 schedule modes
│
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py              # Runs full pipeline top-to-bottom
│   ├── source_collector.py          # RSS + HackerNews + ProductHunt
│   ├── content_filter.py            # Dedup + relevance scoring
│   ├── topic_selector.py            # LLM Agent picks best topic
│   ├── prompt_builder.py            # Dynamic prompt assembly
│   ├── llm_generator.py             # LLM Agent writes post
│   ├── agent_critic.py              # LLM Agent critiques + improves
│   ├── quality_checker.py           # Validation + regeneration
│   └── formatter.py                 # Telegram MarkdownV2 formatter
│
├── publisher/
│   ├── __init__.py
│   ├── base.py                      # Abstract base publisher
│   ├── bot_publisher.py             # Mode A: Bot API
│   └── telethon_publisher.py        # Mode B: User account
│
├── memory/
│   ├── __init__.py
│   ├── models.py                    # SQLAlchemy ORM models
│   ├── database.py                  # Engine, session, migrations
│   ├── post_store.py                # Post CRUD operations
│   ├── topic_store.py               # Topic tracking
│   ├── vector_store.py              # ChromaDB semantic search
│   └── feedback_loop.py             # Learns from engagement metrics
│
├── llm/
│   ├── __init__.py
│   ├── base.py                      # Abstract LLM adapter
│   ├── openai_adapter.py            # OpenAI implementation
│   ├── claude_adapter.py            # Anthropic implementation
│   ├── deepseek_adapter.py          # DeepSeek implementation
│   └── prompts/
│       ├── system.txt               # Base system prompt
│       ├── post_generator.txt       # Post writing prompt
│       ├── topic_selector.txt       # Topic selection prompt
│       ├── agent_critic.txt         # Critic/improvement prompt
│       └── style_analyzer.txt       # Weekly style audit prompt
│
└── utils/
    ├── __init__.py
    ├── retry.py                     # tenacity decorators
    ├── rate_limiter.py              # Token bucket rate limiting
    └── validators.py                # Content safety checks
```

---

## DETAILED MODULE SPECIFICATIONS

### `core/config.py`

```python
# Use Pydantic BaseSettings v2
# Load from both config.yaml and .env file
# All fields must have types and defaults

class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    telegram_channel_id: str  # e.g. "@mychannel" or "-1001234567"
    
    # Telethon (Mode B)
    telethon_api_id: int = 0
    telethon_api_hash: str = ""
    telethon_phone: str = ""
    
    # LLM
    openai_api_key: str
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    llm_provider: Literal["openai", "claude", "deepseek"] = "openai"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.85
    llm_max_tokens: int = 800
    
    # Posting
    posting_mode: Literal["bot", "telethon"] = "bot"
    schedule_type: Literal["interval", "fixed", "random"] = "fixed"
    interval_hours: int = 4
    fixed_times: list[str] = ["09:30", "14:00", "20:00"]
    random_window_start: str = "10:00"
    random_window_end: str = "22:00"
    timezone: str = "Europe/Moscow"
    max_daily_posts: int = 6
    min_interval_minutes: int = 60
    
    # Channel identity
    channel_topic: str = "AI tools and automation for business"
    channel_style: str = "Expert practitioner. No hype. Real cases. Telegram-friendly."
    language: str = "ru"
    
    # Post format
    post_length_min: int = 200
    post_length_max: int = 900
    emojis_per_post: int = 3
    hashtags_count: int = 2
    
    # Sources
    rss_feeds: list[str] = []
    
    # Safety
    manual_approval: bool = False
    admin_telegram_id: int = 0  # for manual approval DMs
    forbidden_words: list[str] = []
    similarity_threshold: float = 0.85  # reject if too similar to recent post
    
    # Database
    db_url: str = "sqlite+aiosqlite:///./data/tg_poster.db"
    
    # Learning
    feedback_learning_enabled: bool = True
    min_reactions_to_learn: int = 5
    top_posts_in_context: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        yaml_file="config.yaml"
    )
```

### `memory/models.py`

```python
# SQLAlchemy 2.x declarative models

class Post(Base):
    id: int (PK)
    content: str           # full post text
    topic: str             # topic slug
    source_url: str        # original source if any
    source_title: str      # original article title
    published_at: datetime
    status: str            # "published" | "draft" | "rejected" | "pending"
    char_count: int
    emoji_count: int
    hashtags: str          # JSON list
    engagement_score: float = 0.0
    reactions_count: int = 0
    views_count: int = 0
    message_id: int = 0    # Telegram message ID for tracking
    format_type: str       # "text" | "photo" | "poll" | "thread"
    created_at: datetime
    chroma_id: str         # reference to vector store

class Topic(Base):
    id: int (PK)
    name: str
    slug: str (unique)
    last_used_at: datetime
    use_count: int = 0
    avg_engagement: float = 0.0
    is_forbidden: bool = False

class Source(Base):
    id: int (PK)
    url: str (unique)
    source_type: str  # "rss" | "hn" | "producthunt" | "manual"
    last_fetched_at: datetime
    total_items_fetched: int = 0
    is_active: bool = True

class StyleProfile(Base):
    id: int (PK)
    created_at: datetime
    sample_posts: str      # JSON — top 5 posts by engagement
    style_instructions: str  # LLM-generated style fingerprint
    is_active: bool = True
```

### `pipeline/source_collector.py`

```python
# Collect articles from multiple sources
# Returns list of Article dataclasses

@dataclass
class Article:
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    relevance_score: float = 0.0

class SourceCollector:
    async def fetch_rss(self, url: str) -> list[Article]
    async def fetch_hackernews_top(self, limit: int = 20) -> list[Article]
    async def fetch_producthunt_today(self) -> list[Article]
    async def fetch_all(self) -> list[Article]
    async def deduplicate(self, articles: list[Article]) -> list[Article]
    
# HackerNews API: https://hacker-news.firebaseio.com/v0/topstories.json
# ProductHunt: use RSS feed https://www.producthunt.com/feed
# Filter by keywords related to channel_topic from config
```

### `pipeline/topic_selector.py`

```python
# LLM Agent that picks the best topic from collected articles
# Considers: recency, not used recently, high relevance to channel

TOPIC_SELECTOR_PROMPT = """
You are an editorial AI for a Telegram channel about: {channel_topic}

Here are today's available topics from news sources:
{articles_list}

Here are topics used in the last 14 days (DO NOT repeat these):
{recent_topics}

Channel audience: entrepreneurs, freelancers, marketers aged 25-40.

Select the SINGLE BEST topic that:
1. Is most relevant to the channel niche
2. Has not been covered recently  
3. Will engage the target audience
4. Has enough depth for a 200-900 character post

Respond with JSON only:
{{"topic": "...", "source_url": "...", "reason": "...", "angle": "..."}}
"""

class TopicSelector:
    async def select(self, articles: list[Article], recent_topics: list[str]) -> SelectedTopic
```

### `pipeline/prompt_builder.py`

```python
# Assembles the full generation prompt dynamically
# Injects: style, recent posts, topic, constraints

class PromptBuilder:
    async def build(self, topic: SelectedTopic, recent_posts: list[Post]) -> GenerationContext
    
# The built prompt must include:
# 1. Channel identity (topic, style, language)
# 2. Last 5 published posts (for style consistency)
# 3. Active style profile from StyleProfile table
# 4. The selected topic + angle + source
# 5. Format requirements (length, emojis, hashtags)
# 6. Forbidden patterns from recent posts
# 7. Example of a "perfect post" (best-performing historical post)
```

### `pipeline/llm_generator.py`

```python
# Agent-Editor: writes the initial post draft

POST_GENERATOR_SYSTEM = """
You are an expert content writer for a Telegram channel.
Channel topic: {channel_topic}
Writing style: {channel_style}
Language: {language}

Write posts that:
- Start with a STRONG HOOK (shocking fact, bold question, or counterintuitive statement)
- Use {emojis_per_post} relevant emojis placed naturally (not just at start)
- Have short paragraphs (2-3 sentences max each)
- End with {hashtags_count} relevant hashtags
- Feel written by a human expert who actually uses these tools
- Never start with "AI", "Нейросеть", "Сегодня"
- Never use corporate buzzwords: "инновационный", "уникальный", "революционный"

Post length: {post_length_min}–{post_length_max} characters.
Format: Telegram MarkdownV2.
"""

class LLMGenerator:
    async def generate(self, context: GenerationContext) -> PostDraft
    async def regenerate(self, draft: PostDraft, feedback: str) -> PostDraft
```

### `pipeline/agent_critic.py`

```python
# Agent-Critic: reviews the draft and suggests improvements
# Then rewrites the post based on its own critique

CRITIC_PROMPT = """
Review this Telegram post draft:

---
{draft}
---

Evaluate on a scale 1-10:
- Hook strength (first sentence)
- Clarity and conciseness  
- Emoji placement naturalness
- Value for the target audience
- Originality vs generic AI text

If ANY score is below 7, rewrite the full post to fix the issues.
If all scores are 7+, return the original post unchanged.

Respond with JSON:
{{"scores": {...}, "needs_rewrite": bool, "improved_post": "..." | null, "critique": "..."}}
"""

class AgentCritic:
    async def review_and_improve(self, draft: PostDraft) -> PostDraft
    # If needs_rewrite: returns improved version
    # If good enough: returns original
    # Max 2 critique cycles to avoid infinite loop
```

### `pipeline/quality_checker.py`

```python
# Final validation before publishing
# If fails: triggers regeneration (max 3 full attempts)

class QualityChecker:
    async def check(self, post: PostDraft) -> QualityResult
    
# Checks:
# 1. Length within [post_length_min, post_length_max]
# 2. Contains at least 1 emoji
# 3. Contains hashtags
# 4. No broken MarkdownV2 tags (unmatched *, _, etc.)
# 5. Semantic similarity < similarity_threshold vs last 10 posts
#    (use ChromaDB cosine similarity)
# 6. No forbidden_words from config
# 7. Hook present (first sentence is ≥ 10 words)

# QualityResult: passed: bool, failures: list[str], score: float
```

### `pipeline/formatter.py`

```python
# Converts LLM output to valid Telegram MarkdownV2
# Telegram MarkdownV2 requires escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !

class Formatter:
    def escape_markdownv2(self, text: str) -> str
    def format_post(self, raw_text: str) -> FormattedPost
    def add_signature(self, post: FormattedPost, channel_tag: str) -> FormattedPost
    def validate_markdown(self, text: str) -> bool

# The formatter must handle:
# - Bold text: **word** → *word* (Telegram syntax)
# - Code blocks preserved
# - URLs properly escaped
# - Hashtags formatted correctly
# - Emojis passed through unchanged
```

### `publisher/base.py`

```python
from abc import ABC, abstractmethod

class BasePublisher(ABC):
    @abstractmethod
    async def send_text(self, text: str, parse_mode: str = "MarkdownV2") -> PublishResult
    
    @abstractmethod  
    async def send_photo(self, text: str, photo_url: str) -> PublishResult
    
    @abstractmethod
    async def send_poll(self, question: str, options: list[str]) -> PublishResult
    
    @abstractmethod
    async def pin_message(self, message_id: int) -> bool
    
    @abstractmethod
    async def get_message_stats(self, message_id: int) -> MessageStats

@dataclass
class PublishResult:
    success: bool
    message_id: int
    published_at: datetime
    error: str | None = None

@dataclass  
class MessageStats:
    views: int
    reactions: dict[str, int]
    forwards: int
```

### `publisher/bot_publisher.py`

```python
# Mode A: Official Bot API via python-telegram-bot
# Bot must be added as admin to the channel
# Pros: safe, official, no ban risk
# Cons: posts show "via @botname" label

class BotPublisher(BasePublisher):
    # Use @with_retry(max_attempts=3, wait=exponential(multiplier=1, max=30))
    # from tenacity for all API calls
    
    # send_text: use bot.send_message(channel_id, text, parse_mode="MarkdownV2")
    # On MarkdownV2 parse error: fallback to plain HTML, log warning
    # Log every published post to database via post_store
    
    async def test_connection(self) -> bool:
        # Verify bot token and channel access on startup
```

### `publisher/telethon_publisher.py`

```python
# Mode B: User Account via Telethon
# Posts appear as regular user messages — no "via bot" label
#
# ⚠️  SECURITY WARNING (include in docstring):
# - Store session file securely (sessions/user.session)
# - Add sessions/ to .gitignore
# - Use a dedicated Telegram account, NOT your main account
# - Automated user account activity may violate Telegram ToS
# - Risk of account ban if Telegram detects automation patterns
# - Use human-like delays between actions (2-5 seconds)
#
# Session management:
# - Check if session file exists → reuse it
# - If not → start interactive phone auth flow
# - Store session encrypted if possible

class TelethonPublisher(BasePublisher):
    async def authenticate(self) -> bool
    async def disconnect(self) -> None
    # Add random delay 2-5 seconds before each post (human simulation)
```

### `memory/vector_store.py`

```python
# ChromaDB for semantic deduplication
# Prevents publishing posts with similar meaning even if different words

class VectorStore:
    def __init__(self, collection_name: str = "tg_posts")
    
    async def add_post(self, post_id: int, content: str) -> str
    # Returns chroma_id, store in Post.chroma_id
    
    async def find_similar(self, content: str, n_results: int = 5) -> list[SimilarPost]
    # Returns posts with similarity scores
    # If any result has similarity > settings.similarity_threshold → reject post
    
    async def get_collection_size(self) -> int

@dataclass
class SimilarPost:
    post_id: int
    content: str
    similarity: float  # 0.0 to 1.0
```

### `memory/feedback_loop.py`

```python
# Learns from engagement metrics
# Periodically fetches stats for recent posts
# Updates StyleProfile with top-performing post examples

class FeedbackLoop:
    async def collect_metrics(self) -> None
    # For each published post in last 7 days:
    # - Fetch views + reactions via Telegram API
    # - Update Post.engagement_score = reactions / max(views, 1) * 1000
    # - Store in database
    
    async def update_style_profile(self) -> None
    # Every 7 days:
    # - Select top 5 posts by engagement_score
    # - Send to LLM with style_analyzer.txt prompt
    # - LLM extracts style fingerprint (what makes these posts work)
    # - Save new StyleProfile, mark old one inactive
    
    async def get_top_posts(self, limit: int = 5) -> list[Post]
    # Returns best-performing posts for injection into prompts
```

### `core/scheduler.py`

```python
# APScheduler with 3 modes, graceful shutdown, error recovery

class Scheduler:
    async def start(self) -> None
    async def stop(self) -> None
    
    def _configure_jobs(self) -> None:
        if config.schedule_type == "interval":
            # Add job: every interval_hours hours
            
        elif config.schedule_type == "fixed":
            # Add cron jobs for each time in fixed_times
            # Respect timezone from config
            
        elif config.schedule_type == "random":
            # Add job that picks random time within window each day
            # Schedule for tomorrow after each run
    
    async def _run_pipeline(self) -> None:
        # Check max_daily_posts not exceeded
        # Check min_interval_minutes since last post
        # Run orchestrator.run_full_pipeline()
        # On failure: log error + notify admin via DM + retry in 30 min
    
    async def _notify_admin(self, error: str) -> None:
        # Send DM to admin_telegram_id with error details
```

### `utils/retry.py`

```python
# tenacity-based retry decorators

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def with_retry(max_attempts: int = 3):
    """Decorator for API calls with exponential backoff"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((httpx.TimeoutException, Exception)),
        reraise=True
    )

# Apply @with_retry() to:
# - All LLM API calls
# - All Telegram publish calls  
# - All external RSS/API fetches
# - All database writes
```

### `utils/rate_limiter.py`

```python
# Token bucket algorithm for rate limiting

class RateLimiter:
    # LLM: max 50 calls per minute
    # Telegram: max 30 messages per second (official limit)
    # Daily posts: enforced via database count check
    
    async def acquire(self, resource: str) -> None
    # Blocks until a token is available
    # resource: "llm" | "telegram" | "rss"
```

---

## LLM PROMPTS

### `llm/prompts/system.txt`

```
You are an AI editorial system managing a professional Telegram channel.

Channel identity:
- Topic: {channel_topic}
- Voice: {channel_style}
- Language: {language}
- Audience: entrepreneurs, freelancers, marketers aged 25-40

Your posts must:
✓ Start with a hook that makes people stop scrolling
✓ Deliver real, actionable value in under 900 characters
✓ Use emojis naturally — not as decoration, but as emphasis
✓ Feel written by a human practitioner, not a marketing bot
✓ Never repeat topics covered in the last 14 days

You never:
✗ Use: "инновационный", "революционный", "уникальный", "cutting-edge"
✗ Start with: "Сегодня", "Привет", "AI", "Нейросеть", "Хочу рассказать"
✗ Write corporate PR language
✗ Make unverifiable claims
```

### `llm/prompts/post_generator.txt`

```
Write a Telegram post about the following topic:

Topic: {topic}
Source material: {source_summary}
Angle to take: {angle}

Style reference — your best-performing recent posts:
{top_posts_examples}

Current style instructions:
{active_style_profile}

Post requirements:
- Length: {min_length}–{max_length} characters
- Emojis: exactly {emoji_count}, placed naturally within text
- Hashtags: {hashtag_count} at the end
- Format: Telegram MarkdownV2
- Hook: first sentence must create curiosity or deliver a surprising fact
- Structure: Hook → Key insight → Practical implication → CTA or hashtags

Do NOT include: post length, word count, or any meta-commentary.
Output the post text only. Nothing else.
```

### `llm/prompts/topic_selector.txt`

```
You are an editorial director for a Telegram channel about: {channel_topic}

Available stories today:
{articles_json}

Topics already covered (last 14 days):
{recent_topics_list}

Select ONE topic that maximizes:
1. Relevance to channel niche (weight: 40%)
2. Not covered recently (weight: 30%)
3. Audience interest potential (weight: 20%)
4. Depth available for a 200-900 char post (weight: 10%)

Return JSON only. No explanation outside JSON:
{{
  "topic": "brief topic name",
  "source_url": "url",
  "source_title": "original article title",
  "angle": "specific angle or insight to highlight",
  "reason": "one sentence why this topic was chosen",
  "estimated_engagement": "low|medium|high"
}}
```

### `llm/prompts/agent_critic.txt`

```
You are a strict post editor reviewing a Telegram post draft.

Channel: {channel_topic}
Language: {language}

POST TO REVIEW:
---
{draft_post}
---

Score each dimension (1-10):
- hook_strength: Does the first sentence stop scrolling?
- clarity: Is every sentence necessary?
- emoji_naturalness: Do emojis enhance meaning (not just decorate)?
- audience_value: Would the target reader save or share this?
- human_feel: Does it sound like a real person, not AI?

Rules:
- If ALL scores ≥ 7: return the original post unchanged
- If ANY score < 7: rewrite the FULL post to fix all issues

Return JSON only:
{{
  "scores": {{
    "hook_strength": N,
    "clarity": N,
    "emoji_naturalness": N,
    "audience_value": N,
    "human_feel": N
  }},
  "needs_rewrite": true|false,
  "critique": "what was wrong (if rewriting)",
  "improved_post": "full improved post text or null"
}}
```

### `llm/prompts/style_analyzer.txt`

```
Analyze these top-performing Telegram posts and extract the writing style fingerprint.

POSTS (ordered by engagement, best first):
{top_posts_with_scores}

Identify:
1. Sentence structure patterns
2. Vocabulary level and tone
3. How emojis are used
4. Information density
5. Hook patterns that work
6. What makes these posts resonate

Output actionable style instructions (max 300 words) that a writer 
could follow to replicate this success. Write as direct instructions.
Start with: "For this channel, always..."
```

---

## CONFIGURATION FILES

### `config.yaml`

```yaml
telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  channel_id: "@your_channel_here"
  posting_mode: "bot"           # "bot" or "telethon"

telethon:
  api_id: "${TELETHON_API_ID}"
  api_hash: "${TELETHON_API_HASH}"
  phone: "${TELETHON_PHONE}"

llm:
  provider: "openai"
  model: "gpt-4o"
  api_key: "${OPENAI_API_KEY}"
  temperature: 0.85
  max_tokens: 800

channel:
  topic: "AI tools and automation for business and freelancers"
  style: >
    Expert practitioner. Writes from personal experience.
    No hype, no buzzwords. Concrete examples and numbers.
    Conversational but professional. Like a smart colleague sharing a discovery.
  language: "ru"
  post_length_min: 250
  post_length_max: 900
  emojis_per_post: 3
  hashtags_count: 2

schedule:
  type: "fixed"
  fixed_times:
    - "09:30"
    - "14:00"  
    - "20:00"
  timezone: "Europe/Moscow"
  max_daily_posts: 3
  min_interval_minutes: 120

sources:
  rss_feeds:
    - "https://feeds.feedburner.com/oreilly/radar"
    - "https://www.producthunt.com/feed"
    - "https://hnrss.org/frontpage"
  use_hackernews: true
  use_producthunt: true

safety:
  manual_approval: false
  admin_telegram_id: "${ADMIN_TELEGRAM_ID}"
  similarity_threshold: 0.85
  forbidden_words: []
  max_regeneration_attempts: 3

learning:
  feedback_enabled: true
  style_update_interval_days: 7
  min_reactions_to_learn: 5
  top_posts_in_context: 5

database:
  url: "sqlite+aiosqlite:///./data/tg_poster.db"

logging:
  level: "INFO"
  file: "logs/tg_poster.log"
  rotation: "1 week"
  retention: "1 month"
```

### `.env.example`

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_ID=your_telegram_user_id

# Telethon (only needed for Mode B)
TELETHON_API_ID=
TELETHON_API_HASH=
TELETHON_PHONE=

# LLM APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=

# Database (for production PostgreSQL)
# DB_URL=postgresql+asyncpg://user:pass@localhost/tg_poster

# Redis (optional)
# REDIS_URL=redis://localhost:6379/0
```

### `requirements.txt`

```
# Telegram
python-telegram-bot==20.7
telethon==1.34.0

# LLM
openai==1.35.0
anthropic==0.29.0

# Database
sqlalchemy==2.0.30
aiosqlite==0.20.0
asyncpg==0.29.0  # for PostgreSQL

# Vector store
chromadb==0.5.0

# Scheduler
apscheduler==3.10.4

# Config
pydantic==2.7.0
pydantic-settings==2.3.0
pyyaml==6.0.1
python-dotenv==1.0.1

# HTTP & RSS
httpx==0.27.0
feedparser==6.0.11

# Retry
tenacity==8.3.0

# Logging
loguru==0.7.2

# Utils
python-dateutil==2.9.0
pytz==2024.1

# Redis (optional)
redis==5.0.5
rq==1.16.1

# Dev
pytest==8.2.0
pytest-asyncio==0.23.7
```

---

## `main.py` — Entry Point

```python
#!/usr/bin/env python3
"""
Autonomous AI Telegram Channel Manager
Usage: python main.py [--dry-run] [--post-now] [--setup]
"""
import asyncio
import argparse
import signal
from core.config import get_settings
from core.logger import setup_logging
from core.scheduler import Scheduler
from memory.database import init_database
from pipeline.orchestrator import Orchestrator

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", 
                       help="Generate post but don't publish")
    parser.add_argument("--post-now", action="store_true",
                       help="Run pipeline once immediately")
    parser.add_argument("--setup", action="store_true",
                       help="Run interactive setup wizard")
    args = parser.parse_args()
    
    settings = get_settings()
    setup_logging(settings)
    
    if args.setup:
        from setup import run_setup_wizard
        await run_setup_wizard()
        return
    
    # Initialize database
    await init_database()
    
    if args.post_now or args.dry_run:
        orchestrator = Orchestrator(settings, dry_run=args.dry_run)
        result = await orchestrator.run_full_pipeline()
        print(f"Result: {result}")
        return
    
    # Start scheduler
    scheduler = Scheduler(settings)
    
    # Graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(scheduler.stop()))
    
    await scheduler.start()
    
if __name__ == "__main__":
    asyncio.run(main())
```

---

## DEPLOYMENT

### Dockerfile

```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Non-root user
RUN useradd -m -u 1000 botuser

WORKDIR /app

COPY --from=builder /root/.local /home/botuser/.local
COPY --chown=botuser:botuser . .

# Create required directories
RUN mkdir -p data logs sessions && chown -R botuser:botuser .

USER botuser

ENV PATH=/home/botuser/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('data/tg_poster.db').close()" || exit 1

CMD ["python", "main.py"]
```

### `docker-compose.yml`

```yaml
version: "3.9"

services:
  app:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./sessions:/app/sessions
      - ./config.yaml:/app/config.yaml:ro
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/0

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  redis_data:
```

### VPS Deployment (Ubuntu 22.04)

```bash
# 1. Clone repo
git clone <repo> /opt/tg_ai_poster
cd /opt/tg_ai_poster

# 2. Setup environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your credentials
# Edit config.yaml with your channel settings

# 4. Initialize
python main.py --setup

# 5. Test run (no publishing)
python main.py --dry-run

# 6. Create systemd service
# /etc/systemd/system/tg-poster.service:
[Unit]
Description=TG AI Poster
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/tg_ai_poster
ExecStart=/opt/tg_ai_poster/venv/bin/python main.py
Restart=always
RestartSec=30
EnvironmentFile=/opt/tg_ai_poster/.env

[Install]
WantedBy=multi-user.target

# 7. Enable & start
systemctl enable tg-poster
systemctl start tg-poster
systemctl status tg-poster

# 8. Monitor logs
journalctl -u tg-poster -f
```

---

## TESTING

### Dry Run Mode

```bash
# Test full pipeline without posting to Telegram
python main.py --dry-run

# Expected output:
# [INFO] Pipeline started
# [INFO] Collected 23 articles from 4 sources
# [INFO] Topic selected: "GPT-4o mini cuts API costs by 60%"
# [INFO] Draft generated (487 chars)
# [INFO] Critic: scores {hook: 8, clarity: 9, ...} — no rewrite needed
# [INFO] Quality check: PASSED
# [INFO] DRY RUN — post NOT published
# [INFO] Generated post preview:
# ---
# <post content here>
# ---
```

### Unit Tests

```python
# Create tests/ directory with:
# tests/test_quality_checker.py — test all validation rules
# tests/test_formatter.py — test MarkdownV2 escaping
# tests/test_vector_store.py — test similarity detection
# tests/test_source_collector.py — mock RSS feeds
# tests/test_pipeline.py — integration test with mocked LLM
```

---

## ERROR HANDLING REQUIREMENTS

Every module must handle these scenarios gracefully:

| Scenario | Behavior |
|----------|----------|
| OpenAI API down | Retry 3x → switch to backup LLM → use cached topic |
| Telegram API rate limit | Wait + retry with backoff |
| No new topics found | Use LLM to generate topic from scratch |
| Generated post too similar | Regenerate with explicit instruction to differ |
| MarkdownV2 parse error | Strip formatting, send as plain text |
| Database locked | Retry with 1s delay |
| Scheduler crash | systemd/Docker auto-restart |
| RSS feed unavailable | Skip source, log warning, continue |

---

## IMPLEMENTATION ORDER

Build modules in this exact order (each depends on previous):

```
1.  core/config.py              ← settings foundation
2.  core/logger.py              ← logging for everything
3.  memory/models.py            ← database schema
4.  memory/database.py          ← DB init + migrations
5.  memory/post_store.py        ← CRUD
6.  memory/vector_store.py      ← ChromaDB wrapper
7.  llm/base.py                 ← abstract adapter
8.  llm/openai_adapter.py       ← OpenAI implementation
9.  utils/retry.py              ← retry decorators
10. utils/rate_limiter.py       ← rate limiting
11. utils/validators.py         ← content checks
12. pipeline/source_collector.py
13. pipeline/content_filter.py
14. pipeline/topic_selector.py
15. pipeline/prompt_builder.py
16. pipeline/llm_generator.py
17. pipeline/agent_critic.py
18. pipeline/quality_checker.py
19. pipeline/formatter.py
20. publisher/base.py
21. publisher/bot_publisher.py
22. publisher/telethon_publisher.py
23. memory/feedback_loop.py
24. pipeline/orchestrator.py    ← wires everything together
25. core/scheduler.py           ← timing control
26. main.py                     ← entry point
27. setup.py                    ← interactive first-run wizard
28. Dockerfile + docker-compose.yml
29. README.md
```

---

## DEFINITION OF DONE

The system is complete when:

- [ ] `python main.py --dry-run` runs without errors and prints a generated post
- [ ] `python main.py --post-now` publishes a real post to a test channel
- [ ] Scheduler runs and publishes at configured times
- [ ] Duplicate detection prevents same-topic posts within 14 days
- [ ] Style profile updates after 7 days based on engagement
- [ ] Docker deployment works: `docker-compose up -d`
- [ ] All errors are logged with full context
- [ ] Admin gets Telegram DM on pipeline failure
- [ ] README has complete setup instructions from zero

---

## START NOW

Begin with module 1 (`core/config.py`) and proceed through 
the implementation order above.

Create all files. Write all code. Make it run.
```
