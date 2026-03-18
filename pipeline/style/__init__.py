"""Style analysis modules."""
from pipeline.style.sentence_variety import SentenceVarietyAnalyzer, SentenceVarietyReport
from pipeline.style.active_voice import (
    ActiveVoiceChecker,
    PassiveVoiceReport,
    PassiveVoiceMatch,
)
from pipeline.style.voice_checker import VoiceChecker, VoiceCheckResult
from pipeline.style.jargon_checker import JargonChecker, JargonReport, JargonTerm

__all__ = [
    "SentenceVarietyAnalyzer", "SentenceVarietyReport",
    "ActiveVoiceChecker",
    "PassiveVoiceReport",
    "PassiveVoiceMatch",
    "VoiceChecker",
    "VoiceCheckResult",
    "JargonChecker",
    "JargonReport",
    "JargonTerm",
]
