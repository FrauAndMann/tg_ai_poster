# Phase 2 Features Design Specification

**Version:** 1.0
**Date:** 2025-03-15
**Status:** Draft
**Author:** Claude

---

## Table of Contents

1. [Overview](#1-overview)
2. [Feature Priority Matrix](#2-feature-priority-matrix)
3. [Thread Mode](#3-thread-mode)
4. [Smart Queue Management](#4-smart-queue-management)
5. [Engagement Tracker](#5-engagement-tracker)
6. [Enhanced RSS Parser](#6-enhanced-rss-parser)
7. [Hashtag Performance Analytics](#7-hashtag-performance-analytics)
8. [Reddit Integration](#8-reddit-integration)
9. [Predictive Analytics](#9-predictive-analytics)
10. [Multi-channel Publishing](#10-multi-channel-publishing)
11. [Implementation Timeline](#11-implementation-timeline)

---

## 1. Overview

### 1.1 Goals

Phase 2 focuses on:
- **Content Quality**: Thread mode for long-form content
- **Workflow Efficiency**: Smart queue with priorities
- **Analytics**: Engagement tracking and predictions
- **Source Diversity**: Reddit and improved RSS

### 1.2 Current State

**Implemented (Phase 1):**
- A/B Testing ✅
- Draft System ✅
- Approval Workflow ✅
- Health Monitoring ✅
- Admin Bot ✅
- Circuit Breaker ✅
- Backup System ✅

**Missing (Phase 2 Targets):**
- Thread Mode ❌
- Smart Queue ❌
- Engagement Tracking ❌
- Predictive Analytics ❌
- Multi-channel ❌

---

## 2. Feature Priority Matrix

| Feature | Impact | Effort | Priority | Dependencies |
|---------|--------|--------|----------|--------------|
| Thread Mode | High | Medium | P1 | None |
| Smart Queue | High | Medium | P1 | None |
| Engagement Tracker | High | Medium | P2 | None |
| Enhanced RSS | Medium | Low | P2 | None |
| Hashtag Analytics | Medium | Low | P2 | Engagement Tracker |
| Reddit Integration | Medium | Medium | P3 | None |
| Predictive Analytics | High | High | P3 | Engagement Tracker |
| Multi-channel | Medium | High | P4 | None |

---

## 3. Thread Mode

### 3.1 Overview

Automatically splits long-form content into a series of connected posts (threads/tlaps).

### 3.2 Configuration

```yaml
# config.yaml
thread:
  enabled: true
  min_length_for_thread: 2000      # chars
  max_posts_per_thread: 5
  delay_between_posts_seconds: 30  # Telegram rate limit consideration
  auto_detect_breaks: true         # AI-powered paragraph detection
  add_thread_numbers: true         # "1/5", "2/5", etc.
  thread_emoji: "🧵"               # Visual indicator
```

### 3.3 Database Schema

```python
# memory/models.py

class Thread(Base):
    """Thread container for connected posts."""
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    total_posts: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # draft, publishing, published, failed

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="thread", order_by="Post.thread_position"
    )

    __table_args__ = (
        Index("ix_threads_status", "status"),
        Index("ix_threads_created", "created_at"),
    )


# Add to Post model:
class Post(Base):
    # ... existing fields ...

    # Thread support
    thread_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("threads.id"), nullable=True
    )
    thread_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_thread_part: Mapped[bool] = mapped_column(Boolean, default=False)

    thread: Mapped["Thread | None"] = relationship("Thread", back_populates="posts")
```

### 3.4 ThreadBuilder Implementation

```python
# pipeline/thread_builder.py

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ThreadPart:
    """Single part of a thread."""
    content: str
    position: int
    is_last: bool
    char_count: int


class ContentSplitter(Protocol):
    """Protocol for content splitting strategies."""

    def can_split(self, content: str) -> bool: ...
    def split(self, content: str, max_length: int) -> list[ThreadPart]: ...


class ThreadBuilder:
    """
    Builds threads from long-form content.

    Strategies:
    1. Paragraph-based: Split at paragraph boundaries
    2. Sentence-based: Split at sentence boundaries
    3. AI-powered: Use LLM to create logical breaks
    """

    MAX_POST_LENGTH = 4000  # Telegram limit minus formatting
    MIN_SPLIT_LENGTH = 500  # Minimum for a valid part

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        min_thread_length: int = 2000,
        max_parts: int = 5,
    ):
        self.llm = llm_adapter
        self.min_thread_length = min_thread_length
        self.max_parts = max_parts

        self.splitters: list[ContentSplitter] = [
            ParagraphSplitter(),
            SentenceSplitter(),
            AIContentSplitter(llm_adapter),
        ]

    def should_create_thread(self, content: str) -> bool:
        """Determine if content should be split into thread."""
        return len(content) >= self.min_thread_length

    async def build_thread(self, content: str, title: str) -> list[ThreadPart]:
        """
        Split content into thread parts.

        Process:
        1. Check length threshold
        2. Try splitters in priority order
        3. Add navigation elements (X/Y, "continued")
        4. Validate all parts meet minimum
        """
        if not self.should_create_thread(content):
            return [ThreadPart(content=content, position=1, is_last=True, char_count=len(content))]

        for splitter in self.splitters:
            if splitter.can_split(content):
                parts = splitter.split(content, self.MAX_POST_LENGTH)
                if self._validate_parts(parts):
                    return self._add_navigation(parts, title)

        # Fallback: force split
        return self._force_split(content)

    def _validate_parts(self, parts: list[ThreadPart]) -> bool:
        """Ensure all parts are valid."""
        if not parts or len(parts) > self.max_parts:
            return False
        return all(p.char_count >= self.MIN_SPLIT_LENGTH for p in parts)

    def _add_navigation(self, parts: list[ThreadPart], title: str) -> list[ThreadPart]:
        """Add thread navigation to each part."""
        total = len(parts)
        enhanced = []

        for i, part in enumerate(parts):
            prefix = f"🧵 {title}\n\n" if i == 0 else ""
            suffix = f"\n\n{i+1}/{total}" if total > 1 else ""

            enhanced.append(ThreadPart(
                content=f"{prefix}{part.content}{suffix}",
                position=i + 1,
                is_last=(i == total - 1),
                char_count=len(part.content) + len(prefix) + len(suffix),
            ))

        return enhanced

    def _force_split(self, content: str) -> list[ThreadPart]:
        """Emergency split when strategies fail."""
        # Implementation: split at fixed intervals
        chunks = []
        for i in range(0, len(content), self.MAX_POST_LENGTH - 100):
            chunk = content[i:i + self.MAX_POST_LENGTH - 100]
            chunks.append(chunk)

        return [
            ThreadPart(content=c, position=i+1, is_last=(i==len(chunks)-1), char_count=len(c))
            for i, c in enumerate(chunks)
        ]


class ParagraphSplitter:
    """Split content at paragraph boundaries."""

    def can_split(self, content: str) -> bool:
        return "\n\n" in content

    def split(self, content: str, max_length: int) -> list[ThreadPart]:
        paragraphs = content.split("\n\n")
        return self._group_paragraphs(paragraphs, max_length)

    def _group_paragraphs(self, paragraphs: list[str], max_length: int) -> list[ThreadPart]:
        """Group paragraphs into parts under max_length."""
        parts = []
        current = []
        current_length = 0
        position = 1

        for para in paragraphs:
            if current_length + len(para) + 2 > max_length and current:
                parts.append(ThreadPart(
                    content="\n\n".join(current),
                    position=position,
                    is_last=False,
                    char_count=current_length,
                ))
                current = [para]
                current_length = len(para)
                position += 1
            else:
                current.append(para)
                current_length += len(para) + 2

        if current:
            parts.append(ThreadPart(
                content="\n\n".join(current),
                position=position,
                is_last=True,
                char_count=current_length,
            ))

        return parts


class AIContentSplitter:
    """Use LLM to create logical content breaks."""

    SPLIT_PROMPT = """Split this content into {max_parts} logical parts for a Twitter thread.

Each part should:
- Be under 4000 characters
- End at a natural breaking point
- Be self-contained enough to read independently

Return JSON array:
{{"parts": [{{"content": "...", "summary": "Part N covers..."}}]}}

Content to split:
{content}"""

    def __init__(self, llm: BaseLLMAdapter):
        self.llm = llm

    def can_split(self, content: str) -> bool:
        # Use AI splitter for complex content
        return len(content) > 3000

    async def split(self, content: str, max_length: int) -> list[ThreadPart]:
        prompt = self.SPLIT_PROMPT.format(
            max_parts=5,
            content=content[:8000],  # Limit for LLM
        )

        response = await self.llm.generate(prompt)
        data = json.loads(response)

        return [
            ThreadPart(
                content=p["content"],
                position=i + 1,
                is_last=(i == len(data["parts"]) - 1),
                char_count=len(p["content"]),
            )
            for i, p in enumerate(data["parts"])
        ]
```

### 3.5 Thread Publisher

```python
# pipeline/thread_publisher.py

class ThreadPublisher:
    """Publishes threads with rate limit handling."""

    def __init__(
        self,
        publisher: BasePublisher,
        delay_seconds: int = 30,
    ):
        self.publisher = publisher
        self.delay_seconds = delay_seconds

    async def publish_thread(
        self,
        thread: Thread,
        posts: list[Post],
    ) -> PublishResult:
        """
        Publish thread parts sequentially.

        Handles:
        - Rate limiting between posts
        - Failure recovery (mark failed position)
        - Progress tracking in DB
        """
        results = []
        thread.status = "publishing"

        for post in posts:
            try:
                result = await self.publisher.publish(post)
                results.append(result)

                if not post.is_thread_part or not post.thread_position == len(posts):
                    await asyncio.sleep(self.delay_seconds)

            except Exception as e:
                thread.status = "failed"
                logger.error(f"Thread publishing failed at position {post.thread_position}: {e}")
                raise ThreadPublishError(
                    thread_id=thread.id,
                    failed_position=post.thread_position,
                    cause=e,
                )

        thread.status = "published"
        thread.published_at = datetime.utcnow()

        return PublishResult(
            success=True,
            thread_id=thread.id,
            posts_published=len(results),
        )
```

### 3.6 Integration Points

```python
# pipeline/orchestrator.py additions

class PipelineOrchestrator:
    async def _generate_content(self, article: Article) -> Post | Thread:
        """Generate post or thread based on content length."""
        raw_content = await self._generate_raw_content(article)

        if self.thread_builder.should_create_thread(raw_content):
            return await self._build_thread(raw_content, article)
        else:
            return await self._build_single_post(raw_content, article)
```

---

## 4. Smart Queue Management

### 4.1 Overview

Intelligent post queue with priorities, expiration, and conflict resolution.

### 4.2 Configuration

```yaml
# config.yaml
queue:
  enabled: true
  max_size: 100
  default_priority: 50        # 1-100 scale
  expiration_hours: 48        # Posts expire after this
  conflict_resolution: "priority"  # priority | time | hybrid

  priorities:
    breaking_news: 100
    trending: 80
    scheduled: 60
    evergreen: 40
    filler: 20

  auto_cleanup: true
  cleanup_interval_hours: 6
```

### 4.3 Database Schema

```python
# memory/models.py

class PostQueue(Base):
    """Smart queue for scheduled posts."""
    __tablename__ = "post_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), unique=True)

    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Priority (1-100, higher = more important)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    priority_reason: Mapped[str | None] = mapped_column(String(100))

    # Status
    status: Mapped[str] = mapped_column(String(20), default="queued")
    # queued, publishing, published, expired, failed

    # Conflict tracking
    conflicts_with: Mapped[int | None] = mapped_column(Integer, ForeignKey("post_queue.id"))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    post: Mapped["Post"] = relationship("Post")

    __table_args__ = (
        Index("ix_post_queue_scheduled", "scheduled_at"),
        Index("ix_post_queue_priority", "priority"),
        Index("ix_post_queue_status", "status"),
    )


class QueueStats(Base):
    """Aggregated queue statistics."""
    __tablename__ = "queue_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True)

    total_queued: Mapped[int] = mapped_column(Integer, default=0)
    total_published: Mapped[int] = mapped_column(Integer, default=0)
    total_expired: Mapped[int] = mapped_column(Integer, default=0)
    avg_wait_time_seconds: Mapped[float] = mapped_column(Float, default=0)
    avg_priority: Mapped[float] = mapped_column(Float, default=0)

    __table_args__ = (
        Index("ix_queue_stats_date", "date"),
    )
```

### 4.4 QueueManager Implementation

```python
# pipeline/queue_manager.py

from enum import IntEnum
from heapq import heappush, heappop
from datetime import timedelta


class Priority(IntEnum):
    """Standard priority levels."""
    FILLER = 20
    EVERGREEN = 40
    SCHEDULED = 60
    TRENDING = 80
    BREAKING = 100


@dataclass(order=True)
class QueuedPost:
    """Heap-compatible queue item."""
    priority: int
    scheduled_at: datetime
    post_id: int = field(compare=False)
    queue_entry_id: int = field(compare=False)


class QueueManager:
    """
    Smart post queue with priority handling.

    Features:
    - Priority-based ordering
    - Time-based scheduling
    - Expiration handling
    - Conflict detection
    """

    def __init__(
        self,
        db: Database,
        max_size: int = 100,
        default_expiration_hours: int = 48,
    ):
        self.db = db
        self.max_size = max_size
        self.default_expiration = timedelta(hours=default_expiration_hours)

        self._heap: list[QueuedPost] = []
        self._dirty = True

    async def enqueue(
        self,
        post: Post,
        scheduled_at: datetime,
        priority: int = Priority.SCHEDULED,
        priority_reason: str | None = None,
        expires_at: datetime | None = None,
    ) -> PostQueue:
        """
        Add post to queue.

        Raises:
            QueueFullError: If queue is at max capacity
            DuplicatePostError: If post is already queued
        """
        async with self.db.session() as session:
            # Check for duplicates
            existing = await session.execute(
                select(PostQueue).where(
                    PostQueue.post_id == post.id,
                    PostQueue.status == "queued",
                )
            )
            if existing.scalar_one_or_none():
                raise DuplicatePostError(post.id)

            # Check queue size
            count = await session.scalar(
                select(func.count()).where(PostQueue.status == "queued")
            )
            if count >= self.max_size:
                raise QueueFullError(self.max_size)

            # Create entry
            entry = PostQueue(
                post_id=post.id,
                scheduled_at=scheduled_at,
                expires_at=expires_at or (datetime.utcnow() + self.default_expiration),
                priority=priority,
                priority_reason=priority_reason,
                status="queued",
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)

            self._dirty = True
            logger.info(f"Queued post {post.id} with priority {priority}")

            return entry

    async def dequeue(self) -> Post | None:
        """
        Get next post to publish.

        Considers:
        - Current time vs scheduled time
        - Priority ordering
        - Expiration
        """
        await self._cleanup_expired()

        async with self.db.session() as session:
            # Find eligible posts (scheduled_at <= now, not expired)
            now = datetime.utcnow()
            result = await session.execute(
                select(PostQueue)
                .join(Post)
                .where(
                    PostQueue.status == "queued",
                    PostQueue.scheduled_at <= now,
                    or_(PostQueue.expires_at.is_(None), PostQueue.expires_at > now),
                )
                .order_by(
                    PostQueue.priority.desc(),
                    PostQueue.scheduled_at.asc(),
                )
                .limit(1)
                .with_for_update(skip_locked=True)
            )

            entry = result.scalar_one_or_none()
            if not entry:
                return None

            # Mark as publishing
            entry.status = "publishing"
            await session.commit()

            return entry.post

    async def peek(self, limit: int = 10) -> list[PostQueue]:
        """Preview upcoming posts without removing from queue."""
        async with self.db.session() as session:
            result = await session.execute(
                select(PostQueue)
                .where(PostQueue.status == "queued")
                .order_by(
                    PostQueue.priority.desc(),
                    PostQueue.scheduled_at.asc(),
                )
                .limit(limit)
            )
            return list(result.scalars().all())

    async def reprioritize(
        self,
        post_id: int,
        new_priority: int,
        reason: str | None = None,
    ) -> bool:
        """Change priority of queued post."""
        async with self.db.session() as session:
            result = await session.execute(
                select(PostQueue).where(
                    PostQueue.post_id == post_id,
                    PostQueue.status == "queued",
                )
            )
            entry = result.scalar_one_or_none()
            if not entry:
                return False

            old_priority = entry.priority
            entry.priority = new_priority
            entry.priority_reason = reason or f"Reprioritized from {old_priority}"

            await session.commit()
            logger.info(f"Post {post_id} priority: {old_priority} -> {new_priority}")

            return True

    async def detect_conflicts(self) -> list[tuple[PostQueue, PostQueue]]:
        """
        Find posts scheduled at similar times with similar topics.

        Returns list of (post1, post2) conflict pairs.
        """
        conflicts = []
        window = timedelta(minutes=30)

        async with self.db.session() as session:
            entries = await session.execute(
                select(PostQueue)
                .where(PostQueue.status == "queued")
                .order_by(PostQueue.scheduled_at)
            )
            queued = list(entries.scalars().all())

            for i, entry1 in enumerate(queued):
                for entry2 in queued[i+1:]:
                    # Time proximity
                    time_diff = abs(entry1.scheduled_at - entry2.scheduled_at)
                    if time_diff > window:
                        break  # Entries are sorted by time

                    # Topic similarity (check post content)
                    if await self._are_similar_topics(entry1.post, entry2.post):
                        conflicts.append((entry1, entry2))
                        entry1.conflicts_with = entry2.id
                        entry2.conflicts_with = entry1.id

            await session.commit()

        return conflicts

    async def resolve_conflict(
        self,
        entry1: PostQueue,
        entry2: PostQueue,
        strategy: str = "priority",
    ) -> PostQueue:
        """
        Resolve conflict between two posts.

        Strategies:
        - priority: Keep higher priority
        - time: Keep earlier scheduled
        - hybrid: Priority then time
        """
        if strategy == "priority":
            winner = entry1 if entry1.priority >= entry2.priority else entry2
        elif strategy == "time":
            winner = entry1 if entry1.scheduled_at <= entry2.scheduled_at else entry2
        else:  # hybrid
            if entry1.priority != entry2.priority:
                winner = entry1 if entry1.priority > entry2.priority else entry2
            else:
                winner = entry1 if entry1.scheduled_at <= entry2.scheduled_at else entry2

        # Reschedule loser
        loser = entry2 if winner == entry1 else entry1
        loser.scheduled_at += timedelta(hours=2)
        loser.priority_reason = "Resolved conflict with post {winner.post_id}"

        async with self.db.session() as session:
            session.add(loser)
            await session.commit()

        return winner

    async def _cleanup_expired(self) -> int:
        """Remove expired posts from queue."""
        async with self.db.session() as session:
            now = datetime.utcnow()
            result = await session.execute(
                update(PostQueue)
                .where(
                    PostQueue.status == "queued",
                    PostQueue.expires_at < now,
                )
                .values(status="expired")
                .returning(PostQueue.id)
            )
            expired_ids = [row[0] for row in result.fetchall()]
            await session.commit()

            if expired_ids:
                logger.warning(f"Expired {len(expired_ids)} posts from queue")

            return len(expired_ids)

    async def get_stats(self) -> dict:
        """Get queue statistics."""
        async with self.db.session() as session:
            stats = await session.execute(
                select(
                    func.count().filter(PostQueue.status == "queued").label("queued"),
                    func.count().filter(PostQueue.status == "publishing").label("publishing"),
                    func.count().filter(PostQueue.status == "expired").label("expired"),
                    func.avg(PostQueue.priority).label("avg_priority"),
                )
            )
            row = stats.one()

            return {
                "queued": row.queued,
                "publishing": row.publishing,
                "expired": row.expired,
                "avg_priority": round(row.avg_priority or 0, 1),
                "queue_health": self._calculate_health(row),
            }

    def _calculate_health(self, stats) -> str:
        """Determine queue health status."""
        if stats.queued == 0:
            return "empty"
        elif stats.expired > stats.queued:
            return "critical"
        elif stats.expired > 0:
            return "warning"
        else:
            return "healthy"
```

### 4.5 Admin Bot Commands

```python
# admin_bot/handlers/queue.py

class QueueCommands:
    """Queue management commands for admin bot."""

    @router.message(Command("queue"))
    async def cmd_queue(self, message: Message):
        """Show queue status."""
        stats = await self.queue_manager.get_stats()
        upcoming = await self.queue_manager.peek(5)

        text = f"""📊 Очередь постов

Статус: {stats['queue_health']}
В очереди: {stats['queued']}
Средний приоритет: {stats['avg_priority']}

📅 Следующие посты:
{self._format_upcoming(upcoming)}
"""
        await message.answer(text)

    @router.message(Command("prioritize"))
    async def cmd_prioritize(self, message: Message, post_id: int, priority: int):
        """Change post priority."""
        success = await self.queue_manager.reprioritize(
            post_id, priority, f"Admin: {message.from_user.id}"
        )
        if success:
            await message.answer(f"✅ Приоритет поста {post_id} изменен на {priority}")
        else:
            await message.answer(f"❌ Пост {post_id} не найден в очереди")
```

---

## 5. Engagement Tracker

### 5.1 Overview

Collects and stores engagement metrics (views, reactions, forwards, replies) for published posts.

### 5.2 Configuration

```yaml
# config.yaml
engagement:
  enabled: true
  tracking_interval_minutes: 30    # How often to fetch updates
  max_tracking_age_hours: 168     # Track for 1 week
  store_reaction_details: true     # Store individual reaction types

  metrics:
    - views
    - reactions
    - forwards
    - replies

  alerts:
    high_engagement_threshold: 1000
    low_engagement_threshold: 50
```

### 5.3 Database Schema

```python
# memory/models.py

class PostEngagement(Base):
    """Engagement metrics for a post."""
    __tablename__ = "post_engagement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), unique=True)

    # Core metrics
    views: Mapped[int] = mapped_column(Integer, default=0)
    reactions_total: Mapped[int] = mapped_column(Integer, default=0)
    forwards: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)

    # Reaction breakdown (JSON)
    reactions_detail: Mapped[dict | None] = mapped_column(JSON)
    # {"👍": 50, "❤️": 30, "🔥": 20, ...}

    # Calculated scores
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    virality_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Tracking metadata
    first_tracked_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_tracked_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    tracking_count: Mapped[int] = mapped_column(Integer, default=1)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="engagement")

    __table_args__ = (
        Index("ix_post_engagement_post", "post_id"),
        Index("ix_post_engagement_rate", "engagement_rate"),
    )


class EngagementHistory(Base):
    """Time-series engagement data."""
    __tablename__ = "engagement_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    views: Mapped[int] = mapped_column(Integer)
    reactions: Mapped[int] = mapped_column(Integer)
    forwards: Mapped[int] = mapped_column(Integer)
    replies: Mapped[int] = mapped_column(Integer)

    # Delta from previous record
    views_delta: Mapped[int] = mapped_column(Integer, default=0)
    reactions_delta: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_engagement_history_post", "post_id"),
        Index("ix_engagement_history_time", "recorded_at"),
    )


# Add to Post model:
class Post(Base):
    # ... existing fields ...
    engagement: Mapped["PostEngagement | None"] = relationship(
        "PostEngagement", back_populates="post", uselist=False
    )
```

### 5.4 EngagementTracker Implementation

```python
# analytics/engagement_tracker.py

from abc import ABC, abstractmethod


class EngagementSource(ABC):
    """Abstract source for engagement data."""

    @abstractmethod
    async def get_post_stats(self, channel_id: str, message_id: int) -> dict:
        """Fetch engagement stats for a post."""
        pass


class TelegramEngagementSource(EngagementSource):
    """Fetch engagement via Telegram Bot API."""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def get_post_stats(self, channel_id: str, message_id: int) -> dict:
        """Get stats from Telegram."""
        try:
            # Get message views and forwards
            # Note: Bot API has limited access to engagement
            # Use Telethon for full access
            return {
                "views": 0,  # Requires channel admin access
                "forwards": 0,
                "reactions": {},
            }
        except Exception as e:
            logger.error(f"Failed to fetch engagement: {e}")
            raise


class TelethonEngagementSource(EngagementSource):
    """Fetch engagement via Telethon (user account)."""

    def __init__(self, client: TelegramClient):
        self.client = client

    async def get_post_stats(self, channel_id: str, message_id: int) -> dict:
        """Get full engagement data."""
        try:
            message = await self.client.get_messages(
                entity=channel_id,
                ids=message_id,
            )

            reactions_detail = {}
            if message.reactions:
                for reaction in message.reactions.results:
                    emoji = reaction.reaction.emoticon
                    count = reaction.count
                    reactions_detail[emoji] = count

            return {
                "views": message.views or 0,
                "forwards": message.forwards or 0,
                "reactions_total": sum(reactions_detail.values()),
                "reactions_detail": reactions_detail,
                "replies": message.replies.replies if message.replies else 0,
            }
        except Exception as e:
            logger.error(f"Telethon engagement fetch failed: {e}")
            raise


class EngagementTracker:
    """
    Tracks and stores post engagement metrics.

    Features:
    - Periodic polling of engagement data
    - Time-series storage for trend analysis
    - Alert generation for notable engagement
    """

    def __init__(
        self,
        db: Database,
        source: EngagementSource,
        tracking_interval: timedelta = timedelta(minutes=30),
        max_age: timedelta = timedelta(hours=168),
    ):
        self.db = db
        self.source = source
        self.tracking_interval = tracking_interval
        self.max_age = max_age
        self._running = False

    async def start(self):
        """Start periodic tracking."""
        self._running = True
        while self._running:
            try:
                await self._track_all()
            except Exception as e:
                logger.error(f"Engagement tracking error: {e}")

            await asyncio.sleep(self.tracking_interval.total_seconds())

    async def stop(self):
        """Stop tracking."""
        self._running = False

    async def track_post(self, post: Post) -> PostEngagement:
        """Track engagement for a single post."""
        stats = await self.source.get_post_stats(
            channel_id=post.channel_id,
            message_id=post.telegram_message_id,
        )

        async with self.db.session() as session:
            # Get or create engagement record
            engagement = await session.get(PostEngagement, post.id)
            is_new = engagement is None

            if is_new:
                engagement = PostEngagement(post_id=post.id)

            # Store history snapshot
            if not is_new:
                history = EngagementHistory(
                    post_id=post.id,
                    views=stats["views"],
                    reactions=stats["reactions_total"],
                    forwards=stats["forwards"],
                    replies=stats["replies"],
                    views_delta=stats["views"] - engagement.views,
                    reactions_delta=stats["reactions_total"] - engagement.reactions_total,
                )
                session.add(history)

            # Update current values
            engagement.views = stats["views"]
            engagement.reactions_total = stats["reactions_total"]
            engagement.reactions_detail = stats["reactions_detail"]
            engagement.forwards = stats["forwards"]
            engagement.replies = stats["replies"]

            # Calculate scores
            engagement.engagement_rate = self._calculate_engagement_rate(engagement)
            engagement.virality_score = self._calculate_virality(engagement)

            engagement.last_tracked_at = datetime.utcnow()
            engagement.tracking_count += 1

            session.add(engagement)
            await session.commit()

            # Check for alerts
            await self._check_alerts(post, engagement)

            return engagement

    async def _track_all(self):
        """Track all eligible posts."""
        cutoff = datetime.utcnow() - self.max_age

        async with self.db.session() as session:
            result = await session.execute(
                select(Post)
                .join(PostEngagement, isouter=True)
                .where(
                    Post.status == "published",
                    Post.published_at > cutoff,
                    or_(
                        PostEngagement.last_tracked_at.is_(None),
                        PostEngagement.last_tracked_at < datetime.utcnow() - timedelta(minutes=15),
                    ),
                )
            )
            posts = list(result.scalars().all())

        logger.info(f"Tracking engagement for {len(posts)} posts")

        for post in posts:
            try:
                await self.track_post(post)
            except Exception as e:
                logger.error(f"Failed to track post {post.id}: {e}")

    def _calculate_engagement_rate(self, engagement: PostEngagement) -> float:
        """
        Calculate engagement rate.

        Formula: (reactions + forwards + replies * 2) / views * 100
        """
        if engagement.views == 0:
            return 0.0

        weighted_engagement = (
            engagement.reactions_total +
            engagement.forwards * 2 +  # Forwards are more valuable
            engagement.replies * 3      # Replies are most valuable
        )

        return round((weighted_engagement / engagement.views) * 100, 2)

    def _calculate_virality(self, engagement: PostEngagement) -> float:
        """
        Calculate virality score.

        Factors:
        - Forward rate
        - Reaction diversity
        - Growth rate (from history)
        """
        if engagement.views == 0:
            return 0.0

        forward_rate = engagement.forwards / engagement.views
        reaction_diversity = len(engagement.reactions_detail or {}) / 10  # Normalize to 0-1

        # Base virality from forwards
        virality = forward_rate * 100

        # Bonus for reaction diversity
        virality *= (1 + reaction_diversity * 0.5)

        return round(min(virality, 100), 2)

    async def _check_alerts(self, post: Post, engagement: PostEngagement):
        """Generate alerts for notable engagement."""
        # High engagement alert
        if engagement.engagement_rate > 10:  # 10% engagement rate
            await self._send_alert(
                level="info",
                message=f"🔥 Post {post.id} has high engagement: {engagement.engagement_rate}%",
                post_id=post.id,
            )

        # Viral alert
        if engagement.virality_score > 5:
            await self._send_alert(
                level="info",
                message=f"🚀 Post {post.id} going viral! Score: {engagement.virality_score}",
                post_id=post.id,
            )

    async def get_top_posts(
        self,
        period: timedelta = timedelta(days=7),
        limit: int = 10,
        metric: str = "engagement_rate",
    ) -> list[tuple[Post, PostEngagement]]:
        """Get top performing posts."""
        cutoff = datetime.utcnow() - period

        async with self.db.session() as session:
            result = await session.execute(
                select(Post, PostEngagement)
                .join(PostEngagement)
                .where(Post.published_at > cutoff)
                .order_by(desc(getattr(PostEngagement, metric)))
                .limit(limit)
            )
            return list(result.all())

    async def get_aggregate_stats(self, period: timedelta = timedelta(days=7)) -> dict:
        """Get aggregated engagement statistics."""
        cutoff = datetime.utcnow() - period

        async with self.db.session() as session:
            result = await session.execute(
                select(
                    func.count().label("posts"),
                    func.sum(PostEngagement.views).label("total_views"),
                    func.sum(PostEngagement.reactions_total).label("total_reactions"),
                    func.sum(PostEngagement.forwards).label("total_forwards"),
                    func.avg(PostEngagement.engagement_rate).label("avg_engagement_rate"),
                    func.max(PostEngagement.views).label("max_views"),
                )
                .select_from(PostEngagement)
                .join(Post)
                .where(Post.published_at > cutoff)
            )
            row = result.one()

            return {
                "period_days": period.days,
                "posts_tracked": row.posts,
                "total_views": row.total_views or 0,
                "total_reactions": row.total_reactions or 0,
                "total_forwards": row.total_forwards or 0,
                "avg_engagement_rate": round(row.avg_engagement_rate or 0, 2),
                "max_views": row.max_views or 0,
            }
```

---

## 6. Enhanced RSS Parser

### 6.1 Overview

Improved RSS parsing with full-text extraction, better error handling, and source management.

### 6.2 Configuration

```yaml
# config.yaml
rss:
  enhanced_mode: true
  full_text_extraction: true
  user_agent: "TG-AI-Poster/2.0"
  timeout_seconds: 30
  max_retries: 3
  cache_ttl_hours: 6

  sources:
    - url: "https://techcrunch.com/feed/"
      name: "TechCrunch"
      priority: 80
      full_text: true
      categories: ["tech", "startups"]

    - url: "https://openai.com/blog/rss.xml"
      name: "OpenAI Blog"
      priority: 100
      full_text: true
      categories: ["ai", "research"]

  filters:
    min_content_length: 500
    exclude_patterns:
      - "\\b(?:sponsored|ad|advertisement)\\b"
      - "\\bpodcast\\b"
    require_categories: ["ai", "tech", "programming"]
```

### 6.3 Database Schema

```python
# memory/models.py

class RSSSource(Base):
    """Managed RSS source."""
    __tablename__ = "rss_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Configuration
    priority: Mapped[int] = mapped_column(Integer, default=50)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    full_text_extraction: Mapped[bool] = mapped_column(Boolean, default=True)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Status
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)
    total_articles_fetched: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    fetch_interval_hours: Mapped[int] = mapped_column(Integer, default=6)

    __table_args__ = (
        Index("ix_rss_sources_enabled", "enabled"),
    )


class RSSArticle(Base):
    """Cached RSS article."""
    __tablename__ = "rss_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("rss_sources.id"))

    # Article data
    url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    full_content: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Processing status
    status: Mapped[str] = mapped_column(String(20), default="new")
    # new, processed, used, expired

    # Metadata
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA256

    # Relationships
    source: Mapped["RSSSource"] = relationship("RSSSource")

    __table_args__ = (
        Index("ix_rss_articles_source", "source_id"),
        Index("ix_rss_articles_status", "status"),
        Index("ix_rss_articles_published", "published_at"),
    )
```

### 6.4 EnhancedRSSParser Implementation

```python
# pipeline/enhanced_rss_parser.py

import hashlib
import httpx
from readability import Document
from bs4 import BeautifulSoup


@dataclass
class ParsedArticle:
    """Parsed RSS article."""
    url: str
    title: str
    summary: str
    full_content: str | None
    author: str | None
    published_at: datetime | None
    source_name: str
    source_priority: int
    content_hash: str


class FullTextExtractor:
    """Extract full text from article URLs."""

    def __init__(
        self,
        timeout: int = 30,
        user_agent: str = "TG-AI-Poster/2.0",
    ):
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent}

    async def extract(self, url: str) -> str | None:
        """
        Extract full text from URL using readability.

        Falls back gracefully on errors.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, follow_redirects=True)
                response.raise_for_status()

            # Use readability for main content extraction
            doc = Document(response.text)
            content = doc.summary()

            # Clean HTML and extract text
            soup = BeautifulSoup(content, "html.parser")
            text = soup.get_text(separator="\n")

            # Clean up whitespace
            text = "\n".join(line.strip() for line in text.split("\n") if line.strip())

            return text

        except Exception as e:
            logger.warning(f"Full text extraction failed for {url}: {e}")
            return None


class EnhancedRSSParser:
    """
    Enhanced RSS parser with full-text extraction.

    Features:
    - Full-text content extraction
    - Source priority management
    - Error tracking and recovery
    - Article deduplication
    """

    def __init__(
        self,
        db: Database,
        extractor: FullTextExtractor,
        user_agent: str = "TG-AI-Poster/2.0",
    ):
        self.db = db
        self.extractor = extractor
        self.user_agent = user_agent

    async def fetch_source(self, source: RSSSource) -> list[ParsedArticle]:
        """Fetch and parse articles from RSS source."""
        articles = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    source.url,
                    headers={"User-Agent": self.user_agent},
                    timeout=30,
                    follow_redirects=True,
                )
                response.raise_for_status()

            feed = feedparser.parse(response.text)

            for entry in feed.entries:
                article = await self._parse_entry(entry, source)
                if article:
                    articles.append(article)

            # Update source status
            await self._update_source_status(source, success=True)

        except Exception as e:
            logger.error(f"RSS fetch failed for {source.name}: {e}")
            await self._update_source_status(source, success=False, error=str(e))

        return articles

    async def _parse_entry(self, entry, source: RSSSource) -> ParsedArticle | None:
        """Parse single RSS entry."""
        url = entry.get("link") or entry.get("guid")
        if not url:
            return None

        # Check for duplicates
        content_hash = self._hash_content(entry)

        async with self.db.session() as session:
            existing = await session.execute(
                select(RSSArticle).where(
                    or_(
                        RSSArticle.url == url,
                        RSSArticle.content_hash == content_hash,
                    )
                )
            )
            if existing.scalar_one_or_none():
                return None

        # Extract full content if enabled
        full_content = None
        if source.full_text_extraction:
            full_content = await self.extractor.extract(url)

        # Parse published date
        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published_at = datetime(*entry.updated_parsed[:6])

        return ParsedArticle(
            url=url,
            title=entry.get("title", ""),
            summary=entry.get("summary", entry.get("description", "")),
            full_content=full_content,
            author=entry.get("author"),
            published_at=published_at,
            source_name=source.name,
            source_priority=source.priority,
            content_hash=content_hash,
        )

    def _hash_content(self, entry) -> str:
        """Generate content hash for deduplication."""
        content = f"{entry.get('title', '')}{entry.get('summary', '')}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def _update_source_status(
        self,
        source: RSSSource,
        success: bool,
        error: str | None = None,
    ):
        """Update source fetch status."""
        async with self.db.session() as session:
            db_source = await session.get(RSSSource, source.id)
            if db_source:
                db_source.last_fetch_at = datetime.utcnow()
                if success:
                    db_source.consecutive_errors = 0
                    db_source.last_error = None
                else:
                    db_source.consecutive_errors += 1
                    db_source.last_error = error

                await session.commit()

    async def get_eligible_sources(self) -> list[RSSSource]:
        """Get sources that should be fetched."""
        async with self.db.session() as session:
            result = await session.execute(
                select(RSSSource)
                .where(
                    RSSSource.enabled == True,
                    or_(
                        RSSSource.last_fetch_at.is_(None),
                        RSSSource.last_fetch_at < datetime.utcnow() - timedelta(hours=RSSSource.fetch_interval_hours),
                    ),
                    RSSSource.consecutive_errors < 5,  # Disable after 5 consecutive errors
                )
                .order_by(RSSSource.priority.desc())
            )
            return list(result.scalars().all())

    async def store_article(self, article: ParsedArticle, source_id: int) -> RSSArticle:
        """Store parsed article in database."""
        async with self.db.session() as session:
            db_article = RSSArticle(
                source_id=source_id,
                url=article.url,
                title=article.title,
                summary=article.summary,
                full_content=article.full_content,
                author=article.author,
                published_at=article.published_at,
                content_hash=article.content_hash,
            )
            session.add(db_article)
            await session.commit()
            return db_article
```

---

## 7. Hashtag Performance Analytics

### 7.1 Overview

Track and analyze which hashtags perform best for engagement.

### 7.2 Database Schema

```python
# memory/models.py

class HashtagStats(Base):
    """Aggregated hashtag performance statistics."""
    __tablename__ = "hashtag_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hashtag: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Usage stats
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    first_used_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Performance metrics
    avg_engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_views: Mapped[float] = mapped_column(Float, default=0.0)
    avg_forwards: Mapped[float] = mapped_column(Float, default=0.0)

    # Derived scores
    performance_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommendation_tier: Mapped[str] = mapped_column(String(20), default="neutral")
    # excellent, good, neutral, poor

    __table_args__ = (
        Index("ix_hashtag_stats_tag", "hashtag"),
        Index("ix_hashtag_stats_score", "performance_score"),
    )


class PostHashtag(Base):
    """Association table for posts and hashtags."""
    __tablename__ = "post_hashtags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"))
    hashtag: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("post_id", "hashtag"),
        Index("ix_post_hashtags_tag", "hashtag"),
    )
```

### 7.3 HashtagAnalyzer Implementation

```python
# analytics/hashtag_analyzer.py

class HashtagAnalyzer:
    """
    Analyze hashtag performance and generate recommendations.

    Features:
    - Performance tracking per hashtag
    - Trend detection
    - Recommendation generation
    """

    def __init__(self, db: Database):
        self.db = db

    async def record_usage(self, post: Post, hashtags: list[str]):
        """Record hashtag usage for a post."""
        async with self.db.session() as session:
            for tag in hashtags:
                # Normalize hashtag
                tag = tag.lower().strip("#")

                # Create/update post association
                association = PostHashtag(post_id=post.id, hashtag=tag)
                session.merge(association)

                # Update stats
                stats = await session.get(HashtagStats, tag)
                if not stats:
                    stats = HashtagStats(hashtag=tag)
                    session.add(stats)

                stats.times_used += 1
                stats.last_used_at = datetime.utcnow()

            await session.commit()

    async def update_performance(self, post: Post, engagement: PostEngagement):
        """Update hashtag performance based on post engagement."""
        async with self.db.session() as session:
            result = await session.execute(
                select(PostHashtag).where(PostHashtag.post_id == post.id)
            )
            hashtags = result.scalars().all()

            for ht in hashtags:
                stats = await session.get(HashtagStats, ht.hashtag)
                if not stats:
                    continue

                # Running average update
                n = stats.times_used
                stats.avg_engagement_rate = (
                    (stats.avg_engagement_rate * (n - 1) + engagement.engagement_rate) / n
                )
                stats.avg_views = (
                    (stats.avg_views * (n - 1) + engagement.views) / n
                )
                stats.avg_forwards = (
                    (stats.avg_forwards * (n - 1) + engagement.forwards) / n
                )

                # Recalculate performance score
                stats.performance_score = self._calculate_score(stats)
                stats.recommendation_tier = self._get_tier(stats.performance_score)

            await session.commit()

    def _calculate_score(self, stats: HashtagStats) -> float:
        """
        Calculate overall performance score.

        Factors:
        - Average engagement rate (50% weight)
        - Average views (30% weight)
        - Forward rate (20% weight)
        """
        engagement_score = min(stats.avg_engagement_rate / 10, 10)  # Max 10
        views_score = min(stats.avg_views / 1000, 10)  # Max 10
        forward_score = min(stats.avg_forwards / 10, 10)  # Max 10

        return round(
            engagement_score * 0.5 +
            views_score * 0.3 +
            forward_score * 0.2,
            2
        )

    def _get_tier(self, score: float) -> str:
        """Determine recommendation tier from score."""
        if score >= 7:
            return "excellent"
        elif score >= 5:
            return "good"
        elif score >= 3:
            return "neutral"
        else:
            return "poor"

    async def get_recommendations(self, limit: int = 10) -> list[dict]:
        """Get recommended hashtags based on performance."""
        async with self.db.session() as session:
            result = await session.execute(
                select(HashtagStats)
                .where(HashtagStats.times_used >= 3)  # Minimum sample size
                .order_by(HashtagStats.performance_score.desc())
                .limit(limit)
            )
            top_tags = result.scalars().all()

            return [
                {
                    "hashtag": tag.hashtag,
                    "score": tag.performance_score,
                    "tier": tag.recommendation_tier,
                    "avg_engagement": tag.avg_engagement_rate,
                    "times_used": tag.times_used,
                }
                for tag in top_tags
            ]

    async def suggest_for_topic(self, topic: str, limit: int = 5) -> list[str]:
        """Suggest hashtags based on topic similarity."""
        # TODO: Implement topic-based suggestion using embeddings
        # For now, return top performers
        recommendations = await self.get_recommendations(limit)
        return [r["hashtag"] for r in recommendations]
```

---

## 8. Reddit Integration

### 8.1 Overview

Monitor Reddit subreddits for trending AI/tech content.

### 8.2 Configuration

```yaml
# config.yaml
reddit:
  enabled: true
  client_id: "${REDDIT_CLIENT_ID}"
  client_secret: "${REDDIT_CLIENT_SECRET}"
  user_agent: "TG-AI-Poster/2.0"

  subreddits:
    - name: "MachineLearning"
      priority: 90
      min_score: 500
      fetch_limit: 25

    - name: "artificial"
      priority: 85
      min_score: 300
      fetch_limit: 25

    - name: "ChatGPT"
      priority: 80
      min_score: 200
      fetch_limit: 20

  fetch_interval_minutes: 60
```

### 8.3 RedditClient Implementation

```python
# sources/reddit_client.py

import praw
from praw.models import Submission


@dataclass
class RedditPost:
    """Parsed Reddit post."""
    id: str
    subreddit: str
    title: str
    selftext: str
    url: str
    score: int
    num_comments: int
    author: str
    created_at: datetime
    permalink: str
    flair: str | None


class RedditClient:
    """
    Reddit API client for content discovery.

    Features:
    - Subreddit monitoring
    - Score-based filtering
    - Rate limit handling
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
    ):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

    async def get_trending(
        self,
        subreddit: str,
        min_score: int = 100,
        limit: int = 25,
        time_filter: str = "day",
    ) -> list[RedditPost]:
        """Get trending posts from subreddit."""
        posts = []

        try:
            subreddit_obj = self.reddit.subreddit(subreddit)

            # Get top posts
            submissions = subreddit_obj.top(
                time_filter=time_filter,
                limit=limit * 2,  # Fetch extra to filter
            )

            for submission in submissions:
                if submission.score < min_score:
                    continue

                # Skip NSFW, stickied, or archived
                if submission.over18 or submission.stickied or submission.archived:
                    continue

                posts.append(self._parse_submission(submission))

                if len(posts) >= limit:
                    break

        except Exception as e:
            logger.error(f"Reddit fetch failed for r/{subreddit}: {e}")

        return posts

    def _parse_submission(self, submission: Submission) -> RedditPost:
        """Parse PRAW submission to our model."""
        return RedditPost(
            id=submission.id,
            subreddit=submission.subreddit.display_name,
            title=submission.title,
            selftext=submission.selftext,
            url=submission.url,
            score=submission.score,
            num_comments=submission.num_comments,
            author=submission.author.name if submission.author else "[deleted]",
            created_at=datetime.fromtimestamp(submission.created_utc),
            permalink=f"https://reddit.com{submission.permalink}",
            flair=submission.link_flair_text,
        )

    async def search(
        self,
        query: str,
        subreddits: list[str],
        limit: int = 25,
    ) -> list[RedditPost]:
        """Search across multiple subreddits."""
        posts = []
        subreddit_str = "+".join(subreddits)

        try:
            results = self.reddit.subreddit(subreddit_str).search(
                query,
                sort="relevance",
                time_filter="week",
                limit=limit,
            )

            for submission in results:
                posts.append(self._parse_submission(submission))

        except Exception as e:
            logger.error(f"Reddit search failed: {e}")

        return posts
```

---

## 9. Predictive Analytics

### 9.1 Overview

Predict post engagement before publishing using historical data.

### 9.2 Configuration

```yaml
# config.yaml
predictive:
  enabled: true
  model_path: "models/engagement_predictor.joblib"
  retrain_interval_days: 7
  min_training_samples: 100

  features:
    - content_length
    - has_emoji
    - emoji_count
    - hashtag_count
    - post_hour
    - post_day_of_week
    - topic_category
    - source_priority

  thresholds:
    high_prediction: 5.0    # Predicted engagement rate
    low_prediction: 1.0
```

### 9.3 EngagementPredictor Implementation

```python
# analytics/engagement_predictor.py

import joblib
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
import numpy as np


@dataclass
class PostFeatures:
    """Features for engagement prediction."""
    content_length: int
    emoji_count: int
    hashtag_count: int
    has_hook: bool
    has_question: bool
    has_numbers: bool
    post_hour: int
    post_day_of_week: int
    source_priority: int
    topic_encoded: int


class EngagementPredictor:
    """
    ML-based engagement prediction.

    Features:
    - Gradient boosting model
    - Automatic retraining
    - Feature importance analysis
    """

    def __init__(
        self,
        db: Database,
        model_path: str = "models/engagement_predictor.joblib",
    ):
        self.db = db
        self.model_path = model_path
        self.model: GradientBoostingRegressor | None = None
        self.scaler: StandardScaler | None = None

    async def load_or_train(self) -> bool:
        """Load existing model or train new one."""
        try:
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            logger.info("Loaded engagement predictor model")
            return True
        except FileNotFoundError:
            logger.info("No model found, training new one")
            return await self.train()

    async def train(self) -> bool:
        """Train model on historical data."""
        # Get training data
        features, targets = await self._get_training_data()

        if len(features) < 100:
            logger.warning("Not enough data for training")
            return False

        # Scale features
        self.scaler = StandardScaler()
        X = self.scaler.fit_transform(features)

        # Train model
        self.model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
        )
        self.model.fit(X, targets)

        # Save model
        joblib.dump({
            "model": self.model,
            "scaler": self.scaler,
        }, self.model_path)

        # Log metrics
        score = self.model.score(X, targets)
        logger.info(f"Model trained, R² score: {score:.3f}")

        return True

    async def predict(self, post: Post) -> float:
        """Predict engagement rate for a post."""
        if not self.model:
            return 0.0

        features = self._extract_features(post)
        X = self.scaler.transform([features])

        prediction = self.model.predict(X)[0]
        return round(max(0, prediction), 2)

    def _extract_features(self, post: Post) -> list:
        """Extract features from post."""
        content = post.content or ""

        return [
            len(content),
            len(re.findall(r"[\U0001F600-\U0001F64F]", content)),
            len(re.findall(r"#\w+", content)),
            bool(re.search(r"^(Как|Почему|Что|How|Why|What)", content, re.I)),
            "?" in content[:100],
            bool(re.search(r"\d+", content[:100])),
            post.scheduled_at.hour if post.scheduled_at else 12,
            post.scheduled_at.weekday() if post.scheduled_at else 3,
            50,  # Default source priority
            0,   # Default topic encoding
        ]

    async def _get_training_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Get historical data for training."""
        async with self.db.session() as session:
            result = await session.execute(
                select(Post, PostEngagement)
                .join(PostEngagement)
                .where(Post.published_at > datetime.utcnow() - timedelta(days=90))
            )

            features = []
            targets = []

            for post, engagement in result:
                features.append(self._extract_features(post))
                targets.append(engagement.engagement_rate)

            return np.array(features), np.array(targets)

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance from model."""
        if not self.model:
            return {}

        feature_names = [
            "content_length",
            "emoji_count",
            "hashtag_count",
            "has_hook",
            "has_question",
            "has_numbers",
            "post_hour",
            "post_day",
            "source_priority",
            "topic",
        ]

        return dict(zip(feature_names, self.model.feature_importances_))
```

---

## 10. Multi-channel Publishing

### 10.1 Overview

Publish to multiple Telegram channels simultaneously.

### 10.2 Configuration

```yaml
# config.yaml
multi_channel:
  enabled: true
  channels:
    - id: "${CHANNEL_1_ID}"
      name: "Main Channel"
      format: "default"
      enabled: true

    - id: "${CHANNEL_2_ID}"
      name: "Secondary Channel"
      format: "compact"
      enabled: true

  formats:
    default:
      include_sources: true
      include_hashtags: true
      max_length: 4096

    compact:
      include_sources: false
      include_hashtags: true
      max_length: 1024
```

### 10.3 MultiPublisher Implementation

```python
# publisher/multi_publisher.py

@dataclass
class ChannelConfig:
    """Channel publishing configuration."""
    id: str
    name: str
    format: str
    enabled: bool


@dataclass
class MultiPublishResult:
    """Result of multi-channel publishing."""
    success: bool
    channel_results: dict[str, PublishResult]
    errors: list[str]


class MultiPublisher:
    """
    Publish to multiple channels.

    Features:
    - Parallel publishing
    - Format per channel
    - Failure handling
    """

    def __init__(
        self,
        bot: Bot,
        channels: list[ChannelConfig],
        formatters: dict[str, "PostFormatter"],
    ):
        self.bot = bot
        self.channels = {c.id: c for c in channels if c.enabled}
        self.formatters = formatters

    async def publish_to_all(
        self,
        post: Post,
        channels: list[str] | None = None,
    ) -> MultiPublishResult:
        """Publish post to all or specified channels."""
        target_channels = channels or list(self.channels.keys())
        results = {}
        errors = []

        # Format for each channel
        formatted_posts = await self._format_for_channels(post, target_channels)

        # Publish in parallel
        tasks = [
            self._publish_to_channel(channel_id, formatted_posts[channel_id])
            for channel_id in target_channels
        ]

        channel_results = await asyncio.gather(*tasks, return_exceptions=True)

        for channel_id, result in zip(target_channels, channel_results):
            if isinstance(result, Exception):
                errors.append(f"{channel_id}: {result}")
                results[channel_id] = PublishResult(success=False, error=str(result))
            else:
                results[channel_id] = result

        return MultiPublishResult(
            success=len(errors) == 0,
            channel_results=results,
            errors=errors,
        )

    async def _format_for_channels(
        self,
        post: Post,
        channels: list[str],
    ) -> dict[str, str]:
        """Format post for each channel."""
        formatted = {}

        for channel_id in channels:
            config = self.channels[channel_id]
            formatter = self.formatters.get(config.format)

            if formatter:
                formatted[channel_id] = await formatter.format(post, config)
            else:
                formatted[channel_id] = post.content

        return formatted

    async def _publish_to_channel(
        self,
        channel_id: str,
        content: str,
    ) -> PublishResult:
        """Publish to single channel."""
        try:
            message = await self.bot.send_message(
                chat_id=channel_id,
                text=content,
                parse_mode="MarkdownV2",
            )

            return PublishResult(
                success=True,
                message_id=message.message_id,
                channel_id=channel_id,
            )

        except Exception as e:
            logger.error(f"Failed to publish to {channel_id}: {e}")
            return PublishResult(success=False, error=str(e))
```

---

## 11. Implementation Timeline

### Week 1-2: Core Features

| Day | Task | Deliverable |
|-----|------|-------------|
| 1-2 | Thread Mode | `thread_builder.py`, models, tests |
| 3-4 | Smart Queue | `queue_manager.py`, admin commands |
| 5 | Integration | Orchestrator updates |

### Week 3-4: Analytics

| Day | Task | Deliverable |
|-----|------|-------------|
| 1-3 | Engagement Tracker | `engagement_tracker.py`, models |
| 4-5 | Hashtag Analytics | `hashtag_analyzer.py` |
| 5 | Admin integration | Bot commands for analytics |

### Week 5-6: Sources & Predictions

| Day | Task | Deliverable |
|-----|------|-------------|
| 1-2 | Enhanced RSS | `enhanced_rss_parser.py` |
| 3-4 | Reddit Integration | `reddit_client.py` |
| 5 | Predictive Analytics | `engagement_predictor.py` |

### Week 7-8: Advanced Features

| Day | Task | Deliverable |
|-----|------|-------------|
| 1-3 | Multi-channel | `multi_publisher.py` |
| 4-5 | Testing & Polish | Full test coverage |

---

## Appendix A: Database Migration

```sql
-- Phase 2 migrations

-- Thread support
CREATE TABLE threads (
    id INTEGER PRIMARY KEY,
    topic VARCHAR(500) NOT NULL,
    total_posts INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP
);

ALTER TABLE posts ADD COLUMN thread_id INTEGER REFERENCES threads(id);
ALTER TABLE posts ADD COLUMN thread_position INTEGER;
ALTER TABLE posts ADD COLUMN is_thread_part BOOLEAN DEFAULT FALSE;

-- Smart Queue
CREATE TABLE post_queue (
    id INTEGER PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id) UNIQUE,
    scheduled_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    priority INTEGER DEFAULT 50,
    priority_reason VARCHAR(100),
    status VARCHAR(20) DEFAULT 'queued',
    conflicts_with INTEGER REFERENCES post_queue(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP
);

-- Engagement Tracking
CREATE TABLE post_engagement (
    id INTEGER PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id) UNIQUE,
    views INTEGER DEFAULT 0,
    reactions_total INTEGER DEFAULT 0,
    forwards INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    reactions_detail JSON,
    engagement_rate FLOAT DEFAULT 0.0,
    virality_score FLOAT DEFAULT 0.0,
    first_tracked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_tracked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tracking_count INTEGER DEFAULT 1
);

CREATE TABLE engagement_history (
    id INTEGER PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    views INTEGER,
    reactions INTEGER,
    forwards INTEGER,
    replies INTEGER,
    views_delta INTEGER DEFAULT 0,
    reactions_delta INTEGER DEFAULT 0
);

-- Hashtag Analytics
CREATE TABLE hashtag_stats (
    id INTEGER PRIMARY KEY,
    hashtag VARCHAR(100) UNIQUE NOT NULL,
    times_used INTEGER DEFAULT 0,
    first_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    avg_engagement_rate FLOAT DEFAULT 0.0,
    avg_views FLOAT DEFAULT 0.0,
    avg_forwards FLOAT DEFAULT 0.0,
    performance_score FLOAT DEFAULT 0.0,
    recommendation_tier VARCHAR(20) DEFAULT 'neutral'
);

CREATE TABLE post_hashtags (
    id INTEGER PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id),
    hashtag VARCHAR(100) NOT NULL,
    UNIQUE(post_id, hashtag)
);

-- Enhanced RSS
CREATE TABLE rss_sources (
    id INTEGER PRIMARY KEY,
    url VARCHAR(500) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    priority INTEGER DEFAULT 50,
    enabled BOOLEAN DEFAULT TRUE,
    full_text_extraction BOOLEAN DEFAULT TRUE,
    categories JSON,
    last_fetch_at TIMESTAMP,
    last_error TEXT,
    consecutive_errors INTEGER DEFAULT 0,
    total_articles_fetched INTEGER DEFAULT 0,
    fetch_interval_hours INTEGER DEFAULT 6
);

CREATE TABLE rss_articles (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES rss_sources(id),
    url VARCHAR(1000) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    full_content TEXT,
    author VARCHAR(200),
    published_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'new',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash VARCHAR(64)
);

-- Indexes
CREATE INDEX ix_threads_status ON threads(status);
CREATE INDEX ix_post_queue_scheduled ON post_queue(scheduled_at);
CREATE INDEX ix_post_queue_priority ON post_queue(priority);
CREATE INDEX ix_engagement_history_post ON engagement_history(post_id);
CREATE INDEX ix_engagement_history_time ON engagement_history(recorded_at);
CREATE INDEX ix_hashtag_stats_score ON hashtag_stats(performance_score);
CREATE INDEX ix_rss_articles_status ON rss_articles(status);
```

---

## Appendix B: Test Coverage Requirements

| Module | Min Coverage | Key Tests |
|--------|--------------|-----------|
| thread_builder | 90% | Split strategies, navigation, edge cases |
| queue_manager | 90% | Priority ordering, conflicts, expiration |
| engagement_tracker | 85% | Data collection, score calculation |
| hashtag_analyzer | 80% | Performance updates, recommendations |
| reddit_client | 75% | API mocking, filtering |
| engagement_predictor | 80% | Training, prediction, features |

---

*Document Version: 1.0*
*Created: 2025-03-15*
*Status: Draft - Ready for Review*
