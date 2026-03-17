"""
Audience Persona Engine - Tailors content to target reader personas.

Maintains a set of target reader personas and adjusts vocabulary complexity,
analogy depth, and assumed knowledge level based on persona selection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter

logger = get_logger(__name__)


@dataclass(slots=True)
class Persona:
    """Represents a target reader persona."""

    id: str
    name: str
    description: str
    vocabulary_level: str  # "beginner", "intermediate", "advanced", "expert"
    analogy_style: str  # "simple", "technical", "real_world"
    assumed_knowledge: list[str] = field(default_factory=list)
    preferred_topics: list[str] = field(default_factory=list)
    engagement_history: dict[str, float] = field(
        default_factory=dict
    )  # topic_cluster -> avg_engagement
    weight: float = 1.0  # Importance weight for this persona

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "vocabulary_level": self.vocabulary_level,
            "analogy_style": self.analogy_style,
            "assumed_knowledge": self.assumed_knowledge,
            "preferred_topics": self.preferred_topics,
            "engagement_history": self.engagement_history,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Persona":
        """Create Persona from dictionary."""
        return cls(
            id=data.get("id", "default"),
            name=data.get("name", "Default"),
            description=data.get("description", ""),
            vocabulary_level=data.get("vocabulary_level", "intermediate"),
            analogy_style=data.get("analogy_style", "real_world"),
            assumed_knowledge=data.get("assumed_knowledge", []),
            preferred_topics=data.get("preferred_topics", []),
            engagement_history=data.get("engagement_history", {}),
            weight=data.get("weight", 1.0),
        )


# Default personas
DEFAULT_PERSONAS = [
    Persona(
        id="senior_ml_engineer",
        name="Senior ML Engineer",
        description="Experienced ML practitioner interested in SOTA techniques",
        vocabulary_level="expert",
        analogy_style="technical",
        assumed_knowledge=[
            "transformers",
            "backpropagation",
            "gradient_descent",
            "regularization",
        ],
        preferred_topics=[
            "research papers",
            "model architecture",
            "training techniques",
        ],
        weight=1.0,
    ),
    Persona(
        id="startup_founder",
        name="Startup Founder",
        description="Non-technical founder looking for AI opportunities",
        vocabulary_level="intermediate",
        analogy_style="real_world",
        assumed_knowledge=["basic AI concepts", "business metrics"],
        preferred_topics=["product launches", "market trends", "funding"],
        weight=0.8,
    ),
    Persona(
        id="cs_student",
        name="CS Student",
        description="Computer science student learning AI fundamentals",
        vocabulary_level="beginner",
        analogy_style="simple",
        assumed_knowledge=["programming basics", "math fundamentals"],
        preferred_topics=["tutorials", "career advice", "learning resources"],
        weight=0.6,
    ),
    Persona(
        id="tech_leader",
        name="Tech Leader",
        description="CTO/VP Engineering evaluating AI for organization",
        vocabulary_level="advanced",
        analogy_style="real_world",
        assumed_knowledge=[
            "software architecture",
            "team management",
            "cloud infrastructure",
        ],
        preferred_topics=["enterprise AI", "ROI analysis", "implementation guides"],
        weight=0.9,
    ),
]


@dataclass(slots=True)
class PersonaMatch:
    """Result of persona matching for content."""

    persona_id: str
    relevance_score: float  # 0.0 to 1.0
    matched_topics: list[str] = field(default_factory=list)
    historical_engagement: float = 0.0


class PersonaEngine:
    """
    Manages audience personas and content personalization.

    Features:
    - Persona selection based on topic relevance
    - Feedback loop for engagement-based weight adjustment
    - Content adaptation instructions for LLM
    """

    PERSONA_CONFIG_PATH = Path("config/personas.json")

    def __init__(
        self,
        llm_adapter: Optional["BaseLLMAdapter"] = None,
        personas: Optional[list[Persona]] = None,
        engagement_threshold: float = 0.5,
        learning_rate: float = 0.1,
    ) -> None:
        """
        Initialize persona engine.

        Args:
            llm_adapter: Optional LLM for persona selection
            personas: List of personas (defaults to DEFAULT_PERSONAS)
            engagement_threshold: Threshold for downweighting
            learning_rate: Rate of weight adjustment
        """
        self.llm = llm_adapter
        self.personas: dict[str, Persona] = {}
        self.engagement_threshold = engagement_threshold
        self.learning_rate = learning_rate

        # Load or use provided personas
        if personas:
            for p in personas:
                self.personas[p.id] = p
        else:
            self._load_personas()

        logger.info("Persona engine initialized with %d personas", len(self.personas))

    def _load_personas(self) -> None:
        """Load personas from config file or use defaults."""
        if self.PERSONA_CONFIG_PATH.exists():
            try:
                with open(self.PERSONA_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for p_data in data.get("personas", []):
                    persona = Persona.from_dict(p_data)
                    self.personas[persona.id] = persona
                logger.info("Loaded %d personas from config", len(self.personas))
                return
            except Exception as e:
                logger.warning("Failed to load personas from config: %s", e)

        # Use defaults
        for persona in DEFAULT_PERSONAS:
            self.personas[persona.id] = persona
        logger.info("Using default personas")

    def save_personas(self) -> None:
        """Save current personas to config file."""
        self.PERSONA_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "personas": [p.to_dict() for p in self.personas.values()],
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.PERSONA_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d personas to config", len(self.personas))

    def get_persona(self, persona_id: str) -> Optional[Persona]:
        """Get persona by ID."""
        return self.personas.get(persona_id)

    def list_personas(self) -> list[Persona]:
        """List all personas."""
        return list(self.personas.values())

    async def select_persona(self, topic: str, content: str = "") -> PersonaMatch:
        """
        Select the most relevant persona for content.

        Args:
            topic: Post topic
            content: Optional post content for better matching

        Returns:
            PersonaMatch: Best matching persona with relevance score
        """
        if not self.llm:
            return self._select_persona_rule_based(topic, content)

        try:
            return await self._select_persona_llm(topic, content)
        except Exception as e:
            logger.warning("LLM persona selection failed: %s, using rules", e)
            return self._select_persona_rule_based(topic, content)

    def _select_persona_rule_based(self, topic: str, content: str) -> PersonaMatch:
        """Rule-based persona selection."""
        topic_lower = topic.lower()
        content_lower = content.lower() if content else ""
        combined = f"{topic_lower} {content_lower}"

        best_match = None
        best_score = 0.0

        for persona in self.personas.values():
            score = 0.0
            matched_topics = []

            # Check preferred topics
            for pref_topic in persona.preferred_topics:
                if pref_topic.lower() in combined:
                    score += 0.3
                    matched_topics.append(pref_topic)

            # Check assumed knowledge relevance
            for knowledge in persona.assumed_knowledge:
                if knowledge.lower() in combined:
                    score += 0.1

            # Apply persona weight
            score *= persona.weight

            # Get historical engagement
            historical = self._get_historical_engagement(persona.id, topic)

            if score > best_score:
                best_score = score
                best_match = PersonaMatch(
                    persona_id=persona.id,
                    relevance_score=min(1.0, score),
                    matched_topics=matched_topics,
                    historical_engagement=historical,
                )

        if not best_match:
            # Default to first persona
            first_persona = next(iter(self.personas.values()))
            best_match = PersonaMatch(
                persona_id=first_persona.id,
                relevance_score=0.5,
                matched_topics=[],
                historical_engagement=0.0,
            )

        return best_match

    async def _select_persona_llm(self, topic: str, content: str) -> PersonaMatch:
        """LLM-based persona selection."""
        persona_descriptions = "\n".join(
            [
                f"- {p.id}: {p.description} (level: {p.vocabulary_level})"
                for p in self.personas.values()
            ]
        )

        prompt = f"""Select the best target audience persona for this content.

