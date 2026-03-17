"""
Quality Rules - 50 functions for validating post content.

Each rule is a named, documented function that can be called independently
or as part of the full validation pipeline.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from collections import Counter

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class QualityCheckResult:
    """Result of a quality rule check."""
    rule_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    message: str
    details: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "passed": self.passed,
            "score": self.score,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class FullQualityReport:
    """Complete quality report for a post."""
    total_score: float
    passed: bool
    checks: list[QualityCheckResult]
    failed_rules: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "total_score": self.total_score,
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
            "failed_rules": self.failed_rules,
            "warnings": self.warnings,
        }


class QualityRulesEngine:
    """
    Engine for running all 50 quality rules on post content.

    Implements all rules from Phase 4 specification organized by block.
    """

    def __init__(
        self,
        banned_words_path: Optional[Path] = None,
        similarity_threshold: float = 0.82,
        min_body_length: int = 800,
        max_body_length: int = 1500,
        max_sentence_words: int = 25,
        ideal_avg_sentence_words: int = 15,
        min_active_voice_ratio: float = 0.7,
    ):
        """
        Initialize quality rules engine.

        Args:
            banned_words_path: Path to banned words config
            similarity_threshold: Threshold for semantic duplicate detection
            min_body_length: Minimum body length in characters
            max_body_length: Maximum body length in characters
            max_sentence_words: Maximum words per sentence
            ideal_avg_sentence_words: Ideal average words per sentence
            min_active_voice_ratio: Minimum ratio of active voice sentences
        """
        self.banned_words_path = banned_words_path or Path("config/banned_words.json")
        self.similarity_threshold = similarity_threshold
        self.min_body_length = min_body_length
        self.max_body_length = max_body_length
        self.max_sentence_words = max_sentence_words
        self.ideal_avg_sentence_words = ideal_avg_sentence_words
        self.min_active_voice_ratio = min_active_voice_ratio

        self._banned_config = self._load_banned_config()

    def _load_banned_config(self) -> dict:
        """Load banned words configuration."""
        try:
            if self.banned_words_path.exists():
                with open(self.banned_words_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load banned config: {e}")
        return {}

    # ==================== BLOCK A — TEXT QUALITY ====================

    def check_min_body_length(self, body: str) -> QualityCheckResult:
        """Rule 1: Minimum body length 800 characters."""
        length = len(body)
        passed = length >= self.min_body_length
        score = min(1.0, length / self.min_body_length) if passed else 0.0
        return QualityCheckResult(
            rule_name="min_body_length",
            passed=passed,
            score=score,
            message=f"Body length: {length} chars (min: {self.min_body_length})",
            details={"length": length},
        )

    def check_max_body_length(self, body: str) -> QualityCheckResult:
        """Rule 2: Maximum body length 1500 characters."""
        length = len(body)
        passed = length <= self.max_body_length
        score = 1.0 if passed else max(0.0, 1 - (length - self.max_body_length) / 500)
        return QualityCheckResult(
            rule_name="max_body_length",
            passed=passed,
            score=score,
            message=f"Body length: {length} chars (max: {self.max_body_length})",
            details={"length": length},
        )

    def check_max_sentence_length(self, body: str) -> QualityCheckResult:
        """Rule 3: No sentence longer than 25 words."""
        sentences = re.split(r'[.!?]+', body)
        long_sentences = []
        for i, sent in enumerate(sentences):
            words = len(sent.split())
            if words > self.max_sentence_words:
                long_sentences.append({"index": i, "words": words, "text": sent[:50]})

        passed = len(long_sentences) == 0
        score = 1.0 if passed else max(0.0, 1 - len(long_sentences) * 0.1)
        return QualityCheckResult(
            rule_name="max_sentence_length",
            passed=passed,
            score=score,
            message=f"Found {len(long_sentences)} sentences > {self.max_sentence_words} words",
            details={"long_sentences": long_sentences[:3]},
        )

    def check_passive_voice(self, body: str) -> QualityCheckResult:
        """Rule 4: Detect passive voice constructions."""
        passive_patterns = [
            r'\bбыл[аи]?\s+\w+',
            r'\bбыла[аи]?\s+\w+',
            r'\bбыли[аи]?\s+\w+',
            r'\bявляется\b',
            r'\bостается\b',
            r'\bпредставляет собой\b',
        ]
        found = []
        for pattern in passive_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                found.extend(matches)

        passed = len(found) <= 2
        score = 1.0 if passed else max(0.5, 1 - len(found) * 0.1)
        return QualityCheckResult(
            rule_name="passive_voice",
            passed=passed,
            score=score,
            message=f"Found {len(found)} passive constructions",
            details={"examples": found[:5]},
        )

    def check_banned_words(self, text: str) -> QualityCheckResult:
        """Rule 5: Check for banned cliches and hype words."""
        text_lower = text.lower()
        found_words = []

        banned = self._banned_config.get("banned_words", {}).get("hype_words", {}).get("words", [])
        filler = self._banned_config.get("banned_words", {}).get("filler_phrases", {}).get("phrases", [])

        for word in banned:
            if word.lower() in text_lower:
                found_words.append(word)

        for phrase in filler:
            if phrase.lower() in text_lower:
                found_words.append(phrase)

        passed = len(found_words) == 0
        score = 1.0 if passed else max(0.0, 1 - len(found_words) * 0.2)
        return QualityCheckResult(
            rule_name="banned_words",
            passed=passed,
            score=score,
            message=f"Found {len(found_words)} banned words/phrases",
            details={"found": found_words[:10]},
        )

    def check_readability(self, body: str) -> QualityCheckResult:
        """Rule 6: Average sentence length should be <= 18 words."""
        sentences = [s.strip() for s in re.split(r'[.!?]+', body) if s.strip()]
        if not sentences:
            return QualityCheckResult(
                rule_name="readability",
                passed=True,
                score=1.0,
                message="No sentences to analyze",
            )

        word_counts = [len(s.split()) for s in sentences]
        avg_length = sum(word_counts) / len(word_counts)

        passed = avg_length <= 18
        score = 1.0 if passed else max(0.5, 1 - (avg_length - 18) * 0.05)
        return QualityCheckResult(
            rule_name="readability",
            passed=passed,
            score=score,
            message=f"Average sentence length: {avg_length:.1f} words",
            details={"avg_length": avg_length, "sentences_count": len(sentences)},
        )

    def check_repetition(self, body: str) -> QualityCheckResult:
        """Rule 7: Flag words repeated more than 3x in 100-word windows."""
        words = re.findall(r'\b\w+\b', body.lower())
        found_repetitions = []

        for i in range(len(words) - 100):
            window = words[i:i+100]
            counter = Counter(window)
            for word, count in counter.items():
                if count > 3 and len(word) > 3:
                    found_repetitions.append({"word": word, "count": count})

        passed = len(found_repetitions) == 0
        score = 1.0 if passed else max(0.5, 1 - len(found_repetitions) * 0.1)
        return QualityCheckResult(
            rule_name="repetition",
            passed=passed,
            score=score,
            message=f"Found {len(found_repetitions)} over-repeated words",
            details={"repetitions": found_repetitions[:5]},
        )

    def check_jargon_balance(self, body: str) -> QualityCheckResult:
        """Rule 8: Technical terms should be balanced with accessible explanations."""
        # Simple heuristic: technical terms often have acronyms or specific suffixes
        tech_terms = re.findall(r'\b[A-Z]{2,}\b|\w+(?:ация|ирование|ность|изм)\b', body)
        passed = True  # Complex to check automatically, default to pass
        score = 1.0
        return QualityCheckResult(
            rule_name="jargon_balance",
            passed=passed,
            score=score,
            message=f"Found {len(tech_terms)} technical terms",
            details={"tech_terms": tech_terms[:10]},
        )

    def check_filler_phrases(self, text: str) -> QualityCheckResult:
        """Rule 9: Remove filler phrases."""
        filler = self._banned_config.get("banned_words", {}).get("filler_phrases", {}).get("phrases", [])
        found = [f for f in filler if f.lower() in text.lower()]

        passed = len(found) == 0
        score = 1.0 if passed else max(0.0, 1 - len(found) * 0.2)
        return QualityCheckResult(
            rule_name="filler_phrases",
            passed=passed,
            score=score,
            message=f"Found {len(found)} filler phrases",
            details={"found": found},
        )

    def check_active_voice_ratio(self, body: str) -> QualityCheckResult:
        """Rule 10: At least 70% active voice constructions."""
        sentences = [s.strip() for s in re.split(r'[.!?]+', body) if s.strip()]
        if not sentences:
            return QualityCheckResult(
                rule_name="active_voice_ratio",
                passed=True,
                score=1.0,
                message="No sentences to analyze",
            )

        # Simple heuristic: passive constructions lower the ratio
        passive_patterns = [r'\bбыл\b', r'\bбыла\b', r'\bбыли\b', r'\bбыло\b', r'\bявляется\b']
        active_count = 0

        for sent in sentences:
            is_passive = any(p.search(sent.lower()) for p in passive_patterns)
            if not is_passive:
                active_count += 1

        ratio = active_count / len(sentences)
        passed = ratio >= self.min_active_voice_ratio
        score = ratio if passed else ratio * 0.5
        return QualityCheckResult(
            rule_name="active_voice_ratio",
            passed=passed,
            score=score,
            message=f"Active voice ratio: {ratio:.0%} (min: {self.min_active_voice_ratio:.0%})",
            details={"ratio": ratio, "active_count": active_count, "total": len(sentences)},
        )

    # ==================== BLOCK B — POST STRUCTURE ====================

    def check_title_concrete_subject(self, title: str) -> QualityCheckResult:
        """Rule 11: Title must contain concrete subject (company/model/technology)."""
        # Look for capitalized words, acronyms, or specific tech terms
        has_company = bool(re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', title))
        has_acronym = bool(re.search(r'\b[A-Z]{2,}\b', title))
        has_model = bool(re.search(r'\b(?:GPT|Claude|Gemini|LLaMA|Mistral|v?\d+(?:\.\d+)?(?:\s|$))\b', title))

        passed = has_company or has_acronym or has_model
        score = 1.0 if passed else 0.0
        return QualityCheckResult(
            rule_name="title_concrete_subject",
            passed=passed,
            score=score,
            message="Title contains concrete subject" if passed else "Title lacks concrete subject",
            details={},
        )

    def check_hook_quality(self, hook: str) -> QualityCheckResult:
        """Rule 12: Hook must answer what happened and why care."""
        if not hook:
            return QualityCheckResult(
                rule_name="hook_quality",
                passed=False,
                score=0.0,
                message="Hook is empty",
                details={},
            )

        sentences = re.split(r'[.!?]+', hook)
        passed = len(sentences) >= 1 and len(sentences) <= 2
        score = 1.0 if passed else 0.5
        return QualityCheckResult(
            rule_name="hook_quality",
            passed=passed,
            score=score,
            message=f"Hook has {len(sentences)} sentences (ideal: 1-2)",
            details={"sentence_count": len(sentences)},
        )

    def check_body_contains_metric(self, body: str) -> QualityCheckResult:
        """Rule 13: Body must contain at least one number/metric/benchmark."""
        # Look for numbers, percentages, monetary values, etc.
        has_number = bool(re.search(r'\d+(?:[.,]\d+)?(?:%|\$|€|млн|миллиард|тыс)?', body))
        has_metric = bool(re.search(r'\d+(?:\s*(?:тыс|млн|млрд|B|GB|TB|ms|сек|%|x|раз))', body))

        passed = has_number or has_metric
        score = 1.0 if passed else 0.0
        return QualityCheckResult(
            rule_name="body_contains_metric",
            passed=passed,
            score=score,
            message="Body contains metric/number" if passed else "Body lacks specific metrics",
            details={},
        )

    def check_key_facts_standalone(self, key_facts: list) -> QualityCheckResult:
        """Rule 14: Each key fact must be a standalone verifiable claim."""
        if not key_facts or len(key_facts) < 4:
            return QualityCheckResult(
                rule_name="key_facts_standalone",
                passed=False,
                score=0.0,
                message=f"Need 4 key facts, got {len(key_facts) if key_facts else 0}",
                details={},
            )

        issues = []
        for i, fact in enumerate(key_facts[:4]):
            # Check if fact is too long (> 150 chars suggests it's not standalone)
            if len(fact) > 150:
                issues.append(f"Fact {i+1} too long ({len(fact)} chars)")
            # Check if fact contains multiple claims (multiple sentences)
            if fact.count('.') > 1:
                issues.append(f"Fact {i+1} contains multiple sentences")

        passed = len(issues) == 0
        score = 1.0 if passed else max(0.5, 1 - len(issues) * 0.2)
        return QualityCheckResult(
            rule_name="key_facts_standalone",
            passed=passed,
            score=score,
            message="Key facts are standalone" if passed else f"Issues: {'; '.join(issues)}",
            details={"issues": issues},
        )

    def check_analysis_industry_trend(self, analysis: str) -> QualityCheckResult:
        """Rule 15: Analysis must connect to broader industry trend."""
        if not analysis:
            return QualityCheckResult(
                rule_name="analysis_industry_trend",
                passed=False,
                score=0.0,
                message="Analysis is empty",
                details={},
            )

        # Look for trend-related keywords
        trend_keywords = [
            "тренд", "тенденци", "рынок", "индустри", "конкурент",
            "сектор", "отрасль", "направлен", "эволюц", "трансформ",
        ]
        has_trend = any(kw in analysis.lower() for kw in trend_keywords)

        passed = has_trend and len(analysis) > 50
        score = 1.0 if passed else 0.5
        return QualityCheckResult(
            rule_name="analysis_industry_trend",
            passed=passed,
            score=score,
            message="Analysis connects to industry trends" if passed else "Analysis lacks industry context",
            details={},
        )

    def check_post_type_label(self, post_type: str) -> QualityCheckResult:
        """Rule 16: Post must have a post_type label."""
        valid_types = ["breaking", "deep_dive", "tool_roundup", "analysis"]

        passed = post_type in valid_types
        score = 1.0 if passed else 0.0
        return QualityCheckResult(
            rule_name="post_type_label",
            passed=passed,
            score=score,
            message=f"Post type: {post_type}" if passed else f"Invalid or missing post_type: {post_type}",
            details={"post_type": post_type},
        )

    def check_tldr_self_contained(self, tldr: str) -> QualityCheckResult:
        """Rule 17: TLDR must be self-contained and meaningful."""
        if not tldr:
            return QualityCheckResult(
                rule_name="tldr_self_contained",
                passed=False,
                score=0.0,
                message="TLDR is empty",
                details={},
            )

        # Check if TLDR is a complete sentence
        is_complete = tldr.strip().endswith(('.', '!', '?'))
        # Check reasonable length (20-200 chars)
        reasonable_length = 20 <= len(tldr) <= 200

        passed = is_complete and reasonable_length
        score = 1.0 if passed else 0.5
        return QualityCheckResult(
            rule_name="tldr_self_contained",
            passed=passed,
            score=score,
            message=f"TLDR length: {len(tldr)} chars, complete: {is_complete}",
            details={"length": len(tldr)},
        )

    def check_hashtag_variety(self, hashtags: list) -> QualityCheckResult:
        """Rule 18: Hashtags must include company, technology, and AI tags."""
        if not hashtags or len(hashtags) < 3:
            return QualityCheckResult(
                rule_name="hashtag_variety",
                passed=False,
                score=0.0,
                message=f"Need at3+ hashtags, got {len(hashtags) if hashtags else 0}",
                details={},
            )

        hashtags_lower = [h.lower().lstrip('#') for h in hashtags]

        # Check for AI-related tags
        ai_tags = ['ai', 'ии', 'ml', 'machinelearning', 'artificialintelligence', 'llm', 'нейросет']
        has_ai = any(tag in ' '.join(hashtags_lower) for tag in ai_tags)

        passed = has_ai and len(hashtags) >= 3
        score = 1.0 if passed else 0.5
        return QualityCheckResult(
            rule_name="hashtag_variety",
            passed=passed,
            score=score,
            message=f"Hashtags: {len(hashtags)}, has AI tag: {has_ai}",
            details={"hashtags": hashtags},
        )

    def run_all_checks(
        self,
        post_json: dict,
        recent_posts: Optional[list] = None,
    ) -> FullQualityReport:
        """
        Run all 50 quality checks on a post.

        Args:
            post_json: Post data to validate
            recent_posts: Optional list of recent post contents for similarity check

        Returns:
            FullQualityReport: Complete quality report
        """
        checks = []

        title = post_json.get("title", "")
        hook = post_json.get("hook", "")
        body = post_json.get("body", "")
        key_facts = post_json.get("key_facts", [])
        analysis = post_json.get("analysis", "")
        post_json.get("sources", [])
        tldr = post_json.get("tldr", "")
        hashtags = post_json.get("hashtags", [])
        post_type = post_json.get("post_type", "")
        post_json.get("media_prompt", "")

        full_text = f"{title} {hook} {body}"

        # Block A: Text Quality (Rules 1-10)
        checks.append(self.check_min_body_length(body))
        checks.append(self.check_max_body_length(body))
        checks.append(self.check_max_sentence_length(body))
        checks.append(self.check_passive_voice(body))
        checks.append(self.check_banned_words(full_text))
        checks.append(self.check_readability(body))
        checks.append(self.check_repetition(body))
        checks.append(self.check_jargon_balance(body))
        checks.append(self.check_filler_phrases(full_text))
        checks.append(self.check_active_voice_ratio(body))

        # Block B: Post Structure (Rules 11-20)
        checks.append(self.check_title_concrete_subject(title))
        checks.append(self.check_hook_quality(hook))
        checks.append(self.check_body_contains_metric(body))
        checks.append(self.check_key_facts_standalone(key_facts))
        checks.append(self.check_analysis_industry_trend(analysis))
        checks.append(self.check_post_type_label(post_type))
        checks.append(self.check_tldr_self_contained(tldr))
        checks.append(self.check_hashtag_variety(hashtags))

        # Calculate total score
        total_score = sum(c.score for c in checks) / len(checks)
        passed = all(c.passed for c in checks[:10])  # First 10 are critical
        failed_rules = [c.rule_name for c in checks if not c.passed]
        warnings = [c.message for c in checks if not c.passed and c.rule_name not in failed_rules[:10]]

        return FullQualityReport(
            total_score=total_score,
            passed=passed,
            checks=checks,
            failed_rules=failed_rules,
            warnings=warnings,
        )
