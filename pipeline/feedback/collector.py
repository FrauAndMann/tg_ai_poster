"""
Feedback Collector - Collects and stores Telegram engagement metrics.

Collects views, reactions, forwards, and replies from Telegram API
and stores them in a SQLite database for analysis.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from core.logger import get_logger

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = get_logger(__name__)


@dataclass
class PostAnalytics:
    """Analytics data for a single post."""

    post_id: str
    telegram_message_id: int
    views: int
    reactions: Dict[str, int]  # emoji -> count
    forwards: int
    replies: int
    quality_score: float
    collected_at: datetime

    @property
    def total_reactions(self) -> int:
        """Get total count of all reactions."""
        return sum(self.reactions.values()) if self.reactions else 0

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate (total engagement / views)."""
        if self.views == 0:
            return 0.0
        total_engagement = self.total_reactions + self.forwards + self.replies
        return total_engagement / self.views

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "post_id": self.post_id,
            "telegram_message_id": self.telegram_message_id,
            "views": self.views,
            "reactions": self.reactions,
            "forwards": self.forwards,
            "replies": self.replies,
            "quality_score": self.quality_score,
            "collected_at": self.collected_at.isoformat(),
        }


class FeedbackCollector:
    """
    Collects and stores Telegram engagement metrics.

    Features:
    - Fetches metrics from Telegram API via Telethon
    - Stores analytics in SQLite database
    - Retrieves analytics for analysis
    """

    def __init__(
        self,
        db_path: str = "data/analytics.db",
        telegram_client: Optional["TelegramClient"] = None,
    ):
        """
        Initialize the feedback collector.

        Args:
            db_path: Path to SQLite database file
            telegram_client: Optional Telethon client for API access
        """
        self.db_path = db_path
        self.telegram_client = telegram_client
        self._init_db()

    def _init_db(self) -> None:
        """Create analytics table if not exists."""
        # Ensure directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL,
                telegram_message_id INTEGER NOT NULL,
                views INTEGER DEFAULT 0,
                reactions TEXT DEFAULT '{}',
                forwards INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                quality_score REAL DEFAULT 0.0,
                collected_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, collected_at)
            )
        """)

        # Create index for faster period queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_post_analytics_collected_at
            ON post_analytics(collected_at)
        """)

        # Create index for post_id lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_post_analytics_post_id
            ON post_analytics(post_id)
        """)

        conn.commit()
        conn.close()

        logger.info(f"Initialized feedback database at {self.db_path}")

    async def collect_metrics(
        self,
        post_id: str,
        message_id: int,
        channel_entity: Any = None,
        quality_score: float = 0.0,
    ) -> Optional[PostAnalytics]:
        """
        Fetch metrics from Telegram API.

        Args:
            post_id: Internal post identifier
            message_id: Telegram message ID
            channel_entity: Channel entity for message lookup
            quality_score: Quality score assigned to the post

        Returns:
            PostAnalytics or None if collection failed
        """
        if not self.telegram_client:
            logger.warning("No Telegram client configured, cannot collect metrics")
            return None

        try:
            # Get message views and reactions
            messages = await self.telegram_client.get_messages(
                entity=channel_entity,
                ids=[message_id],
            )

            if not messages:
                logger.warning(f"Message {message_id} not found")
                return None

            msg = messages[0] if isinstance(messages, list) else messages

            # Extract views
            views = getattr(msg, "views", 0) or 0

            # Extract forwards
            forwards = getattr(msg, "forwards", 0) or 0

            # Extract reactions
            reactions: Dict[str, int] = {}
            reactions_data = getattr(msg, "reactions", None)
            if reactions_data:
                results = getattr(reactions_data, "results", [])
                for reaction in results:
                    count = getattr(reaction, "count", 0)
                    reaction_obj = getattr(reaction, "reaction", None)
                    if reaction_obj:
                        emoticon = getattr(reaction_obj, "emoticon", None)
                        if emoticon:
                            reactions[emoticon] = count

            # Replies - Telegram doesn't expose easily, use 0
            replies = 0

            analytics = PostAnalytics(
                post_id=post_id,
                telegram_message_id=message_id,
                views=views,
                reactions=reactions,
                forwards=forwards,
                replies=replies,
                quality_score=quality_score,
                collected_at=datetime.utcnow(),
            )

            logger.info(
                f"Collected metrics for post {post_id}: "
                f"views={views}, reactions={sum(reactions.values())}, forwards={forwards}"
            )

            return analytics

        except Exception as e:
            logger.error(f"Failed to collect metrics for post {post_id}: {e}")
            return None

    async def store_analytics(self, analytics: PostAnalytics) -> None:
        """
        Store analytics in database.

        Args:
            analytics: PostAnalytics to store
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO post_analytics
                (post_id, telegram_message_id, views, reactions, forwards, replies, quality_score, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analytics.post_id,
                analytics.telegram_message_id,
                analytics.views,
                json.dumps(analytics.reactions),
                analytics.forwards,
                analytics.replies,
                analytics.quality_score,
                analytics.collected_at.isoformat(),
            ))

            conn.commit()
            logger.debug(f"Stored analytics for post {analytics.post_id}")

        except Exception as e:
            logger.error(f"Failed to store analytics: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_analytics_by_post_id(self, post_id: str) -> Optional[PostAnalytics]:
        """
        Get the most recent analytics for a post.

        Args:
            post_id: Post identifier

        Returns:
            PostAnalytics or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT post_id, telegram_message_id, views, reactions, forwards, replies, quality_score, collected_at
                FROM post_analytics
                WHERE post_id = ?
                ORDER BY collected_at DESC
                LIMIT 1
            """, (post_id,))

            row = cursor.fetchone()
            if row:
                return self._row_to_analytics(row)
            return None

        finally:
            conn.close()

    def get_analytics_for_period(
        self,
        start_date: date,
        end_date: date,
    ) -> List[PostAnalytics]:
        """
        Get all analytics for a date range.

        Args:
            start_date: Start of period (inclusive)
            end_date: End of period (inclusive)

        Returns:
            List of PostAnalytics for the period
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT post_id, telegram_message_id, views, reactions, forwards, replies, quality_score, collected_at
                FROM post_analytics
                WHERE DATE(collected_at) >= ? AND DATE(collected_at) <= ?
                ORDER BY collected_at ASC
            """, (start_date.isoformat(), end_date.isoformat()))

            rows = cursor.fetchall()
            return [self._row_to_analytics(row) for row in rows]

        finally:
            conn.close()

    def get_all_analytics(self) -> List[PostAnalytics]:
        """
        Get all stored analytics.

        Returns:
            List of all PostAnalytics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT post_id, telegram_message_id, views, reactions, forwards, replies, quality_score, collected_at
                FROM post_analytics
                ORDER BY collected_at ASC
            """)

            rows = cursor.fetchall()
            return [self._row_to_analytics(row) for row in rows]

        finally:
            conn.close()

    def _row_to_analytics(self, row: Tuple) -> PostAnalytics:
        """Convert database row to PostAnalytics."""
        return PostAnalytics(
            post_id=row[0],
            telegram_message_id=row[1],
            views=row[2],
            reactions=json.loads(row[3]) if row[3] else {},
            forwards=row[4],
            replies=row[5],
            quality_score=row[6],
            collected_at=datetime.fromisoformat(row[7]),
        )

    async def collect_and_store(
        self,
        post_id: str,
        message_id: int,
        channel_entity: Any = None,
        quality_score: float = 0.0,
    ) -> Optional[PostAnalytics]:
        """
        Collect metrics and store them in one operation.

        Args:
            post_id: Internal post identifier
            message_id: Telegram message ID
            channel_entity: Channel entity for message lookup
            quality_score: Quality score assigned to the post

        Returns:
            PostAnalytics or None if collection failed
        """
        analytics = await self.collect_metrics(
            post_id=post_id,
            message_id=message_id,
            channel_entity=channel_entity,
            quality_score=quality_score,
        )

        if analytics:
            await self.store_analytics(analytics)

        return analytics

    def get_latest_analytics_for_posts(
        self,
        post_ids: List[str],
    ) -> Dict[str, PostAnalytics]:
        """
        Get the most recent analytics for multiple posts.

        Args:
            post_ids: List of post identifiers

        Returns:
            Dict mapping post_id to PostAnalytics
        """
        result = {}
        for post_id in post_ids:
            analytics = self.get_analytics_by_post_id(post_id)
            if analytics:
                result[post_id] = analytics
        return result
