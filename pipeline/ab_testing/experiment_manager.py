"""
Experiment Manager for A/B Testing Framework.

Defines and manages experiments for testing prompt variations,
temperature settings, post structures, and tone variations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Variant:
    """
    Individual variant in an experiment.

    Represents a single configuration to test, such as
    a prompt variation, temperature setting, or post structure.

    Attributes:
        id: Unique identifier for the variant
        name: Human-readable name
        config: Configuration dict (prompt, temperature, structure, etc.)
        is_control: Whether this is the control/baseline variant
    """

    id: str
    name: str
    config: Dict[str, Any]
    is_control: bool = False

    def __post_init__(self) -> None:
        """Validate variant configuration."""
        if not self.id:
            raise ValueError("Variant id cannot be empty")
        if not self.name:
            raise ValueError("Variant name cannot be empty")


@dataclass
class Experiment:
    """
    A/B test experiment configuration.

    Represents a complete experiment with multiple variants
    and traffic distribution settings.

    Attributes:
        id: Unique experiment identifier
        name: Human-readable experiment name
        variants: List of Variant objects
        status: Current status ("active", "paused", "completed")
        created_at: When the experiment was created
        traffic_split: Distribution of traffic (variant_id -> percentage)
        description: Optional experiment description
        winner: ID of winning variant (if determined)
        confidence: Confidence level of the result
        started_at: When the experiment started
        ended_at: When the experiment ended
    """

    id: str
    name: str
    variants: List[Variant]
    status: str
    created_at: datetime
    traffic_split: Dict[str, float]
    description: Optional[str] = None
    winner: Optional[str] = None
    confidence: float = 0.0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate experiment configuration."""
        if not self.variants:
            raise ValueError("Experiment must have at least one variant")

        # Validate traffic split sums to approximately 1.0
        total_split = sum(self.traffic_split.values())
        if not 0.99 <= total_split <= 1.01:
            raise ValueError(f"Traffic split must sum to 1.0, got {total_split}")

        # Validate all variants are in traffic split
        variant_ids = {v.id for v in self.variants}
        split_ids = set(self.traffic_split.keys())
        if variant_ids != split_ids:
            raise ValueError(
                f"Traffic split keys {split_ids} must match variant IDs {variant_ids}"
            )

        # Set started_at if not set and status is active
        if self.status == "active" and self.started_at is None:
            self.started_at = self.created_at

    def get_control(self) -> Optional[Variant]:
        """Get the control variant."""
        for variant in self.variants:
            if variant.is_control:
                return variant
        return None

    def get_variant(self, variant_id: str) -> Optional[Variant]:
        """Get variant by ID."""
        for variant in self.variants:
            if variant.id == variant_id:
                return variant
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert experiment to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "variants": [
                {
                    "id": v.id,
                    "name": v.name,
                    "config": v.config,
                    "is_control": v.is_control,
                }
                for v in self.variants
            ],
            "status": self.status,
            "traffic_split": self.traffic_split,
            "winner": self.winner,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


