# Content Quality Improvements Design

**Date:** 2026-03-18
**Author:** Claude + User
**Status:** Draft
**Priority:** High

## Problem Statement

Current AI-generated posts suffer from:
- **"Water" content** - too much filler, low information density
- **Factual inaccuracies** - LLM hallucinations, unverified claims
- **Weak structure** - poor hooks, illogical flow
- **Inconsistent style** - tone shifts, passive voice, jargon without explanation

User wants **super high quality** posts with maximum information density and zero fluff.

## Proposed Solution

Hybrid approach combining:
- **Strict validation** (Approach 1) - multi-level quality gates
- **Specialized agents** (Approach 3 elements) - dedicated agents for critical tasks

## Architecture Overview

```
Source Collection
       ↓
[Researcher Agent] ← NEW: Extract & verify claims from sources
       ↓
Topic Selection
       ↓
[Writer] → Raw Post (JSON)
       ↓
[Conciseness Agent] ← NEW: Remove water, improve density
       ↓
[FactChecker Agent] ← NEW: Verify all claims
       ↓
[Content Validator] → Enhanced validation rules
       ↓
[Editor Agent] ← NEW: Style, tone, flow improvements
       ↓
[Quality Scorer] ← NEW: Unified 0-100 score
       ↓
[Publisher] → Telegram
       ↓
[Feedback Loop] ← NEW: Collect engagement metrics
```

---

## 20 Improvements Specification

### Section 1: Anti-Water System (5 improvements)

#### 1. Filler Words Detector

**Purpose:** Automatically detect and measure "water" content in posts.

**Implementation:**
- Create `pipeline/anti_water/filler_detector.py`
- Dictionary of 200+ Russian/English filler phrases:
  - "стоит отметить", "нельзя не сказать", "безусловно"
  - "it is worth noting", "needless to say", "obviously"
  - Excessive adverbs: "очень", "крайне", "весьма"
- Algorithm:
  1. Tokenize text
  2. Match against filler dictionary
  3. Calculate `water_percentage = (filler_words / total_words) * 100`
  4. If >15%: reject with specific filler list

**Integration Point:** After `LLMGenerator`, before `ContentValidator`

**Metrics:**
- `water_percentage`: float 0-100
- `filler_count`: int
- `filler_list`: list of detected phrases

---

#### 2. Information Density Score

**Purpose:** Ensure posts contain sufficient concrete information.

**Implementation:**
- Create `pipeline/anti_water/density_scorer.py`
- Score calculation:
  ```
  density_score = (
      facts_count * 10 +
      numbers_count * 8 +
      proper_nouns_count * 5 +
      specific_dates_count * 7
  ) / word_count * 100
  ```
- Minimum requirements:
  - 3+ specific facts/numbers per post
  - density_score >= 15

**Detection Rules:**
- Numbers: regex `\d+[.,]?\d*%?`
- Dates: date parser
- Proper nouns: NER or capitalization heuristics
- Facts: sentences with "утверждает", "сообщает", "according to"

---

#### 3. Conciseness Rewriter Agent

**Purpose:** Automatically remove redundancy and improve information density.

**Implementation:**
- Create `pipeline/agents/conciseness_agent.py`
- Prompt template: `llm/prompts/conciseness_rewriter.txt`
- Tasks:
  1. Remove repeated ideas across paragraphs
  2. Merge related sentences
  3. Convert passive to active voice
  4. Eliminate redundant adjectives/adverbs

**Agent Config:**
```python
ConcisenessAgent(
    model="gpt-4o-mini",  # Fast, cheap
    max_reduction=0.3,    # Max 30% length reduction
    preserve_key_facts=True,
)
```

---

#### 4. Banned Phrases Registry

**Purpose:** Block overused cliches and hype language.

**Implementation:**
- Create `pipeline/anti_water/banned_phrases.py`
- YAML database: `config/banned_phrases.yaml`
- Categories:
  - `hype`: "революционный", "прорывной", "game-changing"
  - `filler`: "стоит отметить", "нельзя не упомянуть"
  - `vague`: "некоторое время", "в ближайшем будущем"
  - `cringe`: "друзья", "коллеги", "представьте себе"

**Detection:**
- Case-insensitive matching
- Partial matches (e.g., "революци*" catches all forms)
- Severity levels: `block` vs `warn`

---

#### 5. Paragraph Impact Check

**Purpose:** Ensure each paragraph adds unique value.

**Implementation:**
- Create `pipeline/anti_water/paragraph_checker.py`
- Algorithm:
  1. Extract all paragraphs
  2. For each paragraph, extract key claims
  3. Compare claims between paragraphs
  4. If similarity > 0.7: flag as redundant