TOPIC: {topic}
CONTENT PREVIEW: {content[:500] if content else "N/A"}

AVAILABLE PERSONAS:
{persona_descriptions}

Return JSON:
{{
    "persona_id": "<selected_persona_id>",
    "relevance_score": <0.0-1.0>,
    "reason": "<brief explanation>"
}}"""

        response = await self.llm.generate(prompt)
        result = json.loads(response.content.strip())

        persona_id = result.get("persona_id", "")
        if persona_id not in self.personas:
            persona_id = next(iter(self.personas.keys()))

        historical = self._get_historical_engagement(persona_id, topic)

        return PersonaMatch(
            persona_id=persona_id,
            relevance_score=result.get("relevance_score", 0.5),
            matched_topics=[],
            historical_engagement=historical,
        )

    def _get_historical_engagement(self, persona_id: str, topic: str) -> float:
        """Get historical engagement for persona-topic combination."""
        persona = self.personas.get(persona_id)
        if not persona:
            return 0.0

        # Simple keyword matching for topic cluster
        topic_words = set(topic.lower().split())
        total_engagement = 0.0
        match_count = 0

        for cluster, engagement in persona.engagement_history.items():
            cluster_words = set(cluster.lower().split())
            if topic_words & cluster_words:  # Intersection
                total_engagement += engagement
                match_count += 1

        return total_engagement / match_count if match_count > 0 else 0.0

    def record_engagement(
        self,
        persona_id: str,
        topic: str,
        engagement_score: float,
    ) -> None:
        """
        Record engagement feedback for a persona-topic combination.

        Adjusts persona weight based on performance.

        Args:
            persona_id: Persona ID
            topic: Post topic
            engagement_score: Engagement score (0.0 to 1.0)
        """
        persona = self.personas.get(persona_id)
        if not persona:
            return

        # Extract topic cluster (simple: first 3 significant words)
        words = [w for w in topic.lower().split() if len(w) > 3][:3]
        cluster = " ".join(words) if words else topic[:30]

        # Update engagement history
        current = persona.engagement_history.get(cluster, engagement_score)
        persona.engagement_history[cluster] = (current + engagement_score) / 2

        # Adjust weight if engagement is below threshold
        if engagement_score < self.engagement_threshold:
            persona.weight = max(0.1, persona.weight - self.learning_rate)
            logger.info(
                "Downweighted persona %s to %.2f (low engagement: %.2f)",
                persona_id,
                persona.weight,
                engagement_score,
            )
        else:
            # Gradually restore weight on good performance
            persona.weight = min(1.0, persona.weight + self.learning_rate * 0.5)

    def get_style_instructions(self, persona_id: str) -> str:
        """
        Get style instructions for LLM based on persona.

        Args:
            persona_id: Target persona ID

        Returns:
            str: Style instructions to include in prompt
        """
        persona = self.personas.get(persona_id)
        if not persona:
            return ""

        level_instructions = {
            "beginner": (
                "Explain all technical terms. Use simple analogies. "
                "Avoid jargon. Define acronyms on first use."
            ),
            "intermediate": (
                "Balance technical depth with accessibility. "
                "Explain advanced concepts briefly. Use relatable examples."
            ),
            "advanced": (
                "Use technical terminology freely. Focus on implementation details. "
                "Assume familiarity with core concepts."
            ),
            "expert": (
                "Dive deep into technical nuances. Reference specific papers/techniques. "
                "Assume strong foundational knowledge."
            ),
        }

        analogy_instructions = {
            "simple": "Use everyday analogies that anyone can understand.",
            "technical": "Use technical comparisons within the field.",
            "real_world": "Use real-world business or industry examples.",
        }

        knowledge_note = ""
        if persona.assumed_knowledge:
            knowledge_note = (
                f"Assume familiarity with: {', '.join(persona.assumed_knowledge[:5])}."
            )

        return f"""
TARGET AUDIENCE: {persona.name}
{persona.description}

WRITING GUIDELINES:
{level_instructions.get(persona.vocabulary_level, "")}
{analogy_instructions.get(persona.analogy_style, "")}
{knowledge_note}
""".strip()


# Configuration schema
PERSONA_CONFIG_SCHEMA = {
    "personas": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable persona-based content tailoring",
        },
        "engagement_threshold": {
            "type": "float",
            "default": 0.5,
            "description": "Engagement threshold for downweighting personas",
        },
        "learning_rate": {
            "type": "float",
            "default": 0.1,
            "description": "Rate of persona weight adjustment",
        },
    }
}