class ExperimentManager:
    """
    Manages A/B experiments for prompt optimization.

    Provides functionality to create, pause, resume, and complete
    experiments for testing various content generation parameters.

    Testable elements:
    - Prompt variations
    - Temperature settings
    - Post structures
    - Tone variations

    Example:
        >>> manager = ExperimentManager()
        >>> experiment = manager.create_experiment(
        ...     name="Temperature Test",
        ...     variants=[
        ...         {"id": "control", "name": "Control", "config": {"temp": 0.7}, "is_control": True},
        ...         {"id": "treatment", "name": "Treatment", "config": {"temp": 0.9}, "is_control": False},
        ...     ],
        ... )
    """

    def __init__(self) -> None:
        """Initialize experiment manager with in-memory storage."""
        self._experiments: Dict[str, Experiment] = {}
        logger.info("ExperimentManager initialized")

    def create_experiment(
        self,
        name: str,
        variants: List[Dict[str, Any]],
        traffic_split: Optional[Dict[str, float]] = None,
        description: Optional[str] = None,
    ) -> Experiment:
        """
        Create a new experiment.

        Args:
            name: Experiment name
            variants: List of variant configurations
            traffic_split: Optional traffic distribution (defaults to equal split)
            description: Optional experiment description

        Returns:
            Created Experiment object

        Raises:
            ValueError: If variant configuration is invalid
        """
        # Generate unique ID
        experiment_id = f"exp_{uuid.uuid4().hex[:8]}"

        # Create Variant objects
        variant_objects = []
        for v in variants:
            variant = Variant(
                id=v["id"],
                name=v["name"],
                config=v.get("config", {}),
                is_control=v.get("is_control", False),
            )
            variant_objects.append(variant)

        # Default to equal traffic split if not provided
        if traffic_split is None:
            split_per_variant = 1.0 / len(variant_objects)
            traffic_split = {v.id: split_per_variant for v in variant_objects}

        # Create experiment
        now = datetime.utcnow()
        experiment = Experiment(
            id=experiment_id,
            name=name,
            variants=variant_objects,
            status="active",
            created_at=now,
            traffic_split=traffic_split,
            description=description,
            started_at=now,
        )

        # Store experiment
        self._experiments[experiment_id] = experiment

        logger.info(
            f"Created experiment '{name}' (ID: {experiment_id}) "
            f"with {len(variant_objects)} variants"
        )

        return experiment

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """
        Get experiment by ID.

        Args:
            experiment_id: Experiment ID

        Returns:
            Experiment object or None if not found
        """
        return self._experiments.get(experiment_id)

    def get_active_experiments(self) -> List[Experiment]:
        """
        Get all active experiments.

        Returns:
            List of active Experiment objects
        """
        return [exp for exp in self._experiments.values() if exp.status == "active"]

    def get_all_experiments(self) -> List[Experiment]:
        """
        Get all experiments.

        Returns:
            List of all Experiment objects
        """
        return list(self._experiments.values())

    def pause_experiment(self, experiment_id: str) -> bool:
        """
        Pause an active experiment.

        Args:
            experiment_id: Experiment ID to pause

        Returns:
            True if paused, False if not found or not active
        """
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            logger.warning(f"Experiment {experiment_id} not found")
            return False

        if experiment.status != "active":
            logger.warning(
                f"Cannot pause experiment {experiment_id}: status is {experiment.status}"
            )
            return False

        experiment.status = "paused"
        logger.info(f"Paused experiment {experiment_id}")
        return True

    def resume_experiment(self, experiment_id: str) -> bool:
        """
        Resume a paused experiment.

        Args:
            experiment_id: Experiment ID to resume

        Returns:
            True if resumed, False if not found or not paused
        """
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            logger.warning(f"Experiment {experiment_id} not found")
            return False

        if experiment.status != "paused":
            logger.warning(
                f"Cannot resume experiment {experiment_id}: status is {experiment.status}"
            )
            return False

        experiment.status = "active"
        logger.info(f"Resumed experiment {experiment_id}")
        return True

    def complete_experiment(
        self,
        experiment_id: str,
        winner: Optional[str] = None,
        confidence: float = 0.0,
    ) -> bool:
        """
        Complete an experiment with results.

        Args:
            experiment_id: Experiment ID to complete
            winner: ID of winning variant (optional)
            confidence: Confidence level of result (0.0-1.0)

        Returns:
            True if completed, False if not found
        """
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            logger.warning(f"Experiment {experiment_id} not found")
            return False

        experiment.status = "completed"
        experiment.winner = winner
        experiment.confidence = confidence
        experiment.ended_at = datetime.utcnow()

        logger.info(
            f"Completed experiment {experiment_id}: winner={winner}, confidence={confidence:.2%}"
        )
        return True

    def delete_experiment(self, experiment_id: str) -> bool:
        """
        Delete an experiment.

        Args:
            experiment_id: Experiment ID to delete

        Returns:
            True if deleted, False if not found
        """
        if experiment_id not in self._experiments:
            logger.warning(f"Experiment {experiment_id} not found")
            return False

        del self._experiments[experiment_id]
        logger.info(f"Deleted experiment {experiment_id}")
        return True

    def get_experiment_by_name(self, name: str) -> Optional[Experiment]:
        """
        Get experiment by name.

        Args:
            name: Experiment name

        Returns:
            Experiment object or None if not found
        """
        for experiment in self._experiments.values():
            if experiment.name == name:
                return experiment
        return None
