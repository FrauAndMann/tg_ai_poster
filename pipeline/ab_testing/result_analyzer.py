"""
Result Analyzer for A/B Testing Framework.

Provides statistical analysis of experiment results, including
significance testing and recommendations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VariantResult:
    """
    Results for a single variant.

    Aggregates metrics collected for a variant during an experiment.

    Attributes:
        variant_id: ID of the variant
        sample_size: Number of observations
        avg_engagement: Average engagement score
        avg_quality_score: Average quality score
        conversion_rate: Conversion rate (0.0-1.0)
        raw_engagement_scores: Raw engagement scores for statistical testing
    """

    variant_id: str
    sample_size: int
    avg_engagement: float
    avg_quality_score: float
    conversion_rate: float
    raw_engagement_scores: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "variant_id": self.variant_id,
            "sample_size": self.sample_size,
            "avg_engagement": self.avg_engagement,
            "avg_quality_score": self.avg_quality_score,
            "conversion_rate": self.conversion_rate,
        }


@dataclass
class ExperimentResult:
    """
    Complete analysis results for an experiment.

    Contains variant results, winner determination, and recommendations.

    Attributes:
        experiment_id: ID of the experiment
        variant_results: Dict mapping variant_id to VariantResult
        winner: ID of winning variant (or None)
        confidence: Confidence level of the result (0.0-1.0)
        recommendation: Human-readable recommendation
        p_value: Statistical p-value (if applicable)
    """

    experiment_id: str
    variant_results: Dict[str, VariantResult]
    winner: Optional[str]
    confidence: float
    recommendation: str
    p_value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "variant_results": {
                k: v.to_dict() for k, v in self.variant_results.items()
            },
            "winner": self.winner,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "p_value": self.p_value,
        }


class ResultAnalyzer:
    """
    Analyzes A/B experiment results with statistical comparison.

    Provides methods for:
    - Statistical significance calculation (t-test)
    - Winner determination
    - Recommendations generation

    Example:
        >>> analyzer = ResultAnalyzer(min_sample_size=30, confidence_threshold=0.95)
        >>> results = [
        ...     {"variant_id": "A", "engagement": 4.0, "quality_score": 80, "converted": True},
        ...     {"variant_id": "B", "engagement": 5.0, "quality_score": 85, "converted": True},
        ... ]
        >>> analysis = analyzer.analyze_experiment("exp_001", results, "A")
        >>> print(analysis.winner)
    """

    def __init__(
        self,
        min_sample_size: int = 30,
        confidence_threshold: float = 0.95,
    ) -> None:
        """
        Initialize result analyzer.

        Args:
            min_sample_size: Minimum samples per variant for analysis
            confidence_threshold: Threshold for declaring significance
        """
        self.min_sample_size = min_sample_size
        self.confidence_threshold = confidence_threshold
        logger.info(
            f"ResultAnalyzer initialized with min_sample_size={min_sample_size}, "
            f"confidence_threshold={confidence_threshold}"
        )

    def analyze_experiment(
        self,
        experiment_id: str,
        results: List[Dict[str, Any]],
        control_variant: str,
    ) -> ExperimentResult:
        """
        Analyze experiment results with statistical comparison.

        Args:
            experiment_id: ID of the experiment
            results: List of result dictionaries with keys:
                - variant_id: str
                - engagement: float (engagement score)
                - quality_score: float (optional)
                - converted: bool (optional)
            control_variant: ID of the control variant

        Returns:
            ExperimentResult with analysis and recommendations
        """
        logger.info(f"Analyzing experiment {experiment_id} with {len(results)} results")

        # Group results by variant
        variant_data: Dict[str, Dict[str, List]] = {}
        for result in results:
            variant_id = result["variant_id"]
            if variant_id not in variant_data:
                variant_data[variant_id] = {
                    "engagements": [],
                    "quality_scores": [],
                    "conversions": [],
                }

            variant_data[variant_id]["engagements"].append(
                result.get("engagement", 0.0)
            )
            if "quality_score" in result:
                variant_data[variant_id]["quality_scores"].append(
                    result["quality_score"]
                )
            if "converted" in result:
                variant_data[variant_id]["conversions"].append(
                    1 if result["converted"] else 0
                )

        # Check minimum sample size
        insufficient_data = False
        for variant_id, data in variant_data.items():
            if len(data["engagements"]) < self.min_sample_size:
                insufficient_data = True
                logger.warning(
                    f"Variant {variant_id} has only {len(data['engagements'])} samples, "
                    f"minimum is {self.min_sample_size}"
                )

        # Calculate variant results
        variant_results: Dict[str, VariantResult] = {}
        for variant_id, data in variant_data.items():
            engagements = data["engagements"]
            quality_scores = data["quality_scores"]
            conversions = data["conversions"]

            avg_engagement = sum(engagements) / len(engagements) if engagements else 0.0
            avg_quality = (
                sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            )
            conversion_rate = (
                sum(conversions) / len(conversions) if conversions else 0.0
            )

            variant_results[variant_id] = VariantResult(
                variant_id=variant_id,
                sample_size=len(engagements),
                avg_engagement=avg_engagement,
                avg_quality_score=avg_quality,
                conversion_rate=conversion_rate,
                raw_engagement_scores=engagements,
            )

        # Handle insufficient data
        if insufficient_data or len(variant_results) < 2:
            return ExperimentResult(
                experiment_id=experiment_id,
                variant_results=variant_results,
                winner=None,
                confidence=0.0,
                recommendation="Insufficient data for analysis. "
                f"Each variant needs at least {self.min_sample_size} samples. "
                "Continue collecting data before making conclusions.",
            )

        # Calculate statistical significance
        control_data = variant_data.get(control_variant, {}).get("engagements", [])
        best_variant = None
        best_p_value = 1.0
        best_confidence = 0.0

        for variant_id, data in variant_data.items():
            if variant_id == control_variant:
                continue

            treatment_data = data["engagements"]
            p_value = self._calculate_significance(control_data, treatment_data)
            confidence = 1.0 - p_value

            # Track best performing variant
            variant_result = variant_results[variant_id]
            control_result = variant_results[control_variant]

            if variant_result.avg_engagement > control_result.avg_engagement:
                if confidence > best_confidence:
                    best_variant = variant_id
                    best_p_value = p_value
                    best_confidence = confidence

        # Determine winner
        if best_variant and best_confidence >= self.confidence_threshold:
            winner = best_variant
            confidence = best_confidence
            recommendation = self._generate_recommendation(
                winner,
                variant_results[control_variant],
                variant_results[winner],
                confidence,
            )
        else:
            winner = None
            confidence = best_confidence if best_variant else 0.0
            recommendation = self._generate_no_winner_recommendation(
                variant_results, confidence
            )

        logger.info(
            f"Experiment {experiment_id} analysis complete: "
            f"winner={winner}, confidence={confidence:.2%}"
        )

        return ExperimentResult(
            experiment_id=experiment_id,
            variant_results=variant_results,
            winner=winner,
            confidence=confidence,
            recommendation=recommendation,
            p_value=best_p_value if best_variant else None,
        )

    def _calculate_significance(
        self, control: List[float], treatment: List[float]
    ) -> float:
        """
        Calculate statistical significance using Welch's t-test.

        This is a two-sample t-test that does not assume equal variances.

        Args:
            control: Control group values
            treatment: Treatment group values

        Returns:
            p-value (probability that difference is due to chance)
        """
        if len(control) < 2 or len(treatment) < 2:
            return 1.0

        n1 = len(control)
        n2 = len(treatment)

        mean1 = sum(control) / n1
        mean2 = sum(treatment) / n2

        # Calculate variances
        var1 = sum((x - mean1) ** 2 for x in control) / (n1 - 1)
        var2 = sum((x - mean2) ** 2 for x in treatment) / (n2 - 1)

        # Welch's t-test
        se = math.sqrt(var1 / n1 + var2 / n2)
        if se == 0:
            return 1.0

        t_stat = (mean2 - mean1) / se

        # Degrees of freedom (Welch-Satterthwaite equation)
        df_num = (var1 / n1 + var2 / n2) ** 2
        df_denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
        if df_denom == 0:
            return 1.0
        df = df_num / df_denom

        # Calculate p-value using t-distribution CDF approximation
        p_value = self._t_distribution_p_value(t_stat, df)

        return p_value

    def _t_distribution_p_value(self, t: float, df: float) -> float:
        """
        Approximate two-tailed p-value for t-distribution.

        Uses an approximation formula for the t-distribution CDF.

        Args:
            t: t-statistic
            df: degrees of freedom

        Returns:
            Two-tailed p-value (always in range [0, 1])
        """
        if df <= 0:
            return 1.0

        # Use approximation for large df
        if df > 100:
            # Approximate with normal distribution
            p = 2 * (1 - self._normal_cdf(abs(t)))
            return max(0.0, min(1.0, p))

        # Use numerical approximation for t-distribution
        # Based on Abramowitz and Stegun approximation
        x = df / (df + t * t)
        p = self._incomplete_beta(df / 2, 0.5, x)

        # Two-tailed p-value - ensure it's in valid range
        two_tailed = 2 * min(p, 1 - p)
        return max(0.0, min(1.0, two_tailed))

    def _normal_cdf(self, x: float) -> float:
        """
        Standard normal distribution CDF approximation.

        Uses error function approximation.
        """
        # Constants for approximation
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911

        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2)

        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(
            -x * x
        )

        return 0.5 * (1.0 + sign * y)

    def _incomplete_beta(self, a: float, b: float, x: float) -> float:
        """
        Approximate the incomplete beta function.

        Used for t-distribution p-value calculation.
        """
        if x < 0 or x > 1:
            return 0.0
        if x == 0:
            return 0.0
        if x == 1:
            return 1.0

        # Use continued fraction expansion
        front = (
            math.exp(
                self._log_gamma(a + b)
                - self._log_gamma(a)
                - self._log_gamma(b)
                + a * math.log(x)
                + b * math.log(1 - x)
            )
            / a
        )

        # Lentz's algorithm for continued fraction
        f = 1.0
        c = 1.0
        d = 0.0

        for m in range(1, 200):
            # Calculate a_m coefficients
            m_a = m + m
            d_num = m * (b - m) * x / ((a + m_a - 1) * (a + m_a))
            d_denom = (
                -((a + m) * (a + b + m) * x) / ((a + m_a) * (a + m_a + 1))
            )

            d = 1.0 + d_num * d
            if abs(d) < 1e-30:
                d = 1e-30
            d = 1.0 / d

            c = 1.0 + d_denom / c
            if abs(c) < 1e-30:
                c = 1e-30

            delta = c * d
            f *= delta

            if abs(delta - 1.0) < 1e-10:
                break

        return front * (f - 1.0)

    def _log_gamma(self, x: float) -> float:
        """
        Natural log of gamma function using Lanczos approximation.
        """
        if x <= 0:
            return float("inf")

        # Lanczos coefficients
        coef = [
            76.18009172947146,
            -86.50532032941677,
            24.01409824083091,
            -1.231739572450155,
            0.1208650973866179e-2,
            -0.5395239384953e-5,
        ]

        y = x
        tmp = x + 5.5
        tmp -= (x + 0.5) * math.log(tmp)
        ser = 1.000000000190015

        for c in coef:
            y += 1
            ser += c / y

        return -tmp + math.log(2.5066282746310005 * ser / x)

    def _generate_recommendation(
        self,
        winner: str,
        control: VariantResult,
        treatment: VariantResult,
        confidence: float,
    ) -> str:
        """Generate recommendation when a winner is determined."""
        engagement_lift = (
            (treatment.avg_engagement - control.avg_engagement)
            / control.avg_engagement
            * 100
        )
        quality_lift = (
            (treatment.avg_quality_score - control.avg_quality_score)
            / control.avg_quality_score
            * 100
            if control.avg_quality_score > 0
            else 0
        )
        conversion_lift = (
            (treatment.conversion_rate - control.conversion_rate)
            / control.conversion_rate
            * 100
            if control.conversion_rate > 0
            else 0
        )

        recommendation = (
            f"Variant '{winner}' shows statistically significant improvement "
            f"with {confidence:.1%} confidence.\n\n"
            f"Performance improvements:\n"
            f"- Engagement: +{engagement_lift:.1f}% "
            f"({control.avg_engagement:.2f} -> {treatment.avg_engagement:.2f})\n"
        )

        if quality_lift != 0:
            recommendation += (
                f"- Quality Score: +{quality_lift:.1f}% "
                f"({control.avg_quality_score:.1f} -> {treatment.avg_quality_score:.1f})\n"
            )

        if conversion_lift != 0:
            recommendation += (
                f"- Conversion Rate: +{conversion_lift:.1f}% "
                f"({control.conversion_rate:.1%} -> {treatment.conversion_rate:.1%})\n"
            )

        recommendation += (
            f"\nRecommendation: Adopt the '{winner}' configuration "
            f"as the new baseline for future content generation."
        )

        return recommendation

    def _generate_no_winner_recommendation(
        self,
        variant_results: Dict[str, VariantResult],
        best_confidence: float,
    ) -> str:
        """Generate recommendation when no clear winner is found."""
        if best_confidence < self.confidence_threshold:
            return (
                f"No statistically significant difference found "
                f"(best confidence: {best_confidence:.1%}, "
                f"threshold: {self.confidence_threshold:.1%}).\n\n"
                f"Options:\n"
                f"1. Continue the experiment to collect more data\n"
                f"2. Declare no winner and keep current configuration\n"
                f"3. Design a new experiment with more distinct variations"
            )

        return (
            "Results are inconclusive. Consider:\n"
            "- Running the experiment longer\n"
            "- Increasing traffic to variants\n"
            "- Testing more distinct variations"
        )

    def compare_variants(
        self,
        control: VariantResult,
        treatment: VariantResult,
    ) -> Dict[str, Any]:
        """
        Compare two variants directly.

        Args:
            control: Control variant results
            treatment: Treatment variant results

        Returns:
            Dict with comparison metrics
        """
        p_value = self._calculate_significance(
            control.raw_engagement_scores,
            treatment.raw_engagement_scores,
        )

        engagement_delta = treatment.avg_engagement - control.avg_engagement
        engagement_lift = (
            engagement_delta / control.avg_engagement * 100
            if control.avg_engagement > 0
            else 0
        )

        return {
            "control_id": control.variant_id,
            "treatment_id": treatment.variant_id,
            "engagement_delta": engagement_delta,
            "engagement_lift_percent": engagement_lift,
            "quality_delta": treatment.avg_quality_score - control.avg_quality_score,
            "conversion_delta": treatment.conversion_rate - control.conversion_rate,
            "p_value": p_value,
            "is_significant": p_value < (1 - self.confidence_threshold),
            "confidence": 1 - p_value,
        }
