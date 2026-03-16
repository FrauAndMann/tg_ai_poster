"""
Reporting module - Automated reports and analytics.

Provides benchmark reporting, analytics, and insights generation.
"""

from reporting.benchmark_reporter import (
    BenchmarkReporter,
    BenchmarkReport,
    MetricValue,
    ReportPeriod,
    MetricCategory,
    BENCHMARK_REPORTER_CONFIG_SCHEMA,
)

__all__ = [
    "BenchmarkReporter",
    "BenchmarkReport",
    "MetricValue",
    "ReportPeriod",
    "MetricCategory",
    "BENCHMARK_REPORTER_CONFIG_SCHEMA",
]
