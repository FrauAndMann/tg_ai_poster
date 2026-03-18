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
    # Thinking/reasoning indicators (but NOT JSON in code blocks)
    r"^(thinking|думаю|размышляю)\s*:",
    r"^\*\*?(thinking|думаю|размышления)\*\*?",
    r"```thinking",
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

# Key facts requirements
MIN_KEY_FACTS_COUNT = 4
MAX_KEY_FACTS_COUNT = 5
MIN_TLDR_SENTENCES = 1
MAX_TLDR_SENTENCES = 2

# Chinese/Japanese/Korean character detection (CJK Unified Ideographs)
# Matches Chinese characters, Japanese kanji, and Korean hanja
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002a6df\U0002a700-\U0002b73f\U0002b740-\U0002b81f\U0002b820-\U0002ceaf]")


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


@dataclass
class KeyFactsValidationResult:
    """
    Result of key facts validation.

    Attributes:
        is_valid: Whether key facts pass all checks
        score: Quality score (0-100)
        issues: List of issues found
        facts_count: Number of facts provided
        has_metrics: Whether at least one fact has a metric/number
        tldr_valid: Whether TLDR passes self-contained check
        tldr_sentence_count: Number of sentences in TLDR
    """

    is_valid: bool
    score: float
    issues: list[str] = field(default_factory=list)
    facts_count: int = 0
    has_metrics: bool = False
    tldr_valid: bool = True
    tldr_sentence_count: int = 0

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "issues": self.issues,
            "facts_count": self.facts_count,
            "has_metrics": self.has_metrics,
            "tldr_valid": self.tldr_valid,
            "tldr_sentence_count": self.tldr_sentence_count,
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
        self._meta_patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE) for p in LLM_META_PATTERNS
        ]
        self._question_patterns = [
            re.compile(p, re.IGNORECASE) for p in QUESTION_PATTERNS
        ]
        self._incomplete_patterns = [
            re.compile(p, re.IGNORECASE) for p in INCOMPLETE_PATTERNS
        ]
        # CJK character pattern for detecting Chinese/Japanese/Korean characters
        self._cjk_pattern = CJK_PATTERN

    def _check_cjk_characters(self, content: str) -> list[str]:
        """
        Check for Chinese/Japanese/Korean characters in content.

        GLM-5 and other Chinese models may sometimes output CJK characters
        which should not appear in Russian/English content.

        Args:
            content: Content to check

        Returns:
            List of issues found
        """
        issues = []
        matches = self._cjk_pattern.findall(content)

        if matches:
            # Get unique characters and show example
            unique_chars = list(set(matches))[:5]  # Show max 5 examples
            char_display = "".join(unique_chars)
            total_count = len(matches)
            issues.append(
                f"Chinese/Japanese characters detected ({total_count} found): '{char_display}...'"
            )
            logger.warning(
                f"CJK characters detected in content: {total_count} occurrences"
            )

        return issues

    def _check_meta_text(self, content: str) -> list[str]:
        """
        Check for LLM meta-text patterns.

        Args:
            content: Content to check

        Returns:
            List of found meta-text issues
        """
        issues = []
        content.lower()

        for pattern in self._meta_patterns:
            matches = pattern.findall(content)
            if matches:
                # Get first match as example
                match_example = (
                    matches[0][:50]
                    if isinstance(matches[0], str)
                    else str(matches[0])[:50]
                )
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
            ("\U0001f50d", "Key Facts block"),  # 🔍
            ("\U0001f9e0", "Analysis block"),  # 🧠
            ("\U0001f517", "Sources block"),  # 🔔
            ("\U0001f4a1", "TLDR block"),  # 💡
        ]

        missing_blocks = []
        for marker, name in required_markers:
            if marker not in content:
                missing_blocks.append(name)

        if missing_blocks:
            if self.strict_mode:
                critical.append(f"Missing required blocks: {', '.join(missing_blocks)}")
            else:
                warnings.append(
                    f"Missing recommended blocks: {', '.join(missing_blocks)}"
                )

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
            critical.append(
                f"Body too short: {len(body)} chars (min: {self.min_body_length})"
            )

        # Sentence count
        sentences = [
            s.strip()
            for s in body.replace("!", ".").replace("?", ".").split(".")
            if s.strip()
        ]
        if len(sentences) < self.min_body_sentences:
            critical.append(
                f"Too few sentences: {len(sentences)} (min: {self.min_body_sentences})"
            )

        # Check for numbers/metrics (content should have concrete data)
        has_numbers = bool(re.search(r"\d+[.,]?\d*%?", body))
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
        for field_name in REQUIRED_JSON_FIELDS:
            if field_name not in data or not data[field_name]:
                critical.append(f"Missing required field: {field_name}")

        # Check recommended fields
        for field_name in RECOMMENDED_JSON_FIELDS:
            if field_name not in data or not data[field_name]:
                warnings.append(f"Missing recommended field: {field_name}")

        # Check key_facts count
        key_facts = data.get("key_facts", [])
        if isinstance(key_facts, list) and len(key_facts) < MIN_KEY_FACTS:
            warnings.append(
                f"Too few key_facts: {len(key_facts)} (recommended: {MIN_KEY_FACTS}+)"
            )

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

        # Check for CJK characters (critical issue for GLM models)
        cjk_issues = self._check_cjk_characters(response)
        issues.extend(cjk_issues)
        score -= len(cjk_issues) * 40

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

        # Check for CJK characters (Chinese/Japanese/Korean)
        body = data.get("body", "")
        title = data.get("title", "")
        all_text = f"{title} {body}"
        cjk_issues = self._check_cjk_characters(all_text)
        if cjk_issues:
            critical.extend(cjk_issues)
            score -= len(cjk_issues) * 40  # Heavy penalty for CJK chars

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

        # Check for CJK characters (critical issue for GLM models)
        cjk_issues = self._check_cjk_characters(content)
        critical.extend(cjk_issues)
        score -= len(cjk_issues) * 40

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
        question_count = len(re.findall(r"[?]", content))
        sentence_count = len(
            [
                s
                for s in content.replace("!", ".").replace("?", ".").split(".")
                if s.strip()
            ]
        )
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

    def validate_key_facts(
        self, key_facts: list[str], tldr: Optional[str] = None
    ) -> KeyFactsValidationResult:
        """
        Validate key facts structure and quality.

        Requirements:
        - Exactly 4-5 key facts
        - Each fact must be a single sentence
        - Each fact must be independently verifiable
        - No overlapping facts
        - At least one fact should contain a metric/number

        TLDR requirements:
        - Maximum 2 sentences
        - Must be meaningful without reading full post
        - Must pass self-contained check

        Args:
            key_facts: List of key fact strings
            tldr: Optional TLDR string to validate

        Returns:
            KeyFactsValidationResult with validation outcome
        """
        issues: list[str] = []
        score = 100.0
        has_metrics = False

        # Normalize input
        if not isinstance(key_facts, list):
            key_facts = []

        facts_count = len(key_facts)

        # Check facts count (exactly 4-5)
        if facts_count < MIN_KEY_FACTS_COUNT:
            issues.append(
                f"Too few key facts: {facts_count} (required: {MIN_KEY_FACTS_COUNT}-{MAX_KEY_FACTS_COUNT})"
            )
            score -= 25
        elif facts_count > MAX_KEY_FACTS_COUNT:
            issues.append(
                f"Too many key facts: {facts_count} (required: {MIN_KEY_FACTS_COUNT}-{MAX_KEY_FACTS_COUNT})"
            )
            score -= 15

        # Check each fact structure
        for i, fact in enumerate(key_facts):
            if not isinstance(fact, str):
                issues.append(f"Fact #{i + 1} is not a string")
                score -= 10
                continue

            fact = fact.strip()

            # Check if fact is empty
            if not fact:
                issues.append(f"Fact #{i + 1} is empty")
                score -= 15
                continue

            # Check for single sentence (no compound facts with multiple sentences)
            # Split by common sentence terminators
            sentences = re.split(r"[.!?。।]", fact)
            non_empty_sentences = [s.strip() for s in sentences if s.strip()]

            if len(non_empty_sentences) > 1:
                issues.append(
                    f"Fact #{i + 1} contains multiple sentences (compound fact): '{fact[:50]}...'"
                )
                score -= 10

            # Check for compound facts with "and" connecting separate claims
            # Look for patterns like "X did Y and Z did W" or "X is Y and Z is W"
            compound_patterns = [
                r"\s+и\s+.{10,}\s+и\s+",  # Multiple "и" in Russian
                r"\s+and\s+.{10,}\s+and\s+",  # Multiple "and" in English
            ]
            for pattern in compound_patterns:
                if re.search(pattern, fact, re.IGNORECASE):
                    issues.append(
                        f"Fact #{i + 1} appears to be compound (multiple claims): '{fact[:50]}...'"
                    )
                    score -= 8
                    break

            # Check for numbers/metrics
            if re.search(r"\d+[.,]?\d*%?", fact):
                has_metrics = True

        # Check for overlapping facts
        if facts_count >= 2:
            overlap_issues = self._check_fact_overlaps(key_facts)
            issues.extend(overlap_issues)
            score -= len(overlap_issues) * 12

        # Check if at least one fact has metrics
        if facts_count >= MIN_KEY_FACTS_COUNT and not has_metrics:
            issues.append("No key facts contain metrics or numbers")
            score -= 10

        # Validate TLDR if provided
        tldr_valid = True
        tldr_sentence_count = 0

        if tldr:
            tldr_result = self._validate_tldr(tldr)
            tldr_valid = tldr_result["is_valid"]
            tldr_sentence_count = tldr_result["sentence_count"]
            if not tldr_valid:
                issues.extend(tldr_result["issues"])
                score -= len(tldr_result["issues"]) * 10

        score = max(0, min(100, score))

        return KeyFactsValidationResult(
            is_valid=len(issues) == 0,
            score=score,
            issues=issues,
            facts_count=facts_count,
            has_metrics=has_metrics,
            tldr_valid=tldr_valid,
            tldr_sentence_count=tldr_sentence_count,
        )

    def _check_fact_overlaps(self, key_facts: list[str]) -> list[str]:
        """
        Check for overlapping/duplicate facts.

        Args:
            key_facts: List of key facts

        Returns:
            List of overlap issues
        """
        issues = []

        # Normalize facts for comparison
        normalized_facts = []
        for fact in key_facts:
            if isinstance(fact, str):
                # Convert to lowercase and remove extra whitespace
                normalized = " ".join(fact.lower().split())
                # Remove numbers for semantic comparison
                normalized_no_nums = re.sub(r"\d+[.,]?\d*%?", "", normalized)
                normalized_facts.append((normalized, normalized_no_nums))

        # Compare each pair of facts
        for i in range(len(normalized_facts)):
            for j in range(i + 1, len(normalized_facts)):
                fact1, fact1_no_nums = normalized_facts[i]
                fact2, fact2_no_nums = normalized_facts[j]

                # Check for high similarity (without numbers)
                if self._calculate_similarity(fact1_no_nums, fact2_no_nums) > 0.7:
                    issues.append(
                        f"Facts #{i + 1} and #{j + 1} appear to overlap"
                    )

                # Check if one fact contains most of another
                if len(fact1_no_nums) > 20 and len(fact2_no_nums) > 20:
                    shorter = min(fact1_no_nums, fact2_no_nums, key=len)
                    longer = max(fact1_no_nums, fact2_no_nums, key=len)
                    if shorter in longer:
                        issues.append(
                            f"Facts #{i + 1} and #{j + 1} have overlapping content"
                        )

        return issues

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple word-based similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def _validate_tldr(self, tldr: str) -> dict:
        """
        Validate TLDR quality.

        Requirements:
        - Maximum 2 sentences (under 4 is ideal)
        - Must be meaningful without reading full post
        - No meta-language like "this post discusses"

        Args:
            tldr: TLDR string

        Returns:
            Dict with is_valid, sentence_count, and issues
        """
        issues = []

        if not isinstance(tldr, str):
            return {"is_valid": False, "sentence_count": 0, "issues": ["TLDR is not a string"]}

        tldr = tldr.strip()

        if not tldr:
            return {"is_valid": False, "sentence_count": 0, "issues": ["TLDR is empty"]}

        # Count sentences
        sentences = re.split(r"[.!?。।]", tldr)
        non_empty_sentences = [s.strip() for s in sentences if s.strip()]
        sentence_count = len(non_empty_sentences)

        # Check sentence count
        if sentence_count > MAX_TLDR_SENTENCES:
            issues.append(
                f"TLDR has too many sentences: {sentence_count} (max: {MAX_TLDR_SENTENCES})"
            )

        # Check for meta-language (self-referential phrases)
        meta_patterns = [
            r"этот\s+пост",
            r"данная\s+статья",
            r"этот\s+материал",
            r"в\s+данном\s+тексте",
            r"this\s+post",
            r"this\s+article",
            r"the\s+above\s+text",
            r"мы\s+обсудили",
            r"we\s+discussed",
            r"as\s+mentioned",
            r"как\s+упоминалось",
        ]

        for pattern in meta_patterns:
            if re.search(pattern, tldr, re.IGNORECASE):
                issues.append("TLDR contains self-referential/meta language")
                break

        # Check if TLDR is too short to be meaningful
        if len(tldr) < 20:
            issues.append("TLDR is too short to be meaningful")

        # Check if TLDR starts with vague phrases
        vague_starts = [
            r"^это\s+",
            r"^это\s+-\s+",
            r"^this\s+is\s+",
            r"^вот\s+",
        ]
        for pattern in vague_starts:
            if re.search(pattern, tldr, re.IGNORECASE):
                issues.append("TLDR starts with a vague phrase")
                break

        return {
            "is_valid": len(issues) == 0,
            "sentence_count": sentence_count,
            "issues": issues,
        }

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
                return (
                    False,
                    f"Critical issues: {'; '.join(result.critical_issues[:3])}",
                )
            return False, f"Quality score too low: {result.score}"

        return True, "Content is publication ready"


# Validation update
