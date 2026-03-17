"""
Agent Critic - LLM-based post review and improvement.

Reviews generated posts, scores them on multiple dimensions,
and rewrites if quality thresholds are not met.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger

from llm.base import BaseLLMAdapter


@dataclass
class CritiqueScores:
    """
    Scores for different aspects of a post.

    All scores are on a scale of 1-10.
    """
    hook_strength: int = 0
    clarity: int = 0
    emoji_naturalness: int = 0
    audience_value: int = 0
    human_feel: int = 0

    @property
    def average(self) -> float:
        """Calculate average score."""
        scores = [
            self.hook_strength,
            self.clarity,
            self.emoji_naturalness,
            self.audience_value,
            self.human_feel,
        ]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def min_score(self) -> int:
        """Get minimum score across all dimensions."""
        scores = [
            self.hook_strength,
            self.clarity,
            self.emoji_naturalness,
            self.audience_value,
            self.human_feel,
        ]
        return min(scores) if scores else 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hook_strength": self.hook_strength,
            "clarity": self.clarity,
            "emoji_naturalness": self.emoji_naturalness,
            "audience_value": self.audience_value,
            "human_feel": self.human_feel,
            "average": round(self.average, 2),
            "min_score": self.min_score,
        }


@dataclass
class CritiqueResult:
    """
    Result of a critique operation.

    Attributes:
        scores: Scores for each dimension
        needs_rewrite: Whether the post needs improvement
        critique: Textual critique of the post
        improved_post: Improved version (if rewritten)
        original_post: Original post content
    """
    scores: CritiqueScores
    needs_rewrite: bool
    critique: str
    improved_post: Optional[str] = None
    original_post: str = ""

    @property
    def final_post(self) -> str:
        """Get the final post (improved or original)."""
        return self.improved_post if self.needs_rewrite and self.improved_post else self.original_post

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "scores": self.scores.to_dict(),
            "needs_rewrite": self.needs_rewrite,
            "critique": self.critique,
            "improved_post": self.improved_post,
            "original_post": self.original_post,
            "final_post": self.final_post,
        }


class AgentCritic:
    """
    LLM-based agent that reviews and improves post drafts.

    Evaluates posts on multiple dimensions and rewrites them
    if any score falls below the threshold.

    Example:
        critic = AgentCritic(llm_adapter, threshold=7)
        result = await critic.review_and_improve(draft_content)

        if result.needs_rewrite:
            print(f"Improved post: {result.improved_post}")
        else:
            print("Post passed review unchanged")
    """

    # Default critique prompt template
    DEFAULT_PROMPT = """You are a strict post editor reviewing a Telegram post draft.

Channel topic: {channel_topic}
Language: {language}

POST TO REVIEW:
---
{draft_post}
---

Score each dimension (1-10):
- hook_strength: Does the first sentence stop scrolling?
- clarity: Is every sentence necessary?
- emoji_naturalness: Do emojis enhance meaning (not just decorate)?
- audience_value: Would the target reader save or share this?
- human_feel: Does it sound like a real person, not AI?

Rules:
- If ALL scores >= {threshold}: return the original post unchanged
- If ANY score < {threshold}: rewrite the FULL post to fix all issues

