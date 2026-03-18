"""
Variant Router for A/B Testing Framework.

Provides deterministic variant assignment using consistent hashing,
ensuring the same post_id always routes to the same variant.
"""

from __future__ import annotations

import hashlib
from typing import Dict

from core.logger import get_logger
from pipeline.ab_testing.experiment_manager import Experiment, Variant

logger = get_logger(__name__)


class VariantRouter:
    """
    Routes posts to experiment variants using consistent hashing.

    Ensures deterministic assignment: the same post_id will always
    be assigned to the same variant within an experiment.

    Example:
        >>> router = VariantRouter()
        >>> experiment = manager.create_experiment(...)
        >>> variant = router.assign_variant(experiment, "post_123")
        >>> print(variant.id)  # Always same for "post_123"
    """

    def __init__(self) -> None:
        """Initialize variant router."""
        pass

    def assign_variant(self, experiment: Experiment, post_id: str) -> Variant:
        """
        Deterministically assign a post to a variant.

        Uses consistent hashing to ensure the same post_id always
        maps to the same variant, based on the experiment's traffic split.

        Args:
            experiment: The experiment to assign within
            post_id: Unique identifier for the post

        Returns:
            The assigned Variant object

        Raises:
            ValueError: If experiment has no variants
        """
        if not experiment.variants:
            raise ValueError(f"Experiment {experiment.id} has no variants")

        variant_id = self._hash_to_variant(post_id, experiment.traffic_split)
        variant = experiment.get_variant(variant_id)

        if variant is None:
            # Fallback to first variant (should never happen with valid config)
            logger.warning(
                f"Variant {variant_id} not found in experiment {experiment.id}, "
                f"falling back to first variant"
            )
            variant = experiment.variants[0]

        logger.debug(
            f"Assigned post {post_id} to variant {variant.id} "
            f"in experiment {experiment.id}"
        )
        return variant

    def _hash_to_variant(
        self, post_id: str, traffic_split: Dict[str, float]
    ) -> str:
        """
        Consistent hashing for variant assignment.

        Uses MD5 hashing to generate a deterministic value from post_id,
        then maps it to a variant based on traffic split percentages.

        Args:
            post_id: Unique identifier for the post
            traffic_split: Dict mapping variant_id to traffic percentage

        Returns:
            The selected variant_id
        """
        # Create hash of post_id
        hash_value = hashlib.md5(post_id.encode()).hexdigest()

        # Convert first 8 hex characters to integer (0 to 4294967295)
        hash_int = int(hash_value[:8], 16)

        # Normalize to 0.0 - 1.0 range
        normalized = hash_int / 0xFFFFFFFF

        # Find variant based on cumulative traffic split
        cumulative = 0.0
        for variant_id, split in sorted(traffic_split.items()):
            cumulative += split
            if normalized <= cumulative:
                return variant_id

        # Fallback to last variant (handles floating point edge cases)
        return list(traffic_split.keys())[-1]

    def get_variant_distribution(
        self, experiment: Experiment, post_ids: list[str]
    ) -> Dict[str, int]:
        """
        Calculate the distribution of variant assignments for given post IDs.

        Useful for verifying traffic split implementation.

        Args:
            experiment: The experiment to check
            post_ids: List of post IDs to analyze

        Returns:
            Dict mapping variant_id to count of assignments
        """
        distribution: Dict[str, int] = {v.id: 0 for v in experiment.variants}

        for post_id in post_ids:
            variant = self.assign_variant(experiment, post_id)
            distribution[variant.id] += 1

        return distribution

    def preview_assignment(
        self, experiment: Experiment, post_id: str
    ) -> Dict[str, any]:
        """
        Preview variant assignment details for debugging.

        Args:
            experiment: The experiment to check
            post_id: Post ID to preview

        Returns:
            Dict with assignment details
        """
        hash_value = hashlib.md5(post_id.encode()).hexdigest()
        hash_int = int(hash_value[:8], 16)
        normalized = hash_int / 0xFFFFFFFF

        variant = self.assign_variant(experiment, post_id)

        return {
            "post_id": post_id,
            "hash_value": hash_value[:16],
            "normalized_value": round(normalized, 4),
            "assigned_variant": variant.id,
            "variant_name": variant.name,
            "traffic_split": experiment.traffic_split,
        }
