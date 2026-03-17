"""
Content filter for scoring and filtering collected articles.

Provides relevance scoring and quality filtering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.logger import get_logger
from pipeline.source_collector import Article

logger = get_logger(__name__)


@dataclass
class ScoredArticle:
    """
    Article with relevance score.

    Attributes:
        article: Original article
        score: Relevance score (0-100)
        score_reasons: Reasons for the score
    """

    article: Article
    score: float
    score_reasons: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "article": self.article.to_dict(),
            "score": self.score,
            "score_reasons": self.score_reasons,
        }


class ContentFilter:
    """
    Filters and scores articles for relevance and quality.

    Uses configurable criteria to rank articles.
    """

    def __init__(
        self,
        channel_topic: str,
        min_score: float = 30.0,
        min_title_length: int = 20,
        max_title_length: int = 200,
        min_summary_length: int = 50,
        prefer_recent: bool = True,
        recent_hours: int = 48,
    ) -> None:
        """
        Initialize content filter.

        Args:
            channel_topic: Channel topic for relevance scoring
            min_score: Minimum score threshold
            min_title_length: Minimum title length
            max_title_length: Maximum title length
            min_summary_length: Minimum summary length
            prefer_recent: Prefer more recent articles
            recent_hours: Hours to consider "recent"
        """
        self.channel_topic = channel_topic.lower()
        self.min_score = min_score
        self.min_title_length = min_title_length
        self.max_title_length = max_title_length
        self.min_summary_length = min_summary_length
        self.prefer_recent = prefer_recent
        self.recent_hours = recent_hours

        # Topic-related keywords for scoring
        self._topic_keywords = self._extract_keywords(channel_topic)

    def _extract_keywords(self, text: str) -> list[str]:
        """
        Extract keywords from text.

        Args:
            text: Input text

        Returns:
            list[str]: Extracted keywords
        """
        # Simple keyword extraction
        import re

        # Remove common words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "и", "в", "на", "с", "по", "к", "из", "за", "от", "до", "о", "об",
            "не", "но", "а", "или", "что", "как", "это", "для", "так",
        }

        words = re.findall(r"\b[a-zA-Zа-яА-Я]{3,}\b", text.lower())
        keywords = [w for w in words if w not in stop_words]

        return list(set(keywords))

    def _calculate_relevance_score(self, article: Article) -> tuple[float, list[str]]:
        """
        Calculate relevance score for an article.

        Args:
            article: Article to score

        Returns:
            tuple[float, list[str]]: Score and reasons
        """
        score = 50.0  # Base score
        reasons = []

        text = f"{article.title} {article.summary}".lower()

        # Keyword matching
        keyword_matches = sum(1 for kw in self._topic_keywords if kw in text)
        keyword_score = min(keyword_matches * 5, 30)  # Max 30 points

        if keyword_matches > 0:
            score += keyword_score
            reasons.append(f"+{keyword_score}: {keyword_matches} keyword matches")

        # Title quality
        title_len = len(article.title)
        if self.min_title_length <= title_len <= self.max_title_length:
            score += 5
            reasons.append("+5: Good title length")
        elif title_len < self.min_title_length:
            score -= 10
            reasons.append("-10: Title too short")

        # Summary quality
        if len(article.summary) >= self.min_summary_length:
            score += 5
            reasons.append("+5: Sufficient summary")
        else:
            score -= 5
            reasons.append("-5: Summary too short")

        # Recency bonus
        if self.prefer_recent and article.published_at:
            hours_ago = (datetime.utcnow() - article.published_at).total_seconds() / 3600

            if hours_ago <= self.recent_hours:
                recency_bonus = (self.recent_hours - hours_ago) / self.recent_hours * 15
                score += recency_bonus
                reasons.append(f"+{recency_bonus:.1f}: Recent article")

        # Has tags bonus
        if article.tags:
            score += min(len(article.tags) * 2, 10)
            reasons.append(f"+{min(len(article.tags) * 2, 10)}: Has tags")

        return score, reasons

    def _is_quality_article(self, article: Article) -> tuple[bool, str]:
        """
        Check if article meets quality standards.

        Args:
            article: Article to check

        Returns:
            tuple[bool, str]: (is_quality, reason)
        """
        # Title checks
        if len(article.title) < self.min_title_length:
            return False, "Title too short"

        if len(article.title) > self.max_title_length:
            return False, "Title too long"

        # URL check
        if not article.url:
            return False, "Missing URL"

        # Summary check
        if len(article.summary) < self.min_summary_length:
            return False, "Summary too short"

        # Spam indicators
        spam_words = ["sponsored", "advertisement", "продвижение", "реклама"]
        text = f"{article.title} {article.summary}".lower()
        for word in spam_words:
            if word in text:
                return False, f"Contains spam indicator: {word}"

        return True, "Passed quality check"

    def score_article(self, article: Article) -> ScoredArticle:
        """
        Score a single article.

        Args:
            article: Article to score

        Returns:
            ScoredArticle: Article with score
        """
        is_quality, quality_reason = self._is_quality_article(article)

        if not is_quality:
            return ScoredArticle(
                article=article,
                score=0.0,
                score_reasons=[f"Failed quality check: {quality_reason}"],
            )

        score, reasons = self._calculate_relevance_score(article)
        reasons.insert(0, quality_reason)

        return ScoredArticle(
            article=article,
            score=score,
            score_reasons=reasons,
        )

    def filter_and_score(
        self,
        articles: list[Article],
        top_n: Optional[int] = None,
    ) -> list[ScoredArticle]:
        """
        Filter and score articles.

        Args:
            articles: List of articles to process
            top_n: Return only top N articles

        Returns:
            list[ScoredArticle]: Scored articles above threshold
        """
        scored = []

        for article in articles:
            scored_article = self.score_article(article)

            if scored_article.score >= self.min_score:
                scored.append(scored_article)

        # Sort by score (highest first)
        scored.sort(key=lambda x: x.score, reverse=True)

        # Limit to top N
        if top_n:
            scored = scored[:top_n]

        logger.info(
            f"Content filter: {len(articles)} -> {len(scored)} articles "
            f"(min_score={self.min_score})"
        )

        return scored

    def get_top_articles(
        self,
        articles: list[Article],
        n: int = 5,
    ) -> list[Article]:
        """
        Get top N articles by score.

        Args:
            articles: List of articles
            n: Number of articles to return

        Returns:
            list[Article]: Top articles
        """
        scored = self.filter_and_score(articles, top_n=n)
        return [sa.article for sa in scored]

    def get_topics_from_articles(
        self,
        articles: list[Article],
        max_topics: int = 10,
    ) -> list[dict]:
        """
        Extract topic suggestions from articles.

        Args:
            articles: List of articles
            max_topics: Maximum topics to return

        Returns:
            list[dict]: Topic suggestions with metadata
        """
        scored = self.filter_and_score(articles, top_n=max_topics)

        topics = []
        for sa in scored:
            topics.append({
                "title": sa.article.title,
                "summary": sa.article.summary[:200],
                "source_url": sa.article.url,
                "source_name": sa.article.source,
                "score": sa.score,
                "tags": sa.article.tags,
            })

        return topics
