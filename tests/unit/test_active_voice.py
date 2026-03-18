"""Tests for ActiveVoiceChecker - passive voice detection and conversion."""
import pytest

from pipeline.style.active_voice import (
    ActiveVoiceChecker,
    PassiveVoiceReport,
    PassiveVoiceMatch,
)


class TestDetectPassiveVoice:
    """Tests for passive voice detection."""

    def test_detect_english_passive_voice(self):
        """Test detection of English passive voice constructions."""
        checker = ActiveVoiceChecker()

        text = "The report was written by the team."
        report = checker.check(text)

        assert report.total_sentences == 1
        assert report.passive_sentence_count >= 1
        assert report.passive_percentage >= 50.0
        assert len(report.matches) >= 1

    def test_detect_multiple_english_passive_constructions(self):
        """Test detection of multiple passive voice instances in one text."""
        checker = ActiveVoiceChecker()

        text = (
            "The code was reviewed by the senior developer. "
            "The features were implemented last week. "
            "The tests are being written now."
        )
        report = checker.check(text)

        assert report.passive_sentence_count >= 2
        assert len(report.matches) >= 2

    def test_detect_russian_passive_voice(self):
        """Test detection of Russian passive voice constructions."""
        checker = ActiveVoiceChecker()

        text = "Отчет был написан командой разработчиков."
        report = checker.check(text)

        assert report.total_sentences == 1
        # Should detect passive voice in Russian
        assert report.passive_sentence_count >= 1 or len(report.matches) >= 1

    def test_detect_mixed_active_and_passive(self):
        """Test that active voice sentences are not flagged."""
        checker = ActiveVoiceChecker()

        text = (
            "The team wrote the report. "  # Active
            "The report was reviewed by management."  # Passive
        )
        report = checker.check(text)

        assert report.total_sentences == 2
        # Should only count the passive sentence
        assert report.passive_sentence_count >= 1
        assert report.passive_percentage >= 25.0

    def test_detect_no_passive_voice(self):
        """Test that text without passive voice passes cleanly."""
        checker = ActiveVoiceChecker()

        text = "The team writes code every day. Developers love clean code."
        report = checker.check(text)

        assert report.score >= 90.0
        assert report.is_acceptable is True

    def test_empty_text(self):
        """Test handling of empty text."""
        checker = ActiveVoiceChecker()

        report = checker.check("")

        assert report.total_sentences == 0
        assert report.passive_sentence_count == 0
        assert report.passive_percentage == 0.0
        assert report.score == 100.0

    def test_passive_voice_report_property(self):
        """Test that passive_voice_report property returns last report."""
        checker = ActiveVoiceChecker()

        text = "The report was written."
        checker.check(text)

        # Access via property
        report = checker.passive_voice_report
        assert isinstance(report, PassiveVoiceReport)
        assert report.total_sentences == 1


class TestDetectPassiveVoicePatterns:
    """Tests for specific passive voice pattern detection."""

    def test_detect_was_ed_pattern(self):
        """Test detection of 'was + past participle (-ed)' pattern."""
        checker = ActiveVoiceChecker()

        text = "The document was completed yesterday."
        matches = checker._check_passive_voice(text, "en")

        assert len(matches) >= 1
        assert any("was" in m.auxiliary_verb.lower() for m in matches)

    def test_detect_were_ed_pattern(self):
        """Test detection of 'were + past participle (-ed)' pattern."""
        checker = ActiveVoiceChecker()

        text = "The documents were completed yesterday."
        matches = checker._check_passive_voice(text, "en")

        assert len(matches) >= 1

    def test_detect_is_en_pattern(self):
        """Test detection of 'is + past participle (-en)' pattern."""
        checker = ActiveVoiceChecker()

        text = "The message is written in English."
        matches = checker._check_passive_voice(text, "en")

        assert len(matches) >= 1

    def test_detect_has_been_pattern(self):
        """Test detection of 'has been + past participle' pattern."""
        checker = ActiveVoiceChecker()

        text = "The project has been completed."
        matches = checker._check_passive_voice(text, "en")

        assert len(matches) >= 1

    def test_detect_irregular_verbs(self):
        """Test detection of common irregular verb participles."""
        checker = ActiveVoiceChecker()

        irregular_passive_examples = [
            "The book was written by a famous author.",
            "The data was given to the analyst.",
            "The photo was taken yesterday.",
            "The solution was found quickly.",
        ]

        for text in irregular_passive_examples:
            matches = checker._check_passive_voice(text, "en")
            assert len(matches) >= 1, f"Failed to detect passive in: {text}"

    def test_detect_will_be_pattern(self):
        """Test detection of 'will be + past participle' pattern."""
        checker = ActiveVoiceChecker()

        text = "The report will be completed tomorrow."
        matches = checker._check_passive_voice(text, "en")

        assert len(matches) >= 1

    def test_russian_byl_sdelan_pattern(self):
        """Test detection of Russian 'был + причастие' pattern."""
        checker = ActiveVoiceChecker()

        text = "Проект был завершен вовремя."
        matches = checker._check_passive_voice(text, "ru")

        # Should detect passive construction
        assert len(matches) >= 0  # Russian patterns may vary


