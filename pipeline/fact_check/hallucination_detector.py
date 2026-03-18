"""
Hallucination Detector for Phase 2 Factual Accuracy.

Detects common AI-generated hallucination patterns in text including:
- Vague expert claims without attribution
- Unnamed studies and research
- Future predictions presented as facts
- Impossible or suspicious statistics
- Fake quotes without proper sources
- Made-up company names
- Non-existent products
- Future dates presented as past events
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HallucinationReport:
    """Report of hallucination detection results."""

    score: float  # 0.0 (clean) to 1.0 (highly suspicious)
    indicators: list[str] = field(default_factory=list)
    passes_check: bool = True
    details: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


class HallucinationDetector:
    """
    Detects AI-generated hallucinations in text.

    Features:
    - Pattern-based detection of common hallucination types
    - Confidence scoring for hallucination likelihood
    - Specific indicators with explanations
    - Auto-reject threshold for high-risk content
    - Made-up company name detection
    - Non-existent product detection
    - Fake quote detection
    - Impossible statistics detection
    - Future dates as past events detection
    """

    # Auto-reject threshold - content with score >= this value is flagged
    AUTO_REJECT_THRESHOLD = 0.7

    # Current year for date validation
    CURRENT_YEAR = datetime.now().year

    # Known tech companies (for company name validation)
    KNOWN_TECH_COMPANIES: set[str] = {
        # Big Tech
        "openai", "google", "microsoft", "apple", "meta", "facebook",
        "amazon", "anthropic", "deepmind", "nvidia", "tesla", "intel",
        "amd", "ibm", "oracle", "salesforce", "adobe", "cisco", "samsung",
        # AI Companies
        "stability ai", "midjourney", "mistral ai", "inflection", "cohere",
        "hugging face", "huggingface", "character.ai", "perplexity",
        # Russian Tech
        "yandex", "яндекс", "vk", "сбер", "sber", "тинькофф", "tinkoff",
        "mail.ru", "kaspersky", "касперский",
        # Other major tech
        "spotify", "netflix", "uber", "lyft", "airbnb", "twitter", "x corp",
        "linkedin", "snapchat", "zoom", "slack", "discord", "notion",
        "figma", "canva", "shopify", "stripe", "square", "paypal",
    }

    # Known AI/tech products and models
    KNOWN_PRODUCTS: set[str] = {
        # OpenAI
        "gpt-4", "gpt-4o", "gpt-4-turbo", "gpt-3.5", "gpt-3", "chatgpt",
        "dall-e", "dalle", "dall-e 2", "dall-e 3", "whisper", "sora",
        # Anthropic
        "claude", "claude 3", "claude 3.5", "claude 3 opus", "claude 3 sonnet",
        "claude 3 haiku", "claude 2",
        # Google
        "gemini", "gemini pro", "gemini ultra", "gemini flash", "bard",
        "palm", "palm 2", "lamda", "imagen",
        # Meta
        "llama", "llama 2", "llama 3", "llama 3.1", "llama 3.2",
        "codellama", "llava",
        # Other models
        "mistral", "mistral large", "mistral medium", "mistral small",
        "mixtral", "midjourney", "stable diffusion", "stable diffusion 3",
        "sdxl", "flux",
        # Products
        "copilot", "github copilot", "bing chat", "perplexity ai",
        "character.ai",
    }

    # Patterns that suggest made-up company names
    SUSPICIOUS_COMPANY_PATTERNS: list[tuple[str, float]] = [
        (r"\b[A-Z][a-z]+AI\b", 0.4),
        (r"\bAI[A-Z][a-z]+\b", 0.4),
        (r"\b[A-Z][a-z]+\s+AI\s+(?:Labs|Research|Corp|Inc)\b", 0.5),
        (r"\b(?:Tech|Data|Smart|Neural|Quantum|Cyber)[A-Z][a-z]+\b", 0.35),
        (r"\b[A-Z][a-z]+\s+(?:Solutions|Technologies|Systems|Innovations)\b", 0.3),
    ]

    # Patterns for suspicious product names
    SUSPICIOUS_PRODUCT_PATTERNS: list[tuple[str, float]] = [
        (r"\bGPT-?[6-9]\b", 0.8),
        (r"\bClaude\s*[4-9](?:\.\d+)?\b", 0.8),
        (r"\bLlama\s*[4-9](?:\.\d+)?\b", 0.7),
        (r"\bGemini\s+[2-9](?:\.\d+)?\b", 0.7),
        (r"\bNeoGPT\b", 0.7),
        (r"\bUltraGPT\b", 0.7),
        (r"\bSuperClaude\b", 0.7),
    ]

    # Fake quote patterns with vague attribution
    FAKE_QUOTE_PATTERNS: list[tuple[str, float]] = [
        (r'"[^"]+"\s*[-\u2014]\s*(?:experts?|analysts?|sources?|insiders?)', 0.75),
        (r'"[^"]*future[^"]*"\s*[-\u2014]\s*Steve\s+Jobs', 0.6),
    ]

    # Impossible statistics patterns (includes Russian)
    IMPOSSIBLE_STATISTICS_PATTERNS: list[tuple[str, float]] = [
        (r"\b(?:200|300|400|500|600|700|800|900|1000)\s*%\s*(?:improvement|increase)", 0.9),
        (r"\b(?:200|300|400|500|600|700|800|900|1000)\s*%\s*(?:улучшение|увеличение|рост)", 0.9),
        (r"\b\d+\.\d{4,}\s*%", 0.7),
        (r"\b1[0-9]{2,}\s*%\s*(?:market|рынка)", 0.95),
        (r"grew\s+(?:by\s+)?\d{2,}x\b", 0.6),
        (r"вырос(?:ла|ли|ло)?\s+(?:на\s+)?(?:200|300|400|500|600|700|800|900|1000)\s*%", 0.9),
    ]

    # Future dates presented as past/current events
    FUTURE_AS_PAST_PATTERNS: list[tuple[str, float]] = [
        (r"(?:in\s+)?(\d{4}),?\s+(?:was|released|launched|announced)", 0.5),
        (r"by\s+(\d{4}),?\s+(?:has\s+)?(?:already\s+)?(?:been|completed|achieved)", 0.6),
    ]

    # Common AI hallucination patterns with severity weights
    HALLUCINATION_PATTERNS: dict[str, tuple[str, float]] = {
        "vague_expert_ru": (r"эксперты\s+(?:прогнозируют|утверждают|считают|ожидают|полагают)", 0.8),
        "vague_expert_en": (r"experts\s+(?:predict|claim|believe|expect|suggest)", 0.8),
        "analysts_ru": (r"аналитики\s+(?:прогнозируют|ожидают|считают)", 0.75),
        "analysts_en": (r"analysts\s+(?:predict|expect|forecast)", 0.75),
        "unnamed_study_ru": (r"(?:недавнее\s+)?исследование\s+(?:показало|выявило|подтвердило|демонстрирует)", 0.85),
        "unnamed_study_en": (r"(?:a\s+)?(?:recent\s+)?study\s+(?:showed|found|revealed|demonstrated|suggests)", 0.85),
        "studies_show": (r"studies\s+have\s+shown", 0.8),
        "research_shows": (r"research\s+(?:has\s+)?shows?", 0.75),
        "impossible_improvement": (r"(?:\d{3,}|100+)\s*%\s*(?:улучшение|improvement|увеличение|increase)", 0.9),
        "impossible_growth": (r"вырос(?:ла|ли)?\s+на\s*(?:\d{3,}|100+)\s*%", 0.9),
        "future_as_fact_ru": (r"в\s+(\d{4})\s+году\s+(?:будет|ожидается|планируется|появится)", 0.65),
        "future_as_fact_en": (r"by\s+(\d{4}),?\s+(?:will\s+be|is\s+expected|is\s+projected)", 0.65),
        "guaranteed": (r"(?:гарантированно|guaranteed)\s+(?:приведет|will)", 0.7),
        "reports_suggest": (r"reports\s+suggest", 0.65),
        "sources_say": (r"sources\s+(?:say|indicate|suggest)", 0.6),
    }

    # AI cliche phrases
    AI_CLICHE_PATTERNS: dict[str, tuple[str, float]] = {
        "game_changer": (r"game[- ]?changer", 0.3),
        "revolutionary": (r"revolutionary\s+(?:new|technology|approach)", 0.35),
        "groundbreaking": (r"ground[- ]?breaking", 0.35),
        "paradigm_shift": (r"paradigm\s+shift", 0.3),
    }

    def __init__(
        self,
        auto_reject_threshold: float = 0.7,
        strict_mode: bool = False,
    ) -> None:
        """Initialize the hallucination detector."""
        self.auto_reject_threshold = auto_reject_threshold
        self.strict_mode = strict_mode

        self._compiled_hallucination: dict[str, tuple[re.Pattern, float]] = {
            name: (re.compile(pattern, re.IGNORECASE), weight)
            for name, (pattern, weight) in self.HALLUCINATION_PATTERNS.items()
        }

        self._compiled_cliches: dict[str, tuple[re.Pattern, float]] = {
            name: (re.compile(pattern, re.IGNORECASE), weight)
            for name, (pattern, weight) in self.AI_CLICHE_PATTERNS.items()
        }

        self._compiled_company_patterns: list[tuple[re.Pattern, float]] = [
            (re.compile(p), w) for p, w in self.SUSPICIOUS_COMPANY_PATTERNS
        ]

        self._compiled_product_patterns: list[tuple[re.Pattern, float]] = [
            (re.compile(p), w) for p, w in self.SUSPICIOUS_PRODUCT_PATTERNS
        ]

        self._compiled_fake_quote_patterns: list[tuple[re.Pattern, float]] = [
            (re.compile(p), w) for p, w in self.FAKE_QUOTE_PATTERNS
        ]

        self._compiled_impossible_stats: list[tuple[re.Pattern, float]] = [
            (re.compile(p), w) for p, w in self.IMPOSSIBLE_STATISTICS_PATTERNS
        ]

        self._compiled_future_as_past: list[tuple[re.Pattern, float]] = [
            (re.compile(p), w) for p, w in self.FUTURE_AS_PAST_PATTERNS
        ]

    def detect(self, text: str) -> HallucinationReport:
        """Detect hallucinations in text."""
        indicators: list[str] = []
        details: dict[str, float] = {}
        total_weight = 0.0
        max_possible_weight = 0.0

        for name, (pattern, weight) in self._compiled_hallucination.items():
            matches = list(pattern.finditer(text))
            if matches:
                match_weight = weight * len(matches)
                total_weight += match_weight
                details[name] = match_weight
                for match in matches[:3]:
                    context = self._get_match_context(text, match)
                    indicators.append(f"{self._format_pattern_name(name)}: '{context}'")
            max_possible_weight += weight

        cliche_count = 0
        for name, (pattern, weight) in self._compiled_cliches.items():
            matches = list(pattern.finditer(text))
            if matches:
                cliche_count += len(matches)
                cliche_weight = weight * len(matches) * 0.5
                total_weight += cliche_weight
                details[f"cliche_{name}"] = cliche_weight

        # Check for made-up companies
        company_results = self.detect_made_up_companies(text)
        if company_results["score"] > 0:
            total_weight += company_results["score"] * 2
            details["made_up_companies"] = company_results["score"]
            indicators.extend(company_results["indicators"])

        # Check for fake products
        product_results = self.detect_fake_products(text)
        if product_results["score"] > 0:
            total_weight += product_results["score"] * 2
            details["fake_products"] = product_results["score"]
            indicators.extend(product_results["indicators"])

        # Check for fake quotes
        quote_results = self.detect_fake_quotes(text)
        if quote_results["score"] > 0:
            total_weight += quote_results["score"] * 2
            details["fake_quotes"] = quote_results["score"]
            indicators.extend(quote_results["indicators"])

        # Check for impossible statistics
        stats_results = self.detect_impossible_statistics(text)
        if stats_results["score"] > 0:
            total_weight += stats_results["score"] * 2
            details["impossible_stats"] = stats_results["score"]
            indicators.extend(stats_results["indicators"])

        # Check for future dates as past events
        date_results = self.detect_future_as_past(text)
        if date_results["score"] > 0:
            total_weight += date_results["score"] * 2
            details["future_as_past"] = date_results["score"]
            indicators.extend(date_results["indicators"])

        # Use sigmoid-like normalization for more intuitive scoring
        hallucination_score = self._normalize_score(total_weight, max_possible_weight)
        passes_check = hallucination_score < self.auto_reject_threshold
        recommendations = self._generate_recommendations(hallucination_score, details, cliche_count)

        return HallucinationReport(
            score=round(hallucination_score, 3),
            indicators=indicators,
            passes_check=passes_check,
            details=details,
            recommendations=recommendations,
        )

    def detect_made_up_companies(self, text: str) -> dict:
        """Detect potentially made-up company names in text."""
        indicators: list[str] = []
        total_weight = 0.0
        found_companies: list[str] = []

        for pattern, weight in self._compiled_company_patterns:
            matches = list(pattern.finditer(text))
            for match in matches:
                company_name = match.group()
                if company_name.lower() not in self.KNOWN_TECH_COMPANIES:
                    found_companies.append(company_name)
                    total_weight += weight
                    indicators.append(f"Suspicious company name: '{company_name}'")

        score = min(1.0, total_weight / 2) if total_weight > 0 else 0.0
        return {"score": score, "indicators": indicators, "found": found_companies}

    def detect_fake_products(self, text: str) -> dict:
        """Detect potentially fake/non-existent products in text."""
        indicators: list[str] = []
        total_weight = 0.0
        found_products: list[str] = []

        for pattern, weight in self._compiled_product_patterns:
            matches = list(pattern.finditer(text))
            for match in matches:
                product_name = match.group()
                normalized = product_name.lower().replace("-", " ").replace(".", "")
                if not any(known in normalized or normalized in known for known in self.KNOWN_PRODUCTS):
                    found_products.append(product_name)
                    total_weight += weight
                    indicators.append(f"Suspicious product name: '{product_name}'")

        score = min(1.0, total_weight / 2) if total_weight > 0 else 0.0
        return {"score": score, "indicators": indicators, "found": found_products}

    def detect_fake_quotes(self, text: str) -> dict:
        """Detect potentially fake quotes without proper attribution."""
        indicators: list[str] = []
        total_weight = 0.0
        found_quotes: list[str] = []

        for pattern, weight in self._compiled_fake_quote_patterns:
            matches = list(pattern.finditer(text))
            for match in matches:
                quote_text = match.group()
                found_quotes.append(quote_text)
                total_weight += weight
                indicators.append(f"Quote with suspicious attribution: '{quote_text[:50]}...'")

        score = min(1.0, total_weight / 2) if total_weight > 0 else 0.0
        return {"score": score, "indicators": indicators, "found": found_quotes}

    def detect_impossible_statistics(self, text: str) -> dict:
        """Detect impossible or highly suspicious statistics."""
        indicators: list[str] = []
        total_weight = 0.0
        found_stats: list[str] = []

        for pattern, weight in self._compiled_impossible_stats:
            matches = list(pattern.finditer(text))
            for match in matches:
                stat_text = match.group()
                found_stats.append(stat_text)
                total_weight += weight
                indicators.append(f"Impossible statistic: '{stat_text}'")

        score = min(1.0, total_weight / 2) if total_weight > 0 else 0.0
        return {"score": score, "indicators": indicators, "found": found_stats}

    def detect_future_as_past(self, text: str) -> dict:
        """Detect future dates presented as past events."""
        indicators: list[str] = []
        total_weight = 0.0
        found_dates: list[str] = []

        for pattern, weight in self._compiled_future_as_past:
            matches = list(pattern.finditer(text))
            for match in matches:
                year_match = re.search(r"(\d{4})", match.group())
                if year_match:
                    year = int(year_match.group(1))
                    if year > self.CURRENT_YEAR:
                        date_text = match.group()
                        found_dates.append(date_text)
                        total_weight += weight
                        indicators.append(f"Future date as past event: '{date_text}'")

        score = min(1.0, total_weight / 2) if total_weight > 0 else 0.0
        return {"score": score, "indicators": indicators, "found": found_dates}

    def _get_match_context(self, text: str, match: re.Match, window: int = 30) -> str:
        """Get context around a match."""
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        context = text[start:end]
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        return context.strip()

    def _format_pattern_name(self, name: str) -> str:
        """Format pattern name for display."""
        return name.replace("_", " ").title()

    def _normalize_score(self, total_weight: float, max_possible_weight: float) -> float:
        """Normalize hallucination score using sigmoid-like normalization.

        Args:
            total_weight: Sum of all detected pattern weights
            max_possible_weight: Maximum possible weight for normalization

        Returns:
            Normalized score between 0.0 and 1.0
        """
        if total_weight <= 0:
            return 0.0

        # Use square root scaling for more intuitive scoring
        # This gives higher scores for fewer detections while still capping at 1.0
        # A single high-weight pattern (0.9) should give score ~0.5
        # Multiple patterns should quickly approach 1.0
        normalized = min(1.0, (total_weight / 2.0) ** 0.7)

        return normalized

    def _generate_recommendations(self, score: float, details: dict[str, float], cliche_count: int) -> list[str]:
        """Generate actionable recommendations based on detection results."""
        recommendations = []

        if score >= self.auto_reject_threshold:
            recommendations.append(f"КРИТИЧНО: Высокий риск галлюцинаций (score: {score:.2f}). Требуется ручная проверка.")
        elif score >= 0.5:
            recommendations.append(f"ВНИМАНИЕ: Обнаружены признаки галлюцинаций (score: {score:.2f}).")

        if "unnamed_study_ru" in details or "unnamed_study_en" in details:
            recommendations.append("Укажите конкретное исследование: название, авторы, дата публикации.")
        if "vague_expert_ru" in details or "vague_expert_en" in details:
            recommendations.append("Замените 'эксперты' на конкретные имена или организации.")
        if "made_up_companies" in details:
            recommendations.append("Обнаружены подозрительные названия компаний. Проверьте существование компании.")
        if "fake_products" in details:
            recommendations.append("Обнаружены подозрительные названия продуктов.")
        if "fake_quotes" in details:
            recommendations.append("Обнаружены цитаты с нечётким указанием источника.")
        if "impossible_stats" in details:
            recommendations.append("Проверьте статистику - подозрительно высокие показатели.")
        if "future_as_past" in details:
            recommendations.append("Обнаружены будущие даты как прошедшие события.")

        return recommendations

    def get_hallucination_score(self, text: str) -> float:
        """Get only the hallucination score without full report."""
        return self.detect(text).score

    def is_safe_to_publish(self, text: str) -> bool:
        """Quick check if text passes hallucination threshold."""
        return self.detect(text).passes_check

    def get_high_risk_segments(self, text: str) -> list[dict[str, str]]:
        """Get segments of text with highest hallucination risk."""
        segments = []
        for name, (pattern, weight) in self._compiled_hallucination.items():
            if weight < 0.6:
                continue
            for match in pattern.finditer(text):
                segments.append({
                    "text": match.group(),
                    "pattern": name,
                    "weight": weight,
                    "position": (match.start(), match.end()),
                    "context": self._get_match_context(text, match),
                })
        segments.sort(key=lambda x: x["weight"], reverse=True)
        return segments
