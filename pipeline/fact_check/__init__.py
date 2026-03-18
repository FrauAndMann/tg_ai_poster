"""
Phase 2 Factual Accuracy Modules.

This package provides enhanced claim extraction and hallucination detection
for the content pipeline.

Modules:
    - claim_extractor: Enhanced extraction of verifiable claims from text
    - hallucination_detector: Detection of AI-generated hallucinations
    - source_mapper: Mapping claims to sources and generating footnotes
"""

from pipeline.fact_check.claim_extractor import Claim, ClaimExtractor, ClaimType
from pipeline.fact_check.hallucination_detector import (
    HallucinationDetector,
    HallucinationReport,
)
from pipeline.fact_check.source_mapper import (
    ClaimSource,
    SourceMapper,
    SourceMappingResult,
)

__all__ = [
    "Claim",
    "ClaimExtractor",
    "ClaimType",
    "HallucinationDetector",
    "HallucinationReport",
    "ClaimSource",
    "SourceMapper",
    "SourceMappingResult",
]
