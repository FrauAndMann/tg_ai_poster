"""
Media Prompt Generator - Creates detailed image generation prompts.

Generates cinematic-style prompts for AI news illustrations
following the strict template and ensure consistency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.logger import get_logger
from llm.base import BaseLLMAdapter


logger = get_logger(__name__)


@dataclass
class MediaPromptResult:
    """Result of media prompt generation."""
    prompt: str
    visual_concept: str
    style_keywords: list[str]
    exclusions: list[str]
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "visual_concept": self.visual_concept,
            "style_keywords": self.style_keywords,
            "exclusions": self.exclusions,
            "confidence": self.confidence,
        }


class MediaPromptGenerator:
    """
    Generates detailed image generation prompts for AI news posts.

    Follows a cinematic futuristic technology illustration style
    with specific visual concepts from the content.
    """

    # Style template for consistent image generation
    STYLE_TEMPLATE = (
        "cinematic futuristic technology illustration, "
        "{visual_concept}, "
        "high detail, dramatic lighting, deep colors, "
        "professional digital art, "
        "{style_modifiers}"
    )

    # Mandatory exclusions for all prompts
    DEFAULT_EXCLUSIONS = [
        "no text",
        "no logos",
        "no watermarks",
        "no signatures",
        "no UI elements",
    ]

    # Optional exclusions for specific content
    FACE_EXCLUSIONS = [
        "no human faces",
        "no recognizable people",
    ]

    def __init__(
        self,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        style_template: str = STYLE_TEMPLATE,
        default_exclusions: list[str] = DEFAULT_EXCLUSIONS,
        face_exclusions: list[str] = FACE_EXCLUSIONS,
    ) -> None:
        """
        Initialize media prompt generator.

        Args:
            llm_adapter: Optional LLM adapter for AI-based generation
            style_template: Base style template
            default_exclusions: Default exclusions
            face_exclusions: Face exclusions
        """
        self.llm = llm_adapter
        self.style_template = style_template
        self.default_exclusions = default_exclusions
        self.face_exclusions = face_exclusions

    def _extract_visual_concept(self, content: str, topic: str) -> str:
        """
        Extract the main visual concept from content.

        Args:
            content: Post content
            topic: Post topic

        Returns:
            str: Visual concept description
        """
        # Look for technology-specific visual elements
        concepts = []

        # Neural network / AI concepts
        if any(term in content.lower() for term in [
            "нейron", "neural", "network", "model", "transformer", "gpt", "llm", "ai", "ис",
            "algorithm", "learning", "training", "inference"
        ]):
            concepts.append("neural network architecture visualization")

        # Data / cloud concepts
        if any(term in content.lower() for term in [
            "data", "cloud", "server", "api", "database", "compute", "gpu", "chip", "processor"
        ]):
            concepts.append("data center and computing infrastructure")

        # Robot / automation concepts
        if any(term in content.lower() for term in [
            "robot", "automation", "autonomous", "agent", "assistant", "bot", "chatbot"
        ]):
            concepts.append("autonomous system and AI agent visualization")

        # Research / science concepts
        if any(term in content.lower() for term in [
            "research", "study", "paper", "arxiv", "experiment", "benchmark", "result"
        ]):
            concepts.append("scientific research and data visualization")

        # Default: use topic
        if not concepts:
            concepts.append(f"abstract visualization of {topic[:50]}")

        return concepts[0]

    def _determine_style_modifiers(self, content: str, post_type: str) -> str:
        """
        Determine additional style modifiers based on content.

        Args:
            content: Post content
            post_type: Type of post

        Returns:
            str: Style modifiers
        """
        modifiers = []

        # Add cyber/digital feel for tech posts
        if any(term in content.lower() for term in [
            "cyber", "security", "hack", "breach", "attack"
        ]):
            modifiers.append("cyberpunk aesthetic, neon accents")

        # Add clean minimalist feel for product launches
        if post_type == "tool_roundup" or "breaking":
            modifiers.append("clean modern design, minimalist")

        # Add complexity for deep dive posts
        if post_type == "deep_dive":
            modifiers.append("complex interconnected systems, layered depth")

        return ", ".join(modifiers) if modifiers else ""

    def _should_exclude_faces(self, content: str) -> bool:
        """
        Determine if faces should be excluded from the prompt.

        Args:
            content: Post content

        Returns:
            bool: True if faces should be excluded
        """
        # Exclude faces for most AI/tech content
        face_terms = ["face", "person", "people", "human", "employee", "user", "researcher"]
        return not any(term in content.lower() for term in face_terms)


    async def generate_media_prompt(
        self,
        post_content: str,
        topic: str,
        post_type: str = "analysis",
    ) -> MediaPromptResult:
        """
        Generate a detailed media prompt for an image.

        Args:
            post_content: Post content to extract concept from
            topic: Post topic
            post_type: Type of post

        Returns:
            MediaPromptResult: Generated media prompt
        """
        if not self.llm:
            return self._generate_rule_based_prompt(post_content, topic, post_type)

        try:
            prompt = f"""Generate a detailed image generation prompt for an AI news illustration.

