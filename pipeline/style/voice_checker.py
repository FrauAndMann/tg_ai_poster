"""
Voice Checker - Ensures consistent editorial voice in content.

Analyzes text for voice consistency including:
- Analytical tone (not promotional)
- Direct, clear communication
- No meta-language or "cringe" phrases
- Consistent editorial voice throughout
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class VoiceCheckResult:
    """Result of voice consistency check."""

    score: float = 0.0
    is_analytical: bool = True
    is_promotional: bool = False
    is_direct: bool = True
    has_meta_language: bool = False
    has_cringe_phrases: bool = False
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def grade(self) -> str:
        """
        Get letter grade for voice quality.

        Returns:
            "Excellent" (90+), "Good" (80-89), "Acceptable" (70-79), "Reject" (<70)
        """
        if self.score >= 90:
            return "Excellent"
        elif self.score >= 80:
            return "Good"
        elif self.score >= 70:
            return "Acceptable"
        else:
            return "Reject"


class VoiceChecker:
    """
    Checks voice consistency in content.

    Ensures:
    - Analytical, not promotional tone
    - Direct, clear communication
    - No meta-language (talking about the text itself)
    - No "cringe" phrases
    - Consistent editorial voice

    The checker evaluates multiple aspects of voice and provides
    a composite score along with specific issues and suggestions.
    """

    # Promotional/sales language patterns
    PROMOTIONAL_PATTERNS = [
        # Russian promotional phrases
        r"\bне\s+упустите\s+свою\s+возможность\b",
        r"\bуникальное\s+предложение\b",
        r"\bэксклюзивно\b",
        r"\bтолько\s+сегодня\b",
        r"\bограниченное\s+время\b",
        r"\bспешите\b",
        r"\bзакажите\s+прямо\s+сейчас\b",
        r"\bлучший\s+в\s+своём\s+роде\b",
        r"\bреволюционный\s+продукт\b",
        r"\bгарантированный\s+результат\b",
        r"\bпотрясающий\s+результат\b",
        r"\bвпечатляющий\s+эффект\b",
        r"\bизменит\s+вашу\s+жизнь\b",
        r"\bпокупайт[еи]\b",
        r"\bзаказывай\b",
        r"\bподпишитесь?\s+на\b",
        r"\bподписывайтесь\b",
        # English promotional phrases
        r"\bdon'?t\s+miss\s+(out\s+on|this|your)\b",
        r"\bexclusive\s+offer\b",
        r"\blimited\s+time\b",
        r"\bact\s+now\b",
        r"\bhurry\b",
        r"\border\s+(now|today)\b",
        r"\bbest\s+in\s+(class|the\s+world)\b",
        r"\brevolutionary\b",
        r"\bguaranteed\s+results?\b",
        r"\bamazing\s+results?\b",
        r"\bgame-?changing\b",
        r"\bwill\s+change\s+your\s+life\b",
        r"\bbuy\s+now\b",
        r"\bsubscribe\s+(now|today)\b",
    ]

    # Meta-language patterns (talking about the text itself)
    META_LANGUAGE_PATTERNS = [
        # Russian meta-language
        r"\bв\s+этой\s+статье\b",
        r"\bв\s+данном\s+материале\b",
        r"\bв\s+этом\s+пост[еа]?\b",
        r"\bв\s+данном\s+пост[еа]?\b",
        r"\bмы\s+рассмотрим\b",
        r"\bя\s+расскажу\b",
        r"\bдавайте\s+рассмотрим\b",
        r"\bсегодня\s+мы\s+поговорим\b",
        r"\bхочу\s+отметить\b",
        r"\bхотел\s+бы\s+сказать\b",
        r"\bя\s+бы\s+хотел\b",
        r"\bпозвольте\s+мне\b",
        r"\bкак\s+я\s+уже\s+говорил\b",
        r"\bкак\s+было\s+сказано\b",
        r"\bвозвращаясь\s+к\s+теме\b",
        # English meta-language
        r"\bin\s+this\s+(article|post|piece|blog)\b",
        r"\bin\s+this\s+(text|material)\b",
        r"\bwe\s+will\s+(discuss|examine|explore|look\s+at)\b",
        r"\bi\s+will\s+(tell|explain|show|discuss)\b",
        r"\blet'?s?\s+(look|examine|explore|discuss)\b",
        r"\btoday\s+we'?ll?\s+(talk|discuss)\b",
        r"\bi\s+want\s+to\s+(mention|note|say|highlight)\b",
        r"\bi\s+would\s+like\s+to\s+(say|point\s+out|mention)\b",
        r"\ballow\s+me\s+to\b",
        r"\bas\s+i\s+(mentioned|said|noted)\s+(earlier|before|above)\b",
        r"\bas\s+(was|has\s+been)\s+(mentioned|said|noted)\b",
        r"\bgetting\s+back\s+to\s+(the\s+)?topic\b",
    ]

    # Cringe phrases (unnatural, overly enthusiastic or awkward)
    CRINGE_PHRASES = [
        # Russian cringe phrases
        r"\bни\s*для\s*кого\s*не\s*секрет\b",
        r"\bкак\s*известно\b",
        r"\bвсем\s*известно\b",
        r"\bне\s*секрет\b",
        r"\bмногие\s*спрашивают\b",
        r"\bчасто\s*задают\s*вопрос\b",
        r"\bвопрос\s*который\s*волнует\s*многих\b",
        r"\bмногие\s*думают\b",
        r"\bвсе\s*мы\s*знаем\b",
        r"\bвы\s*наверняка\s*слышали\b",
        r"\bвы\s*конечно\s*же\s*знаете\b",
        r"\bконечно\s*же\b",
        r"\bбез\s*всякого\s*сомнения\b",
        r"\bабсолютно\s*очевидно\b",
        r"\bсамо\s*собой\s*разумеется\b",
        r"\bдрузья\b",
        r"\bколлеги\b",
        r"\bуважаемые\s*читатели\b",
        r"\bя\s*рад\s*сообщить\b",
        r"\bс\s*большим\s*удовольствием\b",
        r"\bс\s*огромным\s*интересом\b",
        r"\bне\s*могу\s*не\s*отметить\b",
        r"\bне\s*могу\s*не\s*сказать\b",
        # English cringe phrases
        r"\bit'?s?\s+no\s+secret\s+that\b",
        r"\bas\s+we\s+all\s+know\b",
        r"\beveryone\s+knows\s+that\b",
        r"\bmany\s+people\s+ask\b",
        r"\ba\s+common\s+question\s+(is|that)\b",
        r"\bmany\s+people\s+think\b",
        r"\bwe\s+all\s+know\s+that\b",
        r"\byou'?ve?\s+probably\s+heard\b",
        r"\byou\s+(surely|certainly|of\s+course)\s+know\b",
        r"\bof\s+course\b",
        r"\bwithout\s+a\s+doubt\b",
        r"\bit'?s?\s+absolutely\s+obvious\b",
        r"\bit\s+goes\s+without\s+saying\b",
        r"\bfriends?\b",
        r"\bdear\s+readers?\b",
        r"\bi'?m?\s+happy\s+to\s+(report|announce|say|tell)\b",
        r"\bwith\s+(great|huge)\s+pleasure\b",
        r"\bi\s+cannot\s+help\s+but\s+(mention|note)\b",
    ]

    # Indirect/weak language patterns (opposite of direct)
    INDIRECT_PATTERNS = [
        # Russian indirect language
        r"\bкак\s+бы\b",
        r"\bтипа\b",
        r"\bвроде\s+бы\b",
        r"\bпо\s+сути\b",
        r"\bсобственно\s+говоря\b",
        r"\bв\s+принципе\b",
        r"\bвобщем[-\s]*то\b",
        r"\bну\b\s*,",
        r"\bкороче\s+(говоря)?\b",
        r"\bпожалуй\b",
        r"\bнаверное\b",
        r"\bвозможно\b",
        r"\bможет\s+быть\b",
        r"\bпо-видимому\b",
        # English indirect language
        r"\bkind\s+of\b",
        r"\bsort\s+of\b",
        r"\blike\b\s*,",
        r"\bbasically\b",
        r"\bin\s+principle\b",
        r"\bwell\b\s*,",
        r"\banyway\b\s*,",
        r"\bperhaps\b",
        r"\bprobably\b",
        r"\bpossibly\b",
        r"\bmaybe\b",
        r"\bapparently\b",
        r"\bit\s+seems\s+(that|like)\b",
    ]

    # Analytical language indicators (positive)
    ANALYTICAL_INDICATORS = [
        # Russian analytical language
        r"\bанализ\b",
        r"\bисследование\b",
        r"\bданные\s+показывают\b",
        r"\bстатистика\b",
        r"\bсравнение\b",
        r"\bвывод\b",
        r"\bзаключение\b",
        r"\bрезультат\s+анализа\b",
        r"\bколичество\s+составляет\b",
        r"\bдоля\s+равна\b",
        r"\bпо\s+сравнению\s+с\b",
        r"\bв\s+отличие\s+от\b",
        r"\bсогласно\s+данным\b",
        r"\bна\s+основании\b",
        r"\bисходя\s+из\b",
        r"\bключевой\s+фактор\b",
        r"\bосновной\s+причина\b",
        # English analytical language
        r"\banalysis\b",
        r"\bresearch\b",
        r"\bdata\s+(shows?|indicates?|suggests?)\b",
        r"\bstatistics?\b",
        r"\bcomparison\b",
        r"\bconclusion\b",
        r"\bresults?\s+(show|indicate|suggest)\b",
        r"\bthe\s+figure\s+(is|stands\s+at)\b",
        r"\bthe\s+share\s+(is|equals)\b",
        r"\bcompared\s+to\b",
        r"\bin\s+contrast\s+to\b",
        r"\baccording\s+to\s+(data|the\s+study)\b",
        r"\bbased\s+on\b",
        r"\bthe\s+key\s+factor\b",
        r"\bthe\s+main\s+reason\b",
    ]

    def __init__(self, pass_threshold: float = 70.0) -> None:
        """
        Initialize the voice checker.

        Args:
            pass_threshold: Minimum score to pass (default: 70.0)
        """
        self.pass_threshold = pass_threshold
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        pattern_groups = {
            "promotional": self.PROMOTIONAL_PATTERNS,
            "meta_language": self.META_LANGUAGE_PATTERNS,
            "cringe": self.CRINGE_PHRASES,
            "indirect": self.INDIRECT_PATTERNS,
            "analytical": self.ANALYTICAL_INDICATORS,
        }

        for group_name, patterns in pattern_groups.items():
            self._compiled_patterns[group_name] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def check(self, text: str) -> VoiceCheckResult:
        """
        Check text for voice consistency.

        Args:
            text: Text to analyze

        Returns:
            VoiceCheckResult with findings
        """
        result = VoiceCheckResult()
        score = 100.0  # Start with perfect score

        # Check for promotional language
        promotional_matches = self._find_matches(text, "promotional")
        result.is_promotional = len(promotional_matches) > 0
        if promotional_matches:
            penalty = min(30.0, len(promotional_matches) * 10)
            score -= penalty
            result.issues.append(f"Promotional language detected: {self._format_matches(promotional_matches[:3])}")
            result.suggestions.append("Remove promotional phrases and focus on factual information")

        # Check for meta-language
        meta_matches = self._find_matches(text, "meta_language")
        result.has_meta_language = len(meta_matches) > 0
        if meta_matches:
            penalty = min(20.0, len(meta_matches) * 5)
            score -= penalty
            result.issues.append(f"Meta-language detected: {self._format_matches(meta_matches[:3])}")
            result.suggestions.append("Remove references to the text itself; focus on content")

        # Check for cringe phrases
        cringe_matches = self._find_matches(text, "cringe")
        result.has_cringe_phrases = len(cringe_matches) > 0
        if cringe_matches:
            penalty = min(25.0, len(cringe_matches) * 8)
            score -= penalty
            result.issues.append(f"Cringe phrases detected: {self._format_matches(cringe_matches[:3])}")
            result.suggestions.append("Replace cliched phrases with more natural, direct language")

        # Check for indirect language
        indirect_matches = self._find_matches(text, "indirect")
        if indirect_matches:
            penalty = min(15.0, len(indirect_matches) * 3)
            score -= penalty
            result.is_direct = penalty < 10
            if penalty >= 10:
                result.issues.append(f"Indirect language detected: {self._format_matches(indirect_matches[:3])}")
                result.suggestions.append("Use more direct, confident language")

        # Check for analytical indicators (bonus)
        analytical_matches = self._find_matches(text, "analytical")
        if analytical_matches:
            result.is_analytical = True
            # Bonus for analytical language (up to 10 points, but don't exceed 100)
            bonus = min(10.0, len(analytical_matches) * 2)
            score = min(100.0, score + bonus)
        else:
            # No penalty for lack of analytical language, just not a bonus
            result.is_analytical = not (result.is_promotional or result.has_meta_language or result.has_cringe_phrases)

        result.score = max(0.0, round(score, 1))
        return result

    def _find_matches(self, text: str, group_name: str) -> list[str]:
        """Find all matches for a pattern group."""
        matches = []
        patterns = self._compiled_patterns.get(group_name, [])

        for pattern in patterns:
            for match in pattern.finditer(text):
                matches.append(match.group())

        return matches

    def _format_matches(self, matches: list[str]) -> str:
        """Format matches for display in issues."""
        unique = list(dict.fromkeys(matches))  # Remove duplicates, preserve order
        if len(unique) <= 3:
            return ", ".join(f'"{m}"' for m in unique)
        return ", ".join(f'"{m}"' for m in unique[:3]) + f" and {len(unique) - 3} more"

    @property
    def grade(self) -> str:
        """
        Get grade description for the checker.

        Returns:
            Description of the voice checker
        """
        return "VoiceChecker - Analytical voice consistency checker"


# Configuration schema
VOICE_CHECKER_CONFIG_SCHEMA = {
    "voice_checker": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable voice consistency checking",
        },
        "pass_threshold": {
            "type": "float",
            "default": 70.0,
            "description": "Minimum score to pass voice check",
        },
        "flag_promotional": {
            "type": "bool",
            "default": True,
            "description": "Flag promotional language",
        },
        "flag_meta_language": {
            "type": "bool",
            "default": True,
            "description": "Flag meta-language references",
        },
        "flag_cringe": {
            "type": "bool",
            "default": True,
            "description": "Flag cringe phrases",
        },
    }
}
