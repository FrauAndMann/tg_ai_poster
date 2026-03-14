# Quick Wins Implementation Design

**Date:** 2025-03-14
**Author:** Claude Code
**Status:** Draft
**Version:** 1.0

---

## Overview

This document describes the design for 5 Quick Win features for the TG AI Poster project, These features are designed for rapid implementation (1-2 days each) while providing immediate value to the the system.

---

## Goals

1. **Polls Generation** - Generate interactive polls for topics that suit them
2. **Weekly Reports** - Automated weekly performance summaries sent to admin
3. **Post Templates** - Configurable templates for different post types
4. **Audit Log** - Comprehensive logging of all system actions
5. **Health Checks** - System health monitoring and startup validation

---

## Design Principles

- **Integration over modularity** - Features integrate into existing pipeline flow
- **Configuration-driven** - All features controlled via config.yaml
- **Minimal dependencies** - Reuse existing infrastructure where possible
- **Graceful degradation** - Features fail independently without breaking core functionality

---

## Feature 1: Polls Generation

### Purpose
Generate interactive polls when the topic is suitable (e.g., surveys, opinions, preferences).

### Integration Point
After TopicSelector in the pipeline flow. Decision based on topic characteristics.

### Components

#### PollGenerator (`pipeline/poll_generator.py`)
```python
@dataclass
class PollData:
    question: str
    options: list[str]
    allows_multiple_answers: bool
    correct_option: int | None  # For quiz mode

class PollGenerator:
    def __init__(self, llm_adapter: BaseLLMAdapter, config: Settings)
        self.llm = llm_adapter
        self.config = config

    async def should_generate_poll(self, article: Article) -> bool:
        """Determine if topic is suitable for a poll."""
        # Based on: topic type, keywords, article content
        pass

    async def generate_poll(self, topic: str, context: dict) -> PollData:
        """Generate poll question and options using LLM."""
        prompt = self._build_prompt(topic, context)
        response = await self.llm.generate(prompt, response_format="json")
        return self._parse_response(response)

    def _build_prompt(self, topic: str, context: dict) -> str:
        """Build prompt for poll generation."""
        return f"""
        Generate an interactive poll for a Telegram channel about: {topic}

        Context: {context}

        Requirements:
        1. Question should be engaging and relevant to the audience
        2. Exactly 4 options (A, B, C, D)
        3. Options should be distinct and clear
        4. One option should be clearly correct based on the context

        Return JSON only:
        {{
            "question": "...",
            "options": ["...", "...", "...", "..."],
            "correct_option": 0
        }}
        """

    def _parse_response(self, response: str) -> PollData:
        """Parse LLM response into PollData."""
        data = json.loads(response)
        return PollData(
            question=data["question"],
            options=data["options"],
            allows_multiple_answers=False,
            correct_option=data.get("correct_option")
        )
```

#### Publisher Integration
Extend `BotPublisher` to support polls:

```python
class BotPublisher(BasePublisher):
    # ... existing methods ...

    async def send_poll(
        self,
        question: str,
        options: list[str],
        allows_multiple_answers: bool = False
    ) -> int:
        """Send poll to channel."""
        message = await self.bot.send_poll(
            chat_id=self.channel_id,
            question=question,
            options=options,
            allows_multiple_answers=allows_multiple_answers
        )
        return message.message_id
```

### Configuration
```yaml
pipeline:
  enable_polls: true
  poll_probability: 0.3  # 30% of posts as polls
  poll_types:
    - opinion  # Ask for opinions
    - preference  # Ask for preferences
    - quiz  # Knowledge quiz
```

### Data Model
Add `poll_data` JSON field to `Post` model:

```python
class Post(Base):
    # ... existing fields ...
    poll_data: Mapped[str, dict] | None  # JSON: {question, options, correct_option}
```

---

## Feature 2: Weekly Reports

### Purpose
Generate and send automated weekly performance summaries to the channel admin.

### Components

