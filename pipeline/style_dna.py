"""
Style DNA System - Extracts writing style signature from top posts.

Analyzes highest-engagement posts and extracts statistical signature:
sentence length, punctuation density, emoji frequency, rhetorical questions, etc.
Injects style constraints into generation prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from core.constants import STYLE_PROFILE_MIN_POSTS
from core.logger import get_logger

if TYPE_CHECKING:
    from memory.post_store import PostStore

logger = get_logger(__name__)


@dataclass(slots=True)
class StyleSignature:
    """Statistical signature of writing style."""

    # Sentence structure
    avg_sentence_length: float = 15.0
    sentence_length_variance: float = 5.0
    max_sentence_length: int = 30

    # Paragraph structure
    avg_paragraph_sentences: float = 3.0
    max_paragraph_length: int = 4

    # Punctuation patterns
    exclamation_frequency: float = 0.02  # Per character
    question_frequency: float = 0.01
    ellipsis_frequency: float = 0.005

    # Emoji patterns
    emoji_frequency: float = 0.01
    emoji_in_title: bool = True
    common_emojis: list[str] = field(default_factory=lambda: ["🚀", "💡", "🤖"])

    # Voice patterns
    first_person_ratio: float = 0.1  # "we", "I"
    second_person_ratio: float = 0.2  # "you"
    rhetorical_questions: float = 0.05  # Per paragraph
    passive_voice_ratio: float = 0.1

    # Content patterns
    numbers_frequency: float = 0.02  # Digits per character
    link_frequency: float = 0.01  # Links per character
    hashtag_frequency: float = 0.005

    # Hook patterns
    hook_with_question: bool = True
    hook_with_statistic: bool = True
    hook_with_quote: bool = False

    # Analysis depth
    analysis_sentence_count: int = 4
    uses_analogies: bool = True

    # Metadata
    posts_analyzed: int = 0
    last_updated: Optional[datetime] = None
    confidence: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "sentence_structure": {
                "avg_length": self.avg_sentence_length,
                "variance": self.sentence_length_variance,
                "max": self.max_sentence_length,
            },
            "paragraph_structure": {
                "avg_sentences": self.avg_paragraph_sentences,
                "max_length": self.max_paragraph_length,
            },
            "punctuation": {
                "exclamation": self.exclamation_frequency,
                "question": self.question_frequency,
                "ellipsis": self.ellipsis_frequency,
            },
            "emoji": {
                "frequency": self.emoji_frequency,
                "in_title": self.emoji_in_title,
                "common": self.common_emojis,
            },
            "voice": {
                "first_person": self.first_person_ratio,
                "second_person": self.second_person_ratio,
                "rhetorical_questions": self.rhetorical_questions,
                "passive_voice": self.passive_voice_ratio,
            },
            "metadata": {
                "posts_analyzed": self.posts_analyzed,
                "last_updated": self.last_updated.isoformat() if self.last_updated else None,
                "confidence": self.confidence,
            },
        }


class StyleDNA:
    """
    Analyzes and maintains channel writing style.

    Features:
    - Statistical analysis of top posts
    - Style signature extraction
    - Style constraint generation for prompts
    - Continuous learning from engagement feedback
    """

    # Passive voice patterns (Russian)
    PASSIVE_PATTERNS = [
        r"\bбыл[аои]?\s+\w+",
        r"\bбыли\s+\w+",
        r"\bявляется\b",
        r"\bостается\b",
        r"\bстановится\b",
        r"\bможет быть\b",
    ]

    # Rhetorical question patterns
    RHETORICAL_STARTERS = [
        "почему",
        "зачем",
        "как",
        "что если",
        "а что",
        "интересно",
        "знаете ли",
    ]

    def __init__(
        self,
        post_store: Optional["PostStore"] = None,
        min_posts: int = STYLE_PROFILE_MIN_POSTS,
    ) -> None:
        """
        Initialize Style DNA system.

        Args:
            post_store: Post store for fetching top posts
            min_posts: Minimum posts needed for analysis
        """
        self.post_store = post_store
        self.min_posts = min_posts
        self.signature = StyleSignature()

    def analyze_posts(self, posts: list[str]) -> StyleSignature:
        """
        Analyze a list of posts and extract style signature.

        Args:
            posts: List of post contents to analyze

        Returns:
            StyleSignature: Extracted style signature
        """
        if not posts:
            return self.signature

        all_text = " ".join(posts)
        total_chars = len(all_text)
        total_words = len(all_text.split())

        # Sentence analysis
        sentences = re.split(r'[.!?]+', all_text)
        sentences = [s.strip() for s in sentences if s.strip()]

        sentence_lengths = [len(s.split()) for s in sentences]
        avg_length = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 15
        variance = (
            sum((l - avg_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)
            if sentence_lengths else 5
        )

        # Paragraph analysis
        paragraphs = all_text.split("\n\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        para_sentences = [
            len(re.split(r'[.!?]+', p))
            for p in paragraphs
        ]

        # Punctuation
        exc_count = all_text.count("!")
        q_count = all_text.count("?")
        ellipsis_count = all_text.count("...")

        # Emoji detection
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "]+",
            flags=re.UNICODE,
        )
        emojis = emoji_pattern.findall(all_text)
        emoji_counter: dict[str, int] = {}
        for e in emojis:
            emoji_counter[e] = emoji_counter.get(e, 0) + 1

        # Voice analysis
        first_person = len(re.findall(r"\b(мы|нам|наш|я|мне|мой)\b", all_text, re.I))
        second_person = len(re.findall(r"\b(вы|вам|ваш|ты|тебе)\b", all_text, re.I))
        rhetorical = sum(
            1 for s in sentences
            if any(s.lower().startswith(st) for st in self.RHETORICAL_STARTERS)
        )
        passive_count = sum(
            len(re.findall(p, all_text, re.I))
            for p in self.PASSIVE_PATTERNS
        )

        # Numbers and links
        numbers = len(re.findall(r"\d+", all_text))
        links = len(re.findall(r"https?://", all_text))
        hashtags = len(re.findall(r"#\w+", all_text))

        # Update signature
        total_sentences = len(sentences)
        total_paragraphs = len(paragraphs)

        self.signature = StyleSignature(
            avg_sentence_length=avg_length,
            sentence_length_variance=variance,
            max_sentence_length=int(max(sentence_lengths)) if sentence_lengths else 30,
            avg_paragraph_sentences=sum(para_sentences) / len(para_sentences) if para_sentences else 3,
            max_paragraph_length=int(max(para_sentences)) if para_sentences else 4,
            exclamation_frequency=exc_count / total_chars if total_chars else 0,
            question_frequency=q_count / total_chars if total_chars else 0,
            ellipsis_frequency=ellipsis_count / total_chars if total_chars else 0,
            emoji_frequency=len(emojis) / total_chars if total_chars else 0,
            emoji_in_title=True,  # Default
            common_emojis=[
                e for e, _ in sorted(emoji_counter.items(), key=lambda x: x[1], reverse=True)[:5]
            ] or ["🚀", "💡"],
            first_person_ratio=first_person / total_sentences if total_sentences else 0,
            second_person_ratio=second_person / total_sentences if total_sentences else 0,
            rhetorical_questions=rhetorical / total_paragraphs if total_paragraphs else 0,
            passive_voice_ratio=passive_count / total_sentences if total_sentences else 0,
            numbers_frequency=numbers / total_chars if total_chars else 0,
            link_frequency=links / total_chars if total_chars else 0,
            hashtag_frequency=hashtags / total_chars if total_chars else 0,
            hook_with_question=rhetorical > len(posts) * 0.5,
            hook_with_statistic=numbers > len(posts) * 3,
            hook_with_quote=all_text.count('"') > len(posts) * 2,
            analysis_sentence_count=int(avg_length * 0.3),
            uses_analogies="как" in all_text.lower() or "например" in all_text.lower(),
            posts_analyzed=len(posts),
            last_updated=datetime.now(),
            confidence=min(1.0, len(posts) / self.min_posts),
        )

        logger.info("Analyzed %d posts, confidence: %.2f", len(posts), self.signature.confidence)
        return self.signature

    async def analyze_top_posts(self, limit: int = 20) -> StyleSignature:
        """
        Analyze top performing posts from store.

        Args:
            limit: Number of top posts to analyze

        Returns:
            StyleSignature: Extracted style signature
        """
        if not self.post_store:
            logger.warning("No post store available for analysis")
            return self.signature

        try:
            # Get top posts by engagement
            top_posts = await self.post_store.get_top_posts(limit=limit)

            if len(top_posts) < self.min_posts:
                logger.warning(
                    "Not enough posts for reliable analysis: %d < %d",
                    len(top_posts), self.min_posts
                )

            posts_content = [p.content for p in top_posts if p.content]
            return self.analyze_posts(posts_content)

        except Exception as e:
            logger.error("Failed to analyze top posts: %s", e)
            return self.signature

    def get_style_prompt_instructions(self) -> str:
        """
        Generate style instructions for LLM prompt.

        Returns:
            str: Style instructions to inject into prompt
        """
        sig = self.signature

        instructions = []

        # Sentence structure
        if sig.avg_sentence_length > 0:
            instructions.append(
                f"- Средняя длина предложения: ~{int(sig.avg_sentence_length)} слов. "
                f"Не более {sig.max_sentence_length} слов в предложении."
            )

        # Paragraph structure
        instructions.append(
            f"- Средний абзац: {int(sig.avg_paragraph_sentences)} предложения. "
            f"Максимум {sig.max_paragraph_length} предложений."
        )

        # Voice
        if sig.second_person_ratio > 0.1:
            instructions.append("- Обращайся к читателю на 'ты' или 'вы'.")
        if sig.first_person_ratio > 0.05:
            instructions.append("- Используй 'мы' для коллективного мнения канала.")

        # Rhetorical questions
        if sig.rhetorical_questions > 0.03:
            instructions.append(
                "- Начинай с риторического вопроса или интригующего факта."
            )

        # Avoid passive voice
        if sig.passive_voice_ratio < 0.15:
            instructions.append("- Избегай пассивного залога. Пиши активно.")

        # Emojis
        if sig.emoji_frequency > 0.005:
            common = ", ".join(sig.common_emojis[:3])
            instructions.append(f"- Используй эмодзи уместно: {common}")
        if sig.emoji_in_title:
            instructions.append("- Добавь 1-2 эмодзи в заголовок.")

        # Numbers and statistics
        if sig.hook_with_statistic:
            instructions.append("- Начинай с конкретных цифр или статистики.")

        return "\n".join(instructions)


# Configuration schema
STYLE_DNA_CONFIG_SCHEMA = {
    "style_dna": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable Style DNA learning",
        },
        "min_posts": {
            "type": "int",
            "default": 10,
            "min": 5,
            "max": 50,
            "description": "Minimum posts for style analysis",
        },
        "update_interval_days": {
            "type": "int",
            "default": 7,
            "description": "Days between style updates",
        },
    }
}
