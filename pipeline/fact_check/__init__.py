"""
Phase 2 Factual Accuracy Modules.

This package provides enhanced claim extraction and hallucination detection
for the content pipeline.

Modules:
    - claim_extractor: Enhanced extraction of verifiable claims from text
    - hallucination_detector: Detection of AI-generated hallucinations
"""

from pipeline.fact_check.claim_extractor import Claim, ClaimExtractor, ClaimType
from pipeline.fact_check.hallucination_detector import (
    HallucinationDetector,
    HallucinationReport,
)

__all__ = [
    "Claim",
    "ClaimExtractor",
    "ClaimType",
    "HallucinationDetector",
    "HallucinationReport",
]
