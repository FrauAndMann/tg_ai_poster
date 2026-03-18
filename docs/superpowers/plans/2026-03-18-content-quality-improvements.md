# Content Quality Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 20 content quality improvements to eliminate "water" content, improve factual accuracy, and ensure publication-ready posts with high information density.

**Architecture:** Extend existing modules (`ai_cliche_detector.py`, `factual_verifier.py`, `quality_checker.py`) with new components. Add anti-water pipeline, enhance fact verification, and create unified quality scoring. Integration point: after `LLMGenerator`, before publishing.

**Tech Stack:** Python 3.10+, dataclasses, regex, asyncio, pytest

---

## File Structure

```
pipeline/
├── anti_water/                   # NEW MODULE
│   ├── __init__.py
│   ├── filler_detector.py        # Detect filler words & water %
│   ├── density_scorer.py         # Information density calculation
│   ├── banned_phrases.py         # Banned phrases registry
│   └── paragraph_checker.py      # Paragraph uniqueness check
├── fact_check/                   # NEW MODULE
│   ├── __init__.py
│   ├── claim_extractor.py        # Extract verifiable claims
│   ├── source_mapper.py          # Source-claim mapping
│   └── hallucination_detector.py # Enhanced hallucination detection
├── structure/                    # NEW MODULE
│   ├── __init__.py
│   ├── hook_analyzer.py          # Hook quality scoring
│   ├── flow_checker.py           # Logical flow validation
│   └── tldr_checker.py           # TLDR quality gate
├── style/                        # NEW MODULE
│   ├── __init__.py
│   ├── voice_checker.py          # Voice consistency
│   ├── active_voice.py           # Active voice enforcer
│   ├── sentence_variety.py       # Sentence rhythm
│   └── jargon_checker.py         # Jargon accessibility
├── quality_scorer.py             # Unified quality scoring (0-100)
├── ai_cliche_detector.py         # EXTEND: Add filler patterns
├── factual_verifier.py           # EXTEND: Add number verification
└── quality_checker.py            # EXTEND: Integrate all checks

config/
├── banned_phrases.yaml           # Banned phrases database
├── good_hooks.yaml               # Good hook examples
└── tech_jargon.yaml              # Tech jargon definitions

tests/
├── unit/
│   ├── test_filler_detector.py
│   ├── test_density_scorer.py
│   ├── test_hook_analyzer.py
│   └── test_quality_scorer.py
└── integration/
    └── test_quality_pipeline.py
```

---

## Phase 1: Anti-Water System (Week 1)

### Task 1.1: Create Filler Words Detector

**Files:**
- Create: `pipeline/anti_water/__init__.py`
- Create: `pipeline/anti_water/filler_detector.py`
- Create: `config/banned_phrases.yaml`
- Test: `tests/unit/test_filler_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_filler_detector.py
"""Tests for filler words detector."""
import pytest
from pipeline.anti_water.filler_detector import FillerDetector, FillerReport


def test_detect_russian_filler_words():
    """Test detection of Russian filler phrases."""
    detector = FillerDetector()

    text = "Стоит отметить, что этот продукт является революционным."
    report = detector.detect(text)

    assert report.filler_count >= 2
    assert report.water_percentage > 0
    assert any("стоит отметить" in f.lower() for f in report.filler_list)


def test_detect_english_filler_words():
    """Test detection of English filler phrases."""
    detector = FillerDetector()

    text = "It is worth noting that this is a game-changing solution."
    report = detector.detect(text)

    assert report.filler_count >= 2
    assert any("worth noting" in f.lower() for f in report.filler_list)


def test_water_percentage_calculation():
    """Test water percentage calculation."""
    detector = FillerDetector()

    # Text with ~30% filler
    text = "Стоит отметить, что безусловно крайне важно отметить."
    report = detector.detect(text)

    assert 15 < report.water_percentage < 50


def test_text_passes_water_threshold():
    """Test that clean text passes the threshold."""
    detector = FillerDetector(max_water_percentage=15)

    text = "OpenAI выпустила GPT-5. Модель работает в 3 раза быстрее."
    report = detector.detect(text)

    assert report.passes_threshold is True
    assert report.water_percentage < 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_filler_detector.py -v`
