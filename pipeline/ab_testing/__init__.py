"""
A/B Testing Framework Module.

Provides data-driven prompt optimization through controlled experiments.

Components:
- ExperimentManager: Define and manage experiments
- VariantRouter: Assign posts to variants deterministically
- ResultAnalyzer: Statistical comparison of variants
"""

from __future__ import annotations

from pipeline.ab_testing.experiment_manager import (
    Experiment,
    ExperimentManager,
    Variant,
)
from pipeline.ab_testing.result_analyzer import (
    ExperimentResult,
    ResultAnalyzer,
    VariantResult,
)
from pipeline.ab_testing.variant_router import VariantRouter

__all__ = [
    # Experiment management
    "Experiment",
    "ExperimentManager",
    "Variant",
    # Routing
    "VariantRouter",
    # Analysis
    "ExperimentResult",
    "ResultAnalyzer",
    "VariantResult",
]
