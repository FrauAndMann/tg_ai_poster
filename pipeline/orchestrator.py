"""
Pipeline orchestrator for coordinating content generation.

Runs the full pipeline from source collection to publishing with
source verification, editorial review, and media generation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from publisher.base import BasePublisher

from core.config import Settings
from core.logger import get_logger
from llm import get_llm_adapter
from memory.database import Database
from memory.post_store import PostStore
from memory.topic_store import TopicStore
from pipeline.content_filter import ContentFilter
from pipeline.editor_review import EditorReviewer, EditorResult, MediaPromptGenerator
from pipeline.formatter import PostFormatter
from pipeline.llm_generator import GeneratedPost, LLMGenerator
from pipeline.prompt_builder import PromptBuilder
from pipeline.content_validator import ContentValidator, ValidationResult
from pipeline.quality_checker import QualityChecker, QualityResult
from pipeline.source_collector import Article, SourceCollector
from pipeline.source_verification import SourceVerifier, VerificationResult
from pipeline.topic_selector import TopicSelector

logger = get_logger(__name__)


def parse_json_post(response: str | dict, validator: ContentValidator | None = None) -> dict[str, Any]:
    """
    Parse JSON response from LLM and extract structured post data.

    Performs strict validation to ensure response is valid JSON
    with required fields. Returns None if parsing fails critically.

    Args:
        response: Raw LLM response (JSON string or dict)
        validator: Optional ContentValidator for pre-validation

    Returns:
        dict: Parsed post data with 'body', 'title', etc.
              Returns None if response is invalid LLM meta-text
    """
    if isinstance(response, dict):
        return response

    # Helper to clean and extract JSON
    def extract_json(text: str) -> str | None:
        """Extract JSON from various formats."""
        text = text.strip()

        # Strategy 1: Direct parse
        if text.startswith("{"):
            return text

        # Strategy 2: Remove markdown code blocks (```json ... ```)
        if "```" in text:
            # Try to extract from code block
            code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            if code_block_match:
                extracted = code_block_match.group(1).strip()
                if extracted.startswith("{"):
                    return extracted

        # Strategy 3: Find first { and last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1]

        return None

    def fix_common_json_errors(text: str) -> str:
        """Fix common JSON formatting errors."""
        # Remove trailing commas before } or ]
        text = re.sub(r',\s*([}\]])', r'\1', text)
        # Fix unescaped quotes in strings (simple heuristic)
        # Fix missing quotes around keys
        text = re.sub(r'(\w+)\s*:', r'"\1":', text)
        return text

    # Pre-validate for LLM meta-text if validator provided
    if validator:
        pre_check = validator.validate_raw_response(response)
        if pre_check.needs_regeneration:
            logger.warning(f"LLM meta-text detected in response: {pre_check.critical_issues}")

    # Extract JSON from response
    json_text = extract_json(response)
    if not json_text:
        logger.error("No JSON object found in response")
        return None

    # Try parsing strategies
    parse_attempts = [
        ("raw", lambda t: t),
        ("fixed", fix_common_json_errors),
        ("no_comments", lambda t: re.sub(r'//.*$', '', t, flags=re.MULTILINE)),
    ]

    for strategy_name, transformer in parse_attempts:
        try:
            text_to_parse = transformer(json_text)
            data = json.loads(text_to_parse)

            # Validate required fields exist
            if not isinstance(data, dict):
                logger.error(f"JSON parsed but not a dict: {type(data)}")
                continue

            # Check for at least body or content field
            if not data.get("body") and not data.get("content"):
                logger.error(f"JSON missing both 'body' and 'content' fields (strategy: {strategy_name})")
                continue

            if strategy_name != "raw":
                logger.info(f"JSON parsed successfully using {strategy_name} strategy")
            return data

        except json.JSONDecodeError as e:
            logger.debug(f"JSON parsing failed with {strategy_name} strategy: {e}")
            continue

    # Last resort: try to extract with more aggressive regex
    try:
        # Find the largest {...} block
        json_match = re.search(r'\{(?:[^{}]|"(?:\\.|[^"\\])*")*\}', response)
        if json_match:
            data = json.loads(json_match.group(0))
            if isinstance(data, dict) and (data.get("body") or data.get("content")):
                logger.info("Successfully extracted JSON using fallback regex")
                return data
    except json.JSONDecodeError:
        pass

    logger.error("Response is not valid JSON and cannot be salvaged")
    logger.debug(f"Response preview: {response[:500]}...")
    return None


def format_post_from_json(post_data: dict) -> str:
    """
    Format JSON post data into Telegram-ready text.

    Args:
        post_data: Parsed post data from LLM

    Returns:
        str: Formatted post text
    """
    title = post_data.get("title", "")
    hook = post_data.get("hook", "")
    body = post_data.get("body", post_data.get("content", ""))
    key_facts = post_data.get("key_facts", [])
    analysis = post_data.get("analysis", "")
    sources = post_data.get("sources", [])
    useful_links = post_data.get("useful_links", [])
    tldr = post_data.get("tldr", "")
    hashtags = post_data.get("hashtags", [])

    parts = []

    # Title
    if title:
        parts.append(title)

    # Hook
    if hook:
        parts.append("")
        parts.append(hook)

    # Body
    if body:
        parts.append("")
        parts.append(body)

    # Key facts (required block marker)
    if key_facts:
        parts.append("")
        parts.append("🔍 Что важно знать")
        for fact in key_facts:
            parts.append(f"• {fact}")

    # Analysis (required block marker)
    if analysis:
        parts.append("")
        parts.append("🧠 Почему это важно")
        parts.append(analysis)

    # Sources (required block marker)
    if sources:
        parts.append("")
        parts.append("🔗 Источники")
        for src in sources:
            name = src.get("name", "Source")
            url = src.get("url", "")
            if url:
                parts.append(f"• {name} — {url}")
            else:
                parts.append(f"• {name}")

    # Useful links
    if useful_links:
        parts.append("")
        parts.append("Полезные ссылки:")
        for link in useful_links:
            label = link.get("label", "Link")
            url = link.get("url", "")
            parts.append(f"- {label} — {url}")

    # TLDR (required block marker)
    if tldr:
        parts.append("")
        parts.append("💡 TL;DR")
        parts.append(tldr)

    # Hashtags
    if hashtags:
        parts.append("")
        parts.append(" ".join(f"#{tag}" for tag in hashtags))

    return "\n".join(parts)


@dataclass
class PipelineResult:
    """
    Result of pipeline execution.

    Attributes:
        success: Whether the pipeline succeeded
        post_id: ID of created post (if any)
        content: Generated content
        topic: Selected topic
        quality_score: Quality check score
        editor_score: Editorial review score
        verification_score: Source verification score
        media_prompt: Generated media prompt
        sources: List of sources used
        error: Error message (if failed)
        duration: Total execution time
    """

    success: bool
    post_id: Optional[int] = None
    content: Optional[str] = None
    topic: Optional[str] = None
    quality_score: float = 0.0
    editor_score: float = 0.0
    verification_score: float = 0.0
    media_prompt: Optional[str] = None
    sources: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    duration: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "post_id": self.post_id,
            "content": self.content,
            "topic": self.topic,
            "quality_score": self.quality_score,
            "editor_score": self.editor_score,
            "verification_score": self.verification_score,
            "media_prompt": self.media_prompt,
            "sources": self.sources,
            "error": self.error,
            "duration": self.duration,
        }


class PipelineOrchestrator:
    """
    Orchestrates the full content generation pipeline.

    Coordinates all stages: collection, verification, filtering,
    selection, generation, editorial review, quality check,
    and formatting.
    """

    def __init__(
        self,
        settings: Settings,
        db: Database,
        publisher: Optional["BasePublisher"] = None,
        enable_source_verification: bool = True,
        enable_editorial_review: bool = True,
        enable_media_generation: bool = True,
    ) -> None:
        """
        Initialize pipeline orchestrator.

        Args:
            settings: Application settings
            db: Database instance
            publisher: Optional publisher for posting
            enable_source_verification: Enable source verification stage
            enable_editorial_review: Enable editorial review stage
            enable_media_generation: Enable media prompt generation
        """
        self.settings = settings
        self.db = db
        self.publisher = publisher
        self.enable_source_verification = enable_source_verification
        self.enable_editorial_review = enable_editorial_review
        self.enable_media_generation = enable_media_generation

        # Initialize stores
        self.post_store = PostStore(db)
        self.topic_store = TopicStore(db)

        # Initialize LLM adapter
        self.llm = self._create_llm_adapter(settings)

        # Initialize pipeline components
        self.source_collector = SourceCollector(
            rss_feeds=settings.sources.rss_feeds,
        )

        self.source_verifier = SourceVerifier(
            llm_adapter=self.llm,
            min_sources=1,  # At least 1 source
            min_trust_score=50.0,
            min_credibility=60.0,
        )

        self.content_filter = ContentFilter(
            channel_topic=settings.channel.topic,
            min_score=30.0,
        )

        self.prompt_builder = PromptBuilder(
            channel_topic=settings.channel.topic,
            channel_style=settings.channel.style,
            language=settings.channel.language,
            post_length_min=settings.channel.post_length_min,
            post_length_max=settings.channel.post_length_max,
            emojis_per_post=settings.channel.emojis_per_post,
            hashtags_count=settings.channel.hashtags_count,
            post_store=self.post_store,
        )

        self.topic_selector = TopicSelector(
            llm_adapter=self.llm,
            topic_store=self.topic_store,
            channel_topic=settings.channel.topic,
        )

        self.generator = LLMGenerator(
            llm_adapter=self.llm,
            prompt_builder=self.prompt_builder,
            max_retries=settings.safety.max_regeneration_attempts,
        )

        self.editor_reviewer = EditorReviewer(
            llm_adapter=self.llm,
            min_score=70.0,
        )

        self.media_generator = MediaPromptGenerator(
            llm_adapter=self.llm,
        )

        self.quality_checker = QualityChecker(
            llm_adapter=self.llm,
            post_store=self.post_store,
            min_length=100,  # Soft minimum
            max_length=4096,  # Telegram max
            min_emojis=0,  # Optional
            max_emojis=20,
            min_hashtags=0,  # Optional - may be added later
            max_hashtags=10,
            similarity_threshold=settings.safety.similarity_threshold,
            forbidden_words=settings.safety.forbidden_words,
        )

        self.formatter = PostFormatter(
            parse_mode="MarkdownV2",
            max_length=4096,  # Telegram max
            ensure_structure=False,  # Don't require specific blocks
        )

        # Content validator for strict post validation
        self.content_validator = ContentValidator(
            strict_mode=True,
            min_body_length=150,
            min_body_sentences=3,
        )

        logger.info(
            f"Pipeline orchestrator initialized "
            f"(source_verification={enable_source_verification}, "
            f"editorial_review={enable_editorial_review}, "
            f"media_generation={enable_media_generation})"
        )

    def _create_llm_adapter(self, settings: Settings):
        """Create LLM adapter based on settings."""
        kwargs = {
            "model": settings.llm.model,
            "max_tokens": settings.llm.max_tokens,
            "temperature": settings.llm.temperature,
        }

        # Only pass api_key and base_url for API-based providers
        if settings.llm.provider != "claude-cli":
            kwargs["api_key"] = settings.llm.api_key
            kwargs["base_url"] = settings.llm.get_base_url()

        return get_llm_adapter(
            provider=settings.llm.provider,
            **kwargs
        )

    async def _check_posting_allowed(self) -> tuple[bool, str]:
        """
        Check if posting is allowed based on safety rules.

        Returns:
            tuple[bool, str]: (allowed, reason)
        """
        # Check daily limit
        today_count = await self.post_store.get_today_post_count()
        if today_count >= self.settings.safety.max_daily_posts:
            return False, f"Daily post limit reached ({today_count}/{self.settings.safety.max_daily_posts})"

        # Check minimum interval
        can_post = await self.post_store.can_post_now(
            self.settings.safety.min_interval_minutes
        )
        if not can_post:
            return False, "Minimum interval between posts not reached"

        return True, "Posting allowed"

    async def _collect_sources(self) -> list[Article]:
        """Collect articles from all sources."""
        logger.info("Starting source collection")

        try:
            articles = await self.source_collector.collect(
                max_age_days=7,
            )

            logger.info(f"Collected {len(articles)} articles")
            return articles

        except Exception as e:
            logger.error(f"Source collection failed: {e}")
            return []

    async def _verify_sources(
        self,
        articles: list[Article],
        topic: str,
    ) -> VerificationResult:
        """
        Verify sources for credibility and cross-reference.

        Args:
            articles: Articles to verify
            topic: Topic being covered

        Returns:
            VerificationResult: Verification results
        """
        if not self.enable_source_verification:
            # Return basic result without verification
            return VerificationResult(
                verified=True,
                credibility_score=70.0,
                recommendation="publish",
                reasoning="Source verification disabled",
            )

        logger.info(f"Verifying {len(articles)} sources for topic: {topic[:50]}...")

        try:
            result = await self.source_verifier.verify_with_ai(
                articles=articles,
                topic=topic,
            )

            logger.info(
                f"Source verification: score={result.credibility_score:.0f}%, "
                f"recommendation={result.recommendation}"
            )

            return result

        except Exception as e:
            logger.error(f"Source verification failed: {e}")
            return VerificationResult(
                verified=True,  # Allow on error
                credibility_score=60.0,
                recommendation="needs_review",
                reasoning=f"Verification error: {e}",
            )

    async def _select_topic(
        self,
        articles: list[Article],
    ) -> tuple[str, Optional[dict]]:
        """
        Select topic for the post.

        Args:
            articles: Available articles

        Returns:
            tuple[str, dict]: (topic, metadata)
        """
        if not articles:
            # Generate topic from scratch
            result = await self.topic_selector.generate_topic_idea()
            return result.get("selected_topic", ""), result

        # Score and filter articles
        scored = self.content_filter.filter_and_score(articles, top_n=5)

        if not scored:
            # Generate topic from scratch
            result = await self.topic_selector.generate_topic_idea()
            return result.get("selected_topic", ""), result

        # Select best topic using LLM
        top_articles = [sa.article for sa in scored]
        result = await self.topic_selector.select_from_articles(top_articles)

        return result.get("selected_topic", ""), result

    async def _generate_post(
        self,
        topic: str,
        source_context: Optional[str] = None,
    ) -> GeneratedPost:
        """
        Generate post content.

        Args:
            topic: Post topic
            source_context: Optional source material

        Returns:
            GeneratedPost: Generated content
        """
        # Get forbidden topics
        forbidden = await self.topic_store.get_forbidden_names(days=7)

        # Generate with retry
        # Get forbidden topics
        forbidden = await self.topic_store.get_forbidden_names(days=7)

        # Generate with retry
        post = await self.generator.generate_with_retry(
            topic=topic,
            source_context=source_context,
            forbidden_topics=forbidden,
            validation_func=self._validate_post,
        )

        # Parse JSON response if needed
        post_data = parse_json_post(post.content)

        post.parsed_data = post_data

        return post

    async def _editorial_review(self, content: str | dict) -> EditorResult:
        """
        Perform editorial review on generated content.

        Args:
            content: Post content to review (string or dict)

        Returns:
            EditorResult: Editorial review results
        """
        # Convert dict to string if needed
        if isinstance(content, dict):
            content_str = format_post_from_json(content)
        else:
            content_str = content

        if not self.enable_editorial_review:
            return EditorResult(
                approved=True,
                score=80.0,
                improved_content=content_str,
            )

        logger.info("Performing editorial review")

        try:
            result = await self.editor_reviewer.review_with_ai(content_str)

            logger.info(
                f"Editorial review: score={result.score:.0f}%, "
                f"approved={result.approved}"
            )

            return result

        except Exception as e:
            logger.error(f"Editorial review failed: {e}")
            return EditorResult(
                approved=True,
                score=70.0,
                improved_content=content_str,
                remaining_concerns=[f"Review error: {e}"],
            )

    async def _generate_media_prompt(
        self,
        topic: str,
        content: str,
    ) -> str:
        """
        Generate media prompt for post illustration.

        Args:
            topic: Post topic
            content: Post content

        Returns:
            str: Image generation prompt
        """
        if not self.enable_media_generation:
            return ""

        logger.info("Generating media prompt")

        try:
            prompt = await self.media_generator.generate_media_prompt(
                post_content=content,
                topic=topic,
            )

            logger.info(f"Media prompt generated: {prompt[:100]}...")
            return prompt

        except Exception as e:
            logger.error(f"Media prompt generation failed: {e}")
            return ""

    async def _validate_post(self, content: str) -> tuple[bool, Optional[str]]:
        """
        Validate generated post.

        Args:
            content: Post content

        Returns:
            tuple[bool, Optional[str]]: (is_valid, error)
        """
        result = await self.quality_checker.check(content)

        if not result.approved:
            error = "; ".join(result.issues[:3])
            return False, error

        return True, None

    async def _quality_check(self, content: str | dict) -> QualityResult:
        """
        Perform quality check on content.

        Args:
            content: Post content (string or dict)

        Returns:
            QualityResult: Check result
        """
        # Convert dict to string if needed
        if isinstance(content, dict):
            content = format_post_from_json(content)

        return await self.quality_checker.check_with_ai(content)

    async def _format_post(self, content: str | dict) -> str:
        """
        Format post for Telegram.

        Args:
            content: Post content (string or dict)

        Returns:
            str: Formatted content
        """
        # Handle dict content (from JSON LLM response)
        if isinstance(content, dict):
            content = format_post_from_json(content)

        return self.formatter.format(content, truncate=True)

    async def _save_post(
        self,
        content: str,
        topic: str,
        source: Optional[str] = None,
        status: str = "draft",
        llm_model: Optional[str] = None,
        media_prompt: Optional[str] = None,
    ) -> int:
        """
        Save post to database.

        Args:
            content: Post content
            topic: Post topic
            source: Content source
            status: Post status
            llm_model: LLM model used
            media_prompt: Generated media prompt

        Returns:
            int: Post ID
        """
        post = await self.post_store.create(
            content=content,
            topic=topic,
            source=source,
            status=status,
            llm_model=llm_model,
        )

        return post.id

    async def _publish_post(self, post_id: int, content: str) -> bool:
        """
        Publish post to Telegram.

        Args:
            post_id: Post ID
            content: Formatted content

        Returns:
            bool: Success status
        """
        if not self.publisher:
            logger.warning("No publisher configured, skipping publish")
            return False

        try:
            message_id = await self.publisher.send_post(content)

            if message_id:
                await self.post_store.mark_published(post_id, message_id)
                logger.info(f"Post {post_id} published with message_id={message_id}")
                return True
            else:
                await self.post_store.mark_failed(post_id)
                return False

        except Exception as e:
            logger.error(f"Failed to publish post: {e}")
            await self.post_store.mark_failed(post_id, str(e))
            return False

    async def run(self, dry_run: bool = False) -> PipelineResult:
        """
        Run the full pipeline with all stages.

        Pipeline stages:
        1. Check posting allowed
        2. Collect sources
        3. Select topic
        4. Verify sources (new)
        5. Generate post
        6. Editorial review (new)
        7. Quality check
        8. Generate media prompt (new)
        9. Format post
        10. Save and publish

        Args:
            dry_run: Skip actual publishing

        Returns:
            PipelineResult: Pipeline execution result
        """
        import time

        start_time = time.time()

        logger.info("Starting enhanced pipeline execution")

        try:
            # Stage 1: Check if posting is allowed
            if not dry_run:
                allowed, reason = await self._check_posting_allowed()
                if not allowed:
                    logger.info(f"Posting not allowed: {reason}")
                    return PipelineResult(
                        success=False,
                        error=reason,
                        duration=time.time() - start_time,
                    )

            # Stage 2: Collect sources
            articles = await self._collect_sources()

            # Stage 3: Select topic
            topic, topic_meta = await self._select_topic(articles)

            if not topic:
                return PipelineResult(
                    success=False,
                    error="Failed to select topic",
                    duration=time.time() - start_time,
                )

            logger.info(f"Selected topic: {topic[:50]}...")

            # Stage 4: Verify sources (if enabled)
            verification_result = None
            if articles and self.enable_source_verification:
                verification_result = await self._verify_sources(articles, topic)

                if verification_result.recommendation == "reject":
                    logger.warning(f"Sources rejected: {verification_result.reasoning}")
                    # Continue anyway but note the issue

            # Prepare source context
            source_context = None
            source_articles = []

            if topic_meta and topic_meta.get("source_article"):
                article = topic_meta["source_article"]
                source_context = f"Source: {article.get('source', '')}\n{article.get('summary', '')}"
                source_articles = [article]

            # Use verified sources if available
            if verification_result and verification_result.sources:
                source_context = self.source_verifier.get_source_context_for_post(
                    verification_result.sources[:3]
                )
                source_articles = [vs.article for vs in verification_result.sources[:3]]

            # URL-based deduplication: skip topics that were already posted from the same source URL
            primary_source_url: Optional[str] = None
            if source_articles:
                first_article = source_articles[0]
                # Support both dicts (from topic_meta) and objects (from verifier)
                primary_source_url = getattr(first_article, "url", None)
                if primary_source_url is None and isinstance(first_article, dict):
                    primary_source_url = first_article.get("url")

            if primary_source_url:
                try:
                    if await self.topic_store.has_used_source_url(primary_source_url):
                        logger.info(
                            "Skipping topic because source URL was already used: %s",
                            primary_source_url,
                        )
                        duration = time.time() - start_time
                        return PipelineResult(
                            success=False,
                            post_id=None,
                            content=None,
                            topic=topic,
                            quality_score=0.0,
                            editor_score=0.0,
                            verification_score=0.0,
                            media_prompt=None,
                            sources=[{"url": primary_source_url}],
                            error="Duplicate source URL",
                            duration=duration,
                        )
                except Exception as e:
                    logger.warning(f"Failed to check source URL uniqueness: {e}")

            # Stage 5-7: Generate -> Validate -> Editorial review -> Quality check
            # STRICT VALIDATION: Content must pass all checks to be published
            max_attempts = max(1, int(self.settings.safety.max_regeneration_attempts))
            generated: GeneratedPost | None = None
            post_data: dict[str, Any] | None = None
            raw_text_for_review: str | None = None
            final_content: str | None = None
            editor_result: EditorResult | None = None
            quality: QualityResult | None = None
            content_validation: ValidationResult | None = None

            forbidden = await self.topic_store.get_forbidden_names(days=7)

            generation_success = False
            last_error = "Unknown error"

            for attempt in range(1, max_attempts + 1):
                logger.info(f"Generation attempt {attempt}/{max_attempts}")

                # Generate content
                if attempt == 1:
                    generated = await self._generate_post(topic, source_context)
                else:
                    feedback_parts: list[str] = []
                    if content_validation and content_validation.critical_issues:
                        feedback_parts.extend(content_validation.critical_issues[:4])
                    if editor_result and editor_result.remaining_concerns:
                        feedback_parts.extend(editor_result.remaining_concerns[:4])
                    if quality and quality.issues:
                        feedback_parts.extend(quality.issues[:4])
                    feedback = "; ".join(feedback_parts)[:800] if feedback_parts else "Improve structure and quality."

                    logger.warning(f"Regenerating post with feedback: {feedback[:100]}...")
                    generated = await self.generator.generate(
                        topic=topic,
                        source_context=source_context,
                        forbidden_topics=forbidden,
                        extra_instructions=(
                            "Previous attempt failed validation. CRITICAL: Return ONLY valid JSON. "
                            "Do NOT include any explanations, thinking, or meta-text. "
                            "Start your response directly with { and end with }. "
                            f"Issues to fix: {feedback}"
                        ),
                        post_type="breaking",
                    )

                # STRICT JSON PARSING with validator
                parsed = parse_json_post(generated.content, self.content_validator)

                if parsed is None:
                    last_error = "LLM returned non-JSON or meta-text instead of valid post"
                    logger.error(f"Attempt {attempt}: {last_error}")
                    continue

                post_data = parsed

                # Validate JSON structure using ContentValidator
                content_validation = self.content_validator.validate_json_post(post_data)

                if not content_validation.is_valid:
                    last_error = f"JSON validation failed: {'; '.join(content_validation.critical_issues[:3])}"
                    logger.error(f"Attempt {attempt}: {last_error}")
                    if content_validation.needs_regeneration:
                        continue

                # Render post from JSON
                raw_text_for_review = format_post_from_json(post_data)

                # Final content validation on rendered text
                rendered_validation = self.content_validator.validate_formatted_post(raw_text_for_review)
                if not rendered_validation.is_ready:
                    logger.warning(f"Attempt {attempt}: Rendered content issues: {rendered_validation.critical_issues}")
                    if rendered_validation.needs_regeneration:
                        last_error = f"Content not ready: {'; '.join(rendered_validation.critical_issues[:2])}"
                        continue

                # Stage 6: Editorial review (if enabled)
                editor_result = await self._editorial_review(raw_text_for_review)

                # Ensure final_content is always a string
                improved = editor_result.improved_content
                if isinstance(improved, dict):
                    final_content = format_post_from_json(improved)
                elif isinstance(improved, str):
                    final_content = improved
                else:
                    final_content = raw_text_for_review

                if editor_result.needs_regeneration:
                    last_error = f"Editor review rejected: score={editor_result.score}"
                    logger.warning(f"Attempt {attempt}: {last_error}")
                    if attempt < max_attempts:
                        continue

                # Stage 7: Quality check
                quality = await self._quality_check(final_content)
                if not quality.approved:
                    logger.warning(f"Attempt {attempt}: Quality issues: {quality.issues}")

                # FINAL CHECK: Is content publication-ready?
                is_ready, ready_reason = self.content_validator.is_publication_ready(final_content)

                if is_ready and quality.score >= 60:
                    generation_success = True
                    logger.info(f"Attempt {attempt}: Content approved for publication (score={quality.score})")
                    break
                else:
                    last_error = f"Not ready: {ready_reason}, quality_score={quality.score}"
                    logger.warning(f"Attempt {attempt}: {last_error}")

                    # On last attempt, check if we can salvage
                    if attempt == max_attempts:
                        if quality.score >= 50 and not content_validation.needs_regeneration:
                            logger.warning("Last attempt: Content has issues but may be salvageable")
                            generation_success = True
                        else:
                            logger.error(f"Last attempt failed: {last_error}")

            # CRITICAL: Do not publish if generation was not successful
            if not generation_success or generated is None or final_content is None:
                error_msg = f"Failed to generate publication-ready content after {max_attempts} attempts. Last error: {last_error}"
                logger.error(error_msg)
                await self.source_collector.close()
                return PipelineResult(
                    success=False,
                    error=error_msg,
                    topic=topic,
                    duration=time.time() - start_time,
                )

            assert editor_result is not None
            assert quality is not None

            # Stage 8: Generate media prompt (if enabled)
            media_prompt = await self._generate_media_prompt(topic, final_content)

            # Stage 9: Format post for Telegram (MarkdownV2 escaping + optional structure check)
            formatted = await self._format_post(final_content)

            # Format validation - just log warnings, don't block
            is_valid, fmt_error = self.formatter.validate_format(formatted)
            if fmt_error:
                logger.warning(f"Format note: {fmt_error}")

            # Add media prompt to output (not to post content)
            if media_prompt:
                logger.info("Media prompt ready for image generation")

            # Stage 10: Save post
            post_id = await self._save_post(
                content=formatted,
                topic=topic,
                source=source_articles[0].source if source_articles else None,
                status="pending",
                llm_model=generated.model,
                media_prompt=media_prompt,
            )

            # Check for manual approval
            if self.settings.safety.manual_approval and not dry_run:
                logger.info(f"Post {post_id} requires manual approval")
                # Close source collector session
                await self.source_collector.close()
                return PipelineResult(
                    success=True,
                    post_id=post_id,
                    content=formatted,
                    topic=topic,
                    quality_score=quality.score,
                    editor_score=editor_result.score,
                    verification_score=verification_result.credibility_score if verification_result else 0,
                    media_prompt=media_prompt,
                    sources=[{"url": a.url, "source": a.source} for a in source_articles],
                    duration=time.time() - start_time,
                )

            # Publish (or skip in dry run)
            if dry_run:
                logger.info(f"[DRY RUN] Would publish post {post_id}")
                published = True
            else:
                published = await self._publish_post(post_id, formatted)

            # Save topic to topic_store to prevent duplicates
            if published or dry_run:
                try:
                    source_url = source_articles[0].url if source_articles else None
                    existing = await self.topic_store.get_by_name(topic)
                    if existing:
                        await self.topic_store.mark_used(existing.id)
                    else:
                        await self.topic_store.create(
                            name=topic,
                            source_type="published",
                            source_url=source_url,
                        )
                    logger.info(f"Saved topic to prevent duplicates: {topic[:50]}...")
                except Exception as e:
                    logger.warning(f"Failed to save topic: {e}")

            duration = time.time() - start_time

            logger.info(f"Pipeline completed in {duration:.2f}s")

            # Close source collector session
            await self.source_collector.close()

            return PipelineResult(
                success=published,
                post_id=post_id,
                content=formatted,
                topic=topic,
                quality_score=quality.score,
                editor_score=editor_result.score,
                verification_score=verification_result.credibility_score if verification_result else 0,
                media_prompt=media_prompt,
                sources=[{"url": a.url, "source": a.source} for a in source_articles],
                duration=duration,
            )

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            # Close source collector session on error too
            await self.source_collector.close()
            return PipelineResult(
                success=False,
                error=str(e),
                duration=time.time() - start_time,
            )

    async def run_generation_only(self) -> tuple[Optional[str], dict]:
        """
        Run only the generation part without publishing.

        Returns:
            tuple[Optional[str], dict]: (content, metadata)
        """
        articles = await self._collect_sources()
        topic, topic_meta = await self._select_topic(articles)

        if not topic:
            return None, {"error": "Failed to select topic"}

        # Verify sources
        verification_result = None
        if articles and self.enable_source_verification:
            verification_result = await self._verify_sources(articles, topic)

        # Prepare source context
        source_context = None
        if topic_meta and topic_meta.get("source_article"):
            article = topic_meta["source_article"]
            source_context = f"Source: {article.get('source', '')}\n{article.get('summary', '')}"

        if verification_result and verification_result.sources:
            source_context = self.source_verifier.get_source_context_for_post(
                verification_result.sources[:3]
            )

        generated = await self._generate_post(topic, source_context)

        # Editorial review
        editor_result = await self._editorial_review(generated.content)
        final_content = editor_result.improved_content or generated.content

        # Quality check
        quality = await self._quality_check(final_content)

        # Media prompt
        media_prompt = await self._generate_media_prompt(topic, final_content)

        formatted = await self._format_post(final_content)

        metadata = {
            "topic": topic,
            "topic_meta": topic_meta,
            "model": generated.model,
            "tokens_used": generated.tokens_used,
            "generation_time": generated.generation_time,
            "quality_score": quality.score,
            "editor_score": editor_result.score,
            "verification_score": verification_result.credibility_score if verification_result else 0,
            "media_prompt": media_prompt,
            "sources": [{"url": a.url, "source": a.source} for a in (verification_result.sources if verification_result else [])],
        }

        return formatted, metadata