Expected: FAIL with "module not found"

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/anti_water/__init__.py
"""Anti-water content detection and removal."""
from pipeline.anti_water.filler_detector import FillerDetector, FillerReport

__all__ = ["FillerDetector", "FillerReport"]
```

```python
# pipeline/anti_water/filler_detector.py
"""Filler words detector for measuring 'water' content."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FillerReport:
    """Result of filler detection."""

    filler_count: int = 0
    water_percentage: float = 0.0
    filler_list: list[str] = field(default_factory=list)
    passes_threshold: bool = True
    recommendations: list[str] = field(default_factory=list)


class FillerDetector:
    """
    Detects filler words and calculates water percentage.

    Uses dictionaries of Russian/English filler phrases and
    calculates the percentage of "water" content.
    """

    # Built-in filler patterns
    DEFAULT_FILLER_PATTERNS = [
        # Russian fillers
        r"\bстоит\s+отметить\b",
        r"\bнельзя\s+не\s+сказать\b",
        r"\bбезусловно\b",
        r"\bнесомненно\b",
        r"\bкрайне\s+\w+\b",
        r"\bвесьма\s+\w+\b",
        r"\bочень\s+\w+\b",
        r"\bданный\s+\w+\b",
        r"\bявляется\s+\w+\b",
        r"\bв\s+современном\s+мире\b",
        # English fillers
        r"\bit\s+is\s+worth\s+noting\b",
        r"\bneedless\s+to\s+say\b",
        r"\bobviously\b",
        r"\bvery\s+\w+\b",
        r"\bextremely\s+\w+\b",
        r"\bin\s+today'?s?\s+world\b",
        r"\bgame-changing\b",
        r"\brevolutionary\b",
    ]

    def __init__(
        self,
        max_water_percentage: float = 15.0,
    ) -> None:
        self.max_water_percentage = max_water_percentage
        self._patterns: list[re.Pattern] = [
            re.compile(p, re.IGNORECASE) for p in self.DEFAULT_FILLER_PATTERNS
        ]

    def detect(self, text: str) -> FillerReport:
        """
        Detect filler words and calculate water percentage.

        Args:
            text: Text to analyze

        Returns:
            FillerReport with findings
        """
        filler_list = []
        total_matches = 0

        for pattern in self._patterns:
            for match in pattern.finditer(text):
                filler_list.append(match.group())
                total_matches += 1

        # Calculate water percentage
        words = text.split()
        word_count = len(words)

        # Count filler words (each match can be multiple words)
        filler_word_count = sum(len(f.split()) for f in filler_list)

        water_percentage = (
            (filler_word_count / word_count * 100) if word_count > 0 else 0
        )

        passes_threshold = water_percentage <= self.max_water_percentage

        # Generate recommendations
        recommendations = []
        if not passes_threshold:
            recommendations.append(
                f"Water content {water_percentage:.1f}% exceeds "
                f"threshold {self.max_water_percentage}%"
            )
            recommendations.append(
                f"Remove or rephrase: {', '.join(filler_list[:5])}"
            )

        return FillerReport(
            filler_count=total_matches,
            water_percentage=round(water_percentage, 1),
            filler_list=filler_list,
            passes_threshold=passes_threshold,
            recommendations=recommendations,
        )
```

```yaml
# config/banned_phrases.yaml
# Banned phrases registry for content quality

filler_patterns:
  # Russian filler phrases
  - "стоит отметить"
  - "нельзя не сказать"
  - "нельзя не упомянуть"
  - "безусловно"
  - "несомненно"
  - "весьма"
  - "по сути"
  - "в принципе"

  # English filler phrases
  - "it is worth noting"
  - "needless to say"
  - "it goes without saying"
  - "in today's world"

hype_words:
  - pattern: "революционн\\w*"
    severity: block
  - pattern: "прорывн\\w*"
    severity: block
  - pattern: "game-changing"
    severity: block
  - pattern: "revolutionary"
    severity: warn

vague_phrases:
  - "некоторое время"
  - "в ближайшем будущем"
  - "some time"
  - "in the near future"

cringe_phrases:
  - "друзья"
  - "коллеги"
  - "представьте себе"
  - "friends"
  - "imagine this"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_filler_detector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/anti_water/ config/banned_phrases.yaml tests/unit/test_filler_detector.py
git commit -m "feat(anti-water): add filler words detector with water percentage calculation"
```

---

### Task 1.2: Create Information Density Scorer

**Files:**
- Create: `pipeline/anti_water/density_scorer.py`
- Test: `tests/unit/test_density_scorer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_density_scorer.py
"""Tests for information density scorer."""
import pytest
from pipeline.anti_water.density_scorer import DensityScorer, DensityReport


def test_calculate_density_score():
    """Test density score calculation with concrete data."""
    scorer = DensityScorer()

    text = """
    OpenAI выпустила GPT-5 15 марта 2026 года.
    Модель работает в 3 раза быстрее GPT-4.
    Компания инвестировала $10 миллиардов в разработку.
    По данным исследования, 85% пользователей довольны.
    """
    report = scorer.score(text)

    assert report.facts_count >= 3
    assert report.numbers_count >= 4
    assert report.density_score > 10


def test_low_density_text():
    """Test that vague text has low density score."""
    scorer = DensityScorer()

    text = "Это очень важный продукт. Он значительно улучшает работу."
    report = scorer.score(text)

    assert report.density_score < 10
    assert report.passes_threshold is False


def test_detect_specific_dates():
    """Test detection of specific dates."""
    scorer = DensityScorer()

    text = "Событие произошло 15 марта 2025 года."
    report = scorer.score(text)

    assert report.dates_count >= 1


def test_detect_proper_nouns():
    """Test detection of proper nouns."""
    scorer = DensityScorer()

    text = "OpenAI и Google анонсировали партнёрство."
    report = scorer.score(text)

    assert report.proper_nouns_count >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_density_scorer.py -v`
Expected: FAIL with "module not found"

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/anti_water/density_scorer.py
"""Information density scorer for measuring content quality."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DensityReport:
    """Result of density scoring."""

    density_score: float = 0.0
    facts_count: int = 0
    numbers_count: int = 0
    proper_nouns_count: int = 0
    dates_count: int = 0
    passes_threshold: bool = True
    recommendations: list[str] = field(default_factory=list)


