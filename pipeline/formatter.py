"""
Post formatter for Telegram markdown.

Converts and validates content for Telegram's MarkdownV2 format.
"""

from __future__ import annotations

import re
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


class PostFormatter:
    """
    Formats posts for Telegram publishing.

    Handles MarkdownV2 conversion and character escaping.
    Supports the new structured post format with all required blocks.
    """

    # Characters that need escaping in MarkdownV2 (outside of URLs)
    MARKDOWN_V2_ESCAPE_CHARS = [
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
    ]

    # Required blocks for the new format (optional - used for best practices)
    REQUIRED_BLOCKS = [
        "🔍",  # Key facts
        "🧠",  # Analysis
        "🔗",  # Sources
        "💡",  # TLDR
    ]

    # Whether structure validation is strict
    STRICT_STRUCTURE = False

    def __init__(
        self,
        parse_mode: str = "MarkdownV2",
        max_length: int = 4096,
        ensure_structure: bool = True,
    ) -> None:
        """
        Initialize post formatter.

        Args:
            parse_mode: Telegram parse mode (MarkdownV2, HTML, or None)
            max_length: Maximum post length
            ensure_structure: Whether to validate/enforce post structure
        """
        self.parse_mode = parse_mode
        self.max_length = max_length
        self.ensure_structure = ensure_structure

    def escape_markdown_v2(self, text: str) -> str:
        """
        Escape special characters for MarkdownV2.

        Args:
            text: Text to escape

        Returns:
            str: Escaped text
        """
        # Escape special characters
        for char in self.MARKDOWN_V2_ESCAPE_CHARS:
            text = text.replace(char, f"\\{char}")

        return text

    def _escape_markdown_v2_with_links(self, text: str) -> str:
        """
        Escape text for MarkdownV2 while preserving links.

        Links in format [text](url) need special handling:
        - Text inside [] must be escaped
        - URL inside () must NOT be escaped

        Args:
            text: Text to escape

        Returns:
            str: Escaped text with working links
        """
        import re

        # Step 1: Extract and preserve URLs first (before any escaping)
        url_pattern = re.compile(r"(https?://[^\s\)\]\>]+)")
        urls = []
        url_counter = [0]

        def save_url(match):
            idx = url_counter[0]
            url_counter[0] += 1
            urls.append(match.group(1))
            return f"\x00URL{idx}\x00"

        text = url_pattern.sub(save_url, text)

        # Step 2: Extract links [text](url_placeholder)
        link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
        links = []
        placeholder_idx = [0]

        def replace_link(match):
            link_text = match.group(1)
            link_url = match.group(2)
            placeholder = f"\x00LINK{placeholder_idx[0]}\x00"
            links.append((placeholder, link_text, link_url))
            placeholder_idx[0] += 1
            return placeholder

        text = link_pattern.sub(replace_link, text)

        # Step 3: Escape all special characters in remaining text
        for char in self.MARKDOWN_V2_ESCAPE_CHARS:
            text = text.replace(char, f"\\{char}")

        # Step 4: Restore links with escaped text but unescaped URL
        for placeholder, link_text, link_url in links:
            # Escape the link text (but not brackets/parens)
            escaped_text = link_text
            for char in self.MARKDOWN_V2_ESCAPE_CHARS:
                if char in ["[", "]", "(", ")"]:
                    continue
                escaped_text = escaped_text.replace(char, f"\\{char}")

            # Find the actual URL from saved URLs
            if link_url.startswith("\x00URL") and link_url.endswith("\x00"):
                url_idx = int(link_url.replace("\x00URL", "").replace("\x00", ""))
                actual_url = urls[url_idx]
            else:
                actual_url = link_url

            text = text.replace(placeholder, f"[{escaped_text}]({actual_url})")

        # Step 5: Restore any remaining standalone URLs (escaped as plain text)
        for idx, url in enumerate(urls):
            # URLs that are not inside links need to be escaped
            escaped_url = url
            for char in self.MARKDOWN_V2_ESCAPE_CHARS:
                escaped_url = escaped_url.replace(char, f"\\{char}")
            text = text.replace(f"\x00URL{idx}\x00", escaped_url)

        return text

    def format_bold(self, text: str) -> str:
        """Format text as bold."""
        if self.parse_mode == "MarkdownV2":
            return f"*{text}*"
        elif self.parse_mode == "HTML":
            return f"<b>{text}</b>"
        return text

    def format_italic(self, text: str) -> str:
        """Format text as italic."""
        if self.parse_mode == "MarkdownV2":
            return f"_{text}_"
        elif self.parse_mode == "HTML":
            return f"<i>{text}</i>"
        return text

    def format_link(self, text: str, url: str) -> str:
        """Format text as a link."""
        if self.parse_mode == "MarkdownV2":
            return f"[{text}]({url})"
        elif self.parse_mode == "HTML":
            return f'<a href="{url}">{text}</a>'
        return f"{text} ({url})"

    def format_code(self, text: str) -> str:
        """Format text as inline code."""
        if self.parse_mode == "MarkdownV2":
            return f"`{text}`"
        elif self.parse_mode == "HTML":
            return f"<code>{text}</code>"
        return text

    def format_code_block(self, text: str, language: str = "") -> str:
        """Format text as code block."""
        if self.parse_mode == "MarkdownV2":
            return f"```{language}\n{text}\n```"
        elif self.parse_mode == "HTML":
            return f"<pre><code>{text}</code></pre>"
        return text

    def convert_to_markdown_v2(self, content: str) -> str:
        """
        Convert content to MarkdownV2 format.

        Handles existing markdown and escapes properly.
        Preserves links so URLs don't get escaped.
        Fixes unbalanced markers automatically.

        Args:
            content: Content to convert

        Returns:
            str: MarkdownV2 formatted content
        """
        if self.parse_mode != "MarkdownV2":
            return content

        # First, fix unbalanced markers by escaping all _ and * that aren't part of proper markdown
        content = self._fix_unbalanced_markers(content)

        # Use the new method that handles links properly
        return self._escape_markdown_v2_with_links(content)

    def _fix_unbalanced_markers(self, content: str) -> str:
        """
        Fix unbalanced markdown markers by escaping stray ones.

        Args:
            content: Content to fix

        Returns:
            str: Content with balanced or escaped markers
        """
        # Count markers (excluding escaped ones)
        # For simplicity, escape all standalone _ and * that might cause issues
        # This is safer than trying to balance them

        lines = content.split("\n")
        fixed_lines = []

        for line in lines:
            # Skip lines that look like they have intentional markdown
            # (pairs of * or _ around text)
            if "*" in line:
                # Count unescaped asterisks
                count = line.count("*")
                if count % 2 != 0:
                    # Odd number - escape one to make it even
                    # Find the last unescaped * and escape it
                    parts = line.rsplit("*", 1)
                    if len(parts) == 2:
                        line = parts[0] + "\\*" + parts[1]

            # Note: _ escaping is handled by _escape_markdown_v2_with_links
            # Don't pre-escape here to avoid double-escaping

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def truncate(self, content: str, max_length: Optional[int] = None) -> str:
        """
        Truncate content to maximum length while preserving structure.

        Args:
            content: Content to truncate
            max_length: Maximum length (uses self.max_length if not specified)

        Returns:
            str: Truncated content (never exceeds max_length)
        """
        max_length = max_length or self.max_length

        if len(content) <= max_length:
            return content

        # Account for ellipsis in the final length
        ellipsis = "..."
        available = max_length - len(ellipsis)

        # Try to preserve the most important blocks
        # Priority: headline, main content, TLDR, hashtags
        # Sources and links can be truncated if needed

        truncated = content[:available]

        # Find a good break point
        last_para = truncated.rfind("\n\n")
        if last_para > available * 0.7:
            return truncated[:last_para].strip() + "\n\n..."

        # Try sentence break
        last_sentence = max(
            truncated.rfind(". "),
            truncated.rfind("! "),
            truncated.rfind("? "),
        )
        if last_sentence > available * 0.7:
            return truncated[: last_sentence + 1].strip() + "..."

        # Word boundary
        last_space = truncated.rfind(" ")
        if last_space > available * 0.8:
            return truncated[:last_space].strip() + "..."

        return truncated.strip() + "..."

    def normalize_whitespace(self, content: str) -> str:
        """
        Normalize whitespace in content.

        Args:
            content: Content to normalize

        Returns:
            str: Normalized content
        """
        # Replace multiple spaces with single space
        content = re.sub(r"[^\S\n]+", " ", content)

        # Replace more than 2 consecutive newlines with 2
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Remove trailing whitespace from lines
        content = "\n".join(line.rstrip() for line in content.split("\n"))

        return content.strip()

    def validate_structure(self, content: str) -> tuple[bool, list[str]]:
        """
        Validate that content has all required blocks.

        Args:
            content: Post content to validate

        Returns:
            tuple[bool, list[str]]: (is_valid, missing_blocks)
        """
        missing = []

        for marker in self.REQUIRED_BLOCKS:
            if marker not in content:
                # Map marker to block name
                block_names = {
                    "🔍": "Key Facts (🔍 Что важно знать)",
                    "🧠": "Analysis (🧠 Почему это важно)",
                    "🔗": "Sources (🔗 Источники)",
                    "💡": "TLDR (💡 TL;DR)",
                }
                missing.append(block_names.get(marker, f"Block with {marker}"))

        # If STRICT_STRUCTURE is False, always return True (just warn)
        if not self.STRICT_STRUCTURE and missing:
            logger.warning(f"Post missing recommended blocks (non-blocking): {missing}")
            return True, []  # Return valid even with missing blocks

        return len(missing) == 0, missing

    def ensure_hashtags_at_end(self, content: str, hashtags: list[str]) -> str:
        """
        Ensure hashtags are at the end of the content.

        Args:
            content: Post content
            hashtags: List of hashtags to include

        Returns:
            str: Content with hashtags at end
        """
        # Remove existing hashtags
        content = re.sub(r"\s*#\w+\s*$", "", content).strip()

        # Add hashtags
        if hashtags:
            hashtag_str = " ".join(f"#{tag}" for tag in hashtags)
            content = f"{content}\n\n{hashtag_str}"

        return content

    def extract_hashtags(self, content: str) -> list[str]:
        """
        Extract hashtags from content.

        Args:
            content: Post content

        Returns:
            list[str]: List of hashtags (without #)
        """
        return [tag.lstrip("#") for tag in re.findall(r"#\w+", content)]

    def remove_hashtags(self, content: str) -> str:
        """
        Remove hashtags from content.

        Args:
            content: Post content

        Returns:
            str: Content without hashtags
        """
        return re.sub(r"\s*#\w+", "", content).strip()

    def format(self, content: str, truncate: bool = True) -> str:
        """
        Full formatting pipeline.

        Args:
            content: Raw content
            truncate: Whether to truncate to max length

        Returns:
            str: Formatted content ready for Telegram
        """
        # Normalize whitespace
        formatted = self.normalize_whitespace(content)

        # Validate structure if enabled
        if self.ensure_structure:
            is_valid, missing = self.validate_structure(formatted)
            if not is_valid:
                logger.warning(f"Post missing required blocks: {missing}")

        # Convert to target format
        if self.parse_mode == "MarkdownV2":
            formatted = self.convert_to_markdown_v2(formatted)

        # Truncate if needed
        if truncate:
            formatted = self.truncate(formatted)

        logger.debug(f"Formatted post: {len(content)} -> {len(formatted)} chars")

        return formatted

    def validate_format(self, content: str) -> tuple[bool, Optional[str]]:
        """
        Validate content format.

        Args:
            content: Content to validate

        Returns:
            tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        # Check length - just warn, don't fail (will be truncated)
        if len(content) > self.max_length:
            logger.warning(
                f"Content will be truncated: {len(content)} > {self.max_length}"
            )

        # Check structure - only warn, don't fail
        if self.ensure_structure:
            is_valid, missing = self.validate_structure(content)
            if not is_valid:
                logger.warning(f"Missing recommended blocks: {', '.join(missing)}")

        # Note: Markdown markers are fixed automatically in convert_to_markdown_v2
        # So we don't need to fail on unbalanced markers here

        return True, None

    def preview(self, content: str, max_preview_length: int = 100) -> str:
        """
        Generate a preview of the content.

        Args:
            content: Post content
            max_preview_length: Maximum preview length

        Returns:
            str: Content preview
        """
        if len(content) <= max_preview_length:
            return content

        return content[:max_preview_length].rsplit(" ", 1)[0] + "..."

    def extract_headline(self, content: str) -> str:
        """
        Extract the headline from structured post.

        Args:
            content: Post content

        Returns:
            str: Headline or first line
        """
        lines = content.strip().split("\n")
        if lines:
            return lines[0].strip()
        return ""

    def extract_sources(self, content: str) -> list[tuple[str, str]]:
        """
        Extract source links from the Sources block.

        Args:
            content: Post content

        Returns:
            list[tuple[str, str]]: List of (name, url) tuples
        """
        sources = []

        # Find sources block
        sources_match = re.search(
            r"🔗.*?Источники:?\s*\n(.*?)(?=\n\n[⚡💡#]|$)", content, re.DOTALL
        )
        if sources_match:
            sources_text = sources_match.group(1)
            # Extract links
            for line in sources_text.split("\n"):
                line = line.strip()
                if line.startswith("•") or line.startswith("-"):
                    # Parse "Name — URL" or "Name: URL" format
                    link_match = re.search(r"([^—\-:]+)[—\-:]\s*(https?://\S+)", line)
                    if link_match:
                        name = link_match.group(1).strip()
                        url = link_match.group(2).strip()
                        sources.append((name, url))

        return sources