**Requirements:**
- Each paragraph must have >= 1 unique claim
- No two paragraphs can share > 50% of claims
- Minimum unique information per paragraph

---

### Section 2: Factual Accuracy (4 improvements)

#### 6. Claim Extraction System

**Purpose:** Identify all factual claims for verification.

**Implementation:**
- Create `pipeline/fact_check/claim_extractor.py`
- Extract claims using patterns:
  - Declarative sentences with facts
  - Sentences with numbers/dates/names
  - "X сказал Y", "according to X", "X announced"
- Output: `List[Claim]` with:
  - `text`: the claim text
  - `type`: fact|quote|statistic|prediction
  - `confidence`: extraction confidence
  - `source_required`: bool

---

#### 7. Number Verifier Agent

**Purpose:** Verify all numbers, dates, and proper nouns.

**Implementation:**
- Create `pipeline/agents/number_verifier_agent.py`
- Process:
  1. Extract all numbers/dates/names
  2. Cross-reference with source articles
  3. Web search for unverifiable claims
  4. Mark unverifiable with `[требует подтверждения]`

**Config:**
```python
NumberVerifierAgent(
    sources=source_articles,
    web_search_enabled=True,
    confidence_threshold=0.8,
)
```

---

#### 8. Source-Claim Mapping

**Purpose:** Ensure every claim is traceable to a source.

**Implementation:**
- Create `pipeline/fact_check/source_mapper.py`
- Data structure:
  ```python
  @dataclass
  class ClaimSource:
      claim_text: str
      source_url: str
      source_quote: str  # Exact quote from source
      confidence: float
  ```
- Validation: All claims with `source_required=True` must have mapping
- Output: Footnotes for post

---

#### 9. Hallucination Detector

**Purpose:** Catch common LLM hallucination patterns.

**Implementation:**
- Create `pipeline/fact_check/hallucination_detector.py`
- Detection rules:
  - Made-up company names (check against Crunchbase API)
  - Non-existent products (web search verification)
  - Fake quotes (no source attribution)
  - Impossible statistics (sanity checks)
  - Future dates presented as past events

**Heuristics:**
- Confidence score based on multiple signals
- Auto-reject if hallucination_score > 0.7

---

### Section 3: Structure & Readability (4 improvements)

#### 10. Hook Quality Analyzer

**Purpose:** Ensure opening sentences grab attention.

**Implementation:**
- Create `pipeline/structure/hook_analyzer.py`
- Scoring criteria (0-10):
  - Specific subject mentioned (+2)
  - Concrete event/news (+2)
  - Relevance implied (+2)
  - Not a question (+1)
  - Not a cliche (+1)
  - Under 25 words (+1)
  - Active voice (+1)
- Minimum score: 6/10
- Examples database: `config/good_hooks.yaml`

---

#### 11. Logical Flow Checker

**Purpose:** Ensure coherent narrative between sections.

**Implementation:**
- Create `pipeline/structure/flow_checker.py`
- Check transitions:
  - Title → Hook: relevance
  - Hook → Body: logical connection
  - Body → Key Facts: facts support body
  - Key Facts → Analysis: facts lead to analysis
  - Analysis → TLDR: summary accuracy
- Score each transition 0-10
- Minimum average: 7/10

---

#### 12. Key Facts Formatting

**Purpose:** Ensure key facts are properly structured.

**Implementation:**
- Enhance `ContentValidator` with `validate_key_facts()`
- Rules:
  - Exactly 4-5 key facts
  - Each fact: single sentence, single idea
  - No compound facts ("X and Y happened")
  - Each fact independently verifiable
  - No overlapping facts

---

#### 13. TLDR Quality Gate

**Purpose:** Ensure TLDR is useful and self-contained.

**Implementation:**
- Create `pipeline/structure/tldr_checker.py`
- Validation:
  - Maximum 2 sentences
  - Contains main subject
  - Contains main event/outcome
  - Meaningful without reading full post
  - No "this post discusses" meta-language

---

### Section 4: Style & Tone (4 improvements)

#### 14. Voice Consistency Checker

**Purpose:** Maintain consistent editorial voice.

**Implementation:**
- Create `pipeline/style/voice_checker.py`
- Target voice profile:
  - Analytical (not promotional)
  - Professional (not casual)
  - Direct (not meandering)
  - Specific (not vague)
- Check for tone shifts within post
- Compare against style guide examples

---

#### 15. Active Voice Enforcer

**Purpose:** Increase sentence impact with active voice.

**Implementation:**
- Create `pipeline/style/active_voice.py`
- Detection: Passive voice patterns
  - "был сделан", "было объявлено"
  - "was done", "has been announced"
- Target: 70%+ active voice
- Auto-suggestions for rewriting