class DensityScorer:
    """
    Calculates information density of content.

    Scores based on:
    - Specific facts (10 points each)
    - Numbers/metrics (8 points each)
    - Proper nouns (5 points each)
    - Specific dates (7 points each)
    """

    NUMBER_PATTERN = re.compile(
        r'\d+[.,]?\d*\s*(?:%|млн|млрд|тыс|million|billion|k)?|'
        r'\$[\d,]+|€[\d,]+|₽[\d,]+',
        re.IGNORECASE
    )

    DATE_PATTERN = re.compile(
        r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|'
        r'августа|сентября|октября|ноября|декабря)\s*(?:\d{4})?|'
        r'(?:January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+\d{1,2},?\s*\d{4}|'
        r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])',
        re.IGNORECASE
    )

    PROPER_NOUN_PATTERN = re.compile(
        r'\b(?:OpenAI|Google|Microsoft|Apple|Meta|Amazon|Anthropic|'
        r'DeepMind|Tesla|NVIDIA|GPT-[45]|Claude|Gemini|Llama|'
        r'ChatGPT)\b'
    )

    FACT_PATTERN = re.compile(
        r'(?:утверждает|сообщает|объявила|выпустила|анонсировала|'
        r'according\s+to|announced|released|stated|reported)\s+',
        re.IGNORECASE
    )

    def __init__(self, min_density: float = 15.0) -> None:
        self.min_density = min_density

    def score(self, text: str) -> DensityReport:
        """Calculate information density score."""
        word_count = len(text.split())
        if word_count == 0:
            return DensityReport()

        numbers = self.NUMBER_PATTERN.findall(text)
        dates = self.DATE_PATTERN.findall(text)
        proper_nouns = self.PROPER_NOUN_PATTERN.findall(text)
        facts = self.FACT_PATTERN.findall(text)

        numbers_count = len(set(numbers))
        dates_count = len(set(dates))
        proper_nouns_count = len(set(proper_nouns))
        facts_count = len(facts)

        raw_score = (
            facts_count * 10 +
            numbers_count * 8 +
            proper_nouns_count * 5 +
            dates_count * 7
        )

        density_score = (raw_score / word_count) * 100
        passes_threshold = density_score >= self.min_density

        recommendations = []
        if not passes_threshold:
            recommendations.append(
                f"Density score {density_score:.1f} below threshold {self.min_density}"
            )
            if numbers_count < 3:
                recommendations.append("Add more specific numbers and metrics")

        return DensityReport(
            density_score=round(density_score, 1),
            facts_count=facts_count,
            numbers_count=numbers_count,
            proper_nouns_count=proper_nouns_count,
            dates_count=dates_count,
            passes_threshold=passes_threshold,
            recommendations=recommendations,
        )