#### WeeklyReporter (`analytics/weekly_reporter.py`)
```python
@dataclass
class WeeklyStats:
    posts_published: int
    total_views: int
    total_reactions: int
    total_forwards: int
    avg_engagement_rate: float
    top_posts: list[dict]
    top_topics: list[str]
    best_posting_times: list[str]
    period_start: datetime
    period_end: datetime

class WeeklyReporter:
    def __init__(self, db: Database, publisher: BasePublisher):
        self.db = db
        self.publisher = publisher

    async def generate_report(self, days: int = 7) -> WeeklyStats:
        """Generate weekly statistics."""
        posts = await self._get_posts_for_period(days)
        return WeeklyStats(
            posts_published=len(posts),
            total_views=sum(p.views_count or 0 for p in posts),
            total_reactions=sum(p.reactions_count or 0 for p in posts),
            total_forwards=sum(p.forwards or 0 for p in posts),
            avg_engagement_rate=self._calculate_avg_engagement(posts),
            top_posts=self._get_top_posts(posts, limit=5),
            top_topics=self._get_top_topics(posts),
            best_posting_times=self._get_best_posting_times(posts),
            period_start=datetime.now() - timedelta(days=days),
            period_end=datetime.now()
        )

    async def send_report(self, admin_id: int, stats: WeeklyStats) -> bool:
        """Send formatted report to admin via Telegram."""
        report_text = self._format_report(stats)
        await self.publisher.send_message(
            chat_id=admin_id,
            text=report_text,
            parse_mode="Markdown"
        )
        return True

    def _format_report(self, stats: WeeklyStats) -> str:
        """Format statistics as readable report."""
        return f"""
📊 *Weekly Report*
📅 {stats.period_start.strftime('%d %b')} - {stats.period_end.strftime('%d %b')}

📝 Posts Published: {stats.posts_published}
👁 Total Views: {stats.total_views:,}
💬 Reactions: {stats.total_reactions}
↗️ Forwards: {stats.total_forwards}
📈 Avg Engagement Rate: {stats.avg_engagement_rate:.2f}%

🔥 *Top Posts:*
{self._format_top_posts(stats.top_posts)}

📚 *Popular Topics:*
{', '.join(stats.top_topics)}

⏰ *Best Posting Times:*
{', '.join(stats.best_posting_times)}

_Generated by TG AI Poster_
        """
```

### Scheduler Integration
Add cron job to scheduler

```python
# In core/scheduler.py
async def schedule_weekly_report(self):
    """Schedule weekly report generation."""
    self.scheduler.add_job(
        func=self._run_weekly_report,
        trigger=CronTrigger(
            day_of_week="mon",
            hour=9,
            minute=0
        )
    )

async def _run_weekly_report(self):
    """Run weekly report generation and sending."""
    reporter = WeeklyReporter(self.db, self.publisher)
    stats = await reporter.generate_report(days=7)
    await reporter.send_report(self.settings.admin.telegram_id, stats)
```

### Configuration
```yaml
reporting:
  enabled: true
  schedule: "0 9 * * 1"  # Cron: every Monday 9 AM
  recipient_admin_id: ${ADMIN_TELEGRAM_ID}
  include_top_posts: 5
  include_analysis: true
```

---

## Feature 3: Post Templates

### Purpose
Provide configurable templates for different post types (breaking news, tutorials, announcements, etc.)

### Components

