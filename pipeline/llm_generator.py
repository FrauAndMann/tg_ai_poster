"""
LLM generator for creating post content.

Uses the configured LLM adapter to generate engaging posts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.logger import get_logger
from llm.base import BaseLLMAdapter, LLMResponse
from pipeline.prompt_builder import PromptBuilder

logger = get_logger(__name__)


@dataclass
class GeneratedPost:
    """
    Container for generated post content.

    Attributes:
        content: Generated post text
        topic: Topic used for generation
        model: LLM model used
        tokens_used: Total tokens consumed
        generation_time: Time taken to generate
        attempts: Number of generation attempts
        raw_response: Original LLM response
    """

    content: str
    topic: str
    model: str
    tokens_used: int
    generation_time: float
    attempts: int = 1
    raw_response: Optional[LLMResponse] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "topic": self.topic,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "generation_time": self.generation_time,
            "attempts": self.attempts,
        }


class LLMGenerator:
    """
    Generates post content using LLM.

    Handles prompt construction, generation, and basic validation.
    """

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        prompt_builder: PromptBuilder,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize LLM generator.

        Args:
            llm_adapter: Configured LLM adapter
            prompt_builder: Prompt builder instance
            max_retries: Maximum regeneration attempts
        """
        self.llm = llm_adapter
        self.prompt_builder = prompt_builder
        self.max_retries = max_retries

    async def generate(
        self,
        topic: str,
        source_context: Optional[str] = None,
        forbidden_topics: Optional[list[str]] = None,
        include_recent_posts: bool = True,
        extra_instructions: Optional[str] = None,
        temperature: Optional[float] = None,
        post_type: str = "breaking",
    ) -> GeneratedPost:
        """
        Generate a post for the given topic.

        Args:
            topic: Topic for the post
            source_context: Optional source material
            forbidden_topics: Topics to avoid
            include_recent_posts: Include recent posts for style
            extra_instructions: Additional instructions for generation
            temperature: Override temperature (0.15 factual, 0.4 analysis)
            post_type: Type of post (breaking, deep_dive, tool_roundup, analysis)

        Returns:
            GeneratedPost: Generated content with metadata
        """
        import time

        start_time = time.time()

        # Select temperature based on post_type if not provided
        if temperature is None:
            if post_type in ("breaking", "tool_roundup"):
                temperature = 0.15  # Factual news
            elif post_type in ("deep_dive", "analysis"):
                temperature = 0.4   # More creative/analytical
            else:
                temperature = 0.2   # Default

        # Build prompts
        system_prompt, user_prompt = await self.prompt_builder.build_full_prompt(
            topic=topic,
            source_context=source_context,
            include_recent_posts=include_recent_posts,
            forbidden_topics=forbidden_topics,
        )

        # Add extra instructions if provided
        if extra_instructions:
            user_prompt = f"{user_prompt}\n\nAdditional instructions: {extra_instructions}"

        logger.info(f"Generating {post_type} post for topic: {topic[:50]}... (temp={temperature})")

        try:
            response = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
            )

            generation_time = time.time() - start_time

            post = GeneratedPost(
                content=response.content.strip(),
                topic=topic,
                model=response.model,
                tokens_used=response.total_tokens,
                generation_time=generation_time,
                raw_response=response,
            )

            logger.info(
                f"Post generated: {len(post.content)} chars, "
                f"{post.tokens_used} tokens, {generation_time:.2f}s"
            )

            return post

        except Exception as e:
            logger.error(f"Post generation failed: {e}")
            raise

    async def generate_with_retry(
        self,
        topic: str,
        source_context: Optional[str] = None,
        forbidden_topics: Optional[list[str]] = None,
        validation_func: Optional[callable] = None,
        temperature: Optional[float] = None,
        post_type: str = "breaking",
    ) -> GeneratedPost:
        """
        Generate with automatic retry on validation failure.

        Args:
            topic: Topic for the post
            source_context: Optional source material
            forbidden_topics: Topics to avoid
            validation_func: Optional validation function
            temperature: Override temperature (0.15 factual, 0.4 analysis)
            post_type: Type of post (breaking, deep_dive, tool_roundup, analysis)

        Returns:
            GeneratedPost: Validated generated content
        """
        import asyncio

        last_post = None
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # Add variation instruction for retries
                extra_instructions = None
                if attempt > 1:
                    extra_instructions = (
                        f"Previous attempt was rejected. "
                        f"Create a DIFFERENT version with a unique angle. "
                        f"Attempt {attempt}/{self.max_retries}"
                    )

                post = await self.generate(
                    topic=topic,
                    source_context=source_context,
                    forbidden_topics=forbidden_topics,
                    extra_instructions=extra_instructions,
                    temperature=temperature,
                    post_type=post_type,
                )

                post.attempts = attempt

                # Validate if function provided
                if validation_func:
                    is_valid, error = await validation_func(post.content)
                    if not is_valid:
                        last_error = error
                        logger.warning(
                            f"Validation failed (attempt {attempt}): {error}"
                        )
                        last_post = post
                        await asyncio.sleep(1)  # Brief pause before retry
                        continue

                return post

            except Exception as e:
                last_error = str(e)
                logger.error(f"Generation attempt {attempt} failed: {e}")
                await asyncio.sleep(2**attempt)  # Exponential backoff

        # Return last attempt even if validation failed
        if last_post:
            logger.warning(f"Returning last attempt after {self.max_retries} tries")
            return last_post

        raise Exception(f"All generation attempts failed: {last_error}")

    async def regenerate(
        self,
        original_post: GeneratedPost,
        feedback: Optional[str] = None,
    ) -> GeneratedPost:
        """
        Regenerate a post with feedback.

        Args:
            original_post: Original post to regenerate
            feedback: Feedback for improvement

        Returns:
            GeneratedPost: Regenerated content
        """
        extra_instructions = "Create a NEW version of this post."

        if feedback:
            extra_instructions += f" Address these issues: {feedback}"

        return await self.generate(
            topic=original_post.topic,
            extra_instructions=extra_instructions,
        )

    async def generate_variations(
        self,
        topic: str,
        count: int = 3,
        source_context: Optional[str] = None,
    ) -> list[GeneratedPost]:
        """
        Generate multiple variations of a post.

        Args:
            topic: Topic for the posts
            count: Number of variations
            source_context: Optional source material

        Returns:
            list[GeneratedPost]: List of variations
        """
        import asyncio

        variations = []

        for i in range(count):
            extra_instructions = (
                f"Variation {i + 1} of {count}. "
                "Create a unique angle different from typical approaches."
            )

            variation = await self.generate(
                topic=topic,
                source_context=source_context,
                extra_instructions=extra_instructions,
            )
            variations.append(variation)

            # Brief pause between generations
            if i < count - 1:
                await asyncio.sleep(0.5)

        logger.info(f"Generated {len(variations)} variations for topic")
        return variations