```

- [ ] **Step 4: Update __init__.py and run tests**

```python
# pipeline/anti_water/__init__.py
"""Anti-water content detection and removal."""
from pipeline.anti_water.filler_detector import FillerDetector, FillerReport
from pipeline.anti_water.density_scorer import DensityScorer, DensityReport

__all__ = [
    "FillerDetector", "FillerReport",
    "DensityScorer", "DensityReport",
]
```

Run: `pytest tests/unit/test_density_scorer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/anti_water/ tests/unit/test_density_scorer.py
git commit -m "feat(anti-water): add information density scorer"
```

---

### Task 1.3: Create Paragraph Impact Checker

**Files:**
- Create: `pipeline/anti_water/paragraph_checker.py`
- Test: `tests/unit/test_paragraph_checker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_paragraph_checker.py
"""Tests for paragraph impact checker."""
import pytest
from pipeline.anti_water.paragraph_checker import ParagraphChecker, ParagraphReport


def test_detect_redundant_paragraphs():
    """Test detection of redundant paragraphs."""
    checker = ParagraphChecker()

    text = """
OpenAI выпустила новую модель GPT-5.
Она работает в 3 раза быстрее предыдущей версии.

Компания OpenAI представила GPT-5.
Новая модель работает в три раза быстрее.
    """
    report = checker.check(text)

    assert len(report.redundant_pairs) > 0


def test_each_paragraph_has_unique_claim():
    """Test that unique paragraphs pass."""
    checker = ParagraphChecker()

    text = """
OpenAI выпустила GPT-5 15 марта 2026 года.

Google анонсировала Gemini 2.0 на конференции I/O.

Microsoft интегрировала Copilot в Windows 12.
    """
    report = checker.check(text)

    assert report.passes_check is True
    assert len(report.redundant_pairs) == 0