#### TemplateManager (`pipeline/template_manager.py`)
```python
@dataclass
class PostTemplate:
    name: str
    description: str
    structure: list[str]  # Ordered sections
    prompts: dict[str, str]  # Section-specific prompts
    constraints: dict[str, any]  # Length, emoji count, etc.
    examples: list[str]

class TemplateManager:
    def __init__(self, templates_path: str = "config/post_templates.yaml"):
        self.templates_path = templates_path
        self.templates: dict[str, PostTemplate] = {}

    def load_templates(self) -> None:
        """Load templates from config file."""
        with open(self.templates_path) as f:
            data = yaml.safe_load(f)
        for name, template_data in data.items():
            self.templates[name] = PostTemplate(**template_data)

    def get_template(self, name: str) -> PostTemplate | None:
        """Get template by name."""
        return self.templates.get(name)

    def get_template_for_topic(self, topic: str, context: dict) -> PostTemplate:
        """Select appropriate template based on topic."""
        # Use LLM or rules to select template
        pass

    def apply_template(self, template: PostTemplate, content: dict) -> str:
        """Apply template to content."""
        sections = []
        for section in template.structure:
                prompt = template.prompts.get(section, "")
                sections.append(self._fill_section(section, content, prompt))
        return "\n\n".join(sections)
```

### PromptBuilder Integration
Modify existing PromptBuilder to use templates

```python
class PromptBuilder:
    def __init__(self, settings: Settings, template_manager: TemplateManager | None):
        self.settings = settings
        self.template_manager = template_manager

    async def build(self, topic: SelectedTopic, context: dict) -> str:
        """Build prompt with optional template."""
        if self.template_manager and self.settings.templates.enabled:
            template = self.template_manager.get_template_for_topic(
                topic.name, context
            )
            return self._build_with_template(template, context)
        return self._build_default(topic, context)
```

### Configuration
```yaml
templates:
  enabled: true
  path: "config/post_templates.yaml"
  default_template: "breaking"  # Default template for news
```

### Templates Config File
```yaml
# config/post_templates.yaml

breaking:
  name: "Breaking News"
  description: "For breaking news and announcements"
  structure:
    - headline
    - hook
    - body
    - key_facts
    - sources
  prompts:
    headline: "Create urgent, attention-grabbing headline with 1-2 emojis"
    hook: "First 1-2 sentences answering: what happened and why it matters"
    body: "Main content explaining the news, 2-4 paragraphs"
  constraints:
    max_length: 1200
    emojis: 2

tutorial:
  name: "Tutorial"
  description: "Step-by-step guides and how-tos"
  structure:
    - title
    - introduction
    - steps
    - tips
    - conclusion
  prompts:
    title: "Clear, actionable title"
    introduction: "Brief intro explaining what will be learned"
  constraints:
    max_length: 1500
    emojis: 3

announcement:
  name: "Announcement"
  description: "Channel announcements, updates"
  structure:
    - title
    - body
    - call_to_action
  constraints:
    max_length: 800
    emojis: 2
```

---

## Feature 4: Audit Log

### Purpose
Comprehensive logging of all system actions for debugging, compliance, and analytics.

### Components

#### AuditLogger (`utils/audit_logger.py`)
```python
from datetime import datetime
from typing import Any, Optional
from functools import wraps
from core.logger import get_logger

logger = get_logger(__name__)

class AuditEvent:
    """Represents a single audit event."""
    timestamp: datetime
    event_type: str
    action: str
    user_id: Optional[int]
    resource_type: str
    resource_id: Optional[str]
    details: dict[str, Any]
    ip_address: Optional[str]

class AuditLogger:
    def __init__(self, db: Database):
        self.db = db
        self._buffer: list[AuditEvent] = []
        self._flush_interval = 60  # seconds

    async def log(
        self,
        event_type: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: int | None = None,
        details: dict | None = None,
        ip_address: str | None = None
    ) -> None:
        """Log an audit event."""
        event = AuditEvent(
            timestamp=datetime.utcnow(),
            event_type=event_type,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address
        )
        self._buffer.append(event)
        if len(self._buffer) >= 100:
            await self._flush()

    async def _flush(self) -> None:
        """Flush buffer to database."""
        if not self._buffer:
            return
        async with self.db.session() as session:
            for event in self._buffer:
                await session.execute(
                    """
                    INSERT INTO audit_log
                    (timestamp, event_type, action, user_id, resource_type, resource_id, details)
                    VALUES (:timestamp, :event_type, :action, :user_id, :resource_type, :resource_id, :details)
                    """,
                    event.model_dump()
                )
        self._buffer.clear()

    async def get_events(
        self,
        event_type: str | None = None,
        resource_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100
    ) -> list[AuditEvent]:
        """Query audit events."""
        pass

# Decorator for automatic audit logging
def audit_action(action: str, resource_type: str):
    """Decorator to automatically log function calls."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            result = await func(self, *args, **kwargs)
            try:
                audit = getattr(self, 'audit_logger', None)
                if audit:
                    await audit.log(
                        event_type=func.__name__,
                        action=action,
                        resource_type=resource_type,
                        resource_id=str(getattr(result, 'id', None)),
                        details={'args': str(args)[:200]}
                    )
            except Exception as e:
                logger.warning(f"Failed to log audit: {e}")
            return result
        return wrapper
    return decorator
```

