"""
Feedback loop for learning from engagement metrics.

Collects post statistics, analyzes top-performing content,
and updates style profiles for improved content generation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy import select, func, desc

from llm.base import BaseLLMAdapter
from memory.database import Database
from memory.models import Post, StyleProfile


class FeedbackLoop:
    """
    Learns from engagement metrics and updates style profiles.

    Collects metrics from published posts, identifies top performers,
    and uses LLM to extract style patterns for future generation.

    Example:
        feedback = FeedbackLoop(db, llm_adapter)
        await feedback.collect_metrics()
        await feedback.update_style_profile()
    """

    # Default style analyzer prompt
    STYLE_ANALYZER_PROMPT = """Analyze these top-performing Telegram posts and extract the writing style fingerprint.

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

STYLE INSTRUCTIONS:"""

    def __init__(
        self,
        db: Database,
        llm_adapter: BaseLLMAdapter,
        min_reactions_to_learn: int = 5,
        style_update_interval_days: int = 7,
        top_posts_count: int = 5,
        prompts_dir: Optional[Path] = None,
    ):
        """
        Initialize feedback loop.

        Args:
            db: Database instance
            llm_adapter: LLM adapter for style analysis
            min_reactions_to_learn: Minimum reactions before considering a post
            style_update_interval_days: Days between style profile updates
            top_posts_count: Number of top posts to analyze
            prompts_dir: Directory containing custom prompts
        """
        self.db = db
        self.llm = llm_adapter
        self.min_reactions_to_learn = min_reactions_to_learn
        self.style_update_interval_days = style_update_interval_days
        self.top_posts_count = top_posts_count
        self.prompts_dir = prompts_dir or Path("llm/prompts")

        # Load custom prompt if available
        self._analyzer_prompt = self._load_prompt("style_analyzer.txt")

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt from file."""
        prompt_path = self.prompts_dir / filename
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return self.STYLE_ANALYZER_PROMPT

    async def collect_metrics(self) -> dict:
        """
        Collect engagement metrics for recent posts.

        Updates Post records with current views, reactions, and
        calculates engagement scores.

        Returns:
            dict: Summary of collected metrics
        """
        logger.info("Starting metrics collection")

        async with self.db.session() as session:
            # Get posts from last 7 days that need metrics update
            cutoff_date = datetime.now() - timedelta(days=7)

            stmt = (
                select(Post)
                .where(Post.status == "published")
                .where(Post.published_at >= cutoff_date)
                .where(Post.telegram_message_id.isnot(None))
            )

            result = await session.execute(stmt)
            posts = result.scalars().all()

            updated_count = 0
            total_engagement = 0.0

            for post in posts:
                # Calculate engagement score
                # Formula: (reactions / max(views, 1)) * 1000
                views = max(post.views, 1)
                reactions = post.reactions

                engagement_score = (reactions / views) * 1000
                post.engagement_score = engagement_score
                total_engagement += engagement_score
                updated_count += 1

            await session.commit()

        avg_engagement = total_engagement / updated_count if updated_count > 0 else 0

        summary = {
            "posts_updated": updated_count,
            "total_engagement": total_engagement,
            "avg_engagement": round(avg_engagement, 2),
        }

        logger.info(f"Metrics collection complete: {summary}")
        return summary

    async def get_top_posts(self, limit: Optional[int] = None) -> list[Post]:
        """
        Get top-performing posts by engagement score.

        Args:
            limit: Maximum number of posts (default: top_posts_count)

        Returns:
            list[Post]: Top posts ordered by engagement
        """
        limit = limit or self.top_posts_count

        async with self.db.session() as session:
            stmt = (
                select(Post)
                .where(Post.status == "published")
                .where(Post.engagement_score > 0)
                .where(Post.reactions >= self.min_reactions_to_learn)
                .order_by(desc(Post.engagement_score))
                .limit(limit)
            )

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_recent_posts(self, days: int = 14, limit: int = 10) -> list[Post]:
        """
        Get recent published posts.

        Args:
            days: Number of days to look back
            limit: Maximum number of posts

        Returns:
            list[Post]: Recent posts
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        async with self.db.session() as session:
            stmt = (
                select(Post)
                .where(Post.status == "published")
                .where(Post.published_at >= cutoff_date)
                .order_by(desc(Post.published_at))
                .limit(limit)
            )

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_style_profile(self) -> Optional[StyleProfile]:
        """
        Update the style profile based on top-performing posts.

        Analyzes the best posts using LLM and creates a new
        StyleProfile with extracted style instructions.

        Returns:
            Optional[StyleProfile]: New style profile, or None if failed
        """
        logger.info("Updating style profile")

        # Get top posts
        top_posts = await self.get_top_posts()

        if len(top_posts) < 3:
            logger.warning(
                f"Not enough posts for style analysis: {len(top_posts)} < 3"
            )
            return None

        # Format posts for analysis
        posts_text = self._format_posts_for_analysis(top_posts)

        # Build prompt
        prompt = self._analyzer_prompt.format(
            top_posts_with_scores=posts_text
        )

        try:
            # Get style analysis from LLM
            response = await self.llm.generate(prompt)
            style_instructions = response.text.strip()

            # Create new style profile
            async with self.db.session() as session:
                # Deactivate old profiles
                old_profiles = await session.execute(
                    select(StyleProfile)
                )
                for profile in old_profiles.scalars().all():
                    # We don't delete, just mark as inactive
                    pass

                # Create new profile
                new_profile = StyleProfile(
                    common_phrases=json.dumps(self._extract_phrases(top_posts)),
                    emoji_patterns=json.dumps(self._analyze_emoji_patterns(top_posts)),
                    hashtag_patterns=json.dumps(self._analyze_hashtag_patterns(top_posts)),
                    posts_analyzed=len(top_posts),
                )

                session.add(new_profile)
                await session.commit()
                await session.refresh(new_profile)

            logger.info(f"Created style profile {new_profile.id}")
            return new_profile

        except Exception as e:
            logger.error(f"Failed to update style profile: {e}")
            return None

    def _format_posts_for_analysis(self, posts: list[Post]) -> str:
        """Format posts for LLM analysis."""
        formatted = []

        for i, post in enumerate(posts, 1):
            formatted.append(
                f"---\n"
                f"POST #{i} (engagement score: {post.engagement_score:.1f})\n"
                f"Views: {post.views}, Reactions: {post.reactions}\n"
                f"{post.content}\n"
                f"---"
            )

        return "\n\n".join(formatted)

    def _extract_phrases(self, posts: list[Post]) -> list[str]:
        """Extract common phrases from posts."""
        # Simple extraction - could be enhanced with NLP
        phrases = []
        for post in posts:
            # Extract sentences
            sentences = post.content.replace("!", ".").replace("?", ".").split(".")
            phrases.extend([s.strip() for s in sentences if len(s.strip()) > 10])

        return phrases[:20]  # Return top 20

    def _analyze_emoji_patterns(self, posts: list[Post]) -> dict:
        """Analyze emoji usage patterns."""
        patterns = {
            "avg_count": 0,
            "positions": [],
            "common_emojis": [],
        }

        total_emojis = 0
        emoji_counts = {}

        for post in posts:
            total_emojis += post.emoji_count

            # Simple emoji detection (could be enhanced)
            import re
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"  # emoticons
                "\U0001F300-\U0001F5FF"  # symbols & pictographs
                "\U0001F680-\U0001F6FF"  # transport & map
                "\U0001F1E0-\U0001F1FF"  # flags
                "\U00002702-\U000027B0"
                "\U000024C2-\U0001F251"
                "]+",
                flags=re.UNICODE,
            )

            emojis = emoji_pattern.findall(post.content)
            for emoji in emojis:
                emoji_counts[emoji] = emoji_counts.get(emoji, 0) + 1

        if posts:
            patterns["avg_count"] = total_emojis / len(posts)

        # Sort by frequency
        sorted_emojis = sorted(emoji_counts.items(), key=lambda x: x[1], reverse=True)
        patterns["common_emojis"] = [e[0] for e in sorted_emojis[:10]]

        return patterns

    def _analyze_hashtag_patterns(self, posts: list[Post]) -> dict:
        """Analyze hashtag usage patterns."""
        patterns = {
            "avg_count": 0,
            "common_hashtags": [],
        }

        total_hashtags = 0
        hashtag_counts = {}

        for post in posts:
            total_hashtags += post.hashtag_count

            # Extract hashtags
            import re
            hashtags = re.findall(r"#\w+", post.content)
            for tag in hashtags:
                tag_lower = tag.lower()
                hashtag_counts[tag_lower] = hashtag_counts.get(tag_lower, 0) + 1

        if posts:
            patterns["avg_count"] = total_hashtags / len(posts)

        # Sort by frequency
        sorted_tags = sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)
        patterns["common_hashtags"] = [t[0] for t in sorted_tags[:10]]

        return patterns

    async def get_active_style_profile(self) -> Optional[StyleProfile]:
        """
        Get the most recent active style profile.

        Returns:
            Optional[StyleProfile]: Active style profile, or None
        """
        async with self.db.session() as session:
            stmt = (
                select(StyleProfile)
                .order_by(desc(StyleProfile.created_at))
                .limit(1)
            )

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_style_instructions(self) -> str:
        """
        Get style instructions for content generation.

        Returns the style fingerprint from the active profile,
        or a default instruction if no profile exists.

        Returns:
            str: Style instructions
        """
        profile = await self.get_active_style_profile()

        if profile and profile.common_phrases:
            phrases = json.loads(profile.common_phrases) if isinstance(profile.common_phrases, str) else profile.common_phrases

            if phrases:
                return (
                    "Style guide based on top-performing posts:\n"
                    f"- Average {profile.avg_sentence_length:.0f} words per sentence\n"
                    f"- Use emojis naturally (avg {profile.emoji_patterns.get('avg_count', 2) if isinstance(profile.emoji_patterns, dict) else 2} per post)\n"
                    f"- Maintain {profile.formality_score:.0%} formality level\n"
                    f"- Keep {profile.enthusiasm_score:.0%} enthusiasm level\n"
                )

        return (
            "Style guide: Expert but accessible. Conversational. "
            "No hype or buzzwords. Practical insights."
        )

    async def get_posting_stats(self, days: int = 7) -> dict:
        """
        Get posting statistics for a period.

        Args:
            days: Number of days to analyze

        Returns:
            dict: Posting statistics
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        async with self.db.session() as session:
            # Total posts
            total_stmt = (
                select(func.count(Post.id))
                .where(Post.published_at >= cutoff_date)
            )
            total_result = await session.execute(total_stmt)
            total_posts = total_result.scalar() or 0

            # Average engagement
            avg_stmt = (
                select(func.avg(Post.engagement_score))
                .where(Post.published_at >= cutoff_date)
                .where(Post.engagement_score > 0)
            )
            avg_result = await session.execute(avg_stmt)
            avg_engagement = avg_result.scalar() or 0

            # Top post
            top_stmt = (
                select(Post)
                .where(Post.published_at >= cutoff_date)
                .where(Post.engagement_score > 0)
                .order_by(desc(Post.engagement_score))
                .limit(1)
            )
            top_result = await session.execute(top_stmt)
            top_post = top_result.scalar_one_or_none()

            return {
                "period_days": days,
                "total_posts": total_posts,
                "avg_engagement": round(float(avg_engagement), 2),
                "top_post": {
                    "id": top_post.id,
                    "engagement": top_post.engagement_score,
                    "topic": top_post.topic,
                } if top_post else None,
            }

    async def should_update_style(self) -> bool:
        """
        Check if style profile should be updated.

        Returns True if:
        - No style profile exists, or
        - Last update was more than style_update_interval_days ago

        Returns:
            bool: Whether update is needed
        """
        profile = await self.get_active_style_profile()

        if not profile:
            return True

        age = datetime.now() - profile.last_updated
        return age.days >= self.style_update_interval_days
