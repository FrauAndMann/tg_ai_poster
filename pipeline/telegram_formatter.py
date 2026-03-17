"""
Telegram Formatter - Converts JSON posts to Telegram-ready format.

Handles MarkdownV2/HTML formatting, character limits, and structured blocks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger


logger = get_logger(__name__)


@dataclass
class FormattedPost:
    """A post formatted for Telegram publishing."""
    telegram_text: str
    character_count: int
    has_all_blocks: bool
    missing_blocks: list[str]
    is_valid: bool
    validation_errors: list[str]

    media_prompt: Optional[str] = None
    hashtags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "telegram_text": self.telegram_text,
            "character_count": self.character_count,
            "has_all_blocks": self.has_all_blocks,
            "missing_blocks": self.missing_blocks,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "media_prompt": self.media_prompt,
            "hashtags": self.hashtags,
        }


class TelegramFormatter:
    """
    Formats structured post JSON into Telegram-ready messages.

    Supports both MarkdownV2 and HTML formatting modes.
    Validates structure and enforces character limits.
    """

    # Required block markers in order
    BLOCK_MARKERS = {
        "key_facts": "🔍",
        "analysis": "🧠",
        "sources": "🔗",
        "useful_links": "⚡",
        "tldr": "💡",
    }

    # Block header templates (Russian)
    BLOCK_HEADERS = {
        "key_facts": "🔍 Что важно знать:",
        "analysis": "🧠 Почему это важно",
        "sources": "🔗 Источники:",
        "useful_links": "⚡ Полезные ссылки:",
        "tldr": "💡 TL;DR:",
    }

    # MarkdownV2 special characters that need escaping
    MARKDOWN_V2_SPECIAL = [
        "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|",
        "{", "}", ".", "!", "!"
    ]

    MAX_POST_LENGTH = 4096

    MIN_BODY_LENGTH = 800
    MAX_BODY_LENGTH = 1500

    def __init__(
        self,
        parse_mode: str = "MarkdownV2",
        max_length: int = MAX_POST_LENGTH,
        min_body_length: int = MIN_BODY_LENGTH,
        max_body_length: int = MAX_BODY_LENGTH,
    ):
        """
        Initialize Telegram formatter.

        Args:
            parse_mode: Telegram parse mode (MarkdownV2 or HTML)
            max_length: Maximum post length
            min_body_length: Minimum body length
            max_body_length: Maximum body length
        """
        self.parse_mode = parse_mode
        self.max_length = max_length
        self.min_body_length = min_body_length
        self.max_body_length = max_body_length

    def format(self, post_json: dict) -> FormattedPost:
        """
        Format a structured post JSON into Telegram-ready text.

        Args:
            post_json: Post data matching the JSON schema

        Returns:
            FormattedPost: Formatted post ready for Telegram
        """
        # Parse JSON if string
        if isinstance(post_json, str):
            try:
                post_data = json.loads(post_json)
            except json.JSONDecodeError:
                return FormattedPost(
                    telegram_text="",
                    character_count=0,
                    has_all_blocks=False,
                    missing_blocks=["Invalid JSON"],
                    is_valid=False,
                    validation_errors=["Failed to parse JSON"],
                )
        else:
            post_data = post_json

        # Validate required fields
        validation_errors = []
        missing_blocks = []

        required_fields = ["title", "hook", "body", "key_facts", "analysis", "sources", "tldr", "hashtags"]
        for field_name in required_fields:
            if field_name not in post_data or not post_data.get(field_name):
                validation_errors.append(f"Missing required field: {field_name}")

        # Build the formatted text
        lines = []

        # Title
        title = post_data.get("title", "")
        lines.append(title)
        lines.append("")

        # Hook
        hook = post_data.get("hook", "")
        lines.append(hook)
        lines.append("")

        # Body
        body = post_data.get("body", "")
        # Check body length
        if len(body) < self.min_body_length:
            validation_errors.append(f"Body too short: {len(body)} < {self.min_body_length}")
        elif len(body) > self.max_body_length:
            validation_errors.append(f"Body too long: {len(body)} > {self.max_body_length}")
            # Truncate at paragraph boundary
            body = self._truncate_body(body)
        lines.append(body)
        lines.append("")

        # Key Facts block
        key_facts = post_data.get("key_facts", [])
        if not key_facts or len(key_facts) < 4:
            missing_blocks.append("key_facts")
        else:
            lines.append(f"{self.BLOCK_HEADERS['key_facts']}")
            for fact in key_facts[:4]:
                lines.append(f"• {fact}")
            lines.append("")

        # Analysis block
        analysis = post_data.get("analysis", "")
        if not analysis:
            missing_blocks.append("analysis")
        else:
            lines.append(f"{self.BLOCK_HEADERS['analysis']}")
            lines.append(analysis)
            lines.append("")

        # Sources block
        sources = post_data.get("sources", [])
        if not sources:
            missing_blocks.append("sources")
        else:
            lines.append(f"{self.BLOCK_HEADERS['sources']}")
            for source in sources[:3]:
                name = source.get("name", "Source")
                url = source.get("url", "")
                lines.append(f"• {name} — {url}")
            lines.append("")

        # Useful Links block (optional)
        useful_links = post_data.get("useful_links", [])
        if useful_links:
            lines.append(f"{self.BLOCK_HEADERS['useful_links']}")
            for link in useful_links[:3]:
                label = link.get("label", "Link")
                url = link.get("url", "")
                lines.append(f"• {label} — {url}")
            lines.append("")

        # TLDR block
        tldr = post_data.get("tldr", "")
        if not tldr:
            missing_blocks.append("tldr")
        else:
            lines.append(f"{self.BLOCK_HEADERS['tldr']} {tldr}")
            lines.append("")

        # Hashtags
        hashtags = post_data.get("hashtags", [])
        if hashtags:
            hashtag_str = " ".join(f"#{tag}" for tag in hashtags)
            lines.append(hashtag_str)

        # Join all lines
        text = "\n".join(lines)

        # Apply formatting
        if self.parse_mode == "MarkdownV2":
            text = self._escape_markdown_v2(text)
        elif self.parse_mode == "HTML":
            text = self._convert_to_html(text)

        # Check total length
        if len(text) > self.max_length:
            validation_errors.append(f"Post too long: {len(text)} > {self.max_length}")
            text = text[:self.max_length]

        # Media prompt (not included in Telegram text)
        media_prompt = post_data.get("media_prompt")

        return FormattedPost(
            telegram_text=text,
            character_count=len(text),
            has_all_blocks=len(missing_blocks) == 0,
            missing_blocks=missing_blocks,
            is_valid=len(validation_errors) == 0,
            validation_errors=validation_errors,
            media_prompt=media_prompt,
            hashtags=hashtags,
        )

    def _truncate_body(self, body: str) -> str:
        """Truncate body at paragraph boundary if too long."""
        if len(body) <= self.max_body_length:
            return body

        paragraphs = body.split("\n\n")
        result = []

        for para in paragraphs:
            test_body = "\n\n".join(result + [para])
            if len(test_body) <= self.max_body_length:
                result.append(para)
            else:
                break

        return "\n\n".join(result)
    def _escape_markdown_v2(self, text: str) -> str:
        """
        Escape special characters for Telegram MarkdownV2.

        IMPORTANT: Telegram MarkdownV2 requires proper balancing of formatting entities.
        Unbalanced _ or * characters cause "can't find end of entity" errors.
        This method escapes ALL potentially problematic characters to ensure
        the post is always valid, sacrificing some formatting for reliability.
        """
        # First, handle intentional formatting by finding balanced pairs
        # and temporarily replacing them with placeholders

        # Find balanced italic pairs: _text_ (not adjacent to other underscores)
        def protect_balanced(text: str, marker: str, placeholder: str) -> str:
            """Protect balanced marker pairs, escape unbalanced ones."""
            result = []
            i = 0
            while i < len(text):
                if text[i] == marker:
                    # Look for a closing marker
                    # Find next marker that's not part of a word
                    for j in range(i + 1, len(text)):
                        if text[j] == marker:
                            # Check if this is a valid closing marker
                            # (not part of a word like variable_name)
                            if j + 1 >= len(text) or not text[j + 1].isalnum():
                                if i > 0 and text[i - 1].isalnum():
                                    # This underscore is part of a word (like variable_name)
                                    # Don't treat it as formatting
                                    break
                                # Valid pair found - protect it
                                result.append(placeholder)
                                result.append(text[i + 1:j])
                                result.append(placeholder)
                                i = j + 1
                                break
                    else:
                        # No closing marker found - escape this one
                        result.append(f"\\{marker}")
                        i += 1
                        continue
                else:
                    result.append(text[i])
                    i += 1
            return "".join(result)

        # For safety in automated content, we escape ALL formatting markers
        # This ensures posts always publish successfully
        # The content should be readable without italic/bold formatting

        # Escape all MarkdownV2 special characters
        # Order matters: escape backslash first
        text = text.replace("\\", "\\\\")

        # Then escape all other special chars
        special_chars = "_*[]()~`>#+-=|{}.!"
        for char in special_chars:
            if char != "\\":  # Already handled
                text = text.replace(char, f"\\{char}")

        return text

    def _convert_to_html(self, text: str) -> str:
        """Convert markdown to HTML format."""
        # Convert bold
        text = re.sub(r'\*([^*]+)\*', r'<b>\1</b>', text)
        # Convert italic
        text = re.sub(r'_([^_]+)_', r'<i>\1</i>', text)
        # Convert links
        text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', text)

        return text

    def validate_post(self, post_json: dict) -> tuple[bool, list[str]]:
        """
        Validate a post against all quality rules.

        Args:
            post_json: Post data to validate

        Returns:
            tuple[bool, list[str]]: (is_valid, list of errors)
        """
        errors = []

        # Check required fields
        if not post_json.get("title"):
            errors.append("Missing title")
        if not post_json.get("hook"):
            errors.append("Missing hook")
        if not post_json.get("body"):
            errors.append("Missing body")
        if not post_json.get("key_facts") or len(post_json.get("key_facts", [])) < 4:
            errors.append("Need exactly 4 key facts")
        if not post_json.get("analysis"):
            errors.append("Missing analysis")
        if not post_json.get("sources") or len(post_json.get("sources", [])) < 1:
            errors.append("Need at least 1 source")
        if not post_json.get("tldr"):
            errors.append("Missing TLDR")
        if not post_json.get("hashtags") or len(post_json.get("hashtags", [])) < 3:
            errors.append("Need at least 3 hashtags")

        # Check lengths
        if len(post_json.get("title", "")) > 120:
            errors.append("Title too long (max 120 chars)")
        if len(post_json.get("body", "")) < 800:
            errors.append("Body too short (min 800 chars)")
        if len(post_json.get("body", "")) > 1500:
            errors.append("Body too long (max 1500 chars)")

        return len(errors) == 0, errors
