"""
Content validator for ensuring posts are publication-ready.

Performs comprehensive validation to prevent LLM meta-text, reasoning,
incomplete content, and other issues from reaching the channel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


# LLM meta-text patterns that indicate the model is "thinking" instead of producing content
LLM_META_PATTERNS = [
    # Russian meta-text
    r"вот\s+(мой|этот|ваш|готовый|написанный)\s+пост",
    r"я\s+(создал|написал|подготовил|составил)\s+(для\s+вас\s+)?пост",
    r"ниже\s+(представлен|находится|расположен|приведён)",
    r"давайте\s+(рассмотрим|поговорим|обсудим)",
    r"в\s+(этом|данном)\s+(посте|материале|тексте)\s+(я|мы)\s+",
    r"хочу\s+(предложить|рассказать|показать)",
    r"сегодня\s+(я|мы)\s+(расскажу|рассмотрим|поговорим)",
    r"предлагаю\s+(вашему\s+вниманию|рассмотреть)",
    r"пост\s+(о\s+том|про\s+то)\s*,?\s*как",
    r"ссылка\s+на\s+источник",
    r"вот\s+что\s+(я|мы)\s+(узнал|нашёл| discovered)",

    # English meta-text
    r"here'?s?\s+(the|a|my|your)\s+post",
    r"i\s+(have\s+)?(created|written|prepared|made)\s+(a\s+)?post",
    r"below\s+(is|you'?ll?\s+find|you\s+can\s+see)",
    r"let'?s?\s+(discuss|explore|talk\s+about|dive\s+into)",
    r"in\s+(this|the)\s+(post|article)\s*,?\s*i\s+",
    r"i\s+want\s+to\s+(share|tell|show)",
    r"today\s+(we|i)\s+(will|are\s+going\s+to)",
    r"the\s+following\s+(post|content|text)",
    r"here\s+is\s+(what|the)",
    r"as\s+(an\s+)?ai",
    r"as\s+a\s+(language\s+)?model",

    # Thinking/reasoning indicators
    r"^(thinking|думаю|размышляю)\s*:",
    r"^\*\*?(thinking|думаю|размышления)\*\*?",
    r"```thinking",
    r"```json\s*\n\s*\{",  # JSON in code blocks (should be raw JSON)
]

# Question patterns that shouldn't be the main content
QUESTION_PATTERNS = [
    r"^задумывались\s+ли\s+вы",
    r"^знали\s+ли\s+вы",
    r"^хотите\s+ли\s+вы\s+узнать",
    r"^интересно\s+ли\s+вам",
    r"^а\s+что\s+если",
    r"^have\s+you\s+ever\s+wondered",
    r"^did\s+you\s+know",
    r"^would\s+you\s+like\s+to\s+know",
    r"^are\s+you\s+curious",
    r"^what\s+if",
]

# Incomplete content indicators
INCOMPLETE_PATTERNS = [
    r"\[требуется\s+добавить",
    r"\[нужно\s+заполнить",
    r"\[вставьте\s+здесь",
    r"\[to\s+be\s+added",
    r"\[insert\s+here",
    r"\[pending\]",
    r"\[tbd\]",
    r"\.\.\.\s*$",  # Ends with ellipsis
    r"продолжение\s+следует",
    r"to\s+be\s+continued",
]

# Required JSON fields for a valid post
REQUIRED_JSON_FIELDS = ["body"]
RECOMMENDED_JSON_FIELDS = ["title", "key_facts", "analysis", "tldr", "hashtags"]

# Minimum content requirements
MIN_BODY_LENGTH = 150
MIN_BODY_SENTENCES = 3
MIN_KEY_FACTS = 2


@dataclass
class ValidationResult:
    """
    Result of content validation.

    Attributes:
        is_valid: Whether content passes all critical checks
        is_ready: Whether content is ready for publication (may have warnings)
        score: Quality score (0-100)
        critical_issues: Issues that must be fixed before publication
        warnings: Non-blocking issues that should be reviewed
        needs_regeneration: Whether the content should be regenerated
        sanitized_content: Content with meta-text removed (if possible)
    """
    is_valid: bool
    is_ready: bool
    score: float
    critical_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    needs_regeneration: bool = False
    sanitized_content: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "is_ready": self.is_ready,
            "score": self.score,
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "needs_regeneration": self.needs_regeneration,
        }


class ContentValidator:
    """
    Comprehensive content validator for publication-ready posts.

    Performs multiple layers of validation:
    1. Meta-text detection (LLM thinking/reasoning)
    2. Incomplete content detection
    3. Structure validation
    4. Quality metrics
    """

    def __init__(
        self,
        strict_mode: bool = True,
        min_body_length: int = MIN_BODY_LENGTH,
        min_body_sentences: int = MIN_BODY_SENTENCES,
    ) -> None:
        """
        Initialize content validator.

        Args:
            strict_mode: If True, warnings become critical issues
            min_body_length: Minimum body text length
            min_body_sentences: Minimum number of sentences in body
        """
        self.strict_mode = strict_mode
        self.min_body_length = min_body_length
        self.min_body_sentences = min_body_sentences

        # Compile regex patterns for performance
        self._meta_patterns = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in LLM_META_PATTERNS]
        self._question_patterns = [re.compile(p, re.IGNORECASE) for p in QUESTION_PATTERNS]
        self._incomplete_patterns = [re.compile(p, re.IGNORECASE) for p in INCOMPLETE_PATTERNS]

    def _check_meta_text(self, content: str) -> list[str]:
        """
        Check for LLM meta-text patterns.

        Args:
            content: Content to check

        Returns:
            List of found meta-text issues
        """
        issues = []
        content_lower = content.lower()

        for pattern in self._meta_patterns:
            matches = pattern.findall(content)
            if matches:
                # Get first match as example
                match_example = matches[0][:50] if isinstance(matches[0], str) else str(matches[0])[:50]
                issues.append(f"LLM meta-text detected: '{match_example}...'")
                logger.warning(f"Meta-text pattern matched: {pattern.pattern}")

        return issues

    def _check_question_start(self, content: str) -> list[str]:
        """
        Check if content starts with generic questions.

        Args:
            content: Content to check

        Returns:
            List of issues
        """
        issues = []
        first_lines = content.strip()[:200].lower()

        for pattern in self._question_patterns:
            if pattern.search(first_lines):
                issues.append("Content starts with generic question (weak hook)")
                break

        return issues

    def _check_incomplete(self, content: str) -> list[str]:
        """
        Check for incomplete content indicators.

        Args:
            content: Content to check

        Returns:
            List of issues
        """
        issues = []

        for pattern in self._incomplete_patterns:
            matches = pattern.findall(content)
            if matches:
                issues.append(f"Incomplete content detected: '{matches[0][:30]}...'")

        return issues

    def _check_structure(self, content: str) -> tuple[list[str], list[str]]:
        """
        Check content structure.

        Args:
            content: Content to check

        Returns:
            Tuple of (critical_issues, warnings)
        """
        critical = []
        warnings = []

        # Check for required block markers
        required_markers = [
            ("\U0001F50D", "Key Facts block"),  # 🔍
            ("\U0001F9E0", "Analysis block"),    # 🧠
            ("\U0001F517", "Sources block"),     # 🔔
            ("\U0001F4A1", "TLDR block"),        # 💡
        ]

        missing_blocks = []
        for marker, name in required_markers:
            if marker not in content:
                missing_blocks.append(name)

        if missing_blocks:
            if self.strict_mode:
                critical.append(f"Missing required blocks: {', '.join(missing_blocks)}")
            else:
                warnings.append(f"Missing recommended blocks: {', '.join(missing_blocks)}")

        return critical, warnings

    def _check_body_quality(self, body: str) -> tuple[list[str], list[str]]:
        """
        Check body text quality.

        Args:
            body: Body text to check

        Returns:
            Tuple of (critical_issues, warnings)
        """
        critical = []
        warnings = []

        if not body:
            critical.append("Body text is empty")
            return critical, warnings

        # Length check
        if len(body) < self.min_body_length:
            critical.append(f"Body too short: {len(body)} chars (min: {self.min_body_length})")

        # Sentence count
        sentences = [s.strip() for s in body.replace('!', '.').replace('?', '.').split('.') if s.strip()]
        if len(sentences) < self.min_body_sentences:
            critical.append(f"Too few sentences: {len(sentences)} (min: {self.min_body_sentences})")

        # Check for numbers/metrics (content should have concrete data)
        has_numbers = bool(re.search(r'\d+[.,]?\d*%?', body))
        if not has_numbers:
            warnings.append("No numbers or metrics found in body")

        return critical, warnings

    def _check_json_structure(self, data: dict) -> tuple[list[str], list[str]]:
        """
        Validate JSON post structure.

        Args:
            data: Parsed JSON data

        Returns:
            Tuple of (critical_issues, warnings)
        """
        critical = []
        warnings = []

        # Check required fields
        for field in REQUIRED_JSON_FIELDS:
            if field not in data or not data[field]:
                critical.append(f"Missing required field: {field}")

        # Check recommended fields
        for field in RECOMMENDED_JSON_FIELDS:
            if field not in data or not data[field]:
                warnings.append(f"Missing recommended field: {field}")

        # Check key_facts count
        key_facts = data.get("key_facts", [])
        if isinstance(key_facts, list) and len(key_facts) < MIN_KEY_FACTS:
            warnings.append(f"Too few key_facts: {len(key_facts)} (recommended: {MIN_KEY_FACTS}+)")

        return critical, warnings

    def _sanitize_content(self, content: str) -> str:
        """
        Attempt to remove meta-text from content.

        Args:
            content: Content to sanitize

        Returns:
            Sanitized content
        """
        result = content

        # Remove common meta-text prefixes
        prefixes_to_remove = [
            r"^вот\s+(мой|этот|готовый)\s+пост\s*[.:]\s*",
            r"^here'?s?\s+(the|a|my)\s+post\s*[:.]?\s*",
            r"^ниже\s+(представлен|находится)\s+пост\s*[:.]?\s*",
            r"^below\s+(is|you'?ll?\s+find)\s+(the\s+)?post\s*[:.]?\s*",
        ]

        for pattern in prefixes_to_remove:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        return result.strip()

    def validate_raw_response(self, response: str) -> ValidationResult:
        """
        Validate raw LLM response before JSON parsing.

        Use this to catch LLM reasoning/meta-text early.

        Args:
            response: Raw LLM response

        Returns:
            ValidationResult with issues found
        """
        issues = []
        score = 100.0

        # Check for meta-text
        meta_issues = self._check_meta_text(response)
        issues.extend(meta_issues)
        score -= len(meta_issues) * 30

        # Check for incomplete content
        incomplete_issues = self._check_incomplete(response)
        issues.extend(incomplete_issues)
        score -= len(incomplete_issues) * 25

        # Check for question start
        question_issues = self._check_question_start(response)
        issues.extend(question_issues)
        score -= len(question_issues) * 15

        score = max(0, min(100, score))

        is_valid = len(issues) == 0
        needs_regeneration = score < 50

        return ValidationResult(
            is_valid=is_valid,
            is_ready=score >= 60,
            score=score,
            critical_issues=issues if not is_valid else [],
            warnings=[],
            needs_regeneration=needs_regeneration,
            sanitized_content=self._sanitize_content(response) if issues else None,
        )

    def validate_json_post(self, data: dict) -> ValidationResult:
        """
        Validate parsed JSON post data.

        Args:
            data: Parsed JSON post data

        Returns:
            ValidationResult with comprehensive checks
        """
        critical = []
        warnings = []
        score = 100.0

        # Check JSON structure
        json_critical, json_warnings = self._check_json_structure(data)
        critical.extend(json_critical)
        warnings.extend(json_warnings)
        score -= len(json_critical) * 25
        score -= len(json_warnings) * 5

        # Get body text for further checks
        body = data.get("body", "")
        if isinstance(body, str):
            # Check body quality
            body_critical, body_warnings = self._check_body_quality(body)
            critical.extend(body_critical)
            warnings.extend(body_warnings)
            score -= len(body_critical) * 20
            score -= len(body_warnings) * 5

            # Check for meta-text in body
            meta_issues = self._check_meta_text(body)
            critical.extend(meta_issues)
            score -= len(meta_issues) * 30

        # Check title if present
        title = data.get("title", "")
        if isinstance(title, str):
            meta_in_title = self._check_meta_text(title)
            if meta_in_title:
                critical.append("Meta-text detected in title")
                score -= 25

        score = max(0, min(100, score))

        is_valid = len(critical) == 0
        is_ready = score >= 60 and len(critical) == 0
        needs_regeneration = score < 50 or len(critical) >= 2

        return ValidationResult(
            is_valid=is_valid,
            is_ready=is_ready,
            score=score,
            critical_issues=critical,
            warnings=warnings,
            needs_regeneration=needs_regeneration,
        )

    def validate_formatted_post(self, content: str) -> ValidationResult:
        """
        Validate formatted post content (after JSON rendering).

        Args:
            content: Formatted post text

        Returns:
            ValidationResult with final checks
        """
        critical = []
        warnings = []
        score = 100.0

        # Check for meta-text
        meta_issues = self._check_meta_text(content)
        critical.extend(meta_issues)
        score -= len(meta_issues) * 30

        # Check for incomplete content
        incomplete_issues = self._check_incomplete(content)
        critical.extend(incomplete_issues)
        score -= len(incomplete_issues) * 25

        # Check structure
        struct_critical, struct_warnings = self._check_structure(content)
        critical.extend(struct_critical)
        warnings.extend(struct_warnings)
        score -= len(struct_critical) * 15
        score -= len(struct_warnings) * 5

        # Length check
        if len(content) < 100:
            critical.append(f"Post too short: {len(content)} chars")
            score -= 30

        # Check for question-only content
        question_count = len(re.findall(r'[?]', content))
        sentence_count = len([s for s in content.replace('!', '.').replace('?', '.').split('.') if s.strip()])
        if sentence_count > 0 and question_count / sentence_count > 0.5:
            warnings.append("Post contains too many questions")
            score -= 10

        score = max(0, min(100, score))

        is_valid = len(critical) == 0
        is_ready = score >= 60
        needs_regeneration = score < 50 or len(critical) >= 2

        return ValidationResult(
            is_valid=is_valid,
            is_ready=is_ready,
            score=score,
            critical_issues=critical,
            warnings=warnings,
            needs_regeneration=needs_regeneration,
            sanitized_content=self._sanitize_content(content) if meta_issues else None,
        )

    def is_publication_ready(self, content: str | dict) -> tuple[bool, str]:
        """
        Quick check if content is ready for publication.

        Args:
            content: Content to check (string or dict)

        Returns:
            Tuple of (is_ready, reason)
        """
        if isinstance(content, dict):
            result = self.validate_json_post(content)
        else:
            result = self.validate_formatted_post(content)

        if not result.is_ready:
            if result.critical_issues:
                return False, f"Critical issues: {'; '.join(result.critical_issues[:3])}"
            return False, f"Quality score too low: {result.score}"

        return True, "Content is publication ready"
# Validation update
