"""
Telegram post formatter.

Formats posts for Telegram with MarkdownV2 support and clickable links.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Union

from core.logger import get_logger
from domain.post import Post, POST_TYPE_CONFIGS
from plugins.formatters.base import PostFormatter, FormattedPost

logger = get_logger(__name__)


class TelegramFormatter(PostFormatter):
    """
    Formats posts for Telegram publishing.

    Supports MarkdownV2 with clickable links and adaptive length limits.
    """

    # Block header templates
    BLOCK_HEADERS = {
        "key_facts": "🔍 Что важно знать:",
        "analysis": "🧠 Почему это важно",
        "sources": "🔗 Источники:",
        "useful_links": "⚡ Полезные ссылки:",
        "tldr": "💡 TL;DR:",
    }

    # MarkdownV2 special characters that need escaping
    MARKDOWN_V2_SPECIAL = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
        "!",
    ]

    # Telegram limits
    MAX_POST_LENGTH = 4096
    DEFAULT_MIN_BODY = 800
    DEFAULT_MAX_BODY = 1500

    def __init__(
        self,
        parse_mode: str = "MarkdownV2",
        max_length: int = MAX_POST_LENGTH,
    ):
        """
        Initialize Telegram formatter.

        Args:
            parse_mode: Telegram parse mode (MarkdownV2 or HTML)
            max_length: Maximum post length
        """
        self.parse_mode = parse_mode
        self.max_length = max_length

    def format(self, post: Union[Post, dict[str, Any]]) -> FormattedPost:
        """
        Format a post for Telegram.

        Args:
            post: Post object or dict with post data

        Returns:
            FormattedPost ready for Telegram
        """
        # Handle dict input for backward compatibility
        if isinstance(post, dict):
            return self._format_dict(post)

        # Handle Post object
        return self._format_post(post)

    def _format_post(self, post: Post) -> FormattedPost:
        """Format Post domain object."""
        validation_errors = []
        missing_blocks = []

        # Get length limits by post type
        config = POST_TYPE_CONFIGS.get(post.post_type)
        if config:
            min_body = config.min_length
            max_body = config.max_length
        else:
            min_body = self.DEFAULT_MIN_BODY
            max_body = self.DEFAULT_MAX_BODY

        # Build formatted text
        lines = []

        # Title
        title = post.content.title
        lines.append(title)
        lines.append("")

        # Hook
        hook = post.content.hook
        lines.append(hook)
        lines.append("")

        # Body with length validation
        body = post.content.body
        if len(body) < min_body:
            validation_errors.append(f"Body too short: {len(body)} < {min_body}")
        elif len(body) > max_body:
            validation_errors.append(f"Body too long: {len(body)} > {max_body}")
            body = self._truncate_body(body, max_body)
        lines.append(body)
        lines.append("")

        # Key Facts block
        key_facts = post.content.key_facts
        if not key_facts:
            missing_blocks.append("key_facts")
        else:
            lines.append(self.BLOCK_HEADERS["key_facts"])
            for fact in key_facts[:4]:
                lines.append(f"• {fact}")
            lines.append("")

        # Analysis block
        analysis = post.content.analysis
        if not analysis:
            missing_blocks.append("analysis")
        else:
            lines.append(self.BLOCK_HEADERS["analysis"])
            lines.append(analysis)
            lines.append("")

        # Sources block with clickable links
        sources = post.sources
        if not sources:
            missing_blocks.append("sources")
        else:
            lines.append(self.BLOCK_HEADERS["sources"])
            for source in sources[:3]:
                # Create clickable link: [Name](URL)
                link_text = self._make_clickable_link(source.name, source.url)
                lines.append(f"• {link_text}")
            lines.append("")

        # TLDR block
        tldr = post.content.tldr
        if not tldr:
            missing_blocks.append("tldr")
        else:
            lines.append(f"{self.BLOCK_HEADERS['tldr']} {tldr}")
            lines.append("")

        # Hashtags
        hashtags = post.content.hashtags
        if hashtags:
            hashtag_str = " ".join(f"#{tag}" for tag in hashtags)
            lines.append(hashtag_str)

        # Join all lines
        text = "\n".join(lines)

        # Apply MarkdownV2 escaping (preserving links)
        if self.parse_mode == "MarkdownV2":
            text = self._escape_markdown_v2(text)
        elif self.parse_mode == "HTML":
            text = self._convert_to_html(text)

        # Check total length
        if len(text) > self.max_length:
            validation_errors.append(f"Post too long: {len(text)} > {self.max_length}")
            text = text[: self.max_length]

        is_valid = len(validation_errors) == 0 and len(missing_blocks) == 0

        return FormattedPost(
            text=text,
            character_count=len(text),
            is_valid=is_valid,
            validation_errors=validation_errors,
            missing_blocks=missing_blocks,
            hashtags=hashtags,
            media_prompt=post.content.media_prompt,
        )

    def _format_dict(self, post_data: dict[str, Any]) -> FormattedPost:
        """Format dict input for backward compatibility."""
        validation_errors = []
        missing_blocks = []

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
        body_len = len(body)
        if body_len < self.DEFAULT_MIN_BODY:
            validation_errors.append(
                f"Body too short: {body_len} < {self.DEFAULT_MIN_BODY}"
            )
        elif body_len > self.DEFAULT_MAX_BODY:
            validation_errors.append(
                f"Body too long: {body_len} > {self.DEFAULT_MAX_BODY}"
            )
            body = self._truncate_body(body, self.DEFAULT_MAX_BODY)
        lines.append(body)
        lines.append("")

        # Key Facts block
        key_facts = post_data.get("key_facts", [])
        if not key_facts or len(key_facts) < 4:
            missing_blocks.append("key_facts")
        else:
            lines.append(self.BLOCK_HEADERS["key_facts"])
            for fact in key_facts[:4]:
                lines.append(f"• {fact}")
            lines.append("")

        # Analysis block
        analysis = post_data.get("analysis", "")
        if not analysis:
            missing_blocks.append("analysis")
        else:
            lines.append(self.BLOCK_HEADERS["analysis"])
            lines.append(analysis)
            lines.append("")

        # Sources block with clickable links
        sources = post_data.get("sources", [])
        if not sources:
            missing_blocks.append("sources")
        else:
            lines.append(self.BLOCK_HEADERS["sources"])
            for source in sources[:3]:
                name = source.get("name", "Source")
                url = source.get("url", "")
                link_text = self._make_clickable_link(name, url)
                lines.append(f"• {link_text}")
            lines.append("")

        # Useful Links block (optional)
        useful_links = post_data.get("useful_links", [])
        if useful_links:
            lines.append(self.BLOCK_HEADERS["useful_links"])
            for link in useful_links[:3]:
                label = link.get("label", "Link")
                url = link.get("url", "")
                link_text = self._make_clickable_link(label, url)
                lines.append(f"• {link_text}")
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
            text = text[: self.max_length]

        # Media prompt (not included in Telegram text)
        media_prompt = post_data.get("media_prompt")

        is_valid = len(validation_errors) == 0 and len(missing_blocks) == 0

        return FormattedPost(
            text=text,
            character_count=len(text),
            is_valid=is_valid,
            validation_errors=validation_errors,
            missing_blocks=missing_blocks,
            hashtags=hashtags,
            media_prompt=media_prompt,
        )

    def validate(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Validate formatted text.

        Args:
            text: Formatted text to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text:
            return False, "Empty text"

        if len(text) > self.max_length:
            return False, f"Text too long: {len(text)} > {self.max_length}"

        # Check for unescaped special characters in MarkdownV2
        if self.parse_mode == "MarkdownV2":
            # Check for common issues
            if text.count("[") != text.count("]"):
                return False, "Unmatched brackets"
            if text.count("(") != text.count(")"):
                return False, "Unmatched parentheses"

        return True, None

    def _make_clickable_link(self, text: str, url: str) -> str:
        """
        Create a clickable link in MarkdownV2 format.

        Args:
            text: Link text to display
            url: URL to link to

        Returns:
            Formatted link string [text](url)
        """
        if not url:
            return text
        return f"[{text}]({url})"

    def _truncate_body(self, body: str, max_length: int) -> str:
        """Truncate body at paragraph boundary if too long."""
        if len(body) <= max_length:
            return body

        paragraphs = body.split("\n\n")
        result = []

        for para in paragraphs:
            test_body = "\n\n".join(result + [para])
            if len(test_body) <= max_length:
                result.append(para)
            else:
                break

        return "\n\n".join(result)

    def _escape_markdown_v2(self, text: str) -> str:
        """Escape special characters for MarkdownV2, preserving links."""
        # Step 1: Extract and preserve URLs first (before any escaping)
        url_pattern = r"(https?://[^\s\)\]\>]+)"
        urls = []
        url_counter = [0]

        def save_url(match):
            idx = url_counter[0]
            url_counter[0] += 1
            urls.append(match.group(1))
            return f"\x00URL{idx}\x00"

        text = re.sub(url_pattern, save_url, text)

        # Step 2: Preserve link structure [text](url_placeholder)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        links = []
        link_counter = [0]

        def save_link(match):
            idx = link_counter[0]
            link_counter[0] += 1
            links.append((match.group(1), match.group(2)))
            return f"\x00LINK{idx}\x00"

        text = re.sub(link_pattern, save_link, text)

        # Step 3: Escape special characters in remaining text
        for char in self.MARKDOWN_V2_SPECIAL:
            text = text.replace(char, f"\\{char}")

        # Step 4: Restore links with properly escaped text
        for idx, (link_text, url_placeholder) in enumerate(links):
            # Escape the link text (but not brackets/parens)
            escaped_text = link_text
            for char in self.MARKDOWN_V2_SPECIAL:
                if char in ["[", "]", "(", ")"]:
                    continue
                escaped_text = escaped_text.replace(char, f"\\{char}")

            # Find the actual URL from saved URLs
            if url_placeholder.startswith("\x00URL") and url_placeholder.endswith(
                "\x00"
            ):
                url_idx = int(
                    url_placeholder.replace("\x00URL", "").replace("\x00", "")
                )
                actual_url = urls[url_idx]
            else:
                actual_url = url_placeholder

            restored_link = f"[{escaped_text}]({actual_url})"
            text = text.replace(f"\x00LINK{idx}\x00", restored_link)

        # Step 5: Restore any remaining standalone URLs (escaped as plain text)
        for idx, url in enumerate(urls):
            # URLs that are not inside links need to be escaped
            escaped_url = url
            for char in self.MARKDOWN_V2_SPECIAL:
                escaped_url = escaped_url.replace(char, f"\\{char}")
            text = text.replace(f"\x00URL{idx}\x00", escaped_url)

        return text

    def _convert_to_html(self, text: str) -> str:
        """Convert markdown to HTML format."""
        # Convert bold
        text = re.sub(r"\*([^*]+)\*", r"<b>\1</b>", text)
        # Convert italic
        text = re.sub(r"_([^_]+)_", r"<i>\1</i>", text)
        # Convert links
        text = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r'<a href="\2">\1</a>', text)

        return text