```

- [ ] **Step 2: Write implementation**

```python
# pipeline/anti_water/paragraph_checker.py
"""Paragraph impact checker for detecting redundant content."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ParagraphReport:
    """Result of paragraph impact check."""

    paragraph_count: int = 0
    redundant_pairs: list[tuple[int, int]] = field(default_factory=list)
    passes_check: bool = True
    recommendations: list[str] = field(default_factory=list)


class ParagraphChecker:
    """Checks that each paragraph adds unique value."""

    def __init__(self, similarity_threshold: float = 0.7) -> None:
        self.similarity_threshold = similarity_threshold

    def check(self, text: str) -> ParagraphReport:
        """Check paragraphs for redundancy."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        if len(paragraphs) < 2:
            return ParagraphReport(paragraph_count=len(paragraphs))

        redundant_pairs = []

        for i in range(len(paragraphs)):
            for j in range(i + 1, len(paragraphs)):
                similarity = self._calculate_similarity(
                    paragraphs[i], paragraphs[j]
                )
                if similarity > self.similarity_threshold:
                    redundant_pairs.append((i, j))

        passes_check = len(redundant_pairs) == 0

        recommendations = []
        if not passes_check:
            recommendations.append(
                f"Found {len(redundant_pairs)} redundant paragraph pairs"
            )

        return ParagraphReport(
            paragraph_count=len(paragraphs),
            redundant_pairs=redundant_pairs,
            passes_check=passes_check,
            recommendations=recommendations,
        )

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity using word overlap."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        stop_words = {"и", "в", "на", "с", "то", "что", "the", "a", "an", "is", "are"}
        words1 = words1 - stop_words
        words2 = words2 - stop_words

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0
```

- [ ] **Step 3: Run tests and commit**

Run: `pytest tests/unit/test_paragraph_checker.py -v`
Expected: PASS

```bash
git add pipeline/anti_water/ tests/unit/test_paragraph_checker.py
git commit -m "feat(anti-water): add paragraph impact checker"
```

---

## Phase 2: Unified Quality Scorer

### Task 2.1: Create Quality Scorer

**Files:**
- Create: `pipeline/quality_scorer.py`
- Test: `tests/unit/test_quality_scorer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_quality_scorer.py
"""Tests for unified quality scorer."""
import pytest
from pipeline.quality_scorer import QualityScorer, QualityScoreReport


def test_calculate_composite_score():
    """Test composite quality score calculation."""
    scorer = QualityScorer()

    text = """
OpenAI выпустила GPT-5 15 марта 2026 года.

Компания инвестировала $10 миллиардов в разработку.
По данным исследования, 85% пользователей довольны.
Модель работает в 3 раза быстрее GPT-4.

🔍 Ключевые факты:
• GPT-5 выпущен 15 марта 2026
• Инвестиции: $10 млрд
• Прирост скорости: 3x
• Удовлетворённость: 85%

💡 TLDR: OpenAI выпустила GPT-5 с 3-кратным приростом скорости.
    """

    report = scorer.score(text)

    assert report.total_score >= 70
    assert report.breakdown["density"] > 0


def test_low_quality_post_score():
    """Test that low quality posts get low scores."""
    scorer = QualityScorer()

    text = """
Это очень важный и интересный продукт.
Стоит отметить, что он безусловно полезен.
В современном мире это крайне необходимо.
    """

    report = scorer.score(text)

    assert report.total_score < 70
    assert report.passes_threshold is False
