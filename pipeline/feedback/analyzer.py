"""
Feedback Analyzer - Analyzes engagement metrics and generates insights.

Correlates quality scores with engagement metrics to generate
recommendations for improving content quality thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Tuple, Optional
import math

from core.logger import get_logger
from pipeline.feedback.collector import PostAnalytics

logger = get_logger(__name__)


@dataclass
class WeeklyAnalysis:
    """Analysis results for a weekly period."""

    period: Tuple[date, date]
    total_posts: int
    avg_quality_score: float
    avg_engagement: float
    correlation: float  # quality vs engagement correlation (-1 to 1)
    recommendations: List[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "period_start": self.period[0].isoformat(),
            "period_end": self.period[1].isoformat(),
            "total_posts": self.total_posts,
            "avg_quality_score": self.avg_quality_score,
            "avg_engagement": self.avg_engagement,
            "correlation": self.correlation,
            "recommendations": self.recommendations,
        }


class FeedbackAnalyzer:
    """
    Analyzes engagement metrics and generates insights.

    Features:
    - Calculates correlation between quality scores and engagement
    - Identifies patterns in high-performing content
    - Generates actionable recommendations
    - Suggests threshold adjustments
    """

    def __init__(
        self,
        min_posts_for_analysis: int = 5,
        quality_threshold: float = 70.0,
    ):
        """
        Initialize the feedback analyzer.

        Args:
            min_posts_for_analysis: Minimum posts needed for meaningful analysis
            quality_threshold: Current quality threshold for recommendations
        """
        self.min_posts_for_analysis = min_posts_for_analysis
        self.quality_threshold = quality_threshold

    def analyze_week(
        self,
        analytics: List[PostAnalytics],
        period: Tuple[date, date],
    ) -> WeeklyAnalysis:
        """
        Analyze a week's worth of analytics.

        Args:
            analytics: List of post analytics for the period
            period: Tuple of (start_date, end_date)

        Returns:
            WeeklyAnalysis with insights and recommendations
        """
        if not analytics:
            return WeeklyAnalysis(
                period=period,
                total_posts=0,
                avg_quality_score=0.0,
                avg_engagement=0.0,
                correlation=0.0,
                recommendations=[
                    "No posts available for analysis. Start publishing to collect data.",
                    "Ensure feedback collection is enabled to track engagement.",
                ],
            )

        # Calculate averages
        avg_quality_score = sum(a.quality_score for a in analytics) / len(analytics)
        avg_engagement = sum(a.engagement_rate for a in analytics) / len(analytics)

        # Calculate correlation between quality and engagement
        correlation = self._calculate_correlation(analytics)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            analytics=analytics,
            avg_quality_score=avg_quality_score,
            avg_engagement=avg_engagement,
            correlation=correlation,
        )

        return WeeklyAnalysis(
            period=period,
            total_posts=len(analytics),
            avg_quality_score=avg_quality_score,
            avg_engagement=avg_engagement,
            correlation=correlation,
            recommendations=recommendations,
        )

    def _calculate_correlation(
        self,
        analytics: List[PostAnalytics],
    ) -> float:
        """
        Calculate Pearson correlation coefficient between quality score and engagement.

        Args:
            analytics: List of post analytics

        Returns:
            Correlation coefficient (-1 to 1), or 0 if cannot calculate
        """
        if len(analytics) < 2:
            return 0.0

        quality_scores = [a.quality_score for a in analytics]
        engagement_rates = [a.engagement_rate for a in analytics]

        n = len(quality_scores)

        # Calculate means
        mean_quality = sum(quality_scores) / n
        mean_engagement = sum(engagement_rates) / n

        # Calculate standard deviations and covariance
        sum_sq_quality = sum((q - mean_quality) ** 2 for q in quality_scores)
        sum_sq_engagement = sum((e - mean_engagement) ** 2 for e in engagement_rates)
        sum_product = sum(
            (quality_scores[i] - mean_quality) * (engagement_rates[i] - mean_engagement)
            for i in range(n)
        )

        # Avoid division by zero
        if sum_sq_quality == 0 or sum_sq_engagement == 0:
            return 0.0

        # Pearson correlation coefficient
        correlation = sum_product / math.sqrt(sum_sq_quality * sum_sq_engagement)

        # Clamp to valid range
        return max(-1.0, min(1.0, correlation))

    def _generate_recommendations(
        self,
        analytics: List[PostAnalytics],
        avg_quality_score: float,
        avg_engagement: float,
        correlation: float,
    ) -> List[str]:
        """
        Generate actionable recommendations based on analysis.

        Args:
            analytics: List of post analytics
            avg_quality_score: Average quality score
            avg_engagement: Average engagement rate
            correlation: Quality-engagement correlation

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check if we have enough data for meaningful analysis
        if len(analytics) < self.min_posts_for_analysis:
            recommendations.append(
                f"Collect more data for reliable analysis. "
                f"Current: {len(analytics)} posts, recommended: {self.min_posts_for_analysis}+"
            )
            return recommendations

        # Analyze correlation
        if correlation >= 0.5:
            recommendations.append(
                "Strong positive correlation: quality scores predict engagement well. "
                "Continue using current quality assessment."
            )
        elif correlation >= 0.2:
            recommendations.append(
                "Moderate correlation between quality and engagement. "
                "Consider refining quality scoring criteria."
            )
        elif correlation >= -0.2:
            recommendations.append(
                "Weak correlation: quality scores don't strongly predict engagement. "
                "Review quality scoring methodology."
            )
        else:
            recommendations.append(
                "Negative correlation detected: high quality posts may be underperforming. "
                "Investigate content style and audience preferences."
            )

        # Quality threshold recommendations
        if avg_quality_score < self.quality_threshold:
            recommendations.append(
                f"Average quality score ({avg_quality_score:.1f}) is below threshold "
                f"({self.quality_threshold}). Consider lowering threshold or improving content."
            )
        elif avg_quality_score > self.quality_threshold + 15:
            recommendations.append(
                f"Average quality score ({avg_quality_score:.1f}) is well above threshold. "
                f"Consider raising threshold from {self.quality_threshold} to {avg_quality_score - 10:.0f}."
            )

        # Engagement recommendations
        if avg_engagement < 0.01:
            recommendations.append(
                "Low engagement rate (<1%). Review content strategy and posting times."
            )
        elif avg_engagement > 0.05:
            recommendations.append(
                f"Good engagement rate ({avg_engagement:.1%}). "
                "Current content strategy is working well."
            )

        # Identify top performers
        top_performers = self._identify_top_performers(analytics)
        if top_performers:
            avg_top_quality = sum(a.quality_score for a in top_performers) / len(top_performers)
            recommendations.append(
                f"Top {len(top_performers)} posts have avg quality score {avg_top_quality:.1f}. "
                f"Use this as a benchmark for content quality."
            )

        return recommendations

    def _identify_top_performers(
        self,
        analytics: List[PostAnalytics],
        top_percent: float = 0.2,
    ) -> List[PostAnalytics]:
        """
        Identify top performing posts by engagement rate.

        Args:
            analytics: List of post analytics
            top_percent: Percentage of top posts to return

        Returns:
            List of top performing posts
        """
        if not analytics:
            return []

        # Sort by engagement rate
        sorted_analytics = sorted(
            analytics,
            key=lambda a: a.engagement_rate,
            reverse=True,
        )

        # Get top percentage
        top_count = max(1, int(len(sorted_analytics) * top_percent))
        return sorted_analytics[:top_count]

    def suggest_threshold_adjustment(
        self,
        analytics: List[PostAnalytics],
    ) -> Optional[float]:
        """
        Suggest a new quality threshold based on engagement data.

        Analyzes the relationship between quality scores and engagement
        to suggest an optimal threshold.

        Args:
            analytics: List of post analytics

        Returns:
            Suggested threshold or None if cannot determine
        """
        if len(analytics) < self.min_posts_for_analysis:
            return None

        # Find posts with above-average engagement
        avg_engagement = sum(a.engagement_rate for a in analytics) / len(analytics)
        high_engagement_posts = [a for a in analytics if a.engagement_rate > avg_engagement]

        if not high_engagement_posts:
            return None

        # Calculate quality score distribution for high-engagement posts
        quality_scores = [a.quality_score for a in high_engagement_posts]
        if not quality_scores:
            return None

        # Suggest threshold at 10th percentile of high-engagement quality scores
        quality_scores.sort()
        percentile_index = max(0, int(len(quality_scores) * 0.1))
        suggested_threshold = quality_scores[percentile_index]

        # Round to nearest 5
        suggested_threshold = round(suggested_threshold / 5) * 5

        # Only suggest if significantly different from current
        if abs(suggested_threshold - self.quality_threshold) < 5:
            return None

        return suggested_threshold

    def get_engagement_trends(
        self,
        analytics: List[PostAnalytics],
    ) -> dict:
        """
        Analyze engagement trends over time.

        Args:
            analytics: List of post analytics sorted by date

        Returns:
            Dict with trend analysis
        """
        if len(analytics) < 2:
            return {"trend": "insufficient_data"}

        # Split into first and second half
        mid = len(analytics) // 2
        first_half = analytics[:mid]
        second_half = analytics[mid:]

        first_avg = sum(a.engagement_rate for a in first_half) / len(first_half)
        second_avg = sum(a.engagement_rate for a in second_half) / len(second_half)

        change = (second_avg - first_avg) / first_avg if first_avg > 0 else 0

        if change > 0.1:
            trend = "improving"
        elif change < -0.1:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "change_percent": change * 100,
            "first_half_avg": first_avg,
            "second_half_avg": second_avg,
        }

    def analyze_by_quality_bracket(
        self,
        analytics: List[PostAnalytics],
        bracket_size: int = 10,
    ) -> dict:
        """
        Analyze engagement by quality score brackets.

        Args:
            analytics: List of post analytics
            bracket_size: Size of quality score brackets

        Returns:
            Dict mapping quality brackets to avg engagement
        """
        if not analytics:
            return {}

        brackets = {}

        for a in analytics:
            bracket = int(a.quality_score // bracket_size) * bracket_size
            bracket_label = f"{bracket}-{bracket + bracket_size}"

            if bracket_label not in brackets:
                brackets[bracket_label] = []
            brackets[bracket_label].append(a.engagement_rate)

        # Calculate averages per bracket
        result = {}
        for bracket_label, rates in brackets.items():
            result[bracket_label] = {
                "avg_engagement": sum(rates) / len(rates),
                "post_count": len(rates),
            }

        return result