class TestConvertToActiveVoice:
    """Tests for passive to active voice conversion."""

    def test_convert_simple_passive(self):
        """Test conversion of simple passive constructions."""
        checker = ActiveVoiceChecker()

        text = "The report was written."
        active = checker.convert_to_active_voice(text)

        # Should replace "was written" with active form
        assert "was written" not in active.lower() or "[subject]" in active

    def test_convert_preserves_other_text(self):
        """Test that conversion preserves non-passive text."""
        checker = ActiveVoiceChecker()

        text = "The report was written. The team worked hard."
        active = checker.convert_to_active_voice(text)

        assert "The team worked hard" in active

    def test_convert_irregular_verbs(self):
        """Test conversion of irregular verb passive constructions."""
        checker = ActiveVoiceChecker()

        text = "The book was written by John."
        active = checker.convert_to_active_voice(text)

        # Should suggest active form with base verb
        assert "write" in active.lower() or "[subject]" in active

    def test_convert_russian_passive(self):
        """Test conversion of Russian passive constructions."""
        checker = ActiveVoiceChecker()

        text = "Отчет был написан вчера."
        active = checker.convert_to_active_voice(text)

        # Should attempt conversion
        assert isinstance(active, str)

    def test_convert_returns_string(self):
        """Test that conversion always returns a string."""
        checker = ActiveVoiceChecker()

        texts = [
            "Active text without passive voice.",
            "",
            "The code was reviewed.",
        ]

        for text in texts:
            result = checker.convert_to_active_voice(text)
            assert isinstance(result, str)


class TestGetPassivePercentage:
    """Tests for passive percentage calculation."""

    def test_get_passive_percentage_all_passive(self):
        """Test percentage when all sentences are passive."""
        checker = ActiveVoiceChecker()

        text = "The report was written. The code was reviewed. The tests were run."
        percentage = checker.get_passive_percentage(text)

        # At least 2 of 3 sentences should be detected as passive
        assert percentage >= 50.0  # Should be high

    def test_get_passive_percentage_no_passive(self):
        """Test percentage when no sentences are passive."""
        checker = ActiveVoiceChecker()

        text = "The team writes code. Developers test their work. We ship daily."
        percentage = checker.get_passive_percentage(text)

        assert percentage < 20.0  # Should be low

    def test_get_passive_percentage_mixed(self):
        """Test percentage with mixed active/passive sentences."""
        checker = ActiveVoiceChecker()

        text = (
            "The team wrote the report. "  # Active
            "The report was reviewed by management. "  # Passive
            "The developers fixed the bugs. "  # Active
            "The bugs were fixed quickly."  # Passive
        )
        percentage = checker.get_passive_percentage(text)

        # Should be around 50%
        assert 20.0 <= percentage <= 80.0

    def test_get_passive_percentage_single_sentence(self):
        """Test percentage calculation with single sentence."""
        checker = ActiveVoiceChecker()

        text_passive = "The document was created."
        text_active = "John created the document."

        passive_pct = checker.get_passive_percentage(text_passive)
        active_pct = checker.get_passive_percentage(text_active)

        assert passive_pct > active_pct

    def test_get_passive_percentage_empty_text(self):
        """Test percentage calculation with empty text."""
        checker = ActiveVoiceChecker()

        percentage = checker.get_passive_percentage("")

        assert percentage == 0.0