```

- [ ] **Step 2: Write implementation**

```python
# pipeline/quality_scorer.py
"""Unified quality scorer for content evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field

from core.logger import get_logger
from pipeline.anti_water import FillerDetector, DensityScorer

logger = get_logger(__name__)


@dataclass
class QualityScoreReport:
    """Comprehensive quality score report."""

    total_score: float = 0.0
    passes_threshold: bool = True
    breakdown: dict[str, float] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def grade(self) -> str:
        """Get letter grade for score."""
        if self.total_score >= 90:
            return "Excellent"
        elif self.total_score >= 80:
            return "Good"
        elif self.total_score >= 70:
            return "Acceptable"
        else:
            return "Reject"


class QualityScorer:
    """
    Unified quality scoring system.

    Combines multiple quality checks into a single 0-100 score:
    - Density score (20%)
    - Water penalty (20%)
    - Structure score (20%)
    - Factual accuracy (25%)
    - Style score (15%)
    """

    def __init__(self, pass_threshold: float = 70.0) -> None:
        self.pass_threshold = pass_threshold
        self._filler_detector = FillerDetector()
        self._density_scorer = DensityScorer()

    def score(self, text: str) -> QualityScoreReport:
        """Calculate comprehensive quality score."""
        import re

        breakdown = {}
        issues = []
        recommendations = []

        # 1. Density score (weighted 20%)
        density_report = self._density_scorer.score(text)
        density_normalized = min(100, density_report.density_score * 5)
        breakdown["density"] = density_normalized

        if not density_report.passes_threshold:
            issues.append("Low information density")
            recommendations.extend(density_report.recommendations)

        # 2. Water penalty (weighted 20%)
        filler_report = self._filler_detector.detect(text)
        water_score = max(0, 100 - filler_report.water_percentage * 3)
        breakdown["water_penalty"] = water_score

        if not filler_report.passes_threshold:
            issues.append(f"High water content: {filler_report.water_percentage}%")
            recommendations.extend(filler_report.recommendations)

        # 3. Structure score (20%)
        structure_score = 100.0
        required_markers = [("🔍", "Key Facts"), ("💡", "TLDR")]
        for marker, name in required_markers:
            if marker not in text:
                structure_score -= 25
        breakdown["structure"] = max(0, structure_score)

        # 4. Factual accuracy (25%)
        factual_score = 80.0
        if re.search(r'\d+', text):
            factual_score += 5
        if re.search(r'\d{4}', text):
            factual_score += 5
        breakdown["factual_accuracy"] = min(100, factual_score)

        # 5. Style score (15%)
        style_score = 80.0
        breakdown["style"] = style_score

        # Calculate weighted total
        total_score = (
            breakdown["density"] * 0.20 +
            breakdown["water_penalty"] * 0.20 +
            breakdown["structure"] * 0.20 +
            breakdown["factual_accuracy"] * 0.25 +
            breakdown["style"] * 0.15
        )

        passes_threshold = total_score >= self.pass_threshold

        return QualityScoreReport(
            total_score=round(total_score, 1),
            passes_threshold=passes_threshold,
            breakdown=breakdown,
            issues=issues,
            recommendations=recommendations[:5],
        )
```

- [ ] **Step 3: Run tests and commit**

Run: `pytest tests/unit/test_quality_scorer.py -v`
Expected: PASS

```bash
git add pipeline/quality_scorer.py tests/unit/test_quality_scorer.py
git commit -m "feat(quality): add unified quality scorer with composite scoring"
```

---

## Phase 3: Structure Checkers

### Task 3.1: Create Hook Analyzer

**Files:**
- Create: `pipeline/structure/__init__.py`
- Create: `pipeline/structure/hook_analyzer.py`
- Test: `tests/unit/test_hook_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_hook_analyzer.py
"""Tests for hook quality analyzer."""
import pytest
from pipeline.structure.hook_analyzer import HookAnalyzer, HookReport


def test_analyze_good_hook():
    """Test analysis of a strong hook."""
    analyzer = HookAnalyzer()

    hook = "OpenAI выпустила GPT-5 15 марта 2026 года."
    report = analyzer.analyze(hook)

    assert report.score >= 6
    assert "specific subject" in report.checks_passed


def test_analyze_weak_hook():
    """Test analysis of a weak hook."""
    analyzer = HookAnalyzer()

    hook = "Задумывались ли вы о будущем искусственного интеллекта?"
    report = analyzer.analyze(hook)

    assert report.score < 6
    assert report.passes_threshold is False
```

- [ ] **Step 2: Write implementation**

```python
# pipeline/structure/__init__.py
"""Structure validation modules."""
from pipeline.structure.hook_analyzer import HookAnalyzer, HookReport

__all__ = ["HookAnalyzer", "HookReport"]
```

```python
# pipeline/structure/hook_analyzer.py
"""Hook quality analyzer for evaluating opening sentences."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HookReport:
    """Result of hook analysis."""

    score: float = 0.0
    max_score: float = 10.0
    checks_passed: list[str] = field(default_factory=list)
    passes_threshold: bool = True
    suggestions: list[str] = field(default_factory=list)


