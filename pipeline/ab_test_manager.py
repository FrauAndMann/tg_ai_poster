"""
A/B Testing Module.

Manages experiments for testing different post formats and content variants.
Integrates with the pipeline.ab_testing framework for advanced experimentation.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime
from utils.datetime_utils import utcnow
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from core.logger import get_logger
from memory.models import Post, ABExperiment, ABVariant
from memory.database import get_database

# Import new A/B testing framework components
from pipeline.ab_testing.experiment_manager import (
    Experiment,
    ExperimentManager,
    Variant,
)
from pipeline.ab_testing.variant_router import VariantRouter
from pipeline.ab_testing.result_analyzer import (
    ExperimentResult,
    ResultAnalyzer,
    VariantResult,
)

logger = get_logger(__name__)


class ABTestManager:
    """
    Manages A/B experiments for post variants.

    Integrates database-backed experiments with the in-memory
    ExperimentManager for prompt and configuration testing.

    Features:
    - Database-persisted experiments for posts
    - In-memory experiments for prompt/config testing
    - Consistent variant routing using hashing
    - Statistical analysis with t-test significance
    """

    def __init__(
        self,
        min_sample_size: int = 100,
        confidence_threshold: float = 0.95,
    ):
        """
        Initialize A/B test manager.

        Args:
            min_sample_size: Minimum impressions before analysis
            confidence_threshold: Statistical significance threshold
        """
        self.min_sample_size = min_sample_size
        self.confidence_threshold = confidence_threshold

        # Initialize new framework components
        self._experiment_manager = ExperimentManager()
        self._variant_router = VariantRouter()
        self._result_analyzer = ResultAnalyzer(
            min_sample_size=min_sample_size,
            confidence_threshold=confidence_threshold,
        )

    async def create_experiment(
        self,
        name: str,
        post_a: Post,
        post_b: Post,
        traffic_split: float = 0.5,
        description: str | None = None,
    ) -> ABExperiment:
        """
        Create new A/B experiment with two variants.

        Args:
            name: Experiment name
            post_a: Variant A post
            post_b: Variant B post
            traffic_split: Traffic split for variant A (0.0-1.0)
            description: Optional description

        Returns:
            ABExperiment: Created experiment
        """
        async with get_database().session() as session:
            experiment = ABExperiment(
                name=name,
                description=description,
                traffic_split=traffic_split,
                is_active=True,
            )
            session.add(experiment)
            await session.flush()

            # Create variant A
            variant_a = ABVariant(
                experiment_id=experiment.id,
                variant_id="A",
                post_id=post_a.id,
            )
            session.add(variant_a)

            # Create variant B
            variant_b = ABVariant(
                experiment_id=experiment.id,
                variant_id="B",
                post_id=post_b.id,
            )
            session.add(variant_b)

            # Update posts with experiment info
            # Get fresh posts from DB
            result_a = await session.execute(select(Post).where(Post.id == post_a.id))
            db_post_a = result_a.scalar_one()

            result_b = await session.execute(select(Post).where(Post.id == post_b.id))
            db_post_b = result_b.scalar_one()

            db_post_a.ab_experiment_id = experiment.id
            db_post_a.ab_variant_id = "A"
            session.add(db_post_a)

            db_post_b.ab_experiment_id = experiment.id
            db_post_b.ab_variant_id = "B"
            session.add(db_post_b)

            await session.commit()
            await session.refresh(experiment)

            logger.info(f"Created A/B experiment '{name}' (ID: {experiment.id})")
            return experiment

    async def select_variant(self, experiment: ABExperiment) -> ABVariant:
        """
        Select variant based on traffic split.

        Args:
            experiment: Active experiment

        Returns:
            ABVariant: Selected variant
        """
        async with get_database().session() as session:
            # Get variants
            result = await session.execute(
                select(ABVariant)
                .where(ABVariant.experiment_id == experiment.id)
                .order_by(ABVariant.variant_id)
            )
            variants = list(result.scalars().all())

            if len(variants) != 2:
                raise ValueError(f"Expected 2 variants, got {len(variants)}")

            # Select based on traffic split
            if random.random() < experiment.traffic_split:
                selected = variants[0]  # Variant A
            else:
                selected = variants[1]  # Variant B

            logger.debug(
                f"Selected variant {selected.variant_id} for experiment {experiment.id}"
            )
            return selected

    async def record_impression(self, variant: ABVariant) -> None:
        """
        Record that variant was shown.

        Args:
            variant: Variant shown
        """
        async with get_database().session() as session:
            result = await session.execute(
                select(ABVariant).where(ABVariant.id == variant.id)
            )
            db_variant = result.scalar_one()
            db_variant.impressions += 1
            session.add(db_variant)
            await session.commit()

            # Update local object
            variant.impressions = db_variant.impressions

            logger.debug(
                f"Recorded impression for variant {variant.variant_id} "
                f"(total: {db_variant.impressions})"
            )

    async def record_engagement(
        self, variant: ABVariant, engagement_score: float
    ) -> None:
        """
        Record engagement metric.

        Args:
            variant: Variant that received engagement
            engagement_score: Engagement score
        """
        async with get_database().session() as session:
            result = await session.execute(
                select(ABVariant).where(ABVariant.id == variant.id)
            )
            db_variant = result.scalar_one()
            db_variant.total_engagement += engagement_score
            session.add(db_variant)
            await session.commit()

            # Update local object
            variant.total_engagement = db_variant.total_engagement

            logger.debug(
                f"Recorded engagement {engagement_score:.2f} for variant {variant.variant_id}"
            )

    async def analyze_experiment(self, experiment_id: int) -> dict:
        """
        Analyze results and determine winner if significant.

        Args:
            experiment_id: Experiment to analyze

        Returns:
            dict: Analysis results
        """
        async with get_database().session() as session:
            # Get experiment
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            experiment = result.scalar_one_or_none()
            if not experiment:
                return {"error": "Experiment not found"}

            # Get variants
            result = await session.execute(
                select(ABVariant)
                .where(ABVariant.experiment_id == experiment_id)
                .order_by(ABVariant.variant_id)
            )
            variants = list(result.scalars().all())

            if len(variants) != 2:
                return {"error": "Expected 2 variants"}

            variant_a, variant_b = variants

            # Check sample size
            if (
                variant_a.impressions < self.min_sample_size
                or variant_b.impressions < self.min_sample_size
            ):
                return {
                    "status": "insufficient_data",
                    "variant_a_impressions": variant_a.impressions,
                    "variant_b_impressions": variant_b.impressions,
                    "min_required": self.min_sample_size,
                }

            # Calculate average engagement
            avg_a = (
                variant_a.total_engagement / variant_a.impressions
                if variant_a.impressions > 0
                else 0
            )
            avg_b = (
                variant_b.total_engagement / variant_b.impressions
                if variant_b.impressions > 0
                else 0
            )

            # Calculate improvement
            improvement = (avg_b - avg_a) / avg_a if avg_a > 0 else 0

            # Determine winner and confidence
            # Using simplified significance test based on effect size
            if abs(improvement) > 0.1:  # 10% improvement threshold
                winner = "B" if avg_b > avg_a else "A"
                # Confidence based on effect size (simplified)
                confidence = min(0.99, 0.85 + abs(improvement))
            else:
                winner = None
                confidence = 0.5

            result_data = {
                "experiment_id": experiment_id,
                "experiment_name": experiment.name,
                "variant_a": {
                    "impressions": variant_a.impressions,
                    "total_engagement": variant_a.total_engagement,
                    "avg_engagement": avg_a,
                },
                "variant_b": {
                    "impressions": variant_b.impressions,
                    "total_engagement": variant_b.total_engagement,
                    "avg_engagement": avg_b,
                },
                "improvement": f"{improvement:.1%}",
                "winner": winner,
                "confidence": confidence,
                "significant": confidence >= self.confidence_threshold,
            }

            # Update experiment if winner determined
            if winner and confidence >= self.confidence_threshold:
                # Refresh experiment in session
                result = await session.execute(
                    select(ABExperiment).where(ABExperiment.id == experiment_id)
                )
                db_experiment = result.scalar_one()
                db_experiment.winner_variant = winner
                db_experiment.confidence_level = confidence
                db_experiment.is_active = False
                db_experiment.ended_at = utcnow()
                session.add(db_experiment)
                await session.commit()

                logger.info(
                    f"Experiment {experiment_id} concluded: winner={winner}, "
                    f"confidence={confidence:.1%}"
                )

            return result_data

    async def get_active_experiments(self) -> list[ABExperiment]:
        """Get all active experiments."""
        async with get_database().session() as session:
            result = await session.execute(
                select(ABExperiment)
                .where(ABExperiment.is_active.is_(True))
                .order_by(ABExperiment.started_at.desc())
            )
            return list(result.scalars().all())

    async def get_experiment(self, experiment_id: int) -> ABExperiment | None:
        """Get experiment by ID."""
        async with get_database().session() as session:
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            return result.scalar_one_or_none()

    async def get_experiment_variants(self, experiment_id: int) -> list[ABVariant]:
        """Get all variants for an experiment."""
        async with get_database().session() as session:
            result = await session.execute(
                select(ABVariant)
                .where(ABVariant.experiment_id == experiment_id)
                .order_by(ABVariant.variant_id)
            )
            return list(result.scalars().all())

    async def end_experiment(self, experiment_id: int) -> bool:
        """End an active experiment."""
        async with get_database().session() as session:
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            experiment = result.scalar_one_or_none()
            if not experiment:
                return False

            experiment.is_active = False
            experiment.ended_at = utcnow()
            session.add(experiment)
            await session.commit()

            logger.info(f"Ended experiment {experiment_id}")
            return True

    async def get_variant_for_post(self, post_id: int) -> ABVariant | None:
        """Get the variant associated with a post."""
        async with get_database().session() as session:
            result = await session.execute(
                select(ABVariant).where(ABVariant.post_id == post_id)
            )
            return result.scalar_one_or_none()

    # ==========================================================================
    # New A/B Testing Framework Integration Methods
    # ==========================================================================

    def create_prompt_experiment(
        self,
        name: str,
        variants: List[Dict[str, Any]],
        traffic_split: Optional[Dict[str, float]] = None,
        description: Optional[str] = None,
    ) -> Experiment:
        """
        Create an in-memory experiment for testing prompts/configs.

        Use this for testing:
        - Prompt variations
        - Temperature settings
        - Post structures
        - Tone variations

        Args:
            name: Experiment name
            variants: List of variant configs with id, name, config, is_control
            traffic_split: Optional traffic distribution
            description: Optional description

        Returns:
            Experiment object

        Example:
            >>> experiment = manager.create_prompt_experiment(
            ...     name="Temperature Test",
            ...     variants=[
            ...         {"id": "control", "name": "Control", "config": {"temp": 0.7}, "is_control": True},
            ...         {"id": "treatment", "name": "Higher Temp", "config": {"temp": 0.9}, "is_control": False},
            ...     ],
            ... )
        """
        return self._experiment_manager.create_experiment(
            name=name,
            variants=variants,
            traffic_split=traffic_split,
            description=description,
        )

    def get_prompt_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get prompt experiment by ID."""
        return self._experiment_manager.get_experiment(experiment_id)

    def get_active_prompt_experiments(self) -> List[Experiment]:
        """Get all active prompt experiments."""
        return self._experiment_manager.get_active_experiments()

    def assign_to_variant(self, experiment: Experiment, post_id: str) -> Variant:
        """
        Deterministically assign a post to a variant.

        Uses consistent hashing to ensure the same post_id always
        gets the same variant within an experiment.

        Args:
            experiment: The experiment
            post_id: Unique post identifier

        Returns:
            Assigned Variant
        """
        return self._variant_router.assign_variant(experiment, post_id)

    def analyze_prompt_experiment(
        self,
        experiment_id: str,
        results: List[Dict[str, Any]],
        control_variant: str,
    ) -> ExperimentResult:
        """
        Analyze prompt experiment results with statistical testing.

        Args:
            experiment_id: Experiment ID
            results: List of result dicts with variant_id, engagement, quality_score, converted
            control_variant: ID of control variant

        Returns:
            ExperimentResult with analysis
        """
        return self._result_analyzer.analyze_experiment(
            experiment_id=experiment_id,
            results=results,
            control_variant=control_variant,
        )

    def pause_prompt_experiment(self, experiment_id: str) -> bool:
        """Pause a prompt experiment."""
        return self._experiment_manager.pause_experiment(experiment_id)

    def resume_prompt_experiment(self, experiment_id: str) -> bool:
        """Resume a paused prompt experiment."""
        return self._experiment_manager.resume_experiment(experiment_id)

    def complete_prompt_experiment(
        self,
        experiment_id: str,
        winner: Optional[str] = None,
        confidence: float = 0.0,
    ) -> bool:
        """Complete a prompt experiment with results."""
        return self._experiment_manager.complete_experiment(
            experiment_id, winner, confidence
        )

    async def analyze_experiment_with_stats(self, experiment_id: int) -> Dict[str, Any]:
        """
        Enhanced experiment analysis using statistical testing.

        Combines database metrics with statistical analysis from the framework.

        Args:
            experiment_id: Database experiment ID

        Returns:
            Enhanced analysis results with statistical significance
        """
        async with get_database().session() as session:
            # Get experiment
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            experiment = result.scalar_one_or_none()
            if not experiment:
                return {"error": "Experiment not found"}

            # Get variants
            result = await session.execute(
                select(ABVariant)
                .where(ABVariant.experiment_id == experiment_id)
                .order_by(ABVariant.variant_id)
            )
            variants = list(result.scalars().all())

            if len(variants) != 2:
                return {"error": "Expected 2 variants"}

            variant_a, variant_b = variants

            # Build results for statistical analysis
            results = []
            for _ in range(variant_a.impressions):
                # Use average engagement as approximation for individual scores
                avg_eng = (
                    variant_a.total_engagement / variant_a.impressions
                    if variant_a.impressions > 0
                    else 0
                )
                results.append({
                    "variant_id": "A",
                    "engagement": avg_eng,
                    "quality_score": 80.0,  # Default
                    "converted": False,
                })

            for _ in range(variant_b.impressions):
                avg_eng = (
                    variant_b.total_engagement / variant_b.impressions
                    if variant_b.impressions > 0
                    else 0
                )
                results.append({
                    "variant_id": "B",
                    "engagement": avg_eng,
                    "quality_score": 80.0,
                    "converted": False,
                })

            # Use framework analyzer for statistical testing
            analysis = self._result_analyzer.analyze_experiment(
                experiment_id=f"db_{experiment_id}",
                results=results,
                control_variant="A",
            )

            return {
                "experiment_id": experiment_id,
                "experiment_name": experiment.name,
                "variant_a": {
                    "impressions": variant_a.impressions,
                    "total_engagement": variant_a.total_engagement,
                    "avg_engagement": analysis.variant_results.get("A", VariantResult(
                        variant_id="A", sample_size=0, avg_engagement=0,
                        avg_quality_score=0, conversion_rate=0
                    )).avg_engagement,
                },
                "variant_b": {
                    "impressions": variant_b.impressions,
                    "total_engagement": variant_b.total_engagement,
                    "avg_engagement": analysis.variant_results.get("B", VariantResult(
                        variant_id="B", sample_size=0, avg_engagement=0,
                        avg_quality_score=0, conversion_rate=0
                    )).avg_engagement,
                },
                "winner": analysis.winner,
                "confidence": analysis.confidence,
                "p_value": analysis.p_value,
                "significant": analysis.confidence >= self.confidence_threshold,
                "recommendation": analysis.recommendation,
            }

    def select_variant_deterministic(
        self, experiment: ABExperiment, post_id: str
    ) -> ABVariant:
        """
        Select variant using consistent hashing (deterministic).

        Unlike select_variant(), this ensures the same post_id always
        gets the same variant.

        Args:
            experiment: Active experiment
            post_id: Unique post identifier

        Returns:
            ABVariant: Selected variant
        """
        import asyncio

        async def _get_variant() -> ABVariant:
            async with get_database().session() as session:
                result = await session.execute(
                    select(ABVariant)
                    .where(ABVariant.experiment_id == experiment.id)
                    .order_by(ABVariant.variant_id)
                )
                variants = list(result.scalars().all())

                if len(variants) != 2:
                    raise ValueError(f"Expected 2 variants, got {len(variants)}")

                # Use consistent hashing
                traffic_split = {
                    "A": experiment.traffic_split,
                    "B": 1.0 - experiment.traffic_split,
                }
                variant_id = self._variant_router._hash_to_variant(
                    post_id, traffic_split
                )

                selected = next(
                    (v for v in variants if v.variant_id == variant_id), variants[0]
                )

                logger.debug(
                    f"Deterministically selected variant {selected.variant_id} "
                    f"for post {post_id} in experiment {experiment.id}"
                )
                return selected

        # Run async function in sync context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(_get_variant())