### Data Model
```python
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    user_id = Column(Integer, nullable=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=False, default={})
    ip_address = Column(String(50), nullable=True)
```

### Integration Points
Apply decorator to key methods

```python
# In pipeline/orchestrator.py
class PipelineOrchestrator:
    def __init__(self, ...):
        # ... existing init ...
        self.audit_logger = AuditLogger(db) if settings.audit.enabled else None

    @audit_action("post_created", "post")
    async def run(self, dry_run: bool = False) -> PipelineResult:
        # ... existing code ...
```

### Configuration
```yaml
audit:
  enabled: true
  retention_days: 90
  log_post_changes: true
  log_llm_calls: true
  log_publishing: true
```

---

## Feature 5: Health Checks

### Purpose
Monitor system health and validate functionality at startup.

### Components

#### HealthChecker (`core/health.py`)
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import asyncio

@dataclass
class HealthStatus:
    component: str
    healthy: bool
    message: str
    latency_ms: Optional[int] = None
    timestamp: datetime

@dataclass
class SystemHealth:
    overall_healthy: bool
    components: list[HealthStatus]
    checked_at: datetime

class HealthChecker:
    def __init__(self, db: Database, publisher, llm_adapter):
        self.db = db
        self.publisher = publisher
        self.llm = llm_adapter

    async def check_all(self) -> SystemHealth:
        """Run all health checks."""
        results = await asyncio.gather(
            self.check_database(),
            self.check_llm_adapter(),
            self.check_telegram(),
            self.check_disk_space(),
            self.check_memory(),
        )
        return SystemHealth(
            overall_healthy=all(r.healthy for r in results),
            components=results,
            checked_at=datetime.utcnow()
        )

    async def check_database(self) -> HealthStatus:
        """Check database connectivity."""
        start = datetime.now()
        try:
            async with self.db.session() as session:
                await session.execute("SELECT 1")
            latency = (datetime.now() - start).total_seconds() * 1000
            return HealthStatus(
                component="database",
                healthy=True,
                message="Connected",
                latency_ms=int(latency)
            )
        except Exception as e:
            return HealthStatus(
                component="database",
                healthy=False,
                message=str(e)
            )

    async def check_llm_adapter(self) -> HealthStatus:
        """Check LLM API availability."""
        try:
            # Light ping - minimal token request
            result = await asyncio.wait_for(
                self.llm.generate("Say 'ok'", max_tokens=5),
                timeout=5.0
            )
            return HealthStatus(
                component="llm_adapter",
                healthy=True,
                message="API responding"
            )
        except Exception as e:
            return HealthStatus(
                component="llm_adapter",
                healthy=False,
                message=str(e)
            )

    async def check_telegram(self) -> HealthStatus:
        """Check Telegram API connectivity."""
        try:
            me = await self.publisher.bot.get_me()
            return HealthStatus(
                component="telegram",
                healthy=True,
                message=f"Connected as @{me.username}"
            )
        except Exception as e:
            return HealthStatus(
                component="telegram",
                healthy=False,
                message=str(e)
            )

    async def check_disk_space(self) -> HealthStatus:
        """Check available disk space."""
        import shutil
        try:
            usage = shutil.disk_usage(".")
            free_gb = usage.free / (1024**3)
            healthy = free_gb > 1.0  # At least 1GB free
            return HealthStatus(
                component="disk_space",
                healthy=healthy,
                message=f"{free_gb:.1f} GB free"
            )
        except Exception as e:
            return HealthStatus(
                component="disk_space",
                healthy=False,
                message=str(e)
            )

    async def check_memory(self) -> HealthStatus:
        """Check memory usage."""
        import psutil
        try:
            memory = psutil.virtual_memory()
            healthy = memory.percent < 90
            return HealthStatus(
                component="memory",
                healthy=healthy,
                message=f"{memory.percent:.1f}% used"
            )
        except Exception as e:
            return HealthStatus(
                component="memory",
                healthy=False,
                message=str(e)
            )
