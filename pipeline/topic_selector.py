"""
Topic selector for choosing the best topic for a post.

Uses LLM to select the most relevant and engaging topic from articles.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger
from pipeline.source_collector import Article

if TYPE_CHECKING:
    from llm.base import BaseLLMAdapter
    from memory.topic_store import TopicStore

logger = get_logger(__name__)


class TopicSelector:
    """
    Selects the best topic for a Telegram post.

    Uses LLM to evaluate topics and select the most engaging one,
    avoiding recently used topics for variety.
    """

    def __init__(
        self,
        llm_adapter: "BaseLLMAdapter",
        topic_store: "TopicStore",
        channel_topic: str,
        similarity_threshold: float = 0.6,
    ) -> None:
        """
        Initialize topic selector.

        Args:
            llm_adapter: LLM adapter for topic evaluation
            topic_store: Store for topic history
            channel_topic: Main channel topic/theme
            similarity_threshold: Threshold for topic similarity (0-1)
        """
        self.llm = llm_adapter
        self.topic_store = topic_store
        self.channel_topic = channel_topic
        self.similarity_threshold = similarity_threshold

    def _format_topics(self, articles: list[Article]) -> str:
        """
        Format articles as a numbered list of topics.

        Args:
            articles: List of articles

        Returns:
            str: Formatted topic list
        """
        lines = []
        for i, article in enumerate(articles, 1):
            lines.append(f"{i}. {article.title}")
            if article.summary:
                lines.append(f"   Summary: {article.summary[:150]}...")
        return "\n".join(lines)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate word overlap similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            float: Similarity score (0-1)
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        # Remove common stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "being", "have", "has", "had", "do", "does", "did", "will",
                      "would", "could", "should", "may", "might", "must", "shall",
                      "can", "need", "dare", "ought", "used", "to", "of", "in",
                      "for", "on", "with", "at", "by", "from", "as", "into",
                      "through", "during", "before", "after", "above", "below",
                      "between", "under", "again", "further", "then", "once",
                      "и", "в", "во", "не", "что", "он", "на", "я", "с", "со",
                      "как", "а", "то", "все", "она", "так", "его", "но", "да",
                      "ты", "к", "у", "же", "вы", "за", "бы", "по", "только",
                      "ее", "мне", "было", "вот", "от", "меня", "еще", "нет"}

        words1 = words1 - stop_words
        words2 = words2 - stop_words

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        if union == 0:
            return 0.0

        return intersection / union

    async def _is_topic_similar_to_recent(
        self,
        topic: str,
        forbidden_topics: list[str],
    ) -> tuple[bool, Optional[str]]:
        """
        Check if topic is too similar to recently used topics.

        Args:
            topic: Topic to check
            forbidden_topics: List of recently used topics

        Returns:
            tuple[bool, Optional[str]]: (is_similar, similar_topic)
        """
        if not forbidden_topics:
            return False, None

        for forbidden in forbidden_topics:
            similarity = self._calculate_similarity(topic, forbidden)
            if similarity >= self.similarity_threshold:
                return True, forbidden

        return False, None

    async def select_from_articles(
        self,
        articles: list[Article],
        max_attempts: int = 3,
    ) -> dict:
        """
        Select the best topic from a list of articles.

        Args:
            articles: List of articles to choose from
            max_attempts: Maximum attempts to find a unique topic

        Returns:
            dict: Selection result with topic, reason, angle, source_article
        """
        if not articles:
            return await self.generate_topic_idea()

        # Get forbidden topics (recently used)
        forbidden_topics = await self.topic_store.get_forbidden_names(days=7)
        logger.info(f"Found {len(forbidden_topics)} forbidden topics")

        # Filter out articles with similar topics
        filtered_articles = []
        for article in articles:
            is_similar, similar_to = await self._is_topic_similar_to_recent(
                article.title, forbidden_topics
            )
            if is_similar:
                logger.debug(f"Skipping similar topic: '{article.title[:50]}...' "
                           f"(similar to: '{similar_to[:50]}...')")
            else:
                filtered_articles.append(article)

        if not filtered_articles:
            logger.warning("All articles filtered, using original list")
            filtered_articles = articles[:5]

        # Format topics for prompt
        topics_str = self._format_topics(filtered_articles[:5])
        forbidden_str = "\n".join(f"- {t}" for t in forbidden_topics[:10]) if forbidden_topics else "None"

        prompt = f"""Select the best topic for a Telegram post about AI and technology.