Return JSON only:
{{
  "scores": {{
    "hook_strength": N,
    "clarity": N,
    "emoji_naturalness": N,
    "audience_value": N,
    "human_feel": N
  }},
  "needs_rewrite": true|false,
  "critique": "what was wrong (if rewriting)",
  "improved_post": "full improved post text or null"
}}"""

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        threshold: int = 7,
        max_cycles: int = 2,
        channel_topic: str = "",
        language: str = "ru",
        prompts_dir: Optional[Path] = None,
    ):
        """
        Initialize the agent critic.

        Args:
            llm_adapter: LLM adapter for text generation
            threshold: Minimum acceptable score (1-10)
            max_cycles: Maximum rewrite cycles
            channel_topic: Channel topic for context
            language: Content language
            prompts_dir: Directory containing custom prompts
        """
        self.llm = llm_adapter
        self.threshold = threshold
        self.max_cycles = max_cycles
        self.channel_topic = channel_topic
        self.language = language
        self.prompts_dir = prompts_dir or Path("llm/prompts")

        # Load custom prompt if available
        self._critic_prompt = self._load_prompt("agent_critic.txt")

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt from file."""
        prompt_path = self.prompts_dir / filename
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return self.DEFAULT_PROMPT

    async def review(
        self,
        draft_post: str,
    ) -> CritiqueResult:
        """
        Review a post draft without rewriting.

        Args:
            draft_post: Post content to review

        Returns:
            CritiqueResult: Review result with scores
        """
        return await self._perform_critique(draft_post, allow_rewrite=False)

    async def review_and_improve(
        self,
        draft_post: str,
    ) -> CritiqueResult:
        """
        Review a post and improve it if needed.

        Performs up to max_cycles rewrite iterations.

        Args:
            draft_post: Post content to review

        Returns:
            CritiqueResult: Final result with improved post if needed
        """
        current_post = draft_post
        cycle = 0

        while cycle < self.max_cycles:
            result = await self._perform_critique(current_post, allow_rewrite=True)

            # If no rewrite needed, we're done
            if not result.needs_rewrite:
                result.original_post = draft_post
                return result

            # If rewrite was performed but improved_post is empty, use original
            if not result.improved_post:
                result.needs_rewrite = False
                result.original_post = draft_post
                return result

            # Use improved post for next cycle
            current_post = result.improved_post
            cycle += 1

            logger.info(
                f"Rewrite cycle {cycle}/{self.max_cycles}, "
                f"avg score: {result.scores.average:.1f}"
            )

        # Return final result
        final_result = await self._perform_critique(current_post, allow_rewrite=False)
        final_result.original_post = draft_post
        final_result.improved_post = current_post if cycle > 0 else None
        final_result.needs_rewrite = cycle > 0

        return final_result

    async def _perform_critique(
        self,
        draft_post: str,
        allow_rewrite: bool = True,
    ) -> CritiqueResult:
        """
        Perform a single critique operation.

        Args:
            draft_post: Post content to critique
            allow_rewrite: Whether to request rewrites

        Returns:
            CritiqueResult: Critique result
        """
        # Build prompt
        prompt = self._critic_prompt.format(
            channel_topic=self.channel_topic,
            language=self.language,
            draft_post=draft_post,
            threshold=self.threshold,
        )

        try:
            # Get LLM response
            response = await self.llm.generate(prompt)

            # Parse JSON response
            result_data = self._parse_response(response.text)

            # Build scores
            scores = CritiqueScores(
                hook_strength=result_data.get("scores", {}).get("hook_strength", 0),
                clarity=result_data.get("scores", {}).get("clarity", 0),
                emoji_naturalness=result_data.get("scores", {}).get("emoji_naturalness", 0),
                audience_value=result_data.get("scores", {}).get("audience_value", 0),
                human_feel=result_data.get("scores", {}).get("human_feel", 0),
            )

            # Determine if rewrite needed
            needs_rewrite = result_data.get("needs_rewrite", False)
            if allow_rewrite and scores.min_score < self.threshold:
                needs_rewrite = True

            return CritiqueResult(
                scores=scores,
                needs_rewrite=needs_rewrite,
                critique=result_data.get("critique", ""),
                improved_post=result_data.get("improved_post"),
                original_post=draft_post,
            )

        except Exception as e:
            logger.error(f"Critique failed: {e}")

            # Return failed result
            return CritiqueResult(
                scores=CritiqueScores(),
                needs_rewrite=False,
                critique=f"Critique failed: {str(e)}",
                improved_post=None,
                original_post=draft_post,
            )

    def _parse_response(self, response: str) -> dict:
        """
        Parse JSON response from LLM.

        Args:
            response: Raw LLM response

        Returns:
            dict: Parsed JSON data
        """
        # Try to extract JSON from response
        response = response.strip()

        # Remove markdown code blocks if present
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()

        # Find JSON object
        start = response.find("{")
        end = response.rfind("}") + 1

        if start >= 0 and end > start:
            json_str = response[start:end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error: {e}")

        # Return empty result if parsing fails
        return {
            "scores": {},
            "needs_rewrite": False,
            "critique": "Failed to parse LLM response",
            "improved_post": None,
        }

    async def batch_review(
        self,
        posts: list[str],
    ) -> list[CritiqueResult]:
        """
        Review multiple posts.

        Args:
            posts: List of post contents

        Returns:
            list[CritiqueResult]: Review results for each post
        """
        results = []

        for i, post in enumerate(posts):
            logger.debug(f"Reviewing post {i + 1}/{len(posts)}")
            result = await self.review(post)
            results.append(result)

        return results

    async def get_best_post(
        self,
        posts: list[str],
    ) -> tuple[str, CritiqueResult]:
        """
        Select the best post from multiple options.

        Args:
            posts: List of post contents

        Returns:
            tuple[str, CritiqueResult]: Best post and its critique
        """
        if not posts:
            raise ValueError("No posts provided")

        results = await self.batch_review(posts)

        # Find post with highest average score
        best_idx = 0
        best_score = 0.0

        for i, result in enumerate(results):
            if result.scores.average > best_score:
                best_score = result.scores.average
                best_idx = i

        return posts[best_idx], results[best_idx]
