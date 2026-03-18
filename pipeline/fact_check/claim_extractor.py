"""
Enhanced Claim Extractor for Phase 2 Factual Accuracy.

Extracts various types of verifiable claims from text including:
- Numbers and statistics
- Dates in multiple formats
- Names of companies and people
- Quotes with attribution
- Predictions and future statements
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ClaimType(Enum):
    """Types of verifiable claims."""

    STATISTIC = "statistic"
    DATE = "date"
    NAME = "name"
    QUOTE = "quote"
    EVENT = "event"
    NUMBER = "number"
    COMPARISON = "comparison"
    GENERAL = "general"
    FACT = "fact"
    PREDICTION = "prediction"


@dataclass(slots=True)
class Claim:
    """A verifiable claim extracted from content."""

    text: str
    claim_type: ClaimType
    position: tuple[int, int]
    confidence: float = 1.0
    context: str = ""
    source_url: str = ""
    source_quote: str = ""

    # Optional verification fields
    source_required: bool = True
    verified: Optional[bool] = None
    sources: list[str] = field(default_factory=list)
    correction: Optional[str] = None


class ClaimExtractor:
    """
    Enhanced claim extractor for factual accuracy checking.

    Features:
    - Multi-pattern claim detection
    - Russian and English language support
    - Confidence scoring based on pattern specificity
    - Automatic source requirement determination
    """

    # Currency symbols for number detection
    CURRENCY_SYMBOLS = r"[\$€₽¥£]"

    # Number patterns including percentages and currency
    NUMBER_PATTERNS = [
        # Currency amounts with optional magnitude
        r"[\$€₽¥£]\s*\d+(?:[.,]\d{3})*(?:[.,]\d+)?\s*(?:млн|млрд|тыс|million|billion|thousand)?",
        # Percentages
        r"\d+(?:[.,]\d+)?\s*%",
        # Numbers with magnitude words (Russian)
        r"\d+(?:[.,]\d{3})*(?:[.,]\d+)?\s*(?:миллионов?|млн|миллиардов?|млрд|тысяч?|тыс\.?)",
        # Numbers with magnitude words (English)
        r"\d+(?:[.,]\d{3})*(?:[.,]\d+)?\s*(?:million|billion|thousand)",
        # Large standalone numbers (likely statistics)
        r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?",
        # Numbers followed by units indicating data
        r"\d+(?:[.,]\d+)?\s*(?:users?|пользователей?|companies|компаний|clients|клиентов)",
    ]

    # Russian month names
    RUSSIAN_MONTHS = (
        "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря"
    )

    # English month names
    ENGLISH_MONTHS = (
        "January|February|March|April|May|June|July|August|September|October|November|December"
    )

    # Date patterns
    DATE_PATTERNS = [
        # Russian format: DD month YYYY
        rf"\d{{1,2}}\s+(?:{RUSSIAN_MONTHS})\s*(?:\d{{4}})?",
        # English format: Month DD, YYYY
        rf"(?:{ENGLISH_MONTHS})\s+\d{{1,2}},?\s*(?:\d{{4}})?",
        # ISO format: YYYY-MM-DD
        r"\d{4}-\d{2}-\d{2}",
        # Year with context
        r"(?:в\s+)?\d{4}\s*(?:году|г\.|year)",
        # Relative dates
        r"(?:в\s+)?(?:прошлом|следующем|этом)\s+(?:году|месяце|квартале)",
        r"(?:last|next|this)\s+(?:year|month|quarter)",
    ]

    # Known tech companies (expandable)
    TECH_COMPANIES = [
        # Big Tech
        r"OpenAI",
        r"Google",
        r"Microsoft",
        r"Apple",
        r"Meta",
        r"Amazon",
        r"Anthropic",
        r"DeepMind",
        r"NVIDIA",
        r"Tesla",
        # AI Companies
        r"Stability\s+AI",
        r"Midjourney",
        r"Mistral\s+AI",
        r"Inflection",
        r"Cohere",
        r"Hugging\s*Face",
        # Russian Tech
        r"Яндекс",
        r"Yandex",
        r"VK",
        r"Сбер",
        r"Sber",
        r"Тинькофф",
        r"Tinkoff",
    ]

    # Known tech people
    TECH_PEOPLE = [
        # English names
        r"Sam\s+Altman",
        r"Elon\s+Musk",
        r"Mark\s+Zuckerberg",
        r"Sundar\s+Pichai",
        r"Satya\s+Nadella",
        r"Tim\s+Cook",
        r"Jensen\s+Huang",
        r"Dario\s+Amodei",
        r"Demis\s+Hassabis",
        # Russian names
        r"Сэм\s+Алтман",
        r"Илон\s+Маск",
        r"Марк\s+Цукерберг",
        r"Сундар\s+Пичаи",
        r"Сатья\s+Наделла",
    ]

    # AI Model names
    AI_MODELS = [
        r"GPT-?[45]",
        r"GPT-?\d+(?:\.\d+)?(?:\s+(?:Turbo|mini|o))?",
        r"Claude\s*(?:\d+(?:\.\d+)?)?",
        r"Gemini(?:\s+(?:Pro|Ultra|Flash))?",
        r"Llama\s*\d*(?:\.\d+)?",
        r"Mistral(?:\s+(?:Large|Medium|Small))?",
        r"ChatGPT",
        r"Midjourney\s*\d*",
        r"Stable\s+Diffusion(?:\s+\w+)?",
        r"DALL-?E\s*\d*",
    ]

    # Name patterns combining companies, people, and models
    NAME_PATTERNS = TECH_COMPANIES + TECH_PEOPLE + AI_MODELS

    # Quote patterns with attribution
    QUOTE_PATTERNS = [
        # Russian quotes with attribution
        r'"[^"]{10,}"\s*[-—]\s*[А-ЯЁ][а-яё]+',
        r'"[^"]{10,}"\s*[-—]\s*[A-Z][a-z]+',
        r"«[^»]{10,}»\s*[-—]\s*[А-ЯЁ][а-яё]+",
        # English quotes with attribution
        r'"[^"]{10,}"\s*[-—]\s*said\s+\w+',
        r"'[^']{10,}'\s*[-—]\s*[A-Z][a-z]+",
        # Explicit quote markers
        r"(?:по\s+словам|according\s+to)\s+[А-ЯЁA-Z][а-яёa-z]+[^.]*[.:]",
    ]

    # Prediction/future tense patterns
    PREDICTION_PATTERNS = [
        # Russian future predictions
        r"(?:ожидается|прогнозируется|предполагается|планируется)\s*,?\s*что",
        r"(?:в\s+будущем|в\s+ближайшие\s+годы|в\s+течение\s+\d+\s+лет)",
        r"(?:будет|смогут|начнут|станут)\s+(?:использовать|применять|работать)",
        r"(?:к\s+\d{4}\s+году|к\s+концу\s+года)",
        # English future predictions
        r"(?:will\s+be|is\s+expected\s+to|is\s+projected\s+to|is\s+predicted\s+to)",
        r"(?:in\s+the\s+(?:next|coming|following)\s+\d+\s+years?)",
        r"(?:by\s+\d{4}|by\s+the\s+end\s+of)",
        r"(?:experts\s+predict|analysts\s+forecast)",
    ]

    # Statistic patterns (more specific than numbers)
    STATISTIC_PATTERNS = [
        # Comparisons
        r"(?:увеличил(?:а|и|ось)?|вырос(?:ла|ли)?|снизил(?:а|и|ось)?|упал(?:а|и)?)\s+на\s+\d+(?:[.,]\d+)?\s*%?",
        r"(?:increased|decreased|grew|dropped|rose|fell)\s+(?:by\s+)?\d+(?:[.,]\d+)?\s*%?",
        # Rankings
        r"(?:топ|top)\s*[-—]?\s*\d+",
        r"№\s*\d+",
        r"#\d+",
    ]

    # Event patterns (X announced Y)
    EVENT_PATTERNS = [
        # Russian event patterns
        r"(\w+)\s+(запустил|выпустил|анонсировал|представил|приобрёл|купил|выкупил)",
        r"(запуск|релиз|анонс|представление|покупка)\s+(\w+)",
        r"(?:на\s+)?(?:конференци[ия]|саммит|форум|встреча|мероприятие)",
        # English event patterns
        r"(\w+)\s+(launched|released|announced|introduced|acquired|unveiled)",
        r"(?:launch|release|announcement|introduction|acquisition)\s+(?:of\s+)?(\w+)",
        r"(?:at\s+the\s+)?(?:conference|summit|forum|event|meeting)",
    ]

    # Comparison patterns
    COMPARISON_PATTERNS = [
        # Russian comparisons
        r"(быстрее|медленнее|лучше|хуже|больше|меньше)\s+(?:чем|на)\s+",
        r"в\s+(\d+(?:[.,]\d+)?)\s*(раза?|раз)\s+(?:быстрее|медленнее|лучше|эффективнее)",
        r"(\d+)x\s+(?:faster|slower|better)",
        # English comparisons
        r"(faster|slower|better|worse|more|less|larger|smaller)\s+than",
        r"(\d+(?:[.,]\d+)?)x\s+(?:improvement|increase|growth)",
    ]

    # Claim indicator phrases that signal factual claims
    CLAIM_INDICATORS = [
        # Russian indicators
        r"по\s+данным\s+",
        r"согласно\s+(?:исследованию|отчёту|докладу)",
        r"как\s+сообщается,?\s*",
        r"по\s+информации\s+",
        r"исследование\s+показало,?\s*",
        r"отч[ёе]т\s+(?:показал|свидетельствует)",
        # English indicators
        r"according\s+to\s+",
        r"as\s+reported\s+",
        r"research\s+(?:shows|indicates|found)\s+",
        r"(?:the\s+)?(?:study|report)\s+(?:found|shows|indicates)\s+",
        r"data\s+(?:shows|indicates|reveals)\s+",
    ]

    # Vague phrases that indicate non-claims
    VAGUE_PHRASES = [
        r"\b(?:очень|крайне|весьма|достаточно)\s+(?:важный|интересный|полезный)\b",
        r"\b(?:very|extremely|highly|quite)\s+(?:important|interesting|useful)\b",
        r"\bэто\s+(?:очень|крайне)\b",
        r"\bthis\s+is\s+(?:very|extremely)\b",
    ]

    def __init__(
        self,
        min_confidence: float = 0.5,
        context_window: int = 50,
    ) -> None:
        """
        Initialize the claim extractor.

        Args:
            min_confidence: Minimum confidence threshold for claims
            context_window: Number of characters to include as context
        """
        self.min_confidence = min_confidence
        self.context_window = context_window

        # Compile patterns for efficiency
        self._compiled_patterns: dict[ClaimType, list[re.Pattern]] = {
            ClaimType.NUMBER: [re.compile(p, re.IGNORECASE) for p in self.NUMBER_PATTERNS],
            ClaimType.DATE: [re.compile(p, re.IGNORECASE) for p in self.DATE_PATTERNS],
            ClaimType.NAME: [re.compile(p, re.IGNORECASE) for p in self.NAME_PATTERNS],
            ClaimType.QUOTE: [re.compile(p, re.IGNORECASE) for p in self.QUOTE_PATTERNS],
            ClaimType.PREDICTION: [re.compile(p, re.IGNORECASE) for p in self.PREDICTION_PATTERNS],
            ClaimType.STATISTIC: [re.compile(p, re.IGNORECASE) for p in self.STATISTIC_PATTERNS],
            ClaimType.EVENT: [re.compile(p, re.IGNORECASE) for p in self.EVENT_PATTERNS],
            ClaimType.COMPARISON: [re.compile(p, re.IGNORECASE) for p in self.COMPARISON_PATTERNS],
        }

        # Compile indicator and vague patterns for helper methods
        self._indicator_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.CLAIM_INDICATORS
        ]
        self._vague_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.VAGUE_PHRASES
        ]

    def extract(
        self,
        text: str,
        source_url: str = "",
        source_quote: str = "",
    ) -> list[Claim]:
        """
        Extract all verifiable claims from text.

        Args:
            text: Text to analyze for claims
            source_url: Optional source URL to attach to claims
            source_quote: Optional source quote to attach to claims

        Returns:
            List of Claim objects found in the text
        """
        claims: list[Claim] = []
        seen_positions: set[tuple[int, int]] = set()

        for claim_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    # Skip if position already claimed by another pattern
                    start, end = match.start(), match.end()
                    if self._is_overlapping(start, end, seen_positions):
                        continue

                    seen_positions.add((start, end))

                    claim = self._create_claim(
                        text=text,
                        match_text=match.group(),
                        claim_type=claim_type,
                        start=start,
                        end=end,
                        source_url=source_url,
                        source_quote=source_quote,
                    )

                    if claim.confidence >= self.min_confidence:
                        claims.append(claim)

        # Sort claims by position
        claims.sort(key=lambda c: c.position[0])

        return claims

    def _is_overlapping(
        self, start: int, end: int, seen_positions: set[tuple[int, int]]
    ) -> bool:
        """Check if position overlaps with existing claims."""
        for seen_start, seen_end in seen_positions:
            if start < seen_end and end > seen_start:
                return True
        return False

    def _create_claim(
        self,
        text: str,
        match_text: str,
        claim_type: ClaimType,
        start: int,
        end: int,
        source_url: str = "",
        source_quote: str = "",
    ) -> Claim:
        """Create a Claim object with calculated properties."""
        confidence = self._calculate_confidence(match_text, claim_type)
        source_required = self._determine_source_required(claim_type, match_text)
        context = self._get_context(text, start, end)

        return Claim(
            text=match_text,
            claim_type=claim_type,
            position=(start, end),
            confidence=confidence,
            source_required=source_required,
            context=context,
            source_url=source_url,
            source_quote=source_quote,
        )

    def _calculate_confidence(self, match_text: str, claim_type: ClaimType) -> float:
        """
        Calculate confidence score for a claim.

        Higher confidence for:
        - Specific names (exact matches)
        - Precise numbers (with decimals)
        - Clear dates (full format)
        """
        base_confidence = 0.7

        if claim_type == ClaimType.NAME:
            # Well-known names get higher confidence
            if any(
                re.search(p, match_text, re.IGNORECASE)
                for p in self.TECH_COMPANIES + self.TECH_PEOPLE
            ):
                return 0.95
            return 0.8

        if claim_type == ClaimType.NUMBER:
            # Percentages and currency are more reliable
            if "%" in match_text:
                return 0.9
            if re.search(self.CURRENCY_SYMBOLS, match_text):
                return 0.85
            # Numbers with magnitude words
            if re.search(r"(?:млн|млрд|million|billion)", match_text, re.IGNORECASE):
                return 0.85
            return 0.75

        if claim_type == ClaimType.DATE:
            # ISO format dates are most reliable
            if re.match(r"\d{4}-\d{2}-\d{2}", match_text):
                return 0.95
            # Full dates with year
            if re.search(r"\d{4}", match_text):
                return 0.9
            # Relative dates are less certain
            if re.search(r"(?:прошлом|следующем|last|next)", match_text, re.IGNORECASE):
                return 0.6
            return 0.8

        if claim_type == ClaimType.QUOTE:
            # Quotes with clear attribution
            if re.search(r"[-—]", match_text):
                return 0.85
            return 0.7

        if claim_type == ClaimType.STATISTIC:
            # Comparison statistics
            return 0.8

        if claim_type == ClaimType.PREDICTION:
            # Predictions are inherently uncertain
            if re.search(r"(?:к\s+\d{4}|by\s+\d{4})", match_text, re.IGNORECASE):
                return 0.6
            return 0.5

        return base_confidence

    def _determine_source_required(self, claim_type: ClaimType, match_text: str) -> bool:
        """
        Determine if a claim requires source verification.

        Source required for:
        - Statistics and numbers (except general counts)
        - Quotes
        - Specific dates
        - Predictions
        """
        # Names of well-known entities don't always need sources
        if claim_type == ClaimType.NAME:
            return False

        # Quotes always need sources
        if claim_type == ClaimType.QUOTE:
            return True

        # Statistics always need sources
        if claim_type == ClaimType.STATISTIC:
            return True

        # Predictions should cite sources
        if claim_type == ClaimType.PREDICTION:
            return True

        # Numbers and dates depend on context
        if claim_type == ClaimType.NUMBER:
            # Currency and percentages need sources
            if "%" in match_text or re.search(self.CURRENCY_SYMBOLS, match_text):
                return True
            return True  # Default to requiring source for numbers

        if claim_type == ClaimType.DATE:
            # Most dates should be verifiable
            return True

        # Facts need sources
        if claim_type == ClaimType.FACT:
            return True

        return True

    def _get_context(self, text: str, start: int, end: int) -> str:
        """Get context around a match."""
        context_start = max(0, start - self.context_window)
        context_end = min(len(text), end + self.context_window)
        return text[context_start:context_end]

    def extract_by_type(self, text: str, claim_type: ClaimType) -> list[Claim]:
        """
        Extract claims of a specific type only.

        Args:
            text: Text to analyze
            claim_type: Type of claims to extract

        Returns:
            List of claims of the specified type
        """
        all_claims = self.extract(text)
        return [c for c in all_claims if c.claim_type == claim_type]

    def get_source_required_claims(self, text: str) -> list[Claim]:
        """
        Get only claims that require source verification.

        Args:
            text: Text to analyze

        Returns:
            List of claims requiring sources
        """
        all_claims = self.extract(text)
        return [c for c in all_claims if c.source_required]
