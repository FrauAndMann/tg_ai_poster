# TG AI Poster: Pipeline Refactor Design

**Date:** 2025-03-11
**Status:** Approved
**Author:** Claude (AI Architect)

---

## Executive Summary

Deep refactoring of TG AI Poster with event-driven architecture, media plugin system, clickable source links, and adaptive post type configurations.

### Key Changes

| Area | Before | After |
|------|--------|-------|
| Architecture | Monolithic PipelineOrchestrator (726 lines) | Event-driven PipelineCoordinator + Stage handlers |
| Media | Prompt generation only (unused) | Unsplash/Pexels integration with real images |
| Links | Plain text sources | Clickable markdown links in dedicated block |
| Post types | Hardcoded temperature/limits | Configurable per-type settings in YAML |
| Testing | Basic unit tests | Full unit + integration coverage |

---

## 1. Architecture Overview

### 1.1 New Project Structure

```
tg_ai_poster/
├── core/
│   ├── events.py           # EventBus, PipelineEvent types
│   ├── config.py           # Extended Settings
│   └── scheduler.py        # APScheduler (unchanged)
│
├── domain/
│   ├── post.py             # Post aggregate, PostType, PostTypeConfig
│   ├── source.py           # Source value object
│   └── media.py            # Media value object
│
├── pipeline/
│   ├── coordinator.py      # Event subscriber, flow control
│   └── stages/             # Individual stage handlers
│       ├── __init__.py
│       ├── collection.py
│       ├── selection.py
│       ├── generation.py
│       ├── review.py
│       ├── quality.py
│       ├── media.py
│       └── formatting.py
│
├── plugins/
│   ├── media/
│   │   ├── __init__.py
│   │   ├── base.py         # MediaProvider interface
│   │   ├── unsplash.py     # Unsplash implementation
│   │   └── pexels.py       # Pexels fallback
│   └── formatters/
│       ├── __init__.py
│       ├── base.py         # PostFormatter interface
│       └── telegram.py     # Telegram MarkdownV2
│
├── llm/                    # Unchanged
├── publisher/              # Unchanged (add media support)
├── memory/                 # + migration
└── main.py
```

### 1.2 Event Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     EventBus (pyee)                         │
└─────────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
   SOURCES_COLLECTED  POST_GENERATED  MEDIA_FETCHED
   TOPIC_SELECTED     POST_REVIEWED   POST_FORMATTED
                      QUALITY_CHECKED POST_PUBLISHED
         │                │                │
         └────────────────┴────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  PipelineCoordinator  │
              │  (subscribes to all)  │
              └───────────────────────┘
```

---

## 2. Event System

### 2.1 Event Types

```python
# core/events.py

from pyee.asyncio import AsyncIOEventEmitter
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class EventType(Enum):
    # Pipeline lifecycle
    PIPELINE_START = "pipeline:start"
    PIPELINE_COMPLETE = "pipeline:complete"
    PIPELINE_ERROR = "pipeline:error"

    # Stage events
    SOURCES_COLLECTED = "sources:collected"
    TOPIC_SELECTED = "topic:selected"
    POST_GENERATED = "post:generated"
    POST_REVIEWED = "post:reviewed"
    QUALITY_CHECKED = "quality:checked"
    MEDIA_FETCHED = "media:fetched"
    POST_FORMATTED = "post:formatted"
    POST_PUBLISHED = "post:published"

    # Error events
    STAGE_FAILED = "stage:failed"

@dataclass
class PipelineEvent:
    type: EventType
    data: dict
    post_id: Optional[int] = None
    error: Optional[str] = None

# Global event bus singleton
event_bus = AsyncIOEventEmitter()
```

### 2.2 Pipeline Coordinator

```python
# pipeline/coordinator.py

