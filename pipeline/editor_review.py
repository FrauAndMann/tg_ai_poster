"""
Editor review module for polishing generated posts.

Performs editorial review to improve style, readability, and quality
before publication.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.logger import get_logger
from llm.base import BaseLLMAdapter

logger = get_logger(__name__)


# AI-typical phrases that should be flagged/removed
AI_PHRASES = [
    # Russian AI cliches
    "в современном мире",
    "стоит отметить",
    "важно понимать",
    "не секрет что",
    "как известно",
    "в заключение",
    "для подведения итогов",
    "в данной статье",
    "в этом посте мы рассмотрим",
    "хотелось бы отметить",
    "интересно отметить",
    "безусловно",
    "несомненно",
    "естественно",
    "разумеется",
    "в настоящее время",
    "на сегодняшний день",
    "в наши дни",

    # English AI cliches
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
    "in this article we will",
    "it's worth noting",
    "play a crucial role",
    "it is essential to",
    "in order to",
    "when it comes to",
]

# Generic opening phrases
GENERIC_OPENINGS = [
    "have you ever wondered",
    "did you know that",
    "here's what you need to know",
    "in this post we will",
    "today we're going to",
    "задумывались ли вы",
    "знали ли вы что",
    "в этом посте мы",
    "сегодня мы поговорим",
    "давайте поговорим о",
]

# Weak transitions
WEAK_TRANSITIONS = [
    "кроме того",
    "более того",
    "также стоит",
    "необходимо упомянуть",
    "furthermore",
    "moreover",
    "additionally",
    "it's also worth",
]


@dataclass
class EditorResult:
    """
    Result of editorial review.

    Attributes:
        approved: Whether the post is approved for publication
        score: Editorial quality score (0-100)
        improved_content: The edited/improved version of the post
        changes_made: List of changes made
        issues_found: Issues that were identified
        remaining_concerns: Issues that couldn't be fixed
        needs_regeneration: Whether the post should be regenerated
    """
    approved: bool
    score: float
    improved_content: str
    changes_made: list[str] = field(default_factory=list)
    issues_found: list[str] = field(default_factory=list)
    remaining_concerns: list[str] = field(default_factory=list)
    needs_regeneration: bool = False

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "score": self.score,
            "changes_made": self.changes_made,
            "issues_found": self.issues_found,
            "remaining_concerns": self.remaining_concerns,
            "needs_regeneration": self.needs_regeneration,
        }


class EditorReviewer:
    """
    Reviews and improves generated posts before publication.

    Performs style improvements, removes AI-typical language,
    and ensures professional quality.
    """

    def __init__(
        self,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        prompts_dir: str | Path = "llm/prompts",
        min_score: float = 70.0,
    ) -> None:
        """
        Initialize editor reviewer.

        Args:
            llm_adapter: Optional LLM for AI-assisted editing
            prompts_dir: Directory containing prompt templates
            min_score: Minimum score for approval
        """
        self.llm = llm_adapter
        self.prompts_dir = Path(prompts_dir)
        self.min_score = min_score

        # Load prompt template
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Load editor review prompt template."""
        prompt_file = self.prompts_dir / "editor_review.txt"
        if prompt_file.exists():
            self.editor_prompt = prompt_file.read_text(encoding="utf-8")
        else:
            self.editor_prompt = ""

    def _find_ai_phrases(self, content: str) -> list[str]:
        """Find AI-typical phrases in content."""
        content_lower = content.lower()
        found = []

        for phrase in AI_PHRASES:
            if phrase in content_lower:
                found.append(phrase)

        return found

    def _find_generic_openings(self, content: str) -> list[str]:
        """Find generic opening phrases."""
        first_part = content[:200].lower()  # Check first 200 chars
        found = []

        for opening in GENERIC_OPENINGS:
            if opening in first_part:
                found.append(opening)

        return found

    def _check_paragraph_length(self, content: str) -> list[str]:
        """Check for overly long paragraphs."""
        issues = []
        paragraphs = content.split("\n\n")

        for i, para in enumerate(paragraphs):
            sentences = len([s for s in para.split(".") if s.strip()])
            if sentences > 5:
                issues.append(f"Paragraph {i+1} has {sentences} sentences (max 5)")

        return issues

    def _check_required_blocks(self, content: str) -> list[str]:
        """Check for required post structure blocks."""
        missing = []

        required_markers = [
            ("🔍", "Key Facts block"),
            ("🧠", "Analysis block"),
            ("🔗", "Sources block"),
            ("💡", "TLDR"),
        ]

        for marker, name in required_markers:
            if marker not in content:
                missing.append(f"Missing {name}")

        return missing

    def _remove_ai_phrases(self, content: str) -> tuple[str, list[str]]:
        """Remove AI-typical phrases from content."""
        changes = []
        result = content

        for phrase in AI_PHRASES:
            # Case-insensitive replacement
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            if pattern.search(result):
                result = pattern.sub("", result)
                changes.append(f"Removed AI phrase: '{phrase}'")

        # Clean up double spaces
        result = re.sub(r" +", " ", result)
        result = re.sub(r"\n\s*\n\s*\n", "\n\n", result)

        return result.strip(), changes

    def _improve_formatting(self, content: str) -> tuple[str, list[str]]:
        """Improve content formatting."""
        changes = []
        result = content

        # Ensure proper spacing around emoji markers
        result = re.sub(r"([^\n])(🔍|🧠|🔗|⚡|💡)", r"\1\n\n\2", result)
        result = re.sub(r"(🔍|🧠|🔗|⚡|💡)([^\n:])", r"\1\2", result)

        # Normalize bullet points
        result = re.sub(r"^[-–—]\s*", "• ", result, flags=re.MULTILINE)

        # Fix multiple newlines
        result = re.sub(r"\n{3,}", "\n\n", result)

        return result, changes

    def review(self, content: str) -> EditorResult:
        """
        Perform editorial review on content.

        Args:
            content: Post content to review

        Returns:
            EditorResult with review results
        """
        issues = []
        changes = []
        score = 100.0

        # Check for AI phrases
        ai_phrases = self._find_ai_phrases(content)
        if ai_phrases:
            issues.append(f"AI-typical phrases found: {', '.join(ai_phrases[:3])}")
            score -= 15

        # Check for generic openings
        generic = self._find_generic_openings(content)
        if generic:
            issues.append(f"Generic opening: '{generic[0]}'")
            score -= 10

        # Check paragraph length
        para_issues = self._check_paragraph_length(content)
        issues.extend(para_issues)
        score -= len(para_issues) * 5

        # Check required blocks
        missing_blocks = self._check_required_blocks(content)
        issues.extend(missing_blocks)
        score -= len(missing_blocks) * 10

        # Apply improvements
        improved, phrase_changes = self._remove_ai_phrases(content)
        changes.extend(phrase_changes)

        improved, format_changes = self._improve_formatting(improved)
        changes.extend(format_changes)

        # Ensure score is in bounds
        score = max(0, min(100, score))

        # Determine approval
        approved = score >= self.min_score
        needs_regeneration = score < 50

        remaining = []
        if not approved:
            remaining = [i for i in issues if i not in changes]

        return EditorResult(
            approved=approved,
            score=score,
            improved_content=improved,
            changes_made=changes,
            issues_found=issues,
            remaining_concerns=remaining,
            needs_regeneration=needs_regeneration,
        )

    async def review_with_ai(self, content: str) -> EditorResult:
        """
        Perform AI-assisted editorial review.

        Args:
            content: Post content to review

        Returns:
            EditorResult with AI-enhanced review
        """
        # First do rule-based review
        base_result = self.review(content)

        if not self.llm:
            return base_result

        try:
            prompt = f"""{self.editor_prompt}

POST TO REVIEW:
---
{content}
---

Review this post and provide an improved version. Respond in JSON:
{{
  "approved": true/false,
  "score": 0-100,
  "improved_content": "the edited version",
  "changes_made": ["list of changes"],
  "issues_found": ["list of issues"],
  "remaining_concerns": ["unfixable issues"],
  "needs_regeneration": true/false
}}"""

            response = await self.llm.generate(prompt)
            response_text = response.content.strip()

            # Handle empty response
            if not response_text:
                logger.warning("AI editorial review returned empty response, using base result")
                return base_result

            # Parse JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]

            # Find JSON object in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                logger.warning("AI editorial review returned no valid JSON, using base result")
                return base_result

            response_text = json_match.group(0)
            ai_result = json.loads(response_text)

            # Use AI result if score is higher, otherwise combine
            if ai_result.get("score", 0) >= base_result.score:
                return EditorResult(
                    approved=ai_result.get("approved", base_result.approved),
                    score=ai_result.get("score", base_result.score),
                    improved_content=ai_result.get("improved_content", base_result.improved_content),
                    changes_made=ai_result.get("changes_made", base_result.changes_made),
                    issues_found=ai_result.get("issues_found", base_result.issues_found),
                    remaining_concerns=ai_result.get("remaining_concerns", base_result.remaining_concerns),
                    needs_regeneration=ai_result.get("needs_regeneration", base_result.needs_regeneration),
                )

            # Combine results
            combined_changes = base_result.changes_made + ai_result.get("changes_made", [])
            combined_issues = base_result.issues_found + ai_result.get("issues_found", [])

            return EditorResult(
                approved=base_result.approved and ai_result.get("approved", True),
                score=(base_result.score + ai_result.get("score", base_result.score)) / 2,
                improved_content=ai_result.get("improved_content", base_result.improved_content),
                changes_made=combined_changes,
                issues_found=combined_issues,
                remaining_concerns=ai_result.get("remaining_concerns", base_result.remaining_concerns),
                needs_regeneration=base_result.needs_regeneration or ai_result.get("needs_regeneration", False),
            )

        except Exception as e:
            logger.error(f"AI editorial review failed: {e}")
            return base_result


