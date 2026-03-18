"""Integration tests for QualityChecker with anti-water and density modules."""
import pytest

from pipeline.quality_checker import QualityChecker


class TestQualityCheckerIntegration:
    """Tests for QualityChecker integration with anti-water and density modules."""

    @pytest.mark.asyncio
    async def test_water_detection_enabled_by_default(self):
        """Test that water detection is enabled by default."""
        checker = QualityChecker()

        # Text with high water content
        watery_text = """
        Стоит отметить, что безусловно крайне важный продукт.
        В современном мире это весьма необходимо отметить.
        """
        watery_text = watery_text.strip() + " \U0001F4CA"

        result = await checker.check(watery_text)

        # Should have water-related issues or suggestions
        all_feedback = result.issues + result.suggestions
        has_water_feedback = any(
            "water" in f.lower() or "filler" in f.lower() for f in all_feedback
        )
        assert has_water_feedback or result.score < 100

    @pytest.mark.asyncio
    async def test_density_scoring_enabled_by_default(self):
        """Test that density scoring is enabled by default."""
        checker = QualityChecker()

        # Text with low information density (no numbers, dates, proper nouns)
        low_density_text = """
        Это очень важный продукт для пользователей.
        Он помогает решать многие задачи.
        """
        low_density_text = low_density_text.strip() + " \U0001F4CA"

        result = await checker.check(low_density_text)

        # Should have density-related suggestions or lower score
        assert result.suggestions or result.score < 100

    @pytest.mark.asyncio
    async def test_can_disable_water_detection(self):
        """Test that water detection can be disabled."""
        checker = QualityChecker(enable_water_detection=False)

        # Verify the detector is not initialized
        assert checker._filler_detector is None

    @pytest.mark.asyncio
    async def test_can_disable_density_scoring(self):
        """Test that density scoring can be disabled."""
        checker = QualityChecker(enable_density_scoring=False)

        # Verify the scorer is not initialized
        assert checker._density_scorer is None

    @pytest.mark.asyncio
    async def test_high_quality_content_passes(self):
        """Test that high-quality content with good density passes checks."""
        checker = QualityChecker()

        high_quality_text = """
        OpenAI выпустила GPT-5 15 марта 2026 года.

        Компания инвестировала $10 миллиардов в разработку.
        По данным исследования, 85% пользователей довольны.
        Модель работает в 3 раза быстрее GPT-4.

        \U0001F50D Ключевые факты:
        \u2022 GPT-5 выпущен 15 марта 2026
        \u2022 Инвестиции: $10 млрд
        \u2022 Прирост скорости: 3x

        \U0001F4A1 TLDR: OpenAI выпустила GPT-5 с 3-кратным приростом скорости.

        #AI #OpenAI #GPT5
        """

        result = await checker.check(high_quality_text)

        # Should have reasonable score (may not pass all checks but should be high)
        assert result.score >= 50, f"Score too low: {result.score}"

    @pytest.mark.asyncio
    async def test_low_density_content_flagged(self):
        """Test that content with low information density is flagged."""
        checker = QualityChecker()

        # Very generic text with no specific facts
        generic_text = "Это хороший продукт для всех людей."
        generic_text = generic_text + " \U0001F4CA"  # Add emoji

        result = await checker.check(generic_text)

        # Should have low score due to multiple issues
        assert result.score < 80

    @pytest.mark.asyncio
    async def test_backward_compatibility_with_existing_checks(self):
        """Test that existing checks still work with new integration."""
        checker = QualityChecker(
            min_emojis=1,
            max_emojis=10,
            forbidden_words=["spam", "scam"],
        )

        # Test emoji check still works
        result = await checker.check("No emojis here but has content")
        assert any("emoji" in i.lower() for i in result.issues)

        # Test forbidden words check still works
        result = await checker.check("This is spam content \U0001F4CA")
        assert any("forbidden" in i.lower() for i in result.issues)