class PipelineCoordinator:
    """Orchestrates pipeline flow via event subscriptions."""

    def __init__(
        self,
        event_bus: AsyncIOEventEmitter,
        settings: Settings,
        db: Database,
        publisher: Optional[BasePublisher] = None,
    ):
        self.bus = event_bus
        self.settings = settings
        self.db = db
        self.publisher = publisher

        # Initialize stages
        self.stages = self._init_stages()
        self._setup_handlers()

    def _setup_handlers(self):
        """Subscribe to stage completion events."""
        self.bus.on(EventType.SOURCES_COLLECTED, self._on_sources_collected)
        self.bus.on(EventType.TOPIC_SELECTED, self._on_topic_selected)
        self.bus.on(EventType.POST_GENERATED, self._on_post_generated)
        self.bus.on(EventType.POST_REVIEWED, self._on_post_reviewed)
        self.bus.on(EventType.QUALITY_CHECKED, self._on_quality_checked)
        self.bus.on(EventType.MEDIA_FETCHED, self._on_media_fetched)
        self.bus.on(EventType.POST_FORMATTED, self._on_post_formatted)

    async def run(self, dry_run: bool = False) -> PipelineResult:
        """Execute full pipeline."""
        self.bus.emit(EventType.PIPELINE_START.value, PipelineEvent(
            type=EventType.PIPELINE_START,
            data={"dry_run": dry_run}
        ))

        # Start with collection
        await self.stages["collection"].execute()

        # Wait for PIPELINE_COMPLETE or error
        # ... coordinator manages state transitions
```

---

## 3. Domain Model

### 3.1 PostType and Configuration

```python
# domain/post.py

from enum import Enum
from dataclasses import dataclass

class PostType(Enum):
    BREAKING = "breaking"
    DEEP_DIVE = "deep_dive"
    ANALYSIS = "analysis"
    TOOL_ROUNDUP = "tool_roundup"

@dataclass(frozen=True)
class PostTypeConfig:
    """Configuration for each post type."""
    min_length: int
    max_length: int
    temperature: float
    require_sources: bool
    require_media: bool
    emoji_range: tuple[int, int]  # (min, max)

POST_TYPE_CONFIGS: dict[PostType, PostTypeConfig] = {
    PostType.BREAKING: PostTypeConfig(
        min_length=800,
        max_length=1500,
        temperature=0.15,
        require_sources=True,
        require_media=True,
        emoji_range=(2, 4),
    ),
    PostType.DEEP_DIVE: PostTypeConfig(
        min_length=2000,
        max_length=3500,
        temperature=0.4,
        require_sources=True,
        require_media=True,
        emoji_range=(1, 3),
    ),
    PostType.ANALYSIS: PostTypeConfig(
        min_length=1500,
        max_length=3000,
        temperature=0.35,
        require_sources=False,
        require_media=False,
        emoji_range=(1, 2),
    ),
    PostType.TOOL_ROUNDUP: PostTypeConfig(
        min_length=1000,
        max_length=2000,
        temperature=0.2,
        require_sources=True,
        require_media=True,
        emoji_range=(3, 5),
    ),
}
```

### 3.2 Post Aggregate

```python
# domain/post.py

@dataclass
class PostContent:
    title: str
    hook: Optional[str]
    body: str
    tldr: Optional[str]
    analysis: Optional[str]
    key_facts: list[str]
    hashtags: list[str]

@dataclass
class PostMetadata:
    created_at: datetime
    llm_model: str
    generation_time: float
    tokens_used: int

@dataclass
class Post:
    """Post aggregate root."""
    id: Optional[int]
    topic: str
    post_type: PostType
    content: PostContent
    sources: list[Source]
    media: Optional[Media]
    metadata: PostMetadata

    def format_sources_block(self) -> str:
        """Generate clickable sources block."""
        lines = ["🔗 Источники:"]
        for src in self.sources[:3]:
            lines.append(f"• [{src.name}]({src.url})")
        return "\n".join(lines)

    def validate_length(self) -> tuple[bool, str]:
        """Validate length by post type."""
        config = POST_TYPE_CONFIGS[self.post_type]
        length = len(self.content.body)

        if length < config.min_length:
            return False, f"Too short: {length} < {config.min_length}"
        if length > config.max_length:
            return False, f"Too long: {length} > {config.max_length}"
        return True, "OK"

    def full_text(self) -> str:
        """Get full post text for length calculation."""
        parts = [self.content.title]
        if self.content.hook:
            parts.append(self.content.hook)
        parts.append(self.content.body)
        if self.content.key_facts:
            parts.extend(self.content.key_facts)
        if self.content.analysis:
            parts.append(self.content.analysis)
        if self.content.tldr:
            parts.append(self.content.tldr)
        return "\n".join(parts)