TOPIC: {topic}
POST TYPE: {post_type}
CONTENT EXCERPT:
{post_content[:500]}

Create a prompt that:
1. Captures a specific visual concept from the content
2. Uses cinematic futuristic technology illustration style
3. Includes high detail and dramatic lighting
4. Uses deep colors (blues, purples, cyans)
5. EXCLUDES: no text, no logos, no watermarks, no UI elements

Return ONLY a single sentence prompt, nothing else.
Example: "cinematic futuristic technology illustration, neural network nodes connected by glowing data streams, high detail, dramatic lighting, deep colors, no text, no logos, no watermarks"
"""

            response = await self.llm.generate(prompt)
            prompt_text = response.content.strip()

            # Clean up the response
            if prompt_text.startswith('"') and prompt_text.endswith('"'):
                prompt_text = prompt_text[1:-1]
            if prompt_text.startswith("'") and prompt_text.endswith("'"):
                prompt_text = prompt_text[1:-1]

            # Validate prompt length
            if len(prompt_text) > 500:
                prompt_text = prompt_text[:500]

            exclusions = self.default_exclusions.copy()
            if self._should_exclude_faces(post_content):
                exclusions.extend(self.face_exclusions)

            return MediaPromptResult(
                prompt=prompt_text,
                visual_concept=self._extract_visual_concept(post_content, topic),
                style_keywords=["cinematic", "futuristic", "technology"],
                exclusions=exclusions,
                confidence=0.0,
            )

        except Exception as e:
            logger.error(f"Media prompt generation failed: {e}")
            return self._generate_rule_based_prompt(post_content, topic, post_type)

    def _generate_rule_based_prompt(
        self,
        post_content: str,
        topic: str,
        post_type: str,
    ) -> MediaPromptResult:
        """
        Generate a rule-based prompt without LLM.

        Args:
            post_content: Post content
            topic: Post topic
            post_type: Type of post

        Returns:
            MediaPromptResult: Generated media prompt
        """
        visual_concept = self._extract_visual_concept(post_content, topic)
        style_modifiers = self._determine_style_modifiers(post_content, post_type)

        exclusions = self.default_exclusions.copy()
        if self._should_exclude_faces(post_content):
            exclusions.extend(self.face_exclusions)

        prompt = self.style_template.format(
            visual_concept=visual_concept,
            style_modifiers=style_modifiers
        )

        # Add exclusions
        prompt += ", " + ", ".join(exclusions)

        return MediaPromptResult(
            prompt=prompt,
            visual_concept=visual_concept,
            style_keywords=["cinematic", "futuristic", "technology"],
            exclusions=exclusions,
            confidence=0.7,
        )
