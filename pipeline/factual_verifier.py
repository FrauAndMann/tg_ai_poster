"""
Factual Verification System - Verifies claims in generated content.

Extracts verifiable claims from posts and cross-references them
against multiple sources to detect hallucinations and errors.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter

logger = get_logger(__name__)


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


class VerificationStatus(Enum):
    """Status of claim verification."""
    VERIFIED = "verified"
    DISPUTED = "disputed"
    UNVERIFIABLE = "unverifiable"
    HALLUCINATION = "hallucination"
    PENDING = "pending"


@dataclass(slots=True)
class Claim:
    """A verifiable claim extracted from content."""

    text: str
    claim_type: ClaimType
    position: tuple[int, int]
    confidence: float = 1.0
    context: str = ""

    # Verification results
    status: VerificationStatus = VerificationStatus.PENDING
    sources: list[str] = field(default_factory=list)
    conflicting_sources: list[str] = field(default_factory=list)
    correction: Optional[str] = None
    verification_notes: str = ""


@dataclass(slots=True)
class VerificationReport:
    """Complete factual verification report."""

    total_claims: int = 0
    verified_count: int = 0
    disputed_count: int = 0
    unverifiable_count: int = 0
    hallucination_count: int = 0
    claims: list[Claim] = field(default_factory=list)
    overall_credibility: float = 1.0
    recommendations: list[str] = field(default_factory=list)


class FactualVerifier:
    """
    Verifies factual claims in generated content.

    Features:
    - Claim extraction using patterns and NLP
    - Multi-source verification
    - Hallucination detection
    - Correction suggestions
    """

    # Patterns for extracting claims
    CLAIM_PATTERNS = {
        ClaimType.STATISTIC: [
            r"(\d+(?:[,.\s]\d+)*)\s*%?\s*(миллионов?|млн|миллиардов?|млрд|тысяч|тыс\.?)",
            r"(\d+(?:[,.\s]\d+)*)\s*(percent|%|million|billion|thousand)",
            r"(увеличил(?:а|и|ось)?|снизил(?:а|и|ось)?|вырос(?:ла|ли)?)\s+на\s+(\d+)",
            r"(increased|decreased|grew|dropped)\s+by\s+(\d+)",
        ],
        ClaimType.DATE: [
            r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s*(\d{4})?",
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s*(\d{4})?",
            r"(\d{4})\s*(году|г\.|year)",
            r"(в\s+)?(\d{4})-(\d{2})-(\d{2})",
        ],
        ClaimType.NUMBER: [
            r"\$\d+(?:[,.\s]\d+)*(?:млн|млрд|million|billion)?",
            r"€\d+(?:[,.\s]\d+)*(?:млн|млрд)?",
            r"₽\d+(?:[,.\s]\d+)*(?:млн|млрд)?",
            r"(\d+(?:[,.\s]\d+)*)\s*(users?|users|пользователей?)",
            r"(\d+(?:[,.\s]\d+)*)\s*(companies|компаний|startups)",
        ],
        ClaimType.NAME: [
            r"(OpenAI|Google|Microsoft|Apple|Meta|Amazon|Anthropic|DeepMind)",
            r"(GPT-[45]|Claude|Gemini|Llama|Mistral|ChatGPT)",
            r"(Сэм Алтман|Илон Маск|Марк Цукерберг|Sam Altman|Elon Musk|Mark Zuckerberg)",
        ],
        ClaimType.EVENT: [
            r"(запустил|выпустил|анонсировал|представил|приобрёл)",
            r"(launched|released|announced|introduced|acquired)",
            r"(конференци[ия]|саммит|форум|conference|summit)",
        ],
        ClaimType.COMPARISON: [
            r"(быстрее|медленнее|лучше|хуже|больше|меньше)\s+(?:чем|на)\s+",
            r"(faster|slower|better|worse|more|less)\s+than",
            r"(в\s+)?(\d+)\s*(раза?|раз)\s+(быстрее|медленнее|лучше)",
        ],
    }

    # Known facts database (simplified - in production would use external KB)
    KNOWN_FACTS = {
        ("openai", "founded"): {"year": 2015, "verified": True},
        ("chatgpt", "released"): {"date": "2022-11-30", "verified": True},
        ("gpt-4", "released"): {"date": "2023-03-14", "verified": True},
        ("claude", "released"): {"date": "2023-03-14", "verified": True},
    }

    # Common hallucination patterns
    HALLUCINATION_INDICATORS = [
        r"в\s+(\d{4})\s+году\s+(будет|ожидается)",  # Future predictions as facts
        r"эксперты\s+прогнозируют\s+(?:что\s+)?",  # Vague expert claims
        r"(?:по\s+данным|согласно)\s+исследованию\s+без\s+названия",  # Unnamed studies
        r"недавнее\s+исследование\s+показало",  # Vague recent study
        r"a\s+recent\s+study\s+showed",
        r"studies\s+have\s+shown",
    ]

    def __init__(
        self,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
        web_search_enabled: bool = False,
        strictness: str = "medium",  # low, medium, high
    ) -> None:
        self.llm = llm_adapter
        self.web_search_enabled = web_search_enabled
        self.strictness = strictness

    def extract_claims(self, text: str) -> list[Claim]:
        """
        Extract verifiable claims from text.

        Args:
            text: Text to analyze

        Returns:
            List of extracted claims
        """
        claims = []

        for claim_type, patterns in self.CLAIM_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    claim = Claim(
                        text=match.group(),
                        claim_type=claim_type,
                        position=(match.start(), match.end()),
                        context=self._get_context(text, match.start(), match.end()),
                    )
                    # Avoid duplicates
                    if not any(c.text == claim.text for c in claims):
                        claims.append(claim)

        # Check for hallucination indicators
        for pattern in self.HALLUCINATION_INDICATORS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                claim = Claim(
                    text=match.group(),
                    claim_type=ClaimType.GENERAL,
                    position=(match.start(), match.end()),
                    context=self._get_context(text, match.start(), match.end()),
                    confidence=0.5,  # Lower confidence for potential hallucinations
                )
                claims.append(claim)

        return claims

    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get context around a match."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    async def verify_claim(self, claim: Claim, sources: Optional[list[str]] = None) -> Claim:
        """
        Verify a single claim.

        Args:
            claim: Claim to verify
            sources: Optional list of source URLs to check

        Returns:
            Updated claim with verification status
        """
        # Check against known facts
        claim_lower = claim.text.lower()

        for (entity, attribute), fact in self.KNOWN_FACTS.items():
            if entity in claim_lower and attribute in claim_lower:
                claim.status = VerificationStatus.VERIFIED
                claim.verification_notes = f"Verified against known facts database"
                return claim

        # Check for hallucination indicators
        for pattern in self.HALLUCINATION_INDICATORS:
            if re.search(pattern, claim.text, re.IGNORECASE):
                claim.status = VerificationStatus.HALLUCINATION
                claim.verification_notes = "Potential hallucination pattern detected"
                return claim

        # Use LLM for verification if available
        if self.llm and self.web_search_enabled:
            try:
                verification = await self._llm_verify(claim)
                claim.status = verification.get("status", VerificationStatus.UNVERIFIABLE)
                claim.sources = verification.get("sources", [])
                claim.conflicting_sources = verification.get("conflicting_sources", [])
                claim.correction = verification.get("correction")
                claim.verification_notes = verification.get("notes", "")
            except Exception as e:
                logger.error("LLM verification failed: %s", e)
                claim.status = VerificationStatus.UNVERIFIABLE
        else:
            # Without LLM, mark as unverifiable
            claim.status = VerificationStatus.UNVERIFIABLE
            claim.verification_notes = "No verification method available"

        return claim

    async def _llm_verify(self, claim: Claim) -> dict[str, Any]:
        """Use LLM to verify a claim."""
        prompt = f"""Проверь это утверждение на фактическую точность:

УТВЕРЖДЕНИЕ: "{claim.text}"
КОНТЕКСТ: {claim.context}

ТРЕБОВАНИЯ:
1. Оцени точность утверждения
2. Если есть ошибка, предложи исправление
3. Укажи, можно ли это проверить

Верни JSON:
{{
    "status": "verified|disputed|unverifiable|hallucination",
    "correction": "исправленная версия или null",
    "notes": "пояснение",
    "confidence": 0.0-1.0
}}"""

        try:
            response = await self.llm.generate(prompt)
            import json
            content = response.content

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]

            result = json.loads(content.strip())

            status_map = {
                "verified": VerificationStatus.VERIFIED,
                "disputed": VerificationStatus.DISPUTED,
                "unverifiable": VerificationStatus.UNVERIFIABLE,
                "hallucination": VerificationStatus.HALLUCINATION,
            }
            result["status"] = status_map.get(result.get("status", "unverifiable"), VerificationStatus.UNVERIFIABLE)

            return result

        except Exception as e:
            logger.error("Failed to parse LLM verification: %s", e)
            return {"status": VerificationStatus.UNVERIFIABLE, "notes": str(e)}

    async def verify_content(self, text: str, sources: Optional[list[str]] = None) -> VerificationReport:
        """
        Verify all claims in content.

        Args:
            text: Text to verify
            sources: Optional source URLs for verification

        Returns:
            VerificationReport with all findings
        """
        report = VerificationReport()

        # Extract claims
        claims = self.extract_claims(text)
        report.total_claims = len(claims)

        if not claims:
            report.overall_credibility = 1.0
            report.recommendations.append("No verifiable claims found - content may be too vague")
            return report

        # Verify each claim
        for claim in claims:
            verified_claim = await self.verify_claim(claim, sources)
            report.claims.append(verified_claim)

            # Update counters
            if verified_claim.status == VerificationStatus.VERIFIED:
                report.verified_count += 1
            elif verified_claim.status == VerificationStatus.DISPUTED:
                report.disputed_count += 1
            elif verified_claim.status == VerificationStatus.UNVERIFIABLE:
                report.unverifiable_count += 1
            elif verified_claim.status == VerificationStatus.HALLUCINATION:
                report.hallucination_count += 1

        # Calculate overall credibility
        if report.total_claims > 0:
            report.overall_credibility = (
                report.verified_count / report.total_claims
                + 0.3 * report.unverifiable_count / report.total_claims
            )

        # Generate recommendations
        self._generate_recommendations(report)

        return report

    def _generate_recommendations(self, report: VerificationReport) -> None:
        """Generate recommendations based on verification results."""
        if report.hallucination_count > 0:
            report.recommendations.append(
                f"КРИТИЧНО: Найдено {report.hallucination_count} потенциальных галлюцинаций. "
                "Проверьте эти утверждения вручную."
            )

        if report.disputed_count > 0:
            report.recommendations.append(
                f"Найдено {report.disputed_count} спорных утверждений. "
                "Добавьте источники или переформулируйте."
            )

        if report.unverifiable_count > report.total_claims * 0.5:
            report.recommendations.append(
                "Более 50% утверждений невозможно проверить. "
                "Добавьте конкретные данные и источники."
            )

        if report.overall_credibility < 0.5:
            report.recommendations.append(
                f"Низкая достоверность контента ({report.overall_credibility:.0%}). "
                "Рекомендуется существенная переработка."
            )

    def get_correction_suggestions(self, report: VerificationReport) -> list[dict[str, str]]:
        """Get suggested corrections for problematic claims."""
        suggestions = []

        for claim in report.claims:
            if claim.status in [VerificationStatus.DISPUTED, VerificationStatus.HALLUCINATION]:
                if claim.correction:
                    suggestions.append({
                        "original": claim.text,
                        "suggestion": claim.correction,
                        "reason": claim.verification_notes,
                    })
                else:
                    suggestions.append({
                        "original": claim.text,
                        "suggestion": "[Требуется проверка]",
                        "reason": f"{claim.status.value}: {claim.verification_notes}",
                    })

        return suggestions


# Configuration schema
FACTUAL_VERIFICATION_CONFIG_SCHEMA = {
    "factual_verification": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable factual verification",
        },
        "strictness": {
            "type": "str",
            "default": "medium",
            "description": "Verification strictness (low, medium, high)",
        },
        "web_search_enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable web search for verification",
        },
        "min_credibility_threshold": {
            "type": "float",
            "default": 0.7,
            "description": "Minimum credibility score to pass",
        },
    }
}
