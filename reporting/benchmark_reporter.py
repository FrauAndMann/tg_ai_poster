"""
Automated Quality Benchmark Reports - Performance analytics and insights.

Generates comprehensive reports on channel performance, quality metrics,
engagement trends, and actionable recommendations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from core.logger import get_logger

if TYPE_CHECKING:
    from memory.database import PostStore

logger = get_logger(__name__)


class ReportPeriod(Enum):
    """Report time periods."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class MetricCategory(Enum):
    """Categories of metrics."""
    VOLUME = "volume"
    QUALITY = "quality"
    ENGAGEMENT = "engagement"
    EFFICIENCY = "efficiency"


@dataclass(slots=True)
class MetricValue:
    """A metric with value and context."""

    name: str
    value: float
    previous_value: Optional[float] = None
    change_pct: Optional[float] = None
    unit: str = ""
    category: MetricCategory = MetricCategory.VOLUME
    is_positive: bool = True


@dataclass(slots=True)
class BenchmarkReport:
    """Complete benchmark report."""

    period: ReportPeriod
    generated_at: datetime
    start_date: datetime
    end_date: datetime

    # Volume metrics
    total_posts: int = 0
    posts_by_type: dict[str, int] = field(default_factory=dict)

    # Quality metrics
    avg_quality_score: float = 0.0
    quality_distribution: dict[str, int] = field(default_factory=dict)
    failed_quality_checks: int = 0

    # Engagement metrics
    total_views: int = 0
    avg_views_per_post: float = 0.0
    total_reactions: int = 0
    total_forwards: int = 0
    engagement_rate: float = 0.0

    # Efficiency metrics
    avg_generation_time_seconds: float = 0.0
    success_rate: float = 0.0
    llm_cost_estimate: float = 0.0

    # Top performers
    top_posts: list[dict[str, Any]] = field(default_factory=list)
    top_topics: list[str] = field(default_factory=list)

    # Insights
    recommendations: list[str] = field(default_factory=list)
    trends: list[str] = field(default_factory=list)

    # Metrics collection
    metrics: list[MetricValue] = field(default_factory=list)


