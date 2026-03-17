"""
Quality checker for validating generated posts.

Performs various checks on post content before publishing,
including semantic similarity via vector store.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger
from llm.base import BaseLLMAdapter
from memory.post_store import PostStore

if TYPE_CHECKING:
    from memory.vector_store import VectorStore

logger = get_logger(__name__)


@dataclass
class QualityResult:
    """
    Result of quality check.

    Attributes:
        approved: Whether the post passes quality check
        score: Quality score (0-100)
        issues: List of issues found
        suggestions: List of improvement suggestions
        needs_regeneration: Whether the post should be regenerated
    """

    approved: bool
    score: float
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    needs_regeneration: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "approved": self.approved,
            "score": self.score,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "needs_regeneration": self.needs_regeneration,
        }


class QualityChecker:
    """
    Validates generated posts against quality criteria.

    Performs length, content, formatting, and similarity checks.
    """

    # AI-typical phrases to flag
    AI_PHRASES = [
        "in today's world",
        "it's important to note",
        "it is worth mentioning",
        "let's dive into",
        "delve into",
        "in conclusion",
        "to summarize",
        "first and foremost",
        "at the end of the day",
        "in this day and age",
        "it goes without saying",
        "needless to say",
        "as we all know",
        "в современном мире",
        "стоит отметить",
        "в заключение",
        "для подведения итогов",
        "как известно",
        "не секрет что",
    ]

    # Generic opening phrases
    GENERIC_OPENINGS = [
        "have you ever wondered",
        "did you know that",
        "here's what you need to know",
        "in this post we will",
        "задумывались ли вы",
        "знали ли вы что",
        "в этом посте мы",
    ]

    def __init__(
        self,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        post_store: Optional[PostStore] = None,
        vector_store: Optional["VectorStore"] = None,
        min_length: int = 200,
        max_length: int = 900,
        min_emojis: int = 1,
        max_emojis: int = 10,
        min_hashtags: int = 1,
        max_hashtags: int = 5,
        similarity_threshold: float = 0.85,
        forbidden_words: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize quality checker.

        Args:
            llm_adapter: Optional LLM for AI-based quality check
            post_store: Post store for similarity checks
            vector_store: Vector store for semantic similarity
            min_length: Minimum post length
            max_length: Maximum post length
            min_emojis: Minimum emoji count
            max_emojis: Maximum emoji count
            min_hashtags: Minimum hashtag count
            max_hashtags: Maximum hashtag count
            similarity_threshold: Threshold for duplicate detection
            forbidden_words: Words that should not appear
        """
        self.llm = llm_adapter
        self.post_store = post_store
        self.vector_store = vector_store
        self.min_length = min_length
        self.max_length = max_length
        self.min_emojis = min_emojis
        self.max_emojis = max_emojis
        self.min_hashtags = min_hashtags
        self.max_hashtags = max_hashtags
        self.similarity_threshold = similarity_threshold
        self.forbidden_words = forbidden_words or []

    def _count_emojis(self, text: str) -> int:
        """Count emojis in text."""
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags
            "\U00002702-\U000027b0"
            "\U000024c2-\U0001f251"
            "]+",
            flags=re.UNICODE,
        )
        return len(emoji_pattern.findall(text))

    def _count_hashtags(self, text: str) -> int:
        """Count hashtags in text."""
        return len(re.findall(r"#\w+", text))

    def _check_length(self, content: str) -> tuple[bool, Optional[str]]:
        """Check content length (soft check - only warn for very short content)."""
        length = len(content)

        # Only fail for very short content (under 100 chars is definitely too short)
        if length < 100:
            return False, f"Too short: {length} chars (min: 100)"

        # Warn but don't fail for long content (Telegram handles up to 4096)
        if length > self.max_length:
            logger.warning(
                f"Post is long: {length} chars, but will be truncated if needed"
            )

        return True, None

    def _check_emojis(self, content: str) -> tuple[bool, Optional[str]]:
        """Check emoji count."""
        count = self._count_emojis(content)

        if count < self.min_emojis:
            return False, f"Too few emojis: {count} (min: {self.min_emojis})"
        if count > self.max_emojis:
            return False, f"Too many emojis: {count} (max: {self.max_emojis})"

        return True, None

    def _check_hashtags(self, content: str) -> tuple[bool, Optional[str]]:
        """Check hashtag count (soft check - hashtags are auto-added from JSON)."""
        count = self._count_hashtags(content)

        # Don't fail on missing hashtags - they may be added during formatting
        if count < self.min_hashtags:
            logger.info(
                f"Hashtags will be auto-added during formatting (current: {count})"
            )

        return True, None

    def _check_forbidden_words(self, content: str) -> tuple[bool, Optional[str]]:
        """Check for forbidden words."""
        content_lower = content.lower()

        for word in self.forbidden_words:
            if word.lower() in content_lower:
                return False, f"Contains forbidden word: {word}"

        return True, None

    def _check_ai_phrases(self, content: str) -> list[str]:
        """Check for AI-typical phrases."""
        content_lower = content.lower()
        found = []

        for phrase in self.AI_PHRASES:
            if phrase in content_lower:
                found.append(phrase)

        return found

    def _check_generic_opening(self, content: str) -> tuple[bool, Optional[str]]:
        """Check for generic opening."""
        first_sentence = (
            content.split(".")[0].lower() if "." in content else content.lower()
        )

        for opening in self.GENERIC_OPENINGS:
            if opening in first_sentence:
                return False, f"Generic opening detected: '{opening}'"

        return True, None

    def _check_telegram_markdown(self, content: str) -> tuple[bool, Optional[str]]:
        """Check Telegram markdown formatting (soft check)."""
        # Check for unbalanced bold/italic tags
        bold_count = content.count("*")
        italic_count = content.count("_")

        if bold_count % 2 != 0:
            return False, "Unbalanced bold tags (*)"
        if italic_count % 2 != 0:
            return False, "Unbalanced italic tags (_)"

        # Markdown headers will be handled by formatter - just warn
        if re.search(r"^#+\s", content, re.MULTILINE):
            logger.warning("Markdown headers found - will be converted by formatter")

        return True, None

    async def _check_similarity(self, content: str) -> tuple[bool, Optional[str]]:
        """
        Check similarity with recent posts using vector store or fallback.

        Uses ChromaDB for semantic similarity if available,
        otherwise falls back to word overlap.
        """
        # Try vector store first for semantic similarity
        if self.vector_store:
            try:
                is_duplicate, similar_post = await self.vector_store.check_similarity(
                    content,
                    threshold=self.similarity_threshold,
                    n_results=5,
                )

                if is_duplicate and similar_post:
                    return False, (
                        f"Semantic duplicate detected: {similar_post.similarity:.0%} "
                        f"similar to post #{similar_post.post_id}"
                    )

                # Log if close but not duplicate
                if similar_post and similar_post.similarity > 0.7:
                    logger.info(
                        f"Content similar ({similar_post.similarity:.0%}) to "
                        f"post #{similar_post.post_id}, but under threshold"
                    )

                return True, None

            except Exception as e:
                logger.warning(f"Vector store similarity check failed: {e}")
                # Fall through to fallback

        # Fallback: word overlap similarity
        if not self.post_store:
            return True, None

        try:
            recent_content = await self.post_store.get_content_for_dedup(limit=10)

            if not recent_content:
                return True, None

            content_words = set(content.lower().split())

            for i, recent in enumerate(recent_content):
                recent_words = set(recent.lower().split())

                if not content_words or not recent_words:
                    continue

                intersection = len(content_words & recent_words)
                union = len(content_words | recent_words)

                if union > 0:
                    similarity = intersection / union

                    if similarity > self.similarity_threshold:
                        return (
                            False,
                            f"Too similar to recent post #{i + 1} ({similarity:.0%})",
                        )

            return True, None

        except Exception as e:
            logger.warning(f"Similarity check failed: {e}")
            return True, None

    async def check(self, content: str | dict) -> QualityResult:
        """
        Perform quality check on content.

        Args:
            content: Post content to check (can be str or dict with 'body' key)

        Returns:
            QualityResult: Check results
        """
        # Handle both string and dict content
        if isinstance(content, dict):
            text_content = content.get("body", "") or content.get("content", "")
            if not text_content:
                text_content = str(content)
        else:
            text_content = content

        issues = []
        suggestions = []
        score = 100.0

        # Length check
        passed, issue = self._check_length(text_content)
        if not passed:
            issues.append(issue)
            score -= 20

        # Emoji check
        passed, issue = self._check_emojis(text_content)
        if not passed:
            issues.append(issue)
            score -= 10

        # Hashtag check
        passed, issue = self._check_hashtags(text_content)
        if not passed:
            issues.append(issue)
            score -= 10

        # Forbidden words check
        passed, issue = self._check_forbidden_words(text_content)
        if not passed:
            issues.append(issue)
            score -= 30

        # AI phrases check
        ai_phrases = self._check_ai_phrases(text_content)
        if ai_phrases:
            issues.append(f"AI-typical phrases found: {', '.join(ai_phrases[:3])}")
            suggestions.append("Replace AI-typical phrases with more natural language")
            score -= 15

        # Generic opening check
        passed, issue = self._check_generic_opening(text_content)
        if not passed:
            issues.append(issue)
            suggestions.append("Start with a stronger, more specific hook")
            score -= 10

        # Markdown check
        passed, issue = self._check_telegram_markdown(text_content)
        if not passed:
            issues.append(issue)
            score -= 15

        # Similarity check
        passed, issue = await self._check_similarity(text_content)
        if not passed:
            issues.append(issue)
            suggestions.append("Make the content more unique")
            score -= 25

        # Ensure score is within bounds
        score = max(0, min(100, score))

        # Determine if regeneration is needed
        needs_regeneration = score < 50 or len(issues) >= 3

        approved = score >= 60 and not needs_regeneration

        if not approved:
            logger.warning(f"Quality check failed: score={score}, issues={len(issues)}")
        else:
            logger.info(f"Quality check passed: score={score}")

        return QualityResult(
            approved=approved,
            score=score,
            issues=issues,
            suggestions=suggestions,
            needs_regeneration=needs_regeneration,
        )

    async def check_with_ai(self, content: str | dict) -> QualityResult:
        """
        Perform quality check using LLM for deeper analysis.

        Args:
            content: Post content to check (can be str or dict with 'body' key)

        Returns:
            QualityResult: Check results with AI feedback
        """
        # Handle both string and dict content
        if isinstance(content, dict):
            # Extract body text from JSON response
            text_content = content.get("body", "") or content.get("content", "")
            if not text_content:
                # Fallback: convert dict to string
                text_content = str(content)
        else:
            text_content = content

        # First do rule-based check
        base_result = await self.check(text_content)

        if not self.llm:
            return base_result

        try:
            prompt = f"""Review this Telegram post for quality:

{content}

Check for:
1. Strong opening hook
2. Natural, human-like writing (not AI-generated feel)
3. Proper structure and flow
4. Engaging content

Respond with JSON only:
{{
    "approved": true/false,
    "score": 0-100,
    "issues": ["list of issues"],
    "suggestions": ["improvement suggestions"],
    "needs_regeneration": true/false
}}"""

            response = await self.llm.generate(prompt)
            response_text = response.content.strip()

            # Parse JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]

            ai_result = json.loads(response_text.strip())

            # Combine results (use lower score)
            combined_score = min(base_result.score, ai_result.get("score", 100))
            combined_issues = base_result.issues + ai_result.get("issues", [])
            combined_suggestions = base_result.suggestions + ai_result.get(
                "suggestions", []
            )

            return QualityResult(
                approved=ai_result.get("approved", base_result.approved)
                and base_result.approved,
                score=combined_score,
                issues=combined_issues,
                suggestions=combined_suggestions,
                needs_regeneration=ai_result.get(
                    "needs_regeneration", base_result.needs_regeneration
                ),
            )

        except Exception as e:
            logger.error(f"AI quality check failed: {e}")
            return base_result

    def get_quality_metrics(self, content: str) -> dict:
        """
        Get quality metrics for content without pass/fail judgment.

        Args:
            content: Post content

        Returns:
            dict: Quality metrics
        """
        return {
            "length": len(content),
            "emoji_count": self._count_emojis(content),
            "hashtag_count": self._count_hashtags(content),
            "word_count": len(content.split()),
            "paragraph_count": len([p for p in content.split("\n\n") if p.strip()]),
            "ai_phrases_found": len(self._check_ai_phrases(content)),
        }
