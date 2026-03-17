"""
Content validators for post quality and safety.

Provides validation functions for duplicate detection, forbidden words,
length checks, and Telegram markdown validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional, Tuple

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """
    Result of content validation.

    Attributes:
        is_valid: Whether content passes validation
        score: Quality score (0-100)
        issues: List of issues found
        warnings: List of warnings (non-blocking issues)
    """

    is_valid: bool
    score: float = 100.0
    issues: list[str] = None
    warnings: list[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "issues": self.issues,
            "warnings": self.warnings,
        }


def check_duplicate(
    content: str,
    recent_contents: list[str],
    threshold: float = 0.85,
) -> Tuple[bool, Optional[str]]:
    """
    Check if content is too similar to recent posts.

    Uses sequence matching for similarity detection.

    Args:
        content: Content to check
        recent_contents: List of recent post contents
        threshold: Similarity threshold (0.0-1.0)

    Returns:
        tuple[bool, Optional[str]]: (is_unique, similarity_info)
    """
    if not recent_contents:
        return True, None

    content_lower = content.lower().strip()

    for i, recent in enumerate(recent_contents):
        recent_lower = recent.lower().strip()

        # Calculate similarity ratio
        similarity = SequenceMatcher(None, content_lower, recent_lower).ratio()

        if similarity >= threshold:
            return False, f"Similar to post #{i + 1} ({similarity:.0%})"

    # Also check for exact phrase matches
    content_words = set(content_lower.split())

    for i, recent in enumerate(recent_contents):
        recent_words = set(recent.lower().split())

        # Check for high word overlap
        if content_words and recent_words:
            overlap = len(content_words & recent_words) / len(content_words)

            if overlap > 0.8:
                return False, f"High word overlap with post #{i + 1} ({overlap:.0%})"

    return True, None


def check_forbidden_words(
    content: str,
    forbidden_list: list[str],
    case_sensitive: bool = False,
) -> Tuple[bool, list[str]]:
    """
    Check for forbidden words in content.

    Args:
        content: Content to check
        forbidden_list: List of forbidden words/phrases
        case_sensitive: Whether to do case-sensitive matching

    Returns:
        tuple[bool, list[str]]: (is_clean, list_of_found_words)
    """
    if not forbidden_list:
        return True, []

    check_content = content if case_sensitive else content.lower()
    found = []

    for word in forbidden_list:
        check_word = word if case_sensitive else word.lower()

        if check_word in check_content:
            found.append(word)

    return len(found) == 0, found


def check_length(
    content: str,
    min_length: int,
    max_length: int,
) -> Tuple[bool, Optional[str]]:
    """
    Check if content length is within bounds.

    Args:
        content: Content to check
        min_length: Minimum length
        max_length: Maximum length

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    length = len(content)

    if length < min_length:
        return False, f"Too short: {length} chars (min: {min_length})"

    if length > max_length:
        return False, f"Too long: {length} chars (max: {max_length})"

    return True, None


def check_telegram_markdown(content: str) -> Tuple[bool, list[str]]:
    """
    Validate Telegram markdown formatting.

    Checks for:
    - Unbalanced bold/italic markers
    - Invalid markdown headers
    - Broken link syntax

    Args:
        content: Content to validate

    Returns:
        tuple[bool, list[str]]: (is_valid, list_of_issues)
    """
    issues = []

    # Check for unbalanced bold markers
    bold_count = content.count("*")
    if bold_count % 2 != 0:
        issues.append(f"Unbalanced bold markers: {bold_count} asterisks")

    # Check for unbalanced italic markers
    # Note: underscores in words are valid, only check pairs
    re.compile(r"(?<!\\)_(?![\s_])(.*?)(?<![\s\\])_(?![\w])", re.DOTALL)

    # Check for markdown headers (not supported)
    if re.search(r"^#+\s", content, re.MULTILINE):
        issues.append("Markdown headers not supported in Telegram")

    # Check for broken link syntax
    # Links should be [text](url)
    broken_links = re.findall(r"\[[^\]]*$", content)
    if broken_links:
        issues.append("Unclosed link bracket detected")

    # Check for malformed URLs in links
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for match in link_pattern.finditer(content):
        url = match.group(2)
        if not url.startswith(("http://", "https://", "tg://")):
            if not re.match(r"^[\w\-\.]+", url):  # Allow relative-looking URLs
                issues.append(f"Potentially malformed URL in link: {url[:30]}")

    return len(issues) == 0, issues


