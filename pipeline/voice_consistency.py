"""
Voice Consistency Checker - Ensures consistent brand voice across posts.

Analyzes writing style, tone, and personality to maintain voice consistency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class ToneAttribute(Enum):
    """Tone attributes for voice."""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    TECHNICAL = "technical"
    FRIENDLY = "friendly"
    AUTHORITATIVE = "authoritative"
    PLAYFUL = "playful"
    SERIOUS = "serious"
    ENTHUSIASTIC = "enthusiastic"


@dataclass(slots=True)
class VoiceProfile:
    """Brand voice profile."""
    name: str
    tone_attributes: list[ToneAttribute]
    formality_level: float  # 0.0 (very casual) to 1.0 (very formal)
    emoji_usage: str  # none, minimal, moderate, expressive
    sentence_complexity: str  # simple, moderate, complex
    technical_depth: str  # beginner, intermediate, advanced
    personality_traits: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VoiceAnalysis:
    """Result of voice analysis on text."""
    detected_tone: list[ToneAttribute]
    formality_score: float
    emoji_count: int
    avg_sentence_length: float
    technical_term_density: float
    consistency_score: float
    deviations: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class VoiceConsistencyChecker:
    """
    Checks and maintains voice consistency across posts.

    Features:
    - Voice profile definition
    - Tone detection
    - Consistency scoring
    - Deviation alerts
    """

    # Default brand voice profile
    DEFAULT_VOICE = VoiceProfile(
        name="tg_ai_poster_default",
        tone_attributes=[
            ToneAttribute.PROFESSIONAL,
            ToneAttribute.FRIENDLY,
            ToneAttribute.TECHNICAL,
        ],
        formality_level=0.6,
        emoji_usage="moderate",
        sentence_complexity="moderate",
        technical_depth="intermediate",
        personality_traits=[
            "analytical",
            "curious",
            "helpful",
            "forward-thinking",
        ],
    )

    # Tone indicators
    TONE_INDICATORS = {
        ToneAttribute.PROFESSIONAL: [
            "анализ", "исследование", "данные", "показывают",
            "analysis", "research", "data", "indicates",
        ],
        ToneAttribute.CASUAL: [
            "кстати", "прикинь", "короче", "в общем",
            "btw", "basically", "honestly", "actually",
        ],
        ToneAttribute.TECHNICAL: [
            "алгоритм", "нейросеть", "API", "интеграция",
            "algorithm", "neural network", "implementation",
        ],
        ToneAttribute.FRIENDLY: [
            "поможет", "полезный", "рекомендую", "совет",
            "helpful", "useful", "recommend", "tip",
        ],
        ToneAttribute.AUTHORITATIVE: [
            "важно понимать", "ключевой момент", "эксперты",
            "important to understand", "key point", "experts",
        ],
        ToneAttribute.PLAYFUL: [
            "забавно", "интересный факт", "представьте",
            "fun fact", "imagine", "cool thing",
        ],
        ToneAttribute.SERIOUS: [
            "критический", "серьезный", "последствия",
            "critical", "serious", "implications",
        ],
        ToneAttribute.ENTHUSIASTIC: [
            "потрясающе", "увлекательно", "не пропустите",
            "amazing", "exciting", "don't miss",
        ],
    }

    # Formality markers
    FORMAL_MARKERS = [
        "следовательно", "таким образом", "в свою очередь",
        "therefore", "thus", "consequently", "furthermore",
    ]

    INFORMAL_MARKERS = [
        "типа", "как бы", "вроде", "прикинь",
        "kinda", "sorta", "like", "basically",
    ]

    def __init__(
        self,
        target_voice: Optional[VoiceProfile] = None,
    ) -> None:
        self.target_voice = target_voice or self.DEFAULT_VOICE
        self._historical_analyses: list[VoiceAnalysis] = []

    def analyze(self, text: str) -> VoiceAnalysis:
        """
        Analyze text for voice consistency.

        Args:
            text: Text to analyze

        Returns:
            VoiceAnalysis with findings
        """
        # Detect tone
        detected_tone = self._detect_tone(text)

        # Calculate formality
        formality_score = self._calculate_formality(text)

        # Count emojis
        emoji_count = self._count_emojis(text)

        # Calculate sentence complexity
        avg_sentence_length = self._avg_sentence_length(text)

        # Technical term density
        technical_density = self._calculate_technical_density(text)

        # Calculate consistency score
        consistency_score, deviations = self._calculate_consistency(
            detected_tone=detected_tone,
            formality_score=formality_score,
            emoji_count=emoji_count,
            avg_sentence_length=avg_sentence_length,
            technical_density=technical_density,
        )

        # Generate suggestions
        suggestions = self._generate_suggestions(deviations)

        analysis = VoiceAnalysis(
            detected_tone=detected_tone,
            formality_score=formality_score,
            emoji_count=emoji_count,
            avg_sentence_length=avg_sentence_length,
            technical_term_density=technical_density,
            consistency_score=consistency_score,
            deviations=deviations,
            suggestions=suggestions,
        )

        self._historical_analyses.append(analysis)
        if len(self._historical_analyses) > 50:
            self._historical_analyses.pop(0)

        return analysis

    def _detect_tone(self, text: str) -> list[ToneAttribute]:
        """Detect tone attributes from text."""
        text_lower = text.lower()
        scores: dict[ToneAttribute, int] = {}

        for tone, indicators in self.TONE_INDICATORS.items():
            score = sum(1 for ind in indicators if ind.lower() in text_lower)
            if score > 0:
                scores[tone] = score

        # Return top 3 detected tones
        sorted_tones = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_tones[:3]]

    def _calculate_formality(self, text: str) -> float:
        """Calculate formality score (0.0 - 1.0)."""
        text_lower = text.lower()

        formal_count = sum(1 for m in self.FORMAL_MARKERS if m.lower() in text_lower)
        informal_count = sum(1 for m in self.INFORMAL_MARKERS if m.lower() in text_lower)

        total = formal_count + informal_count
        if total == 0:
            return 0.5

        return formal_count / total

    def _count_emojis(self, text: str) -> int:
        """Count emoji usage."""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "]+",
            flags=re.UNICODE,
        )
        matches = emoji_pattern.findall(text)
        return len(matches)

    def _avg_sentence_length(self, text: str) -> float:
        """Calculate average sentence length."""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.0

        total_words = sum(len(s.split()) for s in sentences)
        return total_words / len(sentences)

    def _calculate_technical_density(self, text: str) -> float:
        """Calculate technical term density."""
        # Technical terms often are capitalized, contain numbers, or specific patterns
        words = text.split()
        if not words:
            return 0.0

        technical_patterns = [
            r'\b[A-Z]{2,}\b',  # Acronyms
            r'\b\w+\d+\w*\b',  # Terms with numbers (GPT-4, etc.)
            r'\b[A-Z][a-z]+[A-Z]',  # CamelCase
        ]

        technical_count = 0
        for word in words:
            for pattern in technical_patterns:
                if re.search(pattern, word):
                    technical_count += 1
                    break

        return technical_count / len(words)

    def _calculate_consistency(
        self,
        detected_tone: list[ToneAttribute],
        formality_score: float,
        emoji_count: int,
        avg_sentence_length: float,
        technical_density: float,
    ) -> tuple[float, list[str]]:
        """Calculate voice consistency score and deviations."""
        deviations = []
        score = 1.0

        # Check tone alignment
        target_tones = set(self.target_voice.tone_attributes)
        detected_set = set(detected_tone)
        tone_overlap = len(target_tones & detected_set) / max(len(target_tones), 1)

        if tone_overlap < 0.3:
            deviations.append(
                f"Detected tone {detected_tone} doesn't match target {self.target_voice.tone_attributes}"
            )
            score -= 0.3

        # Check formality
        formality_diff = abs(formality_score - self.target_voice.formality_level)
        if formality_diff > 0.3:
            deviations.append(
                f"Formality level {formality_score:.2f} differs from target {self.target_voice.formality_level}"
            )
            score -= 0.2

        # Check emoji usage
        emoji_limits = {"none": 0, "minimal": 2, "moderate": 5, "expressive": 10}
        max_emojis = emoji_limits.get(self.target_voice.emoji_usage, 5)

        if emoji_count > max_emojis:
            deviations.append(
                f"Too many emojis ({emoji_count}) for target level '{self.target_voice.emoji_usage}'"
            )
            score -= 0.1

        # Check sentence complexity
        if self.target_voice.sentence_complexity == "simple" and avg_sentence_length > 15:
            deviations.append(f"Sentences too long (avg {avg_sentence_length:.1f} words) for 'simple' target")
            score -= 0.1
        elif self.target_voice.sentence_complexity == "complex" and avg_sentence_length < 15:
            deviations.append(f"Sentences too short (avg {avg_sentence_length:.1f} words) for 'complex' target")
            score -= 0.1

        return max(0.0, score), deviations

    def _generate_suggestions(self, deviations: list[str]) -> list[str]:
        """Generate suggestions based on deviations."""
        suggestions = []

        for deviation in deviations:
            if "tone" in deviation.lower():
                suggestions.append(
                    f"Adjust tone to match target: {self.target_voice.tone_attributes}"
                )
            elif "formality" in deviation.lower():
                if "differs" in deviation:
                    suggestions.append(
                        "Use more formal language" if self.target_voice.formality_level > 0.5
                        else "Use more casual, conversational language"
                    )
            elif "emoji" in deviation.lower():
                suggestions.append(
                    f"Reduce emoji usage (target: {self.target_voice.emoji_usage})"
                )
            elif "sentences" in deviation.lower():
                suggestions.append(
                    "Break up long sentences" if "too long" in deviation
                    else "Combine short sentences for better flow"
                )

        return suggestions

    def get_voice_drift_report(self) -> dict[str, Any]:
        """Analyze voice drift over recent posts."""
        if len(self._historical_analyses) < 3:
            return {"status": "insufficient_data"}

        recent = self._historical_analyses[-10:]

        avg_consistency = sum(a.consistency_score for a in recent) / len(recent)
        avg_formality = sum(a.formality_score for a in recent) / len(recent)

        # Detect drift
        if len(recent) >= 5:
            early = recent[:len(recent)//2]
            late = recent[len(recent)//2:]

            early_formality = sum(a.formality_score for a in early) / len(early)
            late_formality = sum(a.formality_score for a in late) / len(late)

            drift = late_formality - early_formality
        else:
            drift = 0.0

        return {
            "avg_consistency": avg_consistency,
            "avg_formality": avg_formality,
            "formality_drift": drift,
            "analyses_count": len(recent),
            "target_voice": self.target_voice.name,
            "needs_calibration": avg_consistency < 0.7,
        }


# Configuration schema
VOICE_CONSISTENCY_CONFIG_SCHEMA = {
    "voice_consistency": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable voice consistency checking",
        },
        "min_consistency_score": {
            "type": "float",
            "default": 0.7,
            "description": "Minimum consistency score required",
        },
        "alert_on_drift": {
            "type": "bool",
            "default": True,
            "description": "Alert when voice drifts significantly",
        },
    }
}
