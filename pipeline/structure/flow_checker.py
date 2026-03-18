"""Flow checker for validating logical transitions between content sections."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TransitionScore:
    """Score for a single transition between sections."""

    transition: str
    score: float = 0.0
    max_score: int = 10
    description: str = ""
    issues: list[str] = field(default_factory=list)


@dataclass
class FlowReport:
    """Result of flow checking across all transitions."""

    transitions: dict[str, TransitionScore] = field(default_factory=dict)
    average_score: float = 0.0
    passes_threshold: bool = True
    recommendations: list[str] = field(default_factory=list)


class FlowChecker:
    """
    Checks logical flow and transitions between content sections.

    Evaluates transitions:
    - Title to Hook: relevance (0-10)
    - Hook to Body: facts support (0-10)
    - Body to Analysis: insights flow (0-10)
    - Key Facts to Analysis: leads to thoughts (0-10)
    - Body to TLDR: summary accuracy (0-10)

    Maximum 10 transitions in report.
    Average score >= 7 required to pass.
    """

    # Key terms patterns for subject detection
    SUBJECT_PATTERNS = [
        r"\b(?:OpenAI|Google|Microsoft|Apple|Meta|Amazon|Anthropic|Tesla|NVIDIA)\b",
        r"\b(?:GPT-[45]|Claude|Gemini|ChatGPT|Llama|Copilot)\b",
        r"\b(?:Яндекс|Yandex|Сбер|Sber|ВК|VK)\b",
    ]

    # Event/action patterns
    EVENT_PATTERNS = [
        r"(?:выпустил|анонс|запустил|представил|объяви)",
        r"(?:released|announced|launched|unveiled)",
    ]

    # Number/metric patterns
    METRIC_PATTERNS = [
        r"\d+[xх]\b",  # 3x speedup
        r"\d+\s*(?:раза?|раз)\b",  # 3 раза, 3 раз
        r"\d+%",  # 50% increase
        r"\$[\d,]+(?:\s*(?:млн|млрд|million|billion))?",
        r"\b\d{4}\b",  # Years like 2026
    ]

    def __init__(self, pass_threshold: float = 7.0) -> None:
        """Initialize flow checker.

        Args:
            pass_threshold: Minimum average score to pass (default: 7.0)
        """
        self.pass_threshold = pass_threshold
        self._subject_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SUBJECT_PATTERNS
        ]
        self._event_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.EVENT_PATTERNS
        ]
        self._metric_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.METRIC_PATTERNS
        ]

    def check(self, post: dict[str, Any]) -> FlowReport:
        """Check logical flow between all sections.

        Args:
            post: Dictionary with post sections (title, hook, body, analysis, tldr, key_facts)

        Returns:
            FlowReport with transition scores and overall assessment
        """
        transitions: dict[str, TransitionScore] = {}

        # 1. Title to Hook relevance
        if "title" in post or "hook" in post:
            transitions["title_to_hook"] = self._check_title_to_hook(
                post.get("title", ""),
                post.get("hook", "")
            )

        # 2. Hook to Body facts support
        if "hook" in post or "body" in post:
            transitions["hook_to_body"] = self._check_hook_to_body(
                post.get("hook", ""),
                post.get("body", "")
            )

        # 3. Body to Analysis insights
        if "body" in post or "analysis" in post:
            transitions["body_to_analysis"] = self._check_body_to_analysis(
                post.get("body", ""),
                post.get("analysis", "")
            )

        # 4. Key Facts to Analysis transition
        if "key_facts" in post or "analysis" in post:
            transitions["facts_to_analysis"] = self._check_facts_to_analysis(
                post.get("key_facts", []),
                post.get("analysis", "")
            )

        # 5. Body to TLDR summary accuracy
        if "body" in post or "tldr" in post:
            transitions["body_to_tldr"] = self._check_body_to_tldr(
                post.get("body", ""),
                post.get("tldr", "")
            )

        # Limit to max 10 transitions
        if len(transitions) > 10:
            transitions = dict(list(transitions.items())[:10])

        # Calculate average score
        if transitions:
            total_score = sum(t.score for t in transitions.values())
            average_score = total_score / len(transitions)
        else:
            average_score = 0.0

        passes_threshold = average_score >= self.pass_threshold

        # Generate recommendations
        recommendations = []
        for name, transition in transitions.items():
            if transition.score < 7:
                recommendations.append(
                    f"Improve {name}: {transition.description}"
                )

        return FlowReport(
            transitions=transitions,
            average_score=round(average_score, 1),
            passes_threshold=passes_threshold,
            recommendations=recommendations,
        )

    def _check_title_to_hook(self, title: str, hook: str) -> TransitionScore:
        """Check relevance between title and hook."""
        score = 0.0
        issues = []

        if not title or not hook:
            return TransitionScore(
                transition="title_to_hook",
                score=0.0,
                description="Missing title or hook",
                issues=["Title or hook is empty"]
            )

        title_lower = title.lower()
        hook_lower = hook.lower()

        # Check subject overlap
        title_subjects = self._extract_subjects(title)
        hook_subjects = self._extract_subjects(hook)

        if title_subjects and hook_subjects:
            overlap = title_subjects & hook_subjects
            if overlap:
                score += 4  # Strong subject match
            elif title_subjects or hook_subjects:
                score += 2  # Some subjects present
        elif title_subjects or hook_subjects:
            score += 1

        # Check event/action overlap
        title_events = self._extract_events(title)
        hook_events = self._extract_events(hook)

        if title_events or hook_events:
            score += 2

        # Check metric/number overlap
        title_metrics = self._extract_metrics(title)
        hook_metrics = self._extract_metrics(hook)

        if title_metrics and hook_metrics:
            overlap = title_metrics & hook_metrics
            if overlap:
                score += 2

        # Check word overlap (general relevance)
        title_words = set(re.findall(r'\b\w{3,}\b', title_lower))
        hook_words = set(re.findall(r'\b\w{3,}\b', hook_lower))

        stop_words = {"the", "and", "for", "with", "это", "который", "которая"}
        title_words -= stop_words
        hook_words -= stop_words

        if title_words and hook_words:
            word_overlap = len(title_words & hook_words) / min(len(title_words), len(hook_words))
            score += min(2, word_overlap * 4)

        if score < 7:
            issues.append("Title and hook should share more key terms")

        return TransitionScore(
            transition="title_to_hook",
            score=min(10, score),
            description=f"Relevance score: {min(10, score):.1f}/10",
            issues=issues
        )

    def _check_hook_to_body(self, hook: str, body: str) -> TransitionScore:
        """Check that hook claims are supported by body."""
        score = 0.0
        issues = []

        if not hook or not body:
            return TransitionScore(
                transition="hook_to_body",
                score=0.0,
                description="Missing hook or body",
                issues=["Hook or body is empty"]
            )

        hook_lower = hook.lower()
        body_lower = body.lower()

        # Check subject support
        hook_subjects = self._extract_subjects(hook)
        body_subjects = self._extract_subjects(body)

        if hook_subjects:
            if hook_subjects <= body_subjects:
                score += 4  # All hook subjects in body
            elif hook_subjects & body_subjects:
                score += 2  # Some overlap

        # Check event support
        hook_events = self._extract_events(hook)
        body_events = self._extract_events(body)

        if hook_events:
            if hook_events & body_events:
                score += 3

        # Check metric support
        hook_metrics = self._extract_metrics(hook)
        body_metrics = self._extract_metrics(body)

        if hook_metrics:
            if hook_metrics <= body_metrics:
                score += 3  # All metrics mentioned in body
            elif hook_metrics & body_metrics:
                score += 1

        if score < 7:
            issues.append("Hook claims should be supported by body content")

        return TransitionScore(
            transition="hook_to_body",
            score=min(10, score),
            description=f"Facts support score: {min(10, score):.1f}/10",
            issues=issues
        )

    def _check_body_to_analysis(self, body: str, analysis: str) -> TransitionScore:
        """Check that body content leads to analysis insights."""
        score = 0.0
        issues = []

        if not body or not analysis:
            return TransitionScore(
                transition="body_to_analysis",
                score=0.0,
                description="Missing body or analysis",
                issues=["Body or analysis is empty"]
            )

        body_lower = body.lower()
        analysis_lower = analysis.lower()

        # Check subject continuity
        body_subjects = self._extract_subjects(body)
        analysis_subjects = self._extract_subjects(analysis)

        if body_subjects and analysis_subjects:
            overlap = body_subjects & analysis_subjects
            if overlap:
                score += 3  # Subject continuity
        elif body_subjects or analysis_subjects:
            score += 1  # At least one has subject

        # Check that analysis references body metrics
        body_metrics = self._extract_metrics(body)
        analysis_metrics = self._extract_metrics(analysis)

        if body_metrics and analysis_metrics:
            score += 2
        elif body_metrics:
            # Body has metrics, analysis should reference them somehow
            score += 1

        # Check for insight/analytical indicators in analysis
        insight_patterns = [
            r"(?:это означает|значит|показывает|говорит о)",
            r"(?:this means|indicates|shows|suggests)",
            r"(?:вывод|итак|таким образом)",
            r"(?:важн|серьёзн|значительн)",  # importance/seriousness
            r"(?:important|significant|major)",
            r"(?:шаг|прорыв|улучшен)",  # step/breakthrough/improvement
        ]
        for pattern in insight_patterns:
            if re.search(pattern, analysis_lower):
                score += 2
                break

        # Check analysis length (should be substantial)
        analysis_words = len(analysis.split())
        if analysis_words >= 10:
            score += 2
        elif analysis_words >= 5:
            score += 1

        # Bonus for having proper structure
        if body_subjects and analysis_words >= 5:
            score += 1

        if score < 7:
            issues.append("Analysis should derive insights from body content")

        return TransitionScore(
            transition="body_to_analysis",
            score=min(10, score),
            description=f"Insight flow score: {min(10, score):.1f}/10",
            issues=issues
        )

    def _check_facts_to_analysis(self, key_facts: list, analysis: str) -> TransitionScore:
        """Check that key facts logically lead to analysis thoughts."""
        score = 0.0
        issues = []

        if not key_facts or not analysis:
            return TransitionScore(
                transition="facts_to_analysis",
                score=0.0,
                description="Missing key facts or analysis",
                issues=["Key facts or analysis is empty"]
            )

        analysis_lower = analysis.lower()

        # Handle key_facts as list or string
        if isinstance(key_facts, str):
            key_facts = [key_facts]

        facts_referenced = 0
        total_facts = len([f for f in key_facts if f])

        for fact in key_facts:
            if not fact:
                continue
            fact_str = str(fact).lower()

            # Check if fact content appears in analysis
            fact_words = set(re.findall(r'\b\w{3,}\b', fact_str))
            analysis_words = set(re.findall(r'\b\w{3,}\b', analysis_lower))

            stop_words = {"это", "который", "the", "and", "for", "при"}
            fact_words -= stop_words

            # Check word overlap
            overlap = fact_words & analysis_words
            if fact_words and len(overlap) >= 1:
                facts_referenced += 1
            else:
                # Also check if fact metrics appear in analysis
                fact_metrics = self._extract_metrics(fact_str)
                analysis_metrics = self._extract_metrics(analysis_lower)
                if fact_metrics and analysis_metrics and (fact_metrics & analysis_metrics):
                    facts_referenced += 1

        if total_facts > 0:
            reference_ratio = facts_referenced / total_facts
            score += min(6, reference_ratio * 8)  # Up to 6 points for referencing

        # Check for analytical language
        analytical_patterns = [
            r"(?:потому что|так как|поэтому)",
            r"(?:because|therefore|thus|hence)",
            r"(?:серьёзн|важн|значительн)",
            r"(?:significant|important|major)",
            r"(?:показывает|говорит|означает)",
            r"(?:шаг|прорыв|стратег)",
        ]
        for pattern in analytical_patterns:
            if re.search(pattern, analysis_lower):
                score += 2
                break

        # Bonus for having multiple facts referenced
        if facts_referenced >= 2:
            score += 2
        elif facts_referenced >= 1:
            score += 1

        if score < 7:
            issues.append("Analysis should reference key facts")

        return TransitionScore(
            transition="facts_to_analysis",
            score=min(10, score),
            description=f"Facts-to-thoughts score: {min(10, score):.1f}/10",
            issues=issues
        )

    def _check_body_to_tldr(self, body: str, tldr: str) -> TransitionScore:
        """Check TLDR summary accuracy against body content."""
        score = 0.0
        issues = []

        if not body or not tldr:
            return TransitionScore(
                transition="body_to_tldr",
                score=0.0,
                description="Missing body or TLDR",
                issues=["Body or TLDR is empty"]
            )

        body_lower = body.lower()
        tldr_lower = tldr.lower()

        # Check subject presence in TLDR
        body_subjects = self._extract_subjects(body)
        tldr_subjects = self._extract_subjects(tldr)

        if body_subjects and tldr_subjects:
            if body_subjects & tldr_subjects:
                score += 3

        # Check key metric presence
        body_metrics = self._extract_metrics(body)
        tldr_metrics = self._extract_metrics(tldr)

        if body_metrics:
            if tldr_metrics:
                if body_metrics & tldr_metrics:
                    score += 3  # Key metrics included
                else:
                    score += 1  # Some metrics
            else:
                issues.append("TLDR missing key metrics from body")

        # Check event presence
        body_events = self._extract_events(body)
        tldr_events = self._extract_events(tldr)

        if body_events and tldr_events:
            score += 2

        # Check TLDR length (should be concise)
        tldr_sentences = len(re.split(r'[.!?]+', tldr))
        if tldr_sentences <= 2:
            score += 2
        elif tldr_sentences <= 3:
            score += 1
        else:
            issues.append("TLDR should be 1-2 sentences")

        if score < 7:
            issues.append("TLDR should better summarize body content")

        return TransitionScore(
            transition="body_to_tldr",
            score=min(10, score),
            description=f"Summary accuracy score: {min(10, score):.1f}/10",
            issues=issues
        )

    def _extract_subjects(self, text: str) -> set:
        """Extract subject entities from text."""
        subjects = set()
        for pattern in self._subject_patterns:
            matches = pattern.findall(text)
            subjects.update(m.lower() for m in matches)
        return subjects

    def _extract_events(self, text: str) -> set:
        """Extract event/action terms from text."""
        events = set()
        for pattern in self._event_patterns:
            matches = pattern.findall(text)
            events.update(m.lower() for m in matches)
        return events

    def _extract_metrics(self, text: str) -> set:
        """Extract metrics/numbers from text."""
        metrics = set()
        for pattern in self._metric_patterns:
            matches = pattern.findall(text)
            metrics.update(m.lower() for m in matches)
        return metrics