class MediaPromptGenerator:
    """
    Generates image prompts for posts without media.
    """

    def __init__(
        self,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        prompts_dir: str | Path = "llm/prompts",
    ) -> None:
        """
        Initialize media prompt generator.

        Args:
            llm_adapter: LLM for generating prompts
            prompts_dir: Directory containing prompt templates
        """
        self.llm = llm_adapter
        self.prompts_dir = Path(prompts_dir)

        # Load prompt template
        prompt_file = self.prompts_dir / "media_generator.txt"
        if prompt_file.exists():
            self.media_prompt = prompt_file.read_text(encoding="utf-8")
        else:
            self.media_prompt = ""

    async def generate_media_prompt(self, post_content: str, topic: str) -> str:
        """
        Generate an image prompt for a post.

        Args:
            post_content: The post content
            topic: The post topic

        Returns:
            str: Image generation prompt
        """
        if not self.llm:
            return self._generate_fallback_prompt(topic)

        try:
            # Ensure post_content is a string
            if post_content is None:
                content_preview = ""
            elif isinstance(post_content, str):
                content_preview = post_content[:500]
            else:
                content_preview = str(post_content)[:500]

            prompt = f"""{self.media_prompt}

POST TOPIC: {topic}

POST CONTENT (for context):
{content_preview}...

Generate an image prompt for this AI/technology post."""

            response = await self.llm.generate(prompt)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Media prompt generation failed: {e}")
            return self._generate_fallback_prompt(topic)

    def _generate_fallback_prompt(self, topic: str) -> str:
        """Generate a fallback prompt based on topic keywords."""
        # Extract key terms
        topic_lower = topic.lower()

        # Determine style based on topic
        if "neural" in topic_lower or "ai" in topic_lower or "model" in topic_lower:
            style = "neural network visualization, glowing nodes and connections"
        elif "robot" in topic_lower or "automation" in topic_lower:
            style = "futuristic robot, sleek design, ambient lighting"
        elif "data" in topic_lower or "analytics" in topic_lower:
            style = "data visualization, abstract geometric patterns, flowing lines"
        else:
            style = "abstract AI technology, futuristic aesthetic"

        return f"{style}, cinematic lighting, digital art style, highly detailed, 8K, professional illustration, dark background with blue and purple accents"