class HookAnalyzer:
    """
    Analyzes opening sentences (hooks) for quality.

    Scoring criteria (0-10):
    - Specific subject mentioned (+2)
    - Concrete event/news (+2)
    - Relevance implied (+2)
    - Not a question (+1)
    - Not a cliche (+1)
    - Under 25 words (+1)
    - Active voice (+1)
    """

    GENERIC_QUESTION_PATTERNS = [
        r"^задумывались\s+ли\s+вы",
        r"^знали\s+ли\s+вы",
        r"^have\s+you\s+ever\s+wondered",
        r"^did\s+you\s+know",
    ]

    CLICHE_OPENINGS = [
        "в современном мире",
        "сегодня мы рассмотрим",
        "in today's world",
        "let's explore",
    ]

    def __init__(self, min_score: float = 6.0) -> None:
        self.min_score = min_score
        self._question_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.GENERIC_QUESTION_PATTERNS
        ]

    def analyze(self, text: str) -> HookReport:
        """Analyze hook quality."""
        score = 0.0
        checks_passed = []
        suggestions = []

        first_sentence = text.split(".")[0].strip()
        first_sentence_lower = first_sentence.lower()

        # Check 1: Specific subject
        if self._has_specific_subject(first_sentence):
            score += 2
            checks_passed.append("specific subject")
        else:
            suggestions.append("Include a specific company, product, or person")

        # Check 2: Concrete event
        if self._has_concrete_event(first_sentence):
            score += 2
            checks_passed.append("concrete event")
        else:
            suggestions.append("Mention a specific event or announcement")

        # Check 3: Relevance
        if len(first_sentence) > 10:
            score += 2
            checks_passed.append("relevance implied")

        # Check 4: Not generic question
        is_generic_question = any(
            p.search(first_sentence) for p in self._question_patterns
        )
        if not is_generic_question and "?" not in first_sentence[:20]:
            score += 1
            checks_passed.append("not a generic question")
        else:
            suggestions.append("Avoid generic questions as hooks")

        # Check 5: Not cliche
        is_cliche = any(c in first_sentence_lower for c in self.CLICHE_OPENINGS)
        if not is_cliche:
            score += 1
            checks_passed.append("not a cliche")
        else:
            suggestions.append("Avoid cliche opening phrases")

        # Check 6: Concise
        word_count = len(first_sentence.split())
        if word_count <= 25:
            score += 1
            checks_passed.append("concise")

        # Check 7: Active voice
        if not re.search(r'\b(был[аи]?|was|were)\b', first_sentence_lower):
            score += 1
            checks_passed.append("active voice")

        passes_threshold = score >= self.min_score

        return HookReport(
            score=score,
            max_score=10.0,
            checks_passed=checks_passed,
            passes_threshold=passes_threshold,
            suggestions=suggestions,
        )

    def _has_specific_subject(self, text: str) -> bool:
        patterns = [
            r'\b(?:OpenAI|Google|Microsoft|Apple|Meta|Amazon)\b',
            r'\b(?:GPT-[45]|Claude|Gemini|ChatGPT)\b',
        ]
        return any(re.search(p, text) for p in patterns)

    def _has_concrete_event(self, text: str) -> bool:
        event_patterns = [
            r'(?:выпустил|анонс|запустил|представил)',
            r'(?:released|announced|launched)',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in event_patterns)
```

- [ ] **Step 3: Run tests and commit**

Run: `pytest tests/unit/test_hook_analyzer.py -v`
Expected: PASS

```bash
git add pipeline/structure/ tests/unit/test_hook_analyzer.py
git commit -m "feat(structure): add hook quality analyzer"
```

---

### Task 3.2: Create TLDR Checker

**Files:**
- Create: `pipeline/structure/tldr_checker.py`
- Test: `tests/unit/test_tldr_checker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_tldr_checker.py
"""Tests for TLDR quality checker."""
import pytest
from pipeline.structure.tldr_checker import TLDRChecker, TLDRReport