```

### Startup Integration
```python
# In main.py
async def initialize(settings: Settings) -> tuple[Database, BasePublisher]:
    db = await init_database(settings.database.url)
    publisher = get_publisher(...)

    # Health check on startup
    if settings.health.check_on_startup:
        health_checker = HealthChecker(db, publisher, llm_adapter)
        health = await health_checker.check_all()

        if not health.overall_healthy:
            logger.warning(f"Health check failed: {health}")
            for component in health.components:
                if not component.healthy:
                    logger.error(f"  - {component.component}: {component.message}")
        else:
            logger.info(f"All health checks passed")

    return db, publisher
```

### Optional HTTP Endpoint
```python
# For monitoring systems
from fastapi import FastAPI, Response

app = FastAPI()

@app.get("/health")
async def health_endpoint():
    """Health check endpoint for monitoring."""
    health = await health_checker.check_all()
    if health.overall_healthy:
        return Response(
            content=health.model_dump_json(),
            status_code=200,
            media_type="application/json"
        )
    return Response(
        content=health.model_dump_json(),
        status_code=503,
        media_type="application/json"
    )
```

### Configuration
```yaml
health:
  check_on_startup: true
  check_before_post: true
  endpoint_enabled: false  # Set true to enable /health endpoint
  endpoint_port: 8080
```

---

## Implementation Order

1. **Health Checks** (Foundation - no dependencies)
2. **Audit Log** (Depends on: Health for startup validation)
3. **Post Templates** (Depends on: existing PromptBuilder)
4. **Weekly Reports** (Depends on: existing stats, scheduler)
5. **Polls Generation** (Depends on: all above, plus LLM)

---

## Database Migrations

```sql
-- Add poll_data to posts table
ALTER TABLE posts ADD COLUMN poll_data TEXT;

-- Create audit_log table
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    user_id INTEGER,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    details JSON NOT NULL DEFAULT '{}',
    ip_address VARCHAR(50)
);

CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX idx_audit_event_type ON audit_log(event_type);
```

---

## Testing Strategy

Each feature should have corresponding test files:

- `tests/test_poll_generator.py`
- `tests/test_weekly_reporter.py`
- `tests/test_template_manager.py`
- `tests/test_audit_logger.py`
- `tests/test_health_checker.py`

---

## Success Metrics

| Feature | Success Criteria |
|---------|------------------|
| Polls | Polls published and receiving votes |
| Reports | Admin receives weekly report every Monday |
| Templates | Posts using templates show consistent structure |
| Audit | All key actions logged and queryable |
| Health | Startup validation catches issues before they cause failures |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| LLM rate limits for poll generation | Use light prompts, cache similar questions |
| Report flooding admin | Only send on schedule, deduplicate content |
| Templates becoming stale | Regular review, allow easy updates |
| Audit log growing too large | Retention policy, automatic cleanup |
| Health check slowing startup | Run in parallel, cache results |

---

## Future Enhancements

- Poll results analysis for learning
- Report web dashboard
- Template performance tracking
- Audit log UI viewer
- Health metrics export to monitoring system

---

*Document Version: 1.0*
*Created: 2025-03-14*