def check_emoji_count(
    content: str,
    min_emojis: int,
    max_emojis: int,
) -> Tuple[bool, Optional[str]]:
    """
    Check emoji count in content.

    Args:
        content: Content to check
        min_emojis: Minimum emoji count
        max_emojis: Maximum emoji count

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    # Note: Using character class without + quantifier to count individual emojis
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # Emoticons
        "\U0001f300-\U0001f5ff"  # Misc Symbols and Pictographs
        "\U0001f680-\U0001f6ff"  # Transport and Map
        "\U0001f1e0-\U0001f1ff"  # Flags (regional)
        "\U00002702-\U000027b0"  # Dingbats
        "\U000024c2-\U0001f251"  # Enclosed characters
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols A
        "\U00002600-\U000026ff"  # Misc Symbols
        "\U00002b50-\U00002b55"  # Stars and circles
        "]",
        flags=re.UNICODE,
    )

    count = len(emoji_pattern.findall(content))

    if count < min_emojis:
        return False, f"Too few emojis: {count} (min: {min_emojis})"

    if count > max_emojis:
        return False, f"Too many emojis: {count} (max: {max_emojis})"

    return True, None


def check_hashtag_count(
    content: str,
    min_hashtags: int,
    max_hashtags: int,
) -> Tuple[bool, Optional[str]]:
    """
    Check hashtag count in content.

    Args:
        content: Content to check
        min_hashtags: Minimum hashtag count
        max_hashtags: Maximum hashtag count

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    count = len(re.findall(r"#\w+", content))

    if count < min_hashtags:
        return False, f"Too few hashtags: {count} (min: {min_hashtags})"

    if count > max_hashtags:
        return False, f"Too many hashtags: {count} (max: {max_hashtags})"

    return True, None


def check_hooks(content: str) -> Tuple[bool, Optional[str]]:
    """
    Check if content starts with a strong hook.

    Args:
        content: Content to check

    Returns:
        tuple[bool, Optional[str]]: (has_hook, suggestion)
    """
    first_sentence = content.split(".")[0] if "." in content else content

    # Check for question hook
    if first_sentence.strip().endswith("?"):
        return True, None

    # Check for shocking statement (contains numbers/stats)
    if re.search(
        r"\d+%|\d+\s*(million|billion|thousand|млн|млрд|тыс)", first_sentence, re.I
    ):
        return True, None

    # Check for "how to" or "why" openings
    if re.match(r"^(How|Why|What|Когда|Как|Почему|Что)", first_sentence, re.I):
        return True, None

    # Check for generic openings to avoid
    generic_patterns = [
        r"^in (today's|this) world",
        r"^it('s| is) important",
        r"^here('s| is)",
        r"^did you know",
        r"^в современном мире",
        r"^стоит отметить",
    ]

    for pattern in generic_patterns:
        if re.match(pattern, first_sentence, re.I):
            return False, "Generic opening detected - use a stronger hook"

    return True, None


def validate_post(
    content: str,
    min_length: int = 200,
    max_length: int = 4096,
    min_emojis: int = 1,
    max_emojis: int = 10,
    min_hashtags: int = 1,
    max_hashtags: int = 5,
    forbidden_words: Optional[list[str]] = None,
    recent_contents: Optional[list[str]] = None,
    similarity_threshold: float = 0.85,
) -> ValidationResult:
    """
    Comprehensive post validation.

    Args:
        content: Content to validate
        min_length: Minimum content length
        max_length: Maximum content length
        min_emojis: Minimum emoji count
        max_emojis: Maximum emoji count
        min_hashtags: Minimum hashtag count
        max_hashtags: Maximum hashtag count
        forbidden_words: List of forbidden words
        recent_contents: Recent posts for duplicate check
        similarity_threshold: Duplicate similarity threshold

    Returns:
        ValidationResult: Validation result with score and issues
    """
    issues = []
    warnings = []
    score = 100.0

    # Length check
    length_valid, length_error = check_length(content, min_length, max_length)
    if not length_valid:
        issues.append(length_error)
        score -= 20

    # Markdown check
    md_valid, md_issues = check_telegram_markdown(content)
    if not md_valid:
        issues.extend(md_issues)
        score -= 15

    # Emoji check
    emoji_valid, emoji_error = check_emoji_count(content, min_emojis, max_emojis)
    if not emoji_valid:
        warnings.append(emoji_error)
        score -= 5

    # Hashtag check
    hashtag_valid, hashtag_error = check_hashtag_count(
        content, min_hashtags, max_hashtags
    )
    if not hashtag_valid:
        warnings.append(hashtag_error)
        score -= 5

    # Forbidden words check
    if forbidden_words:
        clean, found = check_forbidden_words(content, forbidden_words)
        if not clean:
            issues.append(f"Forbidden words found: {', '.join(found)}")
            score -= 30

    # Duplicate check
    if recent_contents:
        unique, dup_info = check_duplicate(
            content, recent_contents, similarity_threshold
        )
        if not unique:
            issues.append(dup_info)
            score -= 25

    # Hook check
    has_hook, hook_suggestion = check_hooks(content)
    if not has_hook:
        warnings.append(hook_suggestion)
        score -= 10

    # Ensure score is in bounds
    score = max(0, min(100, score))

    is_valid = len(issues) == 0 and score >= 50

    return ValidationResult(
        is_valid=is_valid,
        score=score,
        issues=issues,
        warnings=warnings,
    )


def sanitize_content(content: str) -> str:
    """
    Sanitize content for safe publishing.

    Removes or escapes potentially problematic content.

    Args:
        content: Content to sanitize

    Returns:
        str: Sanitized content
    """
    # Remove null bytes
    content = content.replace("\x00", "")

    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive newlines
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Remove trailing whitespace from lines
    content = "\n".join(line.rstrip() for line in content.split("\n"))

    # Remove control characters except newlines and tabs
    content = "".join(char for char in content if char.isprintable() or char in "\n\t")

    return content.strip()
