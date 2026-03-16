"""
Media Generation Pipeline v2 - Complete image generation and selection system.

Generates multiple image prompt variants, optionally generates images via API,
runs quality checks, and selects best image for posts.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from pathlib import Path

from core.constants import (
    MAX_IMAGE_PROMPT_LENGTH,
    IMAGE_VARIANTS_COUNT,
    MIN_CONTRAST_RATIO,
)
from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter
    from pipeline.media_prompt_generator import MediaPromptGenerator

logger = get_logger(__name__)


class ImageStyle(str, Enum):
    """Image style variants."""
    PHOTOREALISTIC = "photorealistic"
    ABSTRACT = "abstract"
    INFOGRAPHIC = "infographic"
    MINIMAL = "minimal"
    CYBERPUNK = "cyberpunk"


@dataclass(slots=True)
class ImagePromptVariant:
    """A single image prompt variant."""

    style: ImageStyle
    prompt: str
    generated_url: Optional[str] = None
    quality_score: float = 1.0
    contrast_ratio: float = 1.0
    composition_score: float = 1.0
    selected: bool = False


@dataclass(slots=True)
class MediaPipelineResult:
    """Result of media pipeline."""

    selected_prompt: str
    selected_style: ImageStyle
    image_url: Optional[str] = None
    all_variants: list[ImagePromptVariant] = field(default_factory=list)
    generation_method: str = "prompt_only"  # "prompt_only", "api_generated"


class MediaPipelineV2:
    """
    Advanced media generation pipeline.

    Features:
    - Multiple style variants per post
    - Optional API-based image generation (Replicate, Stability AI)
    - Composition quality checks via PIL
    - Best image selection
    - Fallback to text-only mode
    """

    # Style-specific prompt templates
    STYLE_TEMPLATES = {
        ImageStyle.PHOTOREALISTIC: (
            "photorealistic digital art, {concept}, "
            "hyperrealistic lighting, detailed textures, 8K resolution, "
            "professional photography style, no text, no logos"
        ),
        ImageStyle.ABSTRACT: (
            "abstract technology visualization, {concept}, "
            "flowing shapes and gradients, deep blues and cyans, "
            "modern digital art style, conceptual, no text, no logos"
        ),
        ImageStyle.INFOGRAPHIC: (
            "clean infographic style illustration, {concept}, "
            "simple icons and diagrams, professional business style, "
            "minimal design, white space, no text overlays"
        ),
        ImageStyle.MINIMAL: (
            "minimalist flat design, {concept}, "
            "clean lines, single color accent, white background, "
            "modern UI style, simple, no text, no logos"
        ),
        ImageStyle.CYBERPUNK: (
            "cyberpunk aesthetic illustration, {concept}, "
            "neon accents, dark atmosphere, futuristic city vibes, "
            "blade runner inspired, no text, no logos"
        ),
    }

    def __init__(
        self,
        media_generator: Optional["MediaPromptGenerator"] = None,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
        replicate_api_key: Optional[str] = None,
        stability_api_key: Optional[str] = None,
        image_output_dir: str = "./data/images",
        generate_images: bool = False,
    ) -> None:
        """
        Initialize media pipeline v2.

        Args:
            media_generator: Base media prompt generator
            llm_adapter: LLM for prompt generation
            replicate_api_key: Replicate API key (optional)
            stability_api_key: Stability AI API key (optional)
            image_output_dir: Directory for generated images
            generate_images: Whether to actually generate images
        """
        self.media_generator = media_generator
        self.llm = llm_adapter
        self.replicate_api_key = replicate_api_key
        self.stability_api_key = stability_api_key
        self.image_output_dir = Path(image_output_dir)
        self.generate_images = generate_images and (bool(replicate_api_key) or bool(stability_api_key))
        self.image_output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_variants(
        self,
        content: str,
        topic: str,
        post_type: str = "analysis",
        style_count: int = 3,
    ) -> list[ImagePromptVariant]:
        """
        Generate multiple image prompt variants.

        Args:
            content: Post content
            topic: Post topic
            post_type: Type of post
            style_count: Number of style variants

        Returns:
            List of prompt variants
        """
        variants = []

        # Determine best styles for this content
        styles = self._select_styles(content, post_type)
        selected_styles = styles[:style_count]

        for style in selected_styles:
            prompt = await self._generate_style_prompt(content, topic, style)
            if prompt:
                variants.append(ImagePromptVariant(
                    style=style,
                    prompt=prompt[:MAX_IMAGE_PROMPT_LENGTH],
                ))

        logger.info("Generated %d image prompt variants", len(variants))
        return variants

    def _select_styles(self, content: str, post_type: str) -> list[ImageStyle]:
        """Select appropriate styles based on content and post type."""
        content_lower = content.lower()
        styles = []

        # Photorealistic for news and announcements
        if any(word in content_lower for word in ["announce", "release", "launch", "event"]):
            styles.append(ImageStyle.PHOREALISTIC)

        # Abstract for concepts and theories
        if any(word in content_lower for word in ["concept", "theory", "framework", "architecture"]):
            styles.append(ImageStyle.ABSTRACT)

        # Infographic for data and statistics
        if any(word in content_lower for word in ["data", "statistics", "report", "benchmark"]):
            styles.append(ImageStyle.INFOGRAPHIC)

        # Minimal for tools and products
        if any(word in content_lower for word in ["tool", "product", "app", "software"]):
            styles.append(ImageStyle.MINIMAL)

        # Cyberpunk for security and hacking
        if any(word in content_lower for word in ["security", "hack", "breach", "cyber"]):
            styles.append(ImageStyle.CYBERPUNK)

        # Default to photorealistic + abstract
        if not styles:
            styles = [ImageStyle.PHOTOREALISTIC, ImageStyle.ABSTRACT, ImageStyle.MINIMAL]

        return styles

    async def _generate_style_prompt(
        self,
        content: str,
        topic: str,
        style: ImageStyle,
    ) -> str:
        """Generate prompt for a specific style."""
        # Extract key concept from content
        concept = self._extract_concept(content, topic)
        template = self.STYLE_TEMPLATES.get(style, self.STYLE_TEMPLATES[ImageStyle.PHOTOREALISTIC])
        return template.format(concept=concept)

    def _extract_concept(self, content: str, topic: str) -> str:
        """Extract main visual concept from content."""
        # Simple extraction: use topic and key phrases
        words = content.split()[:50]
        key_phrases = [w for w in words if len(w) > 5][:10]
        if key_phrases:
            return f"{topic}: {' '.join(key_phrases[:5])}"
        return topic

    async def generate_images_for_variants(
        self,
        variants: list[ImagePromptVariant],
    ) -> list[ImagePromptVariant]:
        """
        Generate actual images for variants using configured API.

        Args:
            variants: List of prompt variants

        Returns:
            Updated variants with image URLs
        """
        if not self.generate_images:
            logger.info("Image generation disabled, returning prompts only")
            return variants

        for variant in variants:
            try:
                image_url = await self._call_image_api(variant.prompt)
                if image_url:
                    variant.generated_url = image_url
                    variant.quality_score = await self._check_image_quality(image_url)
            except Exception as e:
                logger.error("Failed to generate image for %s style: %s", variant.style, e)

        return variants

    async def _call_image_api(self, prompt: str) -> Optional[str]:
        """Call configured image generation API."""
        if self.replicate_api_key:
            return await self._call_replicate(prompt)
        elif self.stability_api_key:
            return await self._call_stability(prompt)
        return None

    async def _call_replicate(self, prompt: str) -> Optional[str]:
        """Call Replicate API for image generation."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.replicate.com/v1/predictions",
                    headers={
                        "Authorization": f"Token {self.replicate_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "version": "stability-ai/sdxl:396edb50b8aafb2d0d2dea3af16e66",
                        "input": {"prompt": prompt},
                    },
                ) as response:
                    if response.status == 201:
                        result = await response.json()
                        # Poll for completion
                        return await self._poll_replicate(result.get("urls", {}).get("get"))
        except Exception as e:
            logger.error("Replicate API error: %s", e)
        return None

    async def _poll_replicate(self, poll_url: str) -> Optional[str]:
        """Poll Replicate for result."""
        import aiohttp
        import asyncio
        for _ in range(30):  # 30 attempts, ~30 seconds
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(poll_url) as response:
                        if response.status == 200:
                            result = await response.json()
                            if result.get("status") == "succeeded":
                                return result.get("output")
                            elif result.get("status") == "failed":
                                return None
            except Exception:
                pass
            await asyncio.sleep(1)
        return None

    async def _call_stability(self, prompt: str) -> Optional[str]:
        """Call Stability AI API for image generation."""
        # Placeholder for Stability AI implementation
        logger.warning("Stability AI not yet implemented")
        return None

    async def _check_image_quality(self, image_url: str) -> float:
        """Check image quality using PIL."""
        try:
            # Download image
            import aiohttp
            from PIL import Image
            import io
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        return 0.5
                    image_data = await response.read()
            # Analyze with PIL
            image = Image.open(io.BytesIO(image_data))
            score = 1.0
            # Check contrast
            stat = image.convert("L").statistics()
            if stat.median < 50 or stat.median > 200:
                score *= 0.7  # Low or too high contrast
            # Check dimensions
            if image.width < 512 or image.height < 512:
                score *= 0.8  # Too small
            return score
        except Exception as e:
            logger.warning("Image quality check failed: %s", e)
            return 0.5

    def select_best_variant(
        self,
        variants: list[ImagePromptVariant],
    ) -> ImagePromptVariant:
        """
        Select best image variant based on quality scores.

        Args:
            variants: List of variants

        Returns:
            Best variant
        """
        if not variants:
            raise ValueError("No variants to select from")
        # Prefer generated images with good quality
        generated = [v for v in variants if v.generated_url]
        if generated:
            best = max(generated, key=lambda v: v.quality_score)
            best.selected = True
            return best
        # Fall back to prompt-only selection
        best = max(variants, key=lambda v: v.quality_score)
        best.selected = True
        return best

    async def run_pipeline(
        self,
        content: str,
        topic: str,
        post_type: str = "analysis",
    ) -> MediaPipelineResult:
        """
        Run complete media generation pipeline.

        Args:
            content: Post content
            topic: Post topic
            post_type: Post type

        Returns:
            MediaPipelineResult with selected media
        """
        logger.info("Running media pipeline v2 for: %s", topic[:50])
        # Generate variants
        variants = await self.generate_variants(content, topic, post_type)
        if not variants:
            return MediaPipelineResult(
                selected_prompt="",
                selected_style=ImageStyle.PHOTOREALISTIC,
            )
        # Generate images if configured
        if self.generate_images:
            variants = await self.generate_images_for_variants(variants)
        # Select best
        best = self.select_best_variant(variants)
        return MediaPipelineResult(
            selected_prompt=best.prompt,
            selected_style=best.style,
            image_url=best.generated_url,
            all_variants=variants,
            generation_method="api_generated" if best.generated_url else "prompt_only",
        )


# Configuration schema
MEDIA_PIPELINE_V2_CONFIG_SCHEMA = {
    "media_pipeline_v2": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable media pipeline v2",
        },
        "generate_images": {
            "type": "bool",
            "default": False,
            "description": "Actually generate images via API",
        },
        "replicate_api_key": {
            "type": "str",
            "default": "",
            "secret": True,
            "description": "Replicate API key for image generation",
        },
        "stability_api_key": {
            "type": "str",
            "default": "",
            "secret": True,
            "description": "Stability AI API key",
        },
        "style_count": {
            "type": "int",
            "default": 3,
            "min": 1,
            "max": 5,
            "description": "Number of style variants to generate",
        },
    }
}