```

### 3.3 Value Objects

```python
# domain/source.py

@dataclass(frozen=True)
class Source:
    """Source value object."""
    name: str
    url: str
    title: str
    credibility: int  # 0-100

# domain/media.py

@dataclass(frozen=True)
class Media:
    """Media value object."""
    url: str
    source: str  # "unsplash" | "pexels"
    photographer: Optional[str]
    prompt: Optional[str]
```

---

## 4. Media Plugin System

### 4.1 Interface

```python
# plugins/media/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class MediaSearchResult:
    url: str
    photographer: str
    source: str
    width: int
    height: int

class MediaProvider(ABC):
    """Interface for image providers."""

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[MediaSearchResult]:
        """Search images by query."""
        pass

    @abstractmethod
    async def get_random(self, topic: str) -> Optional[MediaSearchResult]:
        """Get random image for topic. Returns None if no results."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    @abstractmethod
    def rate_limit(self) -> tuple[int, int]:
        """(limit_per_hour, remaining)."""
        pass
```

### 4.2 Unsplash Implementation

```python
# plugins/media/unsplash.py

import httpx
from .base import MediaProvider, MediaSearchResult

class UnsplashProvider(MediaProvider):
    """Unsplash API implementation."""

    TOPIC_KEYWORDS = {
        "ai": "artificial intelligence technology",
        "llm": "machine learning neural network",
        "neural": "neural network abstract",
        "robot": "robot technology",
        "automation": "automation technology",
        "startup": "startup business technology",
        "data": "data science analytics",
        "cloud": "cloud computing technology",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.unsplash.com"
        self._remaining = 50

    async def search(self, query: str, limit: int = 5) -> list[MediaSearchResult]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/search/photos",
                params={"query": query, "per_page": limit},
                headers={"Authorization": f"Client-ID {self.api_key}"}
            )
            self._remaining = int(resp.headers.get("X-RateLimit-Remaining", 0))

            results = []
            for item in resp.json().get("results", []):
                results.append(MediaSearchResult(
                    url=item["urls"]["regular"],
                    photographer=item["user"]["name"],
                    source="unsplash",
                    width=item["width"],
                    height=item["height"],
                ))
            return results

    async def get_random(self, topic: str) -> MediaSearchResult:
        keywords = self._extract_keywords(topic)
        results = await self.search(keywords[0], limit=1)
        return results[0] if results else None

    def _extract_keywords(self, topic: str) -> list[str]:
        topic_lower = topic.lower()
        for key, value in self.TOPIC_KEYWORDS.items():
            if key in topic_lower:
                return [value, "technology", "digital"]
        return ["technology", "innovation", "abstract"]

    @property
    def name(self) -> str:
        return "unsplash"

    @property
    def rate_limit(self) -> tuple[int, int]:
        return (50, self._remaining)
```

### 4.3 Media Stage

```python
# pipeline/stages/media.py

from core.events import event_bus, EventType, PipelineEvent
from domain.post import Post, POST_TYPE_CONFIGS

class MediaStage:
    """Fetches media for posts."""

    def __init__(self, providers: list[MediaProvider]):
        self.providers = sorted(providers, key=lambda p: p.rate_limit[1], reverse=True)

    async def execute(self, post: Post) -> Optional[Media]:
        config = POST_TYPE_CONFIGS[post.post_type]

        if not config.require_media:
            return None

        for provider in self.providers:
            try:
                result = await provider.get_random(post.topic)
                if result:
                    media = Media(
                        url=result.url,
                        source=result.source,
                        photographer=result.photographer,
                        prompt=None,
                    )
                    event_bus.emit(EventType.MEDIA_FETCHED.value, PipelineEvent(
                        type=EventType.MEDIA_FETCHED,
                        data={"media": media, "provider": provider.name}
                    ))
                    return media
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue

        logger.warning("All media providers failed")
        return None
```

---

## 5. Formatting & Links

### 5.1 Telegram Formatter

```python
# plugins/formatters/telegram.py

from domain.post import Post

class TelegramFormatter:
    """Formats posts for Telegram MarkdownV2."""

    ESCAPE_CHARS = "_*[]()~`>#+-=|{}.!"

    def format(self, post: Post) -> str:
        """Format complete post."""
        parts = []

        # 1. Title (bold)
        parts.append(self._bold(self._escape(post.content.title)))
        parts.append("")

        # 2. Hook (italic)
        if post.content.hook:
            parts.append(self._italic(self._escape(post.content.hook)))
            parts.append("")

        # 3. Body
        parts.append(self._escape(post.content.body))
        parts.append("")

        # 4. Key Facts
        if post.content.key_facts:
            parts.append("🔍 Что важно знать:")
            for fact in post.content.key_facts:
                parts.append(f"• {self._escape(fact)}")
            parts.append("")

        # 5. Analysis
        if post.content.analysis:
            parts.append("🧠 Почему это важно:")
            parts.append(self._escape(post.content.analysis))
            parts.append("")

        # 6. TL;DR
        if post.content.tldr:
            parts.append(f"💡 TL;DR: {self._escape(post.content.tldr)}")
            parts.append("")

        # 7. Sources (clickable!)
        if post.sources:
            parts.append(self.format_sources(post.sources))
            parts.append("")

        # 8. Hashtags
        if post.content.hashtags:
            hashtag_str = " ".join(f"#{tag}" for tag in post.content.hashtags)
            parts.append(self._escape(hashtag_str))

        # 9. Photo attribution
        if post.media and post.media.photographer:
            parts.append(f"\n📸 Photo: {post.media.photographer}")

        return "\n".join(parts)

    def format_sources(self, sources: list[Source]) -> str:
        """Format clickable sources block."""
        lines = ["🔗 Источники:"]
        for src in sources[:3]:
            escaped_name = self._escape(src.name)
            # URL stays unescaped for links
            lines.append(f"• [{escaped_name}]({src.url})")
        return "\n".join(lines)

    def _escape(self, text: str) -> str:
        """Escape for MarkdownV2 (not URLs)."""
        for char in self.ESCAPE_CHARS:
            text = text.replace(char, f"\\{char}")
        return text

    def _bold(self, text: str) -> str:
        return f"*{text}*"

    def _italic(self, text: str) -> str:
        return f"_{text}_"

    def validate(self, content: str) -> tuple[bool, Optional[str]]:
        """Validate MarkdownV2 format."""
        if len(content) > 4096:
            return False, f"Exceeds limit: {len(content)} > 4096"

        if content.count("*") % 2 != 0:
            return False, "Unbalanced bold markers (*)"
        if content.count("_") % 2 != 0:
            return False, "Unbalanced italic markers (_)"

        return True, None
```

### 5.2 Example Formatted Post

```
*OpenAI запускает GPT\-5: что изменилось*

_Революция в мире AI или эволюционный шаг?_

OpenAI анонсировала GPT\-5, который обещает значительный скачок
в возможностях\. Новая модель демонстрирует улучшенное понимание
контекста и способность к сложным рассуждениям\.

🔍 Что важно знать:
• Модель обучена на 10x больше данных
• Поддержка контекста до 1M токенов
• Multimodal возможности из коробки

🧠 Почему это важно:
Это не просто улучшение — это качественный скачок в том,
как AI может помогать в сложных задачах\.

💡 TL;DR: GPT\-5 выходит в конце года

🔗 Источники:
• [OpenAI Blog](https://openai.com/blog/gpt5)
• [TechCrunch](https://techcrunch.com/2024/gpt5)

#AI #GPT5 #OpenAI

📸 Photo: John Doe
```

---

## 6. Configuration

### 6.1 Extended config.yaml

```yaml
# config.yaml

telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  channel_id: "${TELEGRAM_CHANNEL_ID}"
  posting_mode: "bot"

llm:
  provider: "claude-cli"
  model: "glm-5"
  max_tokens: 2000
  temperature: 0.15

channel:
  topic: "AI technologies and future of automation"
  style: >
    Expert but accessible. Think pieces. No hype.
  language: "ru"
  post_length_min: 800
  post_length_max: 1500
  emojis_per_post: 3
  hashtags_count: 3

# NEW: Post type configurations
post_types:
  breaking:
    enabled: true
    weight: 40
    min_length: 800
    max_length: 1500
    temperature: 0.15
    require_sources: true
    require_media: true
    emoji_range: [2, 4]
    prompt_template: "post_breaking.txt"

  deep_dive:
    enabled: true
    weight: 25
    min_length: 2000
    max_length: 3500
    temperature: 0.4
    require_sources: true
    require_media: true
    emoji_range: [1, 3]
    prompt_template: "post_deep_dive.txt"

  analysis:
    enabled: true
    weight: 25
    min_length: 1500
    max_length: 3000
    temperature: 0.35
    require_sources: false
    require_media: false
    emoji_range: [1, 2]
    prompt_template: "post_analysis.txt"

  tool_roundup:
    enabled: true
    weight: 10
    min_length: 1000
    max_length: 2000
    temperature: 0.2
    require_sources: true
    require_media: true
    emoji_range: [3, 5]
    prompt_template: "post_tool_roundup.txt"

# NEW: Media configuration
media:
  enabled: true
  providers:
    - name: unsplash
      priority: 1
      api_key: "${UNSPLASH_ACCESS_KEY}"
    - name: pexels
      priority: 2
      api_key: "${PEXELS_API_KEY}"
  fallback_to_none: true
  attribution_required: true

# NEW: Formatting configuration
formatting:
  parse_mode: "MarkdownV2"
  include_sources_block: true
  max_sources: 3
  include_attribution: true

# Existing sections...
schedule:
  type: "fixed"
  timezone: "Europe/Moscow"
  fixed_times: ["07:00", "09:30", "12:00", "14:00", "16:30", "19:00", "20:00", "21:00", "21:30", "22:30", "23:30", "23:50"]
  max_daily_posts: 12

safety:
  manual_approval: false
  similarity_threshold: 0.85
  max_regeneration_attempts: 3

database:
  url: "sqlite+aiosqlite:///./data/tg_poster.db"
```

### 6.2 Settings Model Updates

```python
# core/config.py

@dataclass
class PostTypeSettings:
    enabled: bool
    weight: int
    min_length: int
    max_length: int
    temperature: float
    require_sources: bool
    require_media: bool
    emoji_range: tuple[int, int]
    prompt_template: str

@dataclass
class MediaSettings:
    enabled: bool
    providers: list[dict]
    fallback_to_none: bool
    attribution_required: bool

@dataclass
class FormattingSettings:
    parse_mode: str
    include_sources_block: bool
    max_sources: int
    include_attribution: bool

@dataclass
class Settings:
    # Existing fields...

    # NEW fields
    post_types: dict[str, PostTypeSettings]
    media: MediaSettings
    formatting: FormattingSettings

    def get_post_type_config(self, post_type: str) -> PostTypeSettings:
        return self.post_types.get(post_type, self.post_types["breaking"])

    def select_random_post_type(self) -> str:
        """Select post type by weighted random."""
        import random
        types = [(k, v.weight) for k, v in self.post_types.items() if v.enabled]
        total = sum(w for _, w in types)
        r = random.randint(1, total)
        cumulative = 0
        for name, weight in types:
            cumulative += weight
            if r <= cumulative:
                return name
        return "breaking"
```

---

## 7. Database Migration

### 7.1 Model Changes

```python
# memory/models.py

class Post(Base):
    __tablename__ = "posts"

    # ... existing fields ...

    # NEW: Enhanced media fields
    media_url: Mapped[str] = mapped_column(String(1000), nullable=True)
    media_source: Mapped[str] = mapped_column(String(50), nullable=True)
    media_photographer: Mapped[str] = mapped_column(String(200), nullable=True)

    # NEW: Structured sources
    sources_json: Mapped[str] = mapped_column(Text, nullable=True)
    # Format: [{"name": "...", "url": "...", "title": "...", "credibility": 90}]
```

### 7.2 Migration Script

```python
# migrations/versions/xxx_add_media_fields.py

def upgrade():
    op.add_column('posts', sa.Column('media_url', sa.String(1000), nullable=True))
    op.add_column('posts', sa.Column('media_source', sa.String(50), nullable=True))
    op.add_column('posts', sa.Column('media_photographer', sa.String(200), nullable=True))
    op.add_column('posts', sa.Column('sources_json', sa.Text, nullable=True))

    # Migrate existing post_sources to sources_json
    conn = op.get_bind()
    posts = conn.execute(sa.text("SELECT id, source, source_url FROM posts WHERE source_url IS NOT NULL"))

    for post in posts:
        sources = [{"name": post.source or "Source", "url": post.source_url, "credibility": 70}]
        conn.execute(
            sa.text("UPDATE posts SET sources_json = :sj WHERE id = :id"),
            {"sj": json.dumps(sources), "id": post.id}
        )

def downgrade():
    op.drop_column('posts', 'media_url')
    op.drop_column('posts', 'media_source')
    op.drop_column('posts', 'media_photographer')
    op.drop_column('posts', 'sources_json')
```

---

## 8. Testing Strategy

### 8.1 Test Structure

```
tests/
├── unit/
│   ├── domain/
│   │   ├── test_post.py
│   │   ├── test_post_type.py
│   │   └── test_source.py
│   ├── plugins/
│   │   ├── test_unsplash.py
│   │   └── test_telegram_formatter.py
│   └── stages/
│       ├── test_collection.py
│       ├── test_generation.py
│       └── test_media.py
│
├── integration/
│   ├── test_pipeline_flow.py
│   ├── test_event_bus.py
│   └── test_media_integration.py
│
└── fixtures/
    ├── sample_articles.json
    ├── sample_posts.json
    └── mock_responses.py
```

### 8.2 Coverage Targets

| Module | Target Coverage |
|--------|-----------------|
| `domain/` | 90% |
| `plugins/` | 85% |
| `pipeline/stages/` | 80% |
| `core/events.py` | 95% |

---

## 2.3 Stage Execution Flow

The coordinator manages stage transitions via async state machine:

```python
# pipeline/coordinator.py

class PipelineCoordinator:
    def __init__(self, ...):
        self._current_state = "idle"
        self._pipeline_data = {}  # Shared state across stages
        self._result_future: Optional[asyncio.Future] = None

    async def run(self, dry_run: bool = False) -> PipelineResult:
        """Execute pipeline and wait for completion."""
        self._result_future = asyncio.Future()
        self._pipeline_data = {"dry_run": dry_run}

        # Emit start event
        self.bus.emit(EventType.PIPELINE_START.value, PipelineEvent(
            type=EventType.PIPELINE_START,
            data={"dry_run": dry_run}
        ))

        # Trigger first stage
        await self.stages["collection"].execute()

        # Wait for completion (set by _on_pipeline_complete)
        return await self._result_future

    def _on_sources_collected(self, event: PipelineEvent):
        """Called when sources are collected."""
        self._pipeline_data["articles"] = event.data["articles"]
        asyncio.create_task(self.stages["selection"].execute(self._pipeline_data))

    def _on_topic_selected(self, event: PipelineEvent):
        """Called when topic is selected."""
        self._pipeline_data["topic"] = event.data["topic"]
        asyncio.create_task(self.stages["generation"].execute(self._pipeline_data))

    # ... similar handlers for each stage ...

    def _on_post_published(self, event: PipelineEvent):
        """Called when post is published - pipeline complete."""
        result = PipelineResult(
            success=True,
            post_id=event.post_id,
            content=event.data.get("content"),
            duration=time.time() - self._pipeline_data.get("start_time", time.time()),
        )
        self._result_future.set_result(result)
```

### Event Chaining Pattern

```
PIPELINE_START
    │
    ▼
COLLECTION.execute() ─────────────────────────────────────┐
    │                                                      │
    ▼                                                      │
SOURCES_COLLECTED event ──► _on_sources_collected()       │
    │                                                      │
    ▼                                                      │
SELECTION.execute()                                        │
    │                                                      │
    ▼                                                      │
TOPIC_SELECTED event ──► _on_topic_selected()             │
    │                                                      │
    ▼                                                      │
GENERATION.execute()                                        │
    │                                                      │
    ▼                                                      │
... (continues through review, quality, media, formatting) │
    │                                                      │
    ▼                                                      │
POST_PUBLISHED event ──► _on_post_published() ────────────┘
    │
    ▼
Result returned to caller
```

---

## 3.4 Domain-Model Mapping

Conversion between domain dataclasses and SQLAlchemy models:

```python
# memory/mappers.py

from domain.post import Post, PostContent, PostMetadata, PostType
from domain.source import Source
from domain.media import Media
from memory.models import Post as PostModel

class PostMapper:
    """Converts between domain and persistence layer."""

    @staticmethod
    def to_domain(model: PostModel) -> Post:
        """Convert SQLAlchemy model to domain Post."""
        sources = []
        if model.sources_json:
            for src in json.loads(model.sources_json):
                sources.append(Source(
                    name=src["name"],
                    url=src["url"],
                    title=src.get("title", ""),
                    credibility=src.get("credibility", 70),
                ))

        media = None
        if model.media_url:
            media = Media(
                url=model.media_url,
                source=model.media_source or "unknown",
                photographer=model.media_photographer,
                prompt=None,
            )

        return Post(
            id=model.id,
            topic=model.topic or "",
            post_type=PostType(model.post_type or "breaking"),
            content=PostContent(
                title=model.post_title or "",
                hook=model.post_hook,
                body=model.post_body or model.content,
                tldr=model.post_tldr,
                analysis=model.post_analysis,
                key_facts=json.loads(model.post_key_facts) if model.post_key_facts else [],
                hashtags=json.loads(model.post_hashtags) if model.post_hashtags else [],
            ),
            sources=sources,
            media=media,
            metadata=PostMetadata(
                created_at=model.created_at,
                llm_model=model.llm_model or "",
                generation_time=0.0,
                tokens_used=0,
            ),
        )

    @staticmethod
    def to_model(post: Post) -> PostModel:
        """Convert domain Post to SQLAlchemy model."""
        return PostModel(
            id=post.id,
            topic=post.topic,
            post_type=post.post_type.value,
            content=post.content.body,
            post_title=post.content.title,
            post_hook=post.content.hook,
            post_body=post.content.body,
            post_tldr=post.content.tldr,
            post_analysis=post.content.analysis,
            post_key_facts=json.dumps(post.content.key_facts),
            post_hashtags=json.dumps(post.content.hashtags),
            sources_json=json.dumps([
                {"name": s.name, "url": s.url, "title": s.title, "credibility": s.credibility}
                for s in post.sources
            ]),
            media_url=post.media.url if post.media else None,
            media_source=post.media.source if post.media else None,
            media_photographer=post.media.photographer if post.media else None,
        )
```

---

## 4.4 Pexels Implementation

Pexels provider follows the same pattern as Unsplash:

```python
# plugins/media/pexels.py

import httpx
from typing import Optional
from .base import MediaProvider, MediaSearchResult

class PexelsProvider(MediaProvider):
    """Pexels API implementation (fallback provider)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.pexels.com/v1"
        self._remaining = 200  # Pexels allows 200 req/hour

    async def search(self, query: str, limit: int = 5) -> list[MediaSearchResult]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/search",
                params={"query": query, "per_page": limit},
                headers={"Authorization": self.api_key}
            )

            results = []
            for item in resp.json().get("photos", []):
                results.append(MediaSearchResult(
                    url=item["src"]["large"],
                    photographer=item["photographer"],
                    source="pexels",
                    width=item["width"],
                    height=item["height"],
                ))
            return results

    async def get_random(self, topic: str) -> Optional[MediaSearchResult]:
        # Similar keyword extraction as Unsplash
        results = await self.search(topic, limit=1)
        return results[0] if results else None

    @property
    def name(self) -> str:
        return "pexels"

    @property
    def rate_limit(self) -> tuple[int, int]:
        return (200, self._remaining)
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Events + Domain)
- [ ] Create `core/events.py` with EventBus and EventType enum
- [ ] Create `domain/` models (Post, PostType, Source, Media)
- [ ] Update `core/config.py` with new settings
- [ ] Write unit tests for domain models