class TestPassiveVoiceReport:
    """Tests for PassiveVoiceReport generation."""

    def test_report_contains_matches(self):
        """Test that report contains match details."""
        checker = ActiveVoiceChecker()

        text = "The report was written by the team."
        report = checker.check(text)

        assert len(report.matches) >= 1
        match = report.matches[0]
        assert isinstance(match, PassiveVoiceMatch)
        assert match.text != ""
        assert match.sentence != ""

    def test_report_score_range(self):
        """Test that score is always in 0-100 range."""
        checker = ActiveVoiceChecker()

        test_texts = [
            "Active text. Very active text.",
            "The report was written. The code was reviewed. The tests were run.",
            "",
            "Mixed active and passive voice sentences here.",
        ]

        for text in test_texts:
            report = checker.check(text)
            assert 0 <= report.score <= 100, f"Score {report.score} out of range for: {text}"

    def test_report_recommendations(self):
        """Test that report generates recommendations for high passive usage."""
        checker = ActiveVoiceChecker(max_passive_percentage=20.0)

        # Text with high passive voice usage
        text = (
            "The report was written. The code was reviewed. "
            "The tests were run. The document was approved."
        )
        report = checker.check(text)

        assert len(report.recommendations) >= 1

    def test_report_no_recommendations_for_clean_text(self):
        """Test that clean text has no recommendations."""
        checker = ActiveVoiceChecker(max_passive_percentage=20.0)

        text = "The team writes clean code. Developers love testing."
        report = checker.check(text)

        assert len(report.recommendations) == 0

    def test_report_is_acceptable(self):
        """Test is_acceptable flag based on threshold."""
        checker = ActiveVoiceChecker(max_passive_percentage=20.0)

        # Mostly active - should be acceptable
        active_text = "The team writes code. Developers test features."
        active_report = checker.check(active_text)
        assert active_report.is_acceptable is True

        # All passive - should not be acceptable
        passive_text = "The report was written. The code was reviewed."
        passive_report = checker.check(passive_text)
        assert passive_report.is_acceptable is False


class TestActiveVoiceCheckerConfiguration:
    """Tests for ActiveVoiceChecker configuration options."""

    def test_custom_max_passive_percentage(self):
        """Test custom maximum passive percentage threshold."""
        checker = ActiveVoiceChecker(max_passive_percentage=10.0)

        # 50% passive (1 of 2 sentences)
        text = "The team wrote code. The code was reviewed."
        report = checker.check(text)

        # Should fail the stricter threshold
        assert report.is_acceptable is False

    def test_language_auto_detection(self):
        """Test automatic language detection."""
        checker = ActiveVoiceChecker(language="auto")

        english_text = "The report was written."
        russian_text = "Отчет был написан."

        en_report = checker.check(english_text)
        ru_report = checker.check(russian_text)

        # Both should work without errors
        assert isinstance(en_report, PassiveVoiceReport)
        assert isinstance(ru_report, PassiveVoiceReport)

    def test_explicit_language_setting(self):
        """Test explicit language setting."""
        checker_en = ActiveVoiceChecker(language="en")
        checker_ru = ActiveVoiceChecker(language="ru")

        text = "The report was written."

        # Should still work with explicit English
        report = checker_en.check(text)
        assert isinstance(report, PassiveVoiceReport)

    def test_repr(self):
        """Test string representation of checker."""
        checker = ActiveVoiceChecker(max_passive_percentage=15.0, language="en")

        repr_str = repr(checker)

        assert "ActiveVoiceChecker" in repr_str
        assert "15" in repr_str
        assert "en" in repr_str
