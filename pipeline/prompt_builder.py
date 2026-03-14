"""
Prompt builder for dynamic prompt assembly.

Injects channel settings, style examples, and context into prompts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.logger import get_logger
from memory.post_store import PostStore

logger = get_logger(__name__)


class PromptBuilder:
    """
    Builds dynamic prompts for LLM generation.

    Assembles system prompts, context, and generation instructions
    for the new structured post format.
    """

    def __init__(
        self,
        channel_topic: str,
        channel_style: str,
        language: str = "ru",
        post_length_min: int = 200,
        post_length_max: int = 900,
        emojis_per_post: int = 3,
        hashtags_count: int = 2,
        prompts_dir: str | Path = "llm/prompts",
        post_store: Optional[PostStore] = None,
    ) -> None:
        """
        Initialize prompt builder.

        Args:
            channel_topic: Channel topic/niche
            channel_style: Writing style instructions
            language: Content language
            post_length_min: Minimum post length
            post_length_max: Maximum post length
            emojis_per_post: Target emoji count
            hashtags_count: Target hashtag count
            prompts_dir: Directory containing prompt templates
            post_store: Post store for fetching style examples
        """
        self.channel_topic = channel_topic
        self.channel_style = channel_style
        self.language = language
        self.post_length_min = post_length_min
        self.post_length_max = post_length_max
        self.emojis_per_post = emojis_per_post
        self.hashtags_count = hashtags_count
        self.prompts_dir = Path(prompts_dir)
        self.post_store = post_store

        # Load prompt templates
        self._templates = self._load_templates()

    def _load_templates(self) -> dict[str, str]:
        """Load all prompt templates from files."""
        templates = {}

        template_files = {
            "system_prompt": "system_prompt.txt",
            "post_generator": "post_generator.txt",
            "topic_selector": "topic_selector.txt",
            "quality_checker": "quality_checker.txt",
            "source_verifier": "source_verifier.txt",
            "editor_review": "editor_review.txt",
            "media_generator": "media_generator.txt",
        }

        for name, filename in template_files.items():
            filepath = self.prompts_dir / filename
            if filepath.exists():
                templates[name] = filepath.read_text(encoding="utf-8")
                logger.debug(f"Loaded template: {name}")
            else:
                logger.warning(f"Template not found: {filepath}")

        return templates

    async def get_recent_posts_context(self, limit: int = 5) -> str:
        """
        Get recent posts for style consistency context.

        Args:
            limit: Number of recent posts to include

        Returns:
            str: Formatted recent posts context
        """
        if not self.post_store:
            return "No recent posts available."

        posts = await self.post_store.get_recent(limit=limit, status="published")

        if not posts:
            return "No recent posts available."

        context_parts = ["Here are recent posts for style reference:"]

        for i, post in enumerate(posts, 1):
            # Truncate for context
            content = post.content[:400] + "..." if len(post.content) > 400 else post.content
            context_parts.append(f"\n--- Post {i} ---\n{content}")

        return "\n".join(context_parts)

    async def get_forbidden_topics_context(self, topics: list[str]) -> str:
        """
        Format forbidden topics for prompt.

        Args:
            topics: List of topics to avoid

        Returns:
            str: Formatted forbidden topics
        """
        if not topics:
            return "No restrictions."

        return "Topics recently covered (avoid repeating):\n" + "\n".join(
            f"- {topic[:100]}" for topic in topics[:10]
        )

    def build_system_prompt(
        self,
        style_examples: Optional[str] = None,
        forbidden_topics: Optional[list[str]] = None,
    ) -> str:
        """
        Build the system prompt with all context.

        Args:
            style_examples: Optional style examples
            forbidden_topics: Topics to avoid

        Returns:
            str: Complete system prompt
        """
        template = self._templates.get(
            "system_prompt",
            "You are a technology journalist writing in {language}.\n\n"
            "TOPIC: {channel_topic}\n"
            "STYLE: {channel_style}",
        )

        # Format forbidden topics
        forbidden_str = "None specified"
        if forbidden_topics:
            forbidden_str = "\n".join(f"- {t}" for t in forbidden_topics[:10])

        # Format style examples
        style_str = style_examples or "No specific examples provided."

        return template.format(
            channel_topic=self.channel_topic,
            channel_style=self.channel_style,
            language=self.language,
            emojis_per_post=self.emojis_per_post,
            hashtags_count=self.hashtags_count,
            post_length_min=self.post_length_min,
            post_length_max=self.post_length_max,
            style_examples=style_str,
            forbidden_topics=forbidden_str,
        )

    def build_post_prompt(
        self,
        topic: str,
        source_context: Optional[str] = None,
    ) -> str:
        """
        Build the post generation prompt.

        Args:
            topic: Topic for the post
            source_context: Optional source material/context

        Returns:
            str: Complete post generation prompt
        """
        template = self._templates.get(
            "post_generator",
            "Write a Telegram post about: {topic}\n\n"
            "Context: {source_context}\n\n"
            "Length: {post_length_min}-{post_length_max} characters\n"
            "Language: {language}",
        )

        return template.format(
            topic=topic,
            channel_topic=self.channel_topic,
            source_context=source_context or "No additional context provided. Use your knowledge.",
            post_length_min=self.post_length_min,
            post_length_max=self.post_length_max,
            emojis_per_post=self.emojis_per_post,
            hashtags_count=self.hashtags_count,
            language=self.language,
        )

    def build_quality_check_prompt(
        self,
        post_content: str,
        forbidden_words: Optional[list[str]] = None,
    ) -> str:
        """
        Build the quality check prompt.

        Args:
            post_content: Post content to check
            forbidden_words: Words that should not appear

        Returns:
            str: Complete quality check prompt
        """
        template = self._templates.get(
            "quality_checker",
            "Review this post:\n\n{post_content}\n\n"
            "Check length ({post_length_min}-{post_length_max}), "
            "emojis, hashtags, and quality.",
        )

        forbidden_str = ", ".join(forbidden_words) if forbidden_words else "None"

        return template.format(
            post_content=post_content,
            post_length_min=self.post_length_min,
            post_length_max=self.post_length_max,
            emojis_per_post=self.emojis_per_post,
            hashtags_count=self.hashtags_count,
            language=self.language,
            forbidden_words=forbidden_str,
        )

    def build_source_verification_prompt(
        self,
        topic: str,
        sources: list[dict],
    ) -> str:
        """
        Build the source verification prompt.

        Args:
            topic: Topic being covered
            sources: List of source dictionaries

        Returns:
            str: Complete source verification prompt
        """
        template = self._templates.get(
            "source_verifier",
            "Verify these sources for a news post about: {topic}\n\n"
            "Sources:\n{sources_text}",
        )

        sources_text = "\n".join([
            f"- {s.get('title', 'Unknown')}\n  URL: {s.get('url', '')}\n  Source: {s.get('source', '')}"
            for s in sources[:5]
        ])

        return template.format(
            topic=topic,
            sources_text=sources_text,
        )

    def build_editor_review_prompt(self, post_content: str) -> str:
        """
        Build the editor review prompt.

        Args:
            post_content: Post content to review

        Returns:
            str: Complete editor review prompt
        """
        template = self._templates.get(
            "editor_review",
            "Review and improve this post:\n\n{post_content}",
        )

        return template.format(post_content=post_content)

    def build_media_prompt(self, topic: str, post_content: str) -> str:
        """
        Build the media generation prompt.

        Args:
            topic: Post topic
            post_content: Post content for context

        Returns:
            str: Complete media generation prompt
        """
        template = self._templates.get(
            "media_generator",
            "Generate an image prompt for a post about: {topic}",
        )

        return template.format(
            topic=topic,
            post_content=post_content[:500],
        )

    async def build_full_prompt(
        self,
        topic: str,
        source_context: Optional[str] = None,
        include_recent_posts: bool = True,
        forbidden_topics: Optional[list[str]] = None,
    ) -> tuple[str, str]:
        """
        Build complete prompt with system and user components.

        Args:
            topic: Topic for the post
            source_context: Optional source material
            include_recent_posts: Include recent posts for style
            forbidden_topics: Topics to avoid

        Returns:
            tuple[str, str]: (system_prompt, user_prompt)
        """
        # Get style examples from recent posts
        style_examples = None
        if include_recent_posts and self.post_store:
            style_examples = await self.get_recent_posts_context(limit=5)

        # Build system prompt
        system_prompt = self.build_system_prompt(
            style_examples=style_examples,
            forbidden_topics=forbidden_topics,
        )

        # Build user prompt
        user_prompt = self.build_post_prompt(
            topic=topic,
            source_context=source_context,
        )

        return system_prompt, user_prompt

    def get_template(self, name: str) -> Optional[str]:
        """
        Get a specific template by name.

        Args:
            name: Template name

        Returns:
            str | None: Template content or None
        """
        return self._templates.get(name)

    def reload_templates(self) -> None:
        """Reload all templates from files."""
        self._templates = self._load_templates()
        logger.info("Templates reloaded")
