"""
Localization Engine - Multi-language post generation.

Generates same post in multiple languages simultaneously.
Primary language generates first, then secondary languages are translated
with cultural adaptation using a second LLM call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter

logger = get_logger(__name__)


SUPPORTED_LANGUAGES = ["ru", "en", "es", "zh"]  # Russian, English, Spanish, Chinese


@dataclass(slots=True)
class LocalizedContent:
    """Localized content ready for publishing."""

    language: str
    title: str
    body: str
    hook: str
    tldr: str
    analysis: str
    key_facts: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    cultural_notes: str = ""


class Localizer:
    """
    Multi-language content localization system.

    Features:
    - Primary language generation
    - Cultural adaptation translation
    - Language detection
    - Channel routing by language
    """

    CULTURAL_CONTEXT = {
        "ru": {
            "tone": "профессиональный, аналитический",
            "formality": "formal",
            "emoji_style": "moderate",
            "example_preference": "concrete",
        },
        "en": {
            "tone": "casual, conversational, friendly",
            "formality": "semi-formal",
            "emoji_style": "moderate",
            "example_preference": "storytelling",
        },
        "es": {
            "tone": "enthusiastic",
            "formality": "formal",
            "emoji_style": "expressive",
            "example_preference": "comparative",
        },
        "zh": {
            "tone": "formal, respectful",
            "formality": "formal",
            "emoji_style": "minimal",
            "example_preference": "data-driven",
        },
    }

    def __init__(
        self,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
    ) -> None:
        self.llm = llm_adapter
        self._cultural_context = self.CULTURAL_CONTEXT

    async def localize(
        self,
        content: dict,
        target_language: str,
    ) -> LocalizedContent:
        """
        Localize content to target language.

        Args:
            content: Original content dict (with language, title, body, etc.)
            target_language: Target language code

        Returns:
            LocalizedContent with translated content
        """
        if target_language not in self._cultural_context:
            raise ValueError(f"Unsupported language: {target_language}")

        source_lang = self._detect_language(content)
        context = self._cultural_context.get(
            source_lang, self.CULTURAL_CONTEXT["ru"]
        )

        # Create base localized content
        localized = LocalizedContent(
            language=target_language,
            title=content.get("title", ""),
            body=content.get("body", ""),
            hook=content.get("hook", ""),
            tldr=content.get("tldr", ""),
            analysis=content.get("analysis", ""),
            key_facts=content.get("key_facts", []),
            sources=content.get("sources", []),
            hashtags=content.get("hashtags", []),
            cultural_notes=f"Cultural adaptation for {source_lang} -> {target_language}",
        )

        if source_lang == target_language:
            # Same language - return as is
            return localized

        if not self.llm:
            return localized

        try:
            prompt = self._build_translation_prompt(content, target_language, context)
            response = await self.llm.generate(prompt)
            parsed = self._parse_translated_content(response.content)
            if parsed:
                return LocalizedContent(
                    language=target_language,
                    title=parsed.get("title", localized.title),
                    body=parsed.get("body", localized.body),
                    hook=parsed.get("hook", localized.hook),
                    tldr=parsed.get("tldr", localized.tldr),
                    analysis=parsed.get("analysis", localized.analysis),
                    key_facts=parsed.get("key_facts", localized.key_facts),
                    sources=parsed.get("sources", localized.sources),
                    hashtags=parsed.get("hashtags", localized.hashtags),
                    cultural_notes=f"Cultural adaptation for {source_lang} -> {target_language}",
                )
        except Exception as e:
            logger.error("Localization failed: %s", e)

        return localized

    def _detect_language(self, content: dict) -> str:
        """Detect source language from content."""
        if content.get("language"):
            return content["language"]

        # Check title and body for language hints
        text = f"{content.get('title', '')} {content.get('body', '')}"

        # Simple heuristics for language detection
        russian_markers = ["и", "в", "на", "что", "это", "не", "как"]
        english_markers = ["the", "is", "and", "to", "of", "a", "in"]

        text_lower = text.lower()
        russian_count = sum(1 for m in russian_markers if f" {m} " in text_lower)
        english_count = sum(1 for m in english_markers if f" {m} " in text_lower)

        if russian_count > english_count:
            return "ru"
        elif english_count > 0:
            return "en"

        return "ru"  # Default

    def _get_cultural_context(self, source_lang: str, target_lang: str) -> dict:
        """Get cultural adaptation context."""
        source = self.CULTURAL_CONTEXT.get(source_lang, self.CULTURAL_CONTEXT["ru"])
        target = self.CULTURAL_CONTEXT.get(target_lang, self.CULTURAL_CONTEXT["ru"])
        return {
            "source_tone": source.get("tone", ""),
            "target_tone": target.get("tone", ""),
            "formality": target.get("formality", "semi-formal"),
            "emoji_style": target.get("emoji_style", "moderate"),
            "example_preference": target.get("example_preference", "concrete"),
        }

    def _build_translation_prompt(
        self,
        content: dict,
        target_language: str,
        context: dict,
    ) -> str:
        """Build translation prompt."""
        source_text = content.get("body", "")
        source_title = content.get("title", "")
        source_hook = content.get("hook", "")
        source_tldr = content.get("tldr", "")
        target_lang_name = {
            "ru": "русский",
            "en": "English",
            "es": "Español",
            "zh": "中文",
        }.get(target_language, target_language.upper())

        return f"""Переведи этот пост на {target_lang_name} с культуральной адаптацией.

ИСХОДНЫЙ КОНТЕНТ:
Title: {source_title}
Hook: {source_hook}
Body: {source_text}
TL;DR: {source_tldr}

ТРЕБОВАНИЯ:
- Переведи на {target_lang_name} с культуральной адаптацией
- Сохрани структуру и смысл
- Адаптируй тон под целевую аудиторию
- Сохрани все ссылки и хештеги без изменений

Верни JSON:
{{
    "title": "переведенный заголовок",
    "body": "переведенный текст",
    "hook": "переведенный хук",
    "tldr": "переведенный TL;DR",
    "analysis": "переведенный анализ",
    "key_facts": ["факт 1", "факт 2"],
    "hashtags": ["#хештег1", "#хештег2"]
}}

Если response содержит ```json, извлеки JSON. Иначе парсь напрямую."""

    def _parse_translated_content(self, response: str) -> Optional[dict]:
        """Parse translated content from LLM response."""
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            data = json.loads(response.strip())
            return {
                "title": data.get("title", ""),
                "body": data.get("body", ""),
                "hook": data.get("hook", ""),
                "tldr": data.get("tldr", ""),
                "analysis": data.get("analysis", ""),
                "key_facts": data.get("key_facts", []),
                "sources": data.get("sources", []),
                "hashtags": data.get("hashtags", []),
            }
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning("Failed to parse translated content: %s", e)
            return None


# Configuration schema
LOCALIZATION_CONFIG_SCHEMA = {
    "localization": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable multi-language localization",
        },
        "supported_languages": {
            "type": "list",
            "default": ["ru", "en", "es"],
            "description": "Supported languages for localization",
        },
        "primary_language": {
            "type": "str",
            "default": "ru",
            "description": "Primary content language",
        },
    }
}