class BenchmarkReporter:
    """
    Generates automated quality benchmark reports.

    Features:
    - Multi-period analysis (daily, weekly, monthly)
    - Trend detection and comparison
    - Actionable recommendations
    - Export to multiple formats
    """

    # Benchmark thresholds
    QUALITY_THRESHOLDS = {
        "excellent": 90,
        "good": 75,
        "acceptable": 60,
        "needs_improvement": 40,
    }

    ENGAGEMENT_BENCHMARKS = {
        "high": 0.05,  # 5% engagement rate
        "medium": 0.02,  # 2%
        "low": 0.01,  # 1%
    }

    def __init__(
        self,
        post_store: Optional["PostStore"] = None,
        output_dir: str = "data/reports",
    ) -> None:
        self.post_store = post_store
        self.output_dir = output_dir
        self._previous_reports: dict[ReportPeriod, BenchmarkReport] = {}

    async def generate_report(
        self,
        period: ReportPeriod = ReportPeriod.WEEKLY,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None,
    ) -> BenchmarkReport:
        """
        Generate a benchmark report.

        Args:
            period: Report period type
            custom_start: Custom start date (optional)
            custom_end: Custom end date (optional)

        Returns:
            BenchmarkReport with all metrics
        """
        now = datetime.now()

        # Determine date range
        if custom_start and custom_end:
            start_date, end_date = custom_start, custom_end
        else:
            start_date, end_date = self._get_period_range(period, now)

        report = BenchmarkReport(
            period=period,
            generated_at=now,
            start_date=start_date,
            end_date=end_date,
        )

        # Gather metrics
        await self._gather_volume_metrics(report)
        await self._gather_quality_metrics(report)
        await self._gather_engagement_metrics(report)
        await self._gather_efficiency_metrics(report)

        # Identify top performers
        await self._identify_top_performers(report)

        # Generate insights
        self._generate_recommendations(report)
        self._detect_trends(report)

        # Calculate changes from previous period
        await self._calculate_period_changes(report)

        # Store for comparison
        self._previous_reports[period] = report

        logger.info(
            "Generated %s benchmark report for %s to %s",
            period.value,
            start_date.date(),
            end_date.date(),
        )

        return report

    def _get_period_range(
        self,
        period: ReportPeriod,
        now: datetime,
    ) -> tuple[datetime, datetime]:
        """Get date range for period."""
        if period == ReportPeriod.DAILY:
            start = now - timedelta(days=1)
            end = now
        elif period == ReportPeriod.WEEKLY:
            start = now - timedelta(weeks=1)
            end = now
        elif period == ReportPeriod.MONTHLY:
            start = now - timedelta(days=30)
            end = now
        else:  # QUARTERLY
            start = now - timedelta(days=90)
            end = now
        return start, end

    async def _gather_volume_metrics(self, report: BenchmarkReport) -> None:
        """Gather volume metrics."""
        if not self.post_store:
            return

        try:
            posts = await self.post_store.list(limit=1000)
            filtered = [
                p for p in posts
                if report.start_date <= (p.published_at or datetime.min) <= report.end_date
            ]

            report.total_posts = len(filtered)

            # Count by type
            for post in filtered:
                post_type = post.post_type or "unknown"
                report.posts_by_type[post_type] = report.posts_by_type.get(post_type, 0) + 1

            report.metrics.append(MetricValue(
                name="Total Posts",
                value=report.total_posts,
                unit="posts",
                category=MetricCategory.VOLUME,
            ))

        except Exception as e:
            logger.error("Failed to gather volume metrics: %s", e)

    async def _gather_quality_metrics(self, report: BenchmarkReport) -> None:
        """Gather quality metrics."""
        if not self.post_store:
            return

        try:
            posts = await self.post_store.list(limit=1000)
            filtered = [
                p for p in posts
                if report.start_date <= (p.published_at or datetime.min) <= report.end_date
                and p.quality_score is not None
            ]

            if filtered:
                scores = [p.quality_score for p in filtered]
                report.avg_quality_score = sum(scores) / len(scores)

                # Distribution
                for score in scores:
                    if score >= self.QUALITY_THRESHOLDS["excellent"]:
                        bucket = "excellent"
                    elif score >= self.QUALITY_THRESHOLDS["good"]:
                        bucket = "good"
                    elif score >= self.QUALITY_THRESHOLDS["acceptable"]:
                        bucket = "acceptable"
                    else:
                        bucket = "needs_improvement"
                    report.quality_distribution[bucket] = report.quality_distribution.get(bucket, 0) + 1

            report.metrics.append(MetricValue(
                name="Avg Quality Score",
                value=report.avg_quality_score,
                unit="points",
                category=MetricCategory.QUALITY,
                is_positive=report.avg_quality_score >= self.QUALITY_THRESHOLDS["good"],
            ))

        except Exception as e:
            logger.error("Failed to gather quality metrics: %s", e)

    async def _gather_engagement_metrics(self, report: BenchmarkReport) -> None:
        """Gather engagement metrics."""
        if not self.post_store:
            return

        try:
            posts = await self.post_store.list(limit=1000)
            filtered = [
                p for p in posts
                if report.start_date <= (p.published_at or datetime.min) <= report.end_date
            ]

            report.total_views = sum(p.views or 0 for p in filtered)
            report.total_reactions = sum(getattr(p, "reactions", 0) or 0 for p in filtered)
            report.total_forwards = sum(getattr(p, "forwards", 0) or 0 for p in filtered)

            if report.total_posts > 0:
                report.avg_views_per_post = report.total_views / report.total_posts

            if report.total_views > 0:
                report.engagement_rate = (report.total_reactions + report.total_forwards) / report.total_views

            report.metrics.append(MetricValue(
                name="Engagement Rate",
                value=report.engagement_rate * 100,
                unit="%",
                category=MetricCategory.ENGAGEMENT,
                is_positive=report.engagement_rate >= self.ENGAGEMENT_BENCHMARKS["medium"],
            ))

        except Exception as e:
            logger.error("Failed to gather engagement metrics: %s", e)

    async def _gather_efficiency_metrics(self, report: BenchmarkReport) -> None:
        """Gather efficiency metrics."""
        # Placeholder - would integrate with actual timing data
        report.avg_generation_time_seconds = 15.0  # Default estimate
        report.success_rate = 0.95  # Default estimate
        report.llm_cost_estimate = report.total_posts * 0.02  # Estimate $0.02 per post

        report.metrics.append(MetricValue(
            name="Success Rate",
            value=report.success_rate * 100,
            unit="%",
            category=MetricCategory.EFFICIENCY,
            is_positive=report.success_rate >= 0.9,
        ))

    async def _identify_top_performers(self, report: BenchmarkReport) -> None:
        """Identify top performing posts."""
        if not self.post_store:
            return

        try:
            posts = await self.post_store.list(limit=100)
            filtered = [
                p for p in posts
                if report.start_date <= (p.published_at or datetime.min) <= report.end_date
            ]

            # Sort by views
            sorted_posts = sorted(filtered, key=lambda p: p.views or 0, reverse=True)

            for post in sorted_posts[:5]:
                report.top_posts.append({
                    "id": post.id,
                    "topic": post.topic or "Unknown",
                    "views": post.views or 0,
                    "quality_score": post.quality_score or 0,
                    "published_at": post.published_at.isoformat() if post.published_at else None,
                })

            # Extract top topics
            topics: dict[str, int] = {}
            for post in filtered:
                if post.topic:
                    topics[post.topic] = topics.get(post.topic, 0) + (post.views or 1)

            report.top_topics = sorted(topics.keys(), key=lambda t: topics[t], reverse=True)[:5]

        except Exception as e:
            logger.error("Failed to identify top performers: %s", e)

    def _generate_recommendations(self, report: BenchmarkReport) -> None:
        """Generate actionable recommendations."""
        recommendations = []

        # Quality recommendations
        if report.avg_quality_score < self.QUALITY_THRESHOLDS["good"]:
            recommendations.append(
                "Improve content quality - focus on deeper analysis and better sourcing"
            )

        if report.quality_distribution.get("needs_improvement", 0) > report.total_posts * 0.1:
            recommendations.append(
                "Review quality check rules - too many posts failing quality threshold"
            )

        # Engagement recommendations
        if report.engagement_rate < self.ENGAGEMENT_BENCHMARKS["medium"]:
            recommendations.append(
                "Boost engagement - try more polls, questions, and interactive content"
            )

        # Volume recommendations
        if report.total_posts < 7:
            recommendations.append(
                "Increase posting frequency - aim for at least 1 post per day"
            )

        # Mix recommendations
        if len(report.posts_by_type) < 3:
            recommendations.append(
                "Diversify content types - add variety to keep audience engaged"
            )

        report.recommendations = recommendations

    def _detect_trends(self, report: BenchmarkReport) -> None:
        """Detect trends in the data."""
        trends = []

        # Check previous period
        prev = self._previous_reports.get(report.period)
        if prev:
            if report.total_posts > prev.total_posts:
                trends.append(f"Posting frequency increased by {report.total_posts - prev.total_posts} posts")
            elif report.total_posts < prev.total_posts:
                trends.append(f"Posting frequency decreased by {prev.total_posts - report.total_posts} posts")

            if report.avg_quality_score > prev.avg_quality_score + 5:
                trends.append("Quality scores improving significantly")
            elif report.avg_quality_score < prev.avg_quality_score - 5:
                trends.append("Quality scores declining - investigate cause")

            if report.engagement_rate > prev.engagement_rate * 1.1:
                trends.append("Engagement rate trending upward")

        report.trends = trends

    async def _calculate_period_changes(self, report: BenchmarkReport) -> None:
        """Calculate percentage changes from previous period."""
        prev = self._previous_reports.get(report.period)
        if not prev:
            return

        for metric in report.metrics:
            # Find matching previous metric
            for prev_metric in prev.metrics:
                if prev_metric.name == metric.name and prev_metric.value > 0:
                    metric.previous_value = prev_metric.value
                    metric.change_pct = ((metric.value - prev_metric.value) / prev_metric.value) * 100
                    break

    def export_report(
        self,
        report: BenchmarkReport,
        format: str = "json",
    ) -> str:
        """
        Export report to various formats.

        Args:
            report: Report to export
            format: Output format (json, markdown, html)

        Returns:
            Formatted report string
        """
        if format == "json":
            return self._export_json(report)
        elif format == "markdown":
            return self._export_markdown(report)
        elif format == "html":
            return self._export_html(report)
        else:
            return self._export_json(report)

    def _export_json(self, report: BenchmarkReport) -> str:
        """Export as JSON."""
        data = {
            "period": report.period.value,
            "generated_at": report.generated_at.isoformat(),
            "start_date": report.start_date.isoformat(),
            "end_date": report.end_date.isoformat(),
            "metrics": {
                "total_posts": report.total_posts,
                "avg_quality_score": report.avg_quality_score,
                "engagement_rate": report.engagement_rate,
                "success_rate": report.success_rate,
            },
            "quality_distribution": report.quality_distribution,
            "top_posts": report.top_posts,
            "recommendations": report.recommendations,
            "trends": report.trends,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _export_markdown(self, report: BenchmarkReport) -> str:
        """Export as Markdown."""
        lines = [
            f"# Benchmark Report - {report.period.value.title()}",
            f"",
            f"**Period:** {report.start_date.date()} to {report.end_date.date()}",
            f"**Generated:** {report.generated_at.isoformat()}",
            f"",
            f"## Summary",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Posts | {report.total_posts} |",
            f"| Avg Quality Score | {report.avg_quality_score:.1f} |",
            f"| Engagement Rate | {report.engagement_rate * 100:.2f}% |",
            f"| Success Rate | {report.success_rate * 100:.1f}% |",
            f"",
            f"## Quality Distribution",
            f"",
        ]

        for bucket, count in report.quality_distribution.items():
            lines.append(f"- **{bucket.title()}:** {count} posts")

        if report.recommendations:
            lines.extend([
                f"",
                f"## Recommendations",
                f"",
            ])
            for rec in report.recommendations:
                lines.append(f"- {rec}")

        if report.trends:
            lines.extend([
                f"",
                f"## Trends",
                f"",
            ])
            for trend in report.trends:
                lines.append(f"- {trend}")

        return "\n".join(lines)

    def _export_html(self, report: BenchmarkReport) -> str:
        """Export as HTML."""
        md = self._export_markdown(report)
        # Simple markdown-to-HTML conversion
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Benchmark Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <pre>{md}</pre>
</body>
</html>"""
        return html


# Configuration schema
BENCHMARK_REPORTER_CONFIG_SCHEMA = {
    "benchmark_reporting": {
        "enabled": {
            "type": "bool",
            "default": True,
            "description": "Enable automated benchmark reports",
        },
        "default_period": {
            "type": "str",
            "default": "weekly",
            "description": "Default report period (daily, weekly, monthly)",
        },
        "output_dir": {
            "type": "str",
            "default": "data/reports",
            "description": "Directory to save reports",
        },
        "auto_generate": {
            "type": "bool",
            "default": True,
            "description": "Automatically generate reports on schedule",
        },
    }
}