### Phase 2: Pipeline Refactor
- [ ] Create `pipeline/stages/` modules (6 stages)
- [ ] Create `pipeline/coordinator.py`
- [ ] Deprecate old `PipelineOrchestrator`
- [ ] Write stage tests

### Phase 3: Media Integration
- [ ] Create `plugins/media/base.py` interface
- [ ] Implement `plugins/media/unsplash.py`
- [ ] Implement `plugins/media/pexels.py` (fallback)
- [ ] Create media stage handler
- [ ] Write media plugin tests

### Phase 4: Formatting
- [ ] Create `plugins/formatters/base.py` interface
- [ ] Refactor existing formatter to `plugins/formatters/telegram.py`
- [ ] Add clickable sources formatting
- [ ] Write formatter tests

### Phase 5: Database Migration
- [ ] Create Alembic migration
- [ ] Update `PostStore` with new methods
- [ ] Migrate existing data
- [ ] Test migration

### Phase 6: Integration
- [ ] Wire all components in `main.py`
- [ ] Update publisher to use media
- [ ] End-to-end testing
- [ ] Documentation update

---

## 10. Dependencies

### New Dependencies

```txt
# requirements.txt additions
pyee>=11.0.0          # Event emitter
httpx>=0.27.0         # Already present, for media API calls
```

### Environment Variables

```bash
# .env additions
UNSPLASH_ACCESS_KEY=your_key_here
PEXELS_API_KEY=your_key_here  # Optional fallback
```

---

## 11. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Event flow complexity | Clear event schema, comprehensive logging |
| API rate limits | Provider fallback chain, caching |
| Migration data loss | Backup before migration, rollback script |
| Performance regression | Benchmark before/after, async optimization |

---

## 12. Success Criteria

- [ ] All existing functionality preserved
- [ ] Media images appear in 80%+ posts (when required)
- [ ] Source links are clickable in Telegram
- [ ] Post types follow configured limits
- [ ] Test coverage ≥ 80%
- [ ] Pipeline execution time ≤ 30 seconds
- [ ] Zero data loss in migration

---

## Appendix A: PipelineResult Dataclass

```python
# core/result.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class PipelineResult:
    """Pipeline execution result."""
    success: bool
    post_id: Optional[int] = None
    content: Optional[str] = None
    topic: Optional[str] = None
    quality_score: float = 0.0
    editor_score: float = 0.0
    verification_score: float = 0.0
    media_url: Optional[str] = None
    sources: list[dict] = dataclasses.field(default_factory=dict)
    duration: float = 0.0
    error: Optional[str] = None
```