CHANNEL TOPIC: {self.channel_topic}

TOPICS:
{topics_str}

AVOID (recently covered):
{forbidden_str}

Select the BEST topic that is:
1. Most relevant to AI/technology
2. Not similar to recently covered topics
3. Has potential for engaging discussion

Reply with ONLY this JSON:
{{"selected_topic": "exact topic title from list", "reason": "why this topic", "angle": "unique perspective"}}"""

        try:
            response = await self.llm.generate(prompt)
            content = response.content.strip()

            # Try to extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            selected_topic = result.get("selected_topic", "")

            # Verify selected topic is not too similar to forbidden
            is_similar, similar_to = await self._is_topic_similar_to_recent(
                selected_topic, forbidden_topics
            )
            if is_similar:
                logger.warning(f"LLM selected similar topic: '{selected_topic[:50]}...' "
                             f"(similar to: '{similar_to[:50]}...')")
                # Try next best article
                for article in filtered_articles:
                    if article.title != selected_topic:
                        is_similar2, _ = await self._is_topic_similar_to_recent(
                            article.title, forbidden_topics
                        )
                        if not is_similar2:
                            selected_topic = article.title
                            result["selected_topic"] = selected_topic
                            result["reason"] = "Alternative selection to avoid duplicate"
                            break

            # Find matching article
            matching_article = None
            for article in filtered_articles:
                if article.title == selected_topic or selected_topic in article.title:
                    matching_article = article
                    break

            if not matching_article and filtered_articles:
                matching_article = filtered_articles[0]

            logger.info(f"Selected topic: {selected_topic[:50]}...")

            return {
                "selected_topic": selected_topic,
                "reason": result.get("reason", ""),
                "angle": result.get("angle", ""),
                "source_article": matching_article.to_dict() if matching_article else None,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Fallback to first non-similar article
            for article in filtered_articles:
                is_similar, _ = await self._is_topic_similar_to_recent(
                    article.title, forbidden_topics
                )
                if not is_similar:
                    return {
                        "selected_topic": article.title,
                        "reason": "Fallback: first non-duplicate article",
                        "angle": "",
                        "source_article": article.to_dict(),
                    }

            # Last resort: first article
            if filtered_articles:
                article = filtered_articles[0]
                return {
                    "selected_topic": article.title,
                    "reason": "Fallback to first article",
                    "angle": "",
                    "source_article": article.to_dict(),
                }

            return {
                "selected_topic": "",
                "reason": "No articles available",
                "angle": "",
                "source_article": None,
            }

        except Exception as e:
            logger.error(f"Topic selection failed: {e}")
            raise

    async def generate_topic_idea(self) -> dict:
        """
        Generate a topic idea from scratch when no articles are available.

        Returns:
            dict: Generated topic with reason and angle
        """
        # Get forbidden topics
        forbidden_topics = await self.topic_store.get_forbidden_names(days=7)
        forbidden_str = "\n".join(f"- {t}" for t in forbidden_topics[:10]) if forbidden_topics else "None"

        prompt = f"""Generate a topic idea for a Telegram post about {self.channel_topic}.

AVOID these recently covered topics:
{forbidden_str}

Generate a fresh, engaging topic that:
1. Is relevant to AI/technology
2. Has not been covered recently
3. Would interest a tech-savvy audience

Reply with ONLY this JSON:
{{"selected_topic": "topic title", "reason": "why this topic", "angle": "unique perspective"}}"""

        try:
            response = await self.llm.generate(prompt)
            content = response.content.strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())

            return {
                "selected_topic": result.get("selected_topic", ""),
                "reason": result.get("reason", ""),
                "angle": result.get("angle", ""),
                "source_article": None,
            }

        except Exception as e:
            logger.error(f"Topic generation failed: {e}")
            # Return a generic fallback
            return {
                "selected_topic": "Latest AI developments",
                "reason": "Fallback topic",
                "angle": "General overview",
                "source_article": None,
            }