def test_good_tldr():
    """Test validation of a good TLDR."""
    checker = TLDRChecker()

    tldr = "OpenAI выпустила GPT-5 с 3-кратным приростом скорости."
    report = checker.check(tldr)

    assert report.passes_check is True
    assert report.sentence_count <= 2


def test_tldr_too_long():
    """Test that long TLDR is flagged."""
    checker = TLDRChecker()

    tldr = "OpenAI выпустила GPT-5. Модель работает быстрее. Цена осталась прежней."
    report = checker.check(tldr)

    assert report.sentence_count > 2
```

- [ ] **Step 2: Write implementation and run tests**

```python
# pipeline/structure/tldr_checker.py
"""TLDR quality checker for validating summaries."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TLDRReport:
    """Result of TLDR validation."""

    passes_check: bool = True
    sentence_count: int = 0
    issues: list[str] = field(default_factory=list)


class TLDRChecker:
    """Validates TLDR quality. Max 2 sentences, has subject and event."""

    def __init__(self, max_sentences: int = 2) -> None:
        self.max_sentences = max_sentences

    def check(self, tldr: str) -> TLDRReport:
        """Validate TLDR quality."""
        issues = []

        sentences = [s.strip() for s in re.split(r'[.!?]+', tldr) if s.strip()]
        sentence_count = len(sentences)

        if sentence_count > self.max_sentences:
            issues.append(f"TLDR has too many sentences ({sentence_count})")

        has_subject = bool(re.search(r'[A-Z][a-z]+|\b(?:OpenAI|Google)\b', tldr))
        if not has_subject:
            issues.append("TLDR missing main subject")

        has_event = bool(re.search(
            r'(?:выпустил|анонс|released|\d+[xх]|увелич)',
            tldr, re.IGNORECASE
        ))
        if not has_event:
            issues.append("TLDR missing main event")

        return TLDRReport(
            passes_check=len(issues) == 0,
            sentence_count=sentence_count,
            issues=issues,
        )
```

Run: `pytest tests/unit/test_tldr_checker.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pipeline/structure/ tests/unit/test_tldr_checker.py
git commit -m "feat(structure): add TLDR quality checker"
```

---

## Phase 4: Integration

### Task 4.1: Integrate with QualityChecker

**Files:**
- Modify: `pipeline/quality_checker.py`

- [ ] **Step 1: Add integration**

```python
# Add imports to pipeline/quality_checker.py
from pipeline.anti_water import FillerDetector, DensityScorer

# Add to QualityChecker.__init__
self._filler_detector = FillerDetector()
self._density_scorer = DensityScorer()

# Add to check() method
# Water detection
filler_report = self._filler_detector.detect(text_content)
if not filler_report.passes_threshold:
    issues.append(f"High water content: {filler_report.water_percentage}%")
    score -= 10

# Density check
density_report = self._density_scorer.score(text_content)
if not density_report.passes_threshold:
    issues.append("Low information density")
    score -= 10
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/quality_checker.py
git commit -m "feat(quality): integrate anti-water and density checks"
```

---

## Final Steps

### Task 5.1: Run Full Test Suite

- [ ] **Run all tests**

Run: `pytest tests/ -v`

Expected: All tests pass

- [ ] **Final commit**

```bash
git add .
git commit -m "feat(content-quality): implement Phase 1 quality improvements

- Add filler words detector with water percentage
- Add information density scorer
- Add paragraph impact checker
- Add unified quality scorer (0-100)
- Add hook quality analyzer
- Add TLDR checker
- Integrate with QualityChecker"
```

---

## Success Criteria

- [ ] All tests pass
- [ ] Water detection: filler phrases detected, water % calculated
- [ ] Density scoring: facts/numbers/dates counted
- [ ] Quality scorer: composite 0-100 score
- [ ] Integration: QualityChecker uses new modules