---

#### 16. Sentence Variety Analyzer

**Purpose:** Improve text rhythm and readability.

**Implementation:**
- Create `pipeline/style/sentence_variety.py`
- Metrics:
  - Length distribution (short/medium/long)
  - No 3+ consecutive sentences of same length
  - Variety score based on standard deviation
- Target: Variety score >= 0.5

---

#### 17. Jargon Accessibility Check

**Purpose:** Make technical content accessible.

**Implementation:**
- Create `pipeline/style/jargon_checker.py`
- Jargon dictionary: `config/tech_jargon.yaml`
- Rule: Every jargon term must have:
  - Definition in same/next sentence
  - Or link to explanation
  - Or be in "common knowledge" list
- Auto-flag unexplained jargon

---

### Section 5: Meta-Processes (3 improvements)

#### 18. Quality Scoring Dashboard

**Purpose:** Unified quality metric for all posts.

**Implementation:**
- Create `pipeline/quality_scorer.py`
- Composite score (0-100):
  ```
  total_score = (
      density_score * 0.20 +
      factual_accuracy * 0.25 +
      structure_score * 0.20 +
      style_score * 0.15 +
      water_penalty * 0.20
  )
  ```
- Visualization: Breakdown by category
- Thresholds:
  - 90+: Excellent
  - 80-89: Good
  - 70-79: Acceptable
  - <70: Reject

---

#### 19. Feedback Loop Integration

**Purpose:** Learn from audience engagement.

**Implementation:**
- Create `pipeline/feedback/collector.py`
- Collect from Telegram:
  - Views
  - Reactions (emoji counts)
  - Forwards
  - Link clicks (if tracked)
- Store in database: `post_analytics` table
- Weekly analysis: Correlate quality scores with engagement
- Adjust thresholds based on data

---

#### 20. A/B Testing Framework

**Purpose:** Data-driven prompt optimization.

**Implementation:**
- Create `pipeline/ab_testing/` module
- Components:
  - `experiment_manager.py`: Define experiments
  - `variant_router.py`: Assign posts to variants
  - `result_analyzer.py`: Statistical comparison
- Testable elements:
  - Prompt variations
  - Temperature settings
  - Post structures
  - Tone variations
- Integration: Existing `ab_test_manager.py` enhancement

---

## File Structure

```
pipeline/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py
│   ├── conciseness_agent.py
│   ├── number_verifier_agent.py
│   └── editor_agent.py
├── anti_water/
│   ├── __init__.py
│   ├── filler_detector.py
│   ├── density_scorer.py
│   ├── banned_phrases.py
│   └── paragraph_checker.py
├── fact_check/
│   ├── __init__.py
│   ├── claim_extractor.py
│   ├── source_mapper.py
│   └── hallucination_detector.py
├── structure/
│   ├── __init__.py
│   ├── hook_analyzer.py
│   ├── flow_checker.py
│   └── tldr_checker.py
├── style/
│   ├── __init__.py
│   ├── voice_checker.py
│   ├── active_voice.py
│   ├── sentence_variety.py
│   └── jargon_checker.py
├── feedback/
│   ├── __init__.py
│   └── collector.py
├── ab_testing/
│   ├── __init__.py
│   └── result_analyzer.py
└── quality_scorer.py

config/
├── banned_phrases.yaml
├── good_hooks.yaml
└── tech_jargon.yaml

llm/prompts/
├── conciseness_rewriter.txt
├── number_verifier.txt
└── editor_agent.txt
```

## Implementation Priority

### Phase 1: Anti-Water (Week 1)
1. Filler Words Detector
2. Information Density Score
3. Banned Phrases Registry

### Phase 2: Factual Accuracy (Week 2)
4. Claim Extraction System
5. Number Verifier Agent
6. Hallucination Detector

### Phase 3: Structure & Style (Week 3)
7. Hook Quality Analyzer
8. Logical Flow Checker
9. Voice Consistency Checker
10. Active Voice Enforcer

### Phase 4: Agents & Meta (Week 4)
11. Conciseness Rewriter Agent
12. Quality Scoring Dashboard
13. Feedback Loop Integration

## Success Metrics

- Water percentage: <10% (current: ~25% estimated)
- Information density: >20 facts per 1000 words
- Factual accuracy: >95% verified claims
- Quality score average: >80/100
- Engagement increase: +30% in 30 days

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Over-filtering rejects good posts | Soft thresholds initially, A/B test |
| Slower pipeline | Parallel agent execution |
| High API costs | Use cheaper models for simple checks |
| False positives in hallucination detection | Human review queue |

## Next Steps

1. User reviews this spec
2. Create implementation plan via writing-plans skill
3. Begin Phase 1 implementation
