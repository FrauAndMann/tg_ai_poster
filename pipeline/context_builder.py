"""
Context Builder - Assembles structured context for LLM generation.

Transforms raw articles into a structured context object with
verified facts, entities, and confidence scores.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import re

from core.logger import get_logger
from pipeline.source_collector import Article

logger = get_logger(__name__)


@dataclass
class KeyFact:
    """A verified key fact with confidence score."""
    content: str
    source_url: str
    source_name: str
    confidence: float = 1.0
    needs_verification: bool = False

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "confidence": self.confidence,
            "needs_verification": self.needs_verification,
        }


@dataclass
class Entity:
    """An extracted entity (company, model, researcher, etc.)."""
    name: str
    entity_type: str  # company, model, researcher, benchmark, technology
    mentions: int = 1
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "mentions": self.mentions,
            "confidence": self.confidence,
        }


@dataclass
class VerifiedSource:
    """A verified source with trust score."""
    article: Article
    tier: int
    trust_score: float
    url_valid: bool = True
    snapshot: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "title": self.article.title,
            "url": self.article.url,
            "source": self.article.source,
            "tier": self.tier,
            "trust_score": self.trust_score,
            "url_valid": self.url_valid,
            "published_at": self.article.published_at.isoformat() if self.article.published_at else None,
        }


@dataclass
class StructuredContext:
    """
    Structured context object for LLM generation.

    Contains all verified information needed to generate a post,
    eliminating hallucination surface area.
    """
    topic: str
    sources: list[VerifiedSource]
    key_facts: list[KeyFact]
    entities: list[Entity]
    source_context: str
    avg_confidence: float = 1.0
    min_sources_met: bool = True
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "sources": [s.to_dict() for s in self.sources],
            "key_facts": [f.to_dict() for f in self.key_facts],
            "entities": [e.to_dict() for e in self.entities],
            "source_context": self.source_context,
            "avg_confidence": self.avg_confidence,
            "min_sources_met": self.min_sources_met,
            "generated_at": self.generated_at.isoformat(),
        }

    def to_llm_context(self) -> str:
        """Format context for LLM prompt."""
        parts = [f"TOPIC: {self.topic}\n"]

        # Sources with confidence
        parts.append("SOURCES:")
        for s in self.sources:
            confidence_marker = "" if s.trust_score >= 0.8 else " [lower confidence]"
            parts.append(f"- {s.article.source}: {s.article.title}{confidence_marker}")
            parts.append(f"  URL: {s.article.url}")
            parts.append(f"  Tier: {s.tier}, Trust: {s.trust_score:.0%}")
        parts.append("")

        # Key facts with confidence
        parts.append("KEY FACTS:")
        for f in self.key_facts:
            verification_marker = " [requires verification]" if f.needs_verification else ""
            parts.append(f"- {f.content}{verification_marker}")
            parts.append(f"  Source: {f.source_name} (confidence: {f.confidence:.0%})")
        parts.append("")

        # Entities
        parts.append("KEY ENTITIES:")
        entity_groups = {}
        for e in self.entities:
            if e.entity_type not in entity_groups:
                entity_groups[e.entity_type] = []
            entity_groups[e.entity_type].append(e.name)
        for etype, names in entity_groups.items():
            parts.append(f"- {etype.capitalize()}: {', '.join(names)}")
        parts.append("")

        # Overall confidence
        parts.append(f"AVERAGE CONFIDENCE: {self.avg_confidence:.0%}")
        if not self.min_sources_met:
            parts.append("WARNING: Minimum source requirement not met")

        return "\n".join(parts)


class ContextBuilder:
    """
    Builds structured context from verified sources.

    Extracts facts, entities, and creates a context object
    that minimizes hallucination risk.
    """

    # Known AI companies and their patterns
    KNOWN_COMPANIES = [
        "OpenAI", "Anthropic", "Google", "DeepMind", "Meta", "Microsoft",
        "Amazon", "NVIDIA", "Stability AI", "Midjourney", "Cohere",
        "Mistral", "Inflection", "Character.AI", "Hugging Face",
        "DeepSeek", "Alibaba", "Baidu", "Tencent", "xAI",
    ]

    # Known AI models
    KNOWN_MODELS = [
        "GPT-4", "GPT-4o", "GPT-3.5", "ChatGPT", "DALL-E", "Sora",
        "Claude", "Claude 3", "Claude 4", "Gemini", "PaLM", "Bard",
        "Llama", "Llama 2", "Llama 3", "Mistral", "Mixtral",
        "Stable Diffusion", "Midjourney", "DALL-E 3",
        "DeepSeek", "Qwen", "Gemma", "Phi",
    ]

    # Known benchmarks
    KNOWN_BENCHMARKS = [
        "MMLU", "GSM8K", "HumanEval", "MBPP", "HellaSwag",
        "ARC", "WinoGrande", "TruthfulQA", "BBH",
        "MATH", "GPQA", "MuSR", "IFEval",
    ]

    def __init__(
        self,
        domain_trust_config: Optional[Path] = None,
        min_sources: int = 2,
        min_confidence: float = 0.5,
    ) -> None:
        """
        Initialize context builder.

        Args:
            domain_trust_config: Path to domain trust configuration
            min_sources: Minimum number of sources required
            min_confidence: Minimum confidence threshold
        """
        self.min_sources = min_sources
        self.min_confidence = min_confidence

        # Load domain trust config
        self.domain_config = self._load_domain_config(domain_trust_config)

    def _load_domain_config(self, config_path: Optional[Path]) -> dict:
        """Load domain trust configuration."""
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load domain config: {e}")

        # Default config
        return {
            "tiers": {
                "tier1": {"score": 100, "domains": []},
                "tier2": {"score": 80, "domains": []},
                "tier3": {"score": 50, "domains": []},
            }
        }

    def _get_domain_tier(self, url: str) -> tuple[int, float]:
        """
        Get trust tier and score for a domain.

        Args:
            url: Source URL

        Returns:
            tuple[int, float]: (tier, score)
        """
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
        except (ValueError, AttributeError) as e:
            logger.debug("Failed to parse URL for domain: %s", e)
            return 3, 50.0

        for tier_name, tier_data in self.domain_config.get("tiers", {}).items():
            tier_num = int(tier_name.replace("tier", ""))
            tier_domains = tier_data.get("domains", [])

            for allowed_domain in tier_domains:
                if domain == allowed_domain.lower() or domain.endswith("." + allowed_domain.lower()):
                    return tier_num, float(tier_data.get("score", 50))

        # Default to tier 3
        return 3, 50.0

    def _extract_entities(self, text: str) -> list[Entity]:
        """
        Extract named entities from text.

        Args:
            text: Text to analyze

        Returns:
            list[Entity]: Extracted entities
        """
        entities = []

        # Extract companies
        for company in self.KNOWN_COMPANIES:
            count = len(re.findall(re.escape(company), text, re.IGNORECASE))
            if count > 0:
                entities.append(Entity(
                    name=company,
                    entity_type="company",
                    mentions=count,
                    confidence=0.95,
                ))

        # Extract models
        for model in self.KNOWN_MODELS:
            count = len(re.findall(re.escape(model), text, re.IGNORECASE))
            if count > 0:
                entities.append(Entity(
                    name=model,
                    entity_type="model",
                    mentions=count,
                    confidence=0.9,
                ))

        # Extract benchmarks
        for benchmark in self.KNOWN_BENCHMARKS:
            count = len(re.findall(re.escape(benchmark), text, re.IGNORECASE))
            if count > 0:
                entities.append(Entity(
                    name=benchmark,
                    entity_type="benchmark",
                    mentions=count,
                    confidence=0.85,
                ))

        # Extract numbers (metrics, benchmarks)
        number_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:billion|млрд|миллиард)',
            r'(\d+(?:\.\d+)?)\s*(?:million|млн|миллион)',
            r'(\d+(?:\.\d+)?)\s*%',
            r'\$(\d+(?:\.\d+)?)[MBK]?',
            r'(\d+(?:,\d+)?)\s*(?:параметров|parameters|токенов|tokens)',
        ]

        for pattern in number_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append(Entity(
                    name=str(match),
                    entity_type="metric",
                    mentions=1,
                    confidence=0.8,
                ))

        return entities

    def _extract_key_facts(
        self,
        articles: list[Article],
        max_facts: int = 8,
    ) -> list[KeyFact]:
        """
        Extract key facts from articles.

        Args:
            articles: Source articles
            max_facts: Maximum facts to extract

        Returns:
            list[KeyFact]: Extracted key facts
        """
        facts = []

        for article in articles[:5]:  # Limit source articles
            text = f"{article.title} {article.summary}"

            # Split into sentences
            sentences = re.split(r'[.!?]\s+', text)

            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20 or len(sentence) > 200:
                    continue

                # Score sentence as potential fact
                score = self._score_fact_candidate(sentence)

                if score >= 0.6:
                    tier, trust = self._get_domain_tier(article.url)
                    confidence = min(score, trust / 100)

                    facts.append(KeyFact(
                        content=sentence,
                        source_url=article.url,
                        source_name=article.source,
                        confidence=confidence,
                        needs_verification=confidence < 0.8,
                    ))

        # Sort by confidence and limit
        facts.sort(key=lambda f: f.confidence, reverse=True)
        return facts[:max_facts]

    def _score_fact_candidate(self, sentence: str) -> float:
        """
        Score a sentence as a potential fact.

        Args:
            sentence: Sentence to score

        Returns:
            float: Fact score (0-1)
        """
        score = 0.5  # Base score

        # Boost for specific indicators
        if re.search(r'\d+', sentence):
            score += 0.15  # Contains numbers

        if re.search(r'(?:announced|released|launched|представил|выпустил|запустил)', sentence, re.IGNORECASE):
            score += 0.1  # Action verb

        if re.search(r'(?:today|yesterday|сегодня|вчера|на этой неделе)', sentence, re.IGNORECASE):
            score += 0.05  # Temporal marker

        # Penalize vague language
        if re.search(r'(?:might|could|possibly|возможно|может быть)', sentence, re.IGNORECASE):
            score -= 0.15

        # Penalize opinions
        if re.search(r'(?:I think|we believe|по моему мнению)', sentence, re.IGNORECASE):
            score -= 0.2

        return max(0, min(1, score))

    def build_context(
        self,
        topic: str,
        articles: list[Article],
        min_sources_required: Optional[int] = None,
    ) -> StructuredContext:
        """
        Build structured context from articles.

        Args:
            topic: Selected topic
            articles: Source articles
            min_sources_required: Override minimum sources

        Returns:
            StructuredContext: Structured context for LLM
        """
        min_sources = min_sources_required or self.min_sources

        # Verify and score sources
        verified_sources = []
        for article in articles:
            tier, trust_score = self._get_domain_tier(article.url)
            verified_sources.append(VerifiedSource(
                article=article,
                tier=tier,
                trust_score=trust_score / 100,
                snapshot=article.summary[:500] if article.summary else None,
            ))

        # Sort by trust score
        verified_sources.sort(key=lambda s: s.trust_score, reverse=True)

        # Check minimum sources
        min_sources_met = len(verified_sources) >= min_sources

        # Extract key facts
        key_facts = self._extract_key_facts(articles)

        # Extract entities
        all_text = " ".join(f"{a.title} {a.summary}" for a in articles)
        entities = self._extract_entities(all_text)

        # Merge duplicate entities
        merged_entities = {}
        for entity in entities:
            key = (entity.name.lower(), entity.entity_type)
            if key in merged_entities:
                merged_entities[key].mentions += entity.mentions
            else:
                merged_entities[key] = entity

        entities = list(merged_entities.values())
        entities.sort(key=lambda e: e.mentions, reverse=True)

        # Build source context string
        source_context = self._build_source_context(verified_sources, key_facts)

        # Calculate average confidence
        if key_facts:
            avg_confidence = sum(f.confidence for f in key_facts) / len(key_facts)
        else:
            avg_confidence = 0.5

        context = StructuredContext(
            topic=topic,
            sources=verified_sources,
            key_facts=key_facts,
            entities=entities[:10],  # Limit entities
            source_context=source_context,
            avg_confidence=avg_confidence,
            min_sources_met=min_sources_met,
        )

        logger.info(
            f"Built context: {len(verified_sources)} sources, "
            f"{len(key_facts)} facts, {len(entities)} entities, "
            f"avg_confidence={avg_confidence:.0%}"
        )

        return context

    def _build_source_context(
        self,
        sources: list[VerifiedSource],
        facts: list[KeyFact],
    ) -> str:
        """
        Build source context string for LLM.

        Args:
            sources: Verified sources
            facts: Extracted key facts

        Returns:
            str: Formatted context string
        """
        parts = []

        # Add sources
        parts.append("SOURCE ARTICLES:")
        for i, source in enumerate(sources[:5], 1):
            confidence_note = "" if source.trust_score >= 0.8 else " [lower confidence source]"
            parts.append(f"\n{i}. {source.article.title}")
            parts.append(f"   Source: {source.article.source} (Tier {source.tier}){confidence_note}")
            parts.append(f"   URL: {source.article.url}")
            if source.article.summary:
                parts.append(f"   Summary: {source.article.summary[:300]}...")
        parts.append("")

        # Add verified facts
        parts.append("VERIFIED FACTS:")
        for fact in facts[:6]:
            verification = " [requires verification]" if fact.needs_verification else ""
            parts.append(f"- {fact.content}{verification}")
        parts.append("")

        return "\n".join(parts)

    def get_sources_for_post(self, sources: list[VerifiedSource]) -> list[dict]:
        """
        Get sources formatted for post JSON.

        Args:
            sources: Verified sources

        Returns:
            list[dict]: Sources in post format
        """
        return [
            {
                "name": s.article.source,
                "url": s.article.url,
                "confidence": round(s.trust_score, 2),
            }
            for s in sources[:3]
        ]
