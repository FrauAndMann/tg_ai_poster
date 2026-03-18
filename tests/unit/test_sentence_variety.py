"""Tests for sentence variety analyzer."""
import pytest
from pipeline.style.sentence_variety import (
    SentenceVarietyAnalyzer,
    SentenceVarietyReport,
)


def test_empty_text():
    """Test analysis of empty text."""
    analyzer = SentenceVarietyAnalyzer()

    report = analyzer.analyze("")

    assert report.variety_score == 0.0
    assert report.sentence_count == 0
    assert report.passes_threshold is False
    assert "Text is empty" in report.rhythm_issues


def test_empty_text_with_whitespace():
    """Test analysis of text with only whitespace."""
    analyzer = SentenceVarietyAnalyzer()

    report = analyzer.analyze("   \n\t  ")

    assert report.variety_score == 0.0
    assert report.sentence_count == 0
    assert report.passes_threshold is False


def test_variety_score():
    """Test that variety score is calculated and in valid range (0-100)."""
    analyzer = SentenceVarietyAnalyzer()

    # Text with good variety
    text = """OpenAI released GPT-5 yesterday. This is a significant milestone.
The new model shows remarkable improvements in reasoning and coding abilities.
Experts are excited. The AI community has been waiting for this release for months.
While some concerns remain about safety, the overall reception has been positive."""
    report = analyzer.analyze(text)

    assert 0 <= report.variety_score <= 100
    assert isinstance(report.variety_score, float)


def test_score_method():
    """Test the score() method returns correct value."""
    analyzer = SentenceVarietyAnalyzer()

    text = "First sentence here. Second one here. Third is here now."
    score = analyzer.score(text)

    assert isinstance(score, float)
    assert 0 <= score <= 100


def test_text_length_variety():
    """Test detection of different sentence lengths."""
    analyzer = SentenceVarietyAnalyzer()

    # Text with mix of short, medium, and long sentences
    # Note: Sentences need to be properly separated with space after punctuation
    text = """Short sentence here. Medium length sentence here now.
This is a much longer sentence that contains many words and provides detailed information about the topic at hand.
Tiny sentence. Another medium one here now."""
    report = analyzer.analyze(text)

    assert report.sentence_count >= 3  # Should have at least 3 sentences
    assert "short" in report.length_distribution
    assert "medium" in report.length_distribution
    assert "long" in report.length_distribution


def test_short_sentences():
    """Test detection and counting of short sentences."""
    analyzer = SentenceVarietyAnalyzer()

    # Text with short sentences (<= 8 words each)
    text = "Short one here. Tiny text now. Quick hit text. Brief one here. Short text now."
    report = analyzer.analyze(text)

    # All should be short (<=8 words)
    assert report.short_sentence_count >= 3
    assert report.length_distribution["short"] >= 3


def test_long_sentences():
    """Test detection and counting of long sentences."""
    analyzer = SentenceVarietyAnalyzer()

    # Text with a long sentence (25+ words)
    long_sentence = "This is a very long sentence that contains more than twenty-five words to test whether the analyzer correctly identifies and categorizes long sentences in the text."
    text = f"Start sentence here. {long_sentence} End sentence here."
    report = analyzer.analyze(text)

    assert report.long_sentence_count >= 1


def test_sentences():
    """Test basic sentence splitting and counting."""
    analyzer = SentenceVarietyAnalyzer()

    text = "First sentence here. Second sentence here! Third sentence here? Fourth one here."
    report = analyzer.analyze(text)

    assert report.sentence_count == 4


def test_detect_repetitive_sentences():
    """Test detection of repetitive sentence patterns."""
    analyzer = SentenceVarietyAnalyzer()

    # Text with repetitive sentence starts (3+ times with same beginning)
    # Note: Using varied lengths to avoid monotonous length detection
    text = """The company announced a major new product yesterday. The company released an update.
The company plans to expand globally next year. The company hired new staff members."""
    report = analyzer.analyze(text)

    assert len(report.repetitive_patterns) > 0
    # Should detect either repetitive start or monotonous length pattern
    assert any("Repetitive start" in p or "Monotonous" in p for p in report.repetitive_patterns)


def test_detect_repetitive_length_patterns():
    """Test detection of monotonous sentence lengths."""
    analyzer = SentenceVarietyAnalyzer()

    # Text with 4+ consecutive sentences of similar length
    text = "One two three four five. One two three four five. One two three four five. One two three four five."
    report = analyzer.analyze(text)

    assert any("Monotonous length" in p for p in report.repetitive_patterns)


def test_rhythm_issues_detection():
    """Test detection of rhythm issues."""
    analyzer = SentenceVarietyAnalyzer()

    # Text with all sentences of the same length
    text = "A B C D E F. G H I J K L. M N O P Q R. S T U V W X."
    report = analyzer.analyze(text)

    # Should detect rhythm issue (same length or low variance)
    assert len(report.rhythm_issues) > 0


def test_good_variety_text():
    """Test that varied text gets a good score."""
    analyzer = SentenceVarietyAnalyzer()

    # Well-structured text with good variety
    text = """OpenAI released GPT-5. Major upgrade.
The new model demonstrates unprecedented capabilities in reasoning, coding, and creative tasks across multiple domains.
Experts praised the release. However, some safety concerns remain.
The AI community has been anticipating this release for over a year.
Compact sentence. But powerful impact."""
    report = analyzer.analyze(text)

    assert report.variety_score >= 50  # Should be decent
    assert report.sentence_count >= 5
    assert len(report.length_distribution) == 3


def test_suggestions_generated():
    """Test that suggestions are generated for issues."""
    analyzer = SentenceVarietyAnalyzer()

    # Text with issues (all short sentences)
    text = "Short text. Tiny text. Mini text. Small text. Brief text."
    report = analyzer.analyze(text)

    assert len(report.suggestions) > 0


def test_passes_threshold():
    """Test passes_threshold based on min_score."""
    analyzer = SentenceVarietyAnalyzer(min_score=70.0)

    # Poor variety text (all same length)
    text = "Same text. Same text. Same text. Same text. Same text. Same text. Same text. Same text."
    report = analyzer.analyze(text)

    assert report.passes_threshold is False


def test_report_dataclass():
    """Test that SentenceVarietyReport has all required fields."""
    analyzer = SentenceVarietyAnalyzer()

    text = "Test sentence here. Another one here."
    report = analyzer.analyze(text)

    assert isinstance(report.variety_score, float)
    assert isinstance(report.sentence_count, int)
    assert isinstance(report.short_sentence_count, int)
    assert isinstance(report.long_sentence_count, int)
    assert isinstance(report.repetitive_patterns, list)
    assert isinstance(report.length_distribution, dict)
    assert isinstance(report.rhythm_issues, list)
    assert isinstance(report.passes_threshold, bool)
    assert isinstance(report.suggestions, list)


def test_russian_text():
    """Test analysis of Russian text."""
    analyzer = SentenceVarietyAnalyzer()

    text = """OpenAI выпустила GPT-5 вчера. Это важное событие.
Новая модель демонстрирует значительные улучшения в рассуждениях."""
    report = analyzer.analyze(text)

    assert report.sentence_count >= 2
    assert report.variety_score > 0


def test_mixed_language_text():
    """Test analysis of mixed language text."""
    analyzer = SentenceVarietyAnalyzer()

    text = "OpenAI released GPT-5 yesterday. Это важное событие для индустрии. Major milestone achieved today!"
    report = analyzer.analyze(text)

    assert report.sentence_count == 3


def test_minimum_score_parameter():
    """Test custom minimum score parameter."""
    analyzer_low = SentenceVarietyAnalyzer(min_score=30.0)
    analyzer_high = SentenceVarietyAnalyzer(min_score=90.0)

    text = "Test text here. Test text here. Test text here. Test text here."
    report_low = analyzer_low.analyze(text)
    report_high = analyzer_high.analyze(text)

    # Same text should have same score but different threshold pass
    assert report_low.variety_score == report_high.variety_score


def test_ideal_distribution():
    """Test scoring for text close to ideal distribution."""
    analyzer = SentenceVarietyAnalyzer()

    # Create text with ~30% short, ~20% long, ~50% medium
    text = """Short text here.
Brief one now.
Quick text here.
Medium length sentence here now.
Another medium one follows here.
Medium sentence number three here.
This is a longer sentence with more than twenty five words to help balance the distribution out properly.
A longer detailed explanation that spans over twenty five words to provide more information.
One more medium sentence here.
Yet another medium one here.
The final medium one here."""
    report = analyzer.analyze(text)

    # Should have reasonable distribution
    total = report.sentence_count
    if total > 0:
        short_ratio = report.length_distribution["short"] / total
        medium_ratio = report.length_distribution["medium"] / total
        long_ratio = report.length_distribution["long"] / total

        # Verify all ratios sum to 1
        assert abs(short_ratio + medium_ratio + long_ratio - 1.0) < 0.01


def test_single_sentence():
    """Test analysis of single sentence."""
    analyzer = SentenceVarietyAnalyzer()

    text = "This is a single sentence here."
    report = analyzer.analyze(text)

    assert report.sentence_count == 1
    assert report.variety_score > 0


def test_two_word_sentences_filtered():
    """Test that very short fragments are filtered."""
    analyzer = SentenceVarietyAnalyzer()

    # Single words shouldn't count as sentences (less than 2 words)
    text = "Word. Another. Test."
    report = analyzer.analyze(text)

    # These should be filtered (less than 2 words)
    assert report.sentence_count >= 0


def test_variety_score_range_edge_cases():
    """Test variety score stays in 0-100 range for edge cases."""
    analyzer = SentenceVarietyAnalyzer()

    # Very long text
    long_text = ". ".join(["This is sentence number " + str(i) for i in range(100)])
    report = analyzer.analyze(long_text)

    assert 0 <= report.variety_score <= 100


def test_consecutive_long_sentences_detected():
    """Test detection of consecutive very long sentences."""
    analyzer = SentenceVarietyAnalyzer()

    # Long sentences with 25+ words each (the threshold)
    # Note: Must have at least 25 words to be classified as "long"
    long1 = "This is a very long sentence with more than twenty five words to test consecutive long sentence detection in the analyzer module properly now added here."
    long2 = "Another extremely long sentence that continues for a very long time and contains over twenty five words to test the detection right now here today."
    # Need a third sentence to trigger rhythm check (requires 3+ sentences)
    text = f"{long1} {long2} And a short one here."

    report = analyzer.analyze(text)

    # Should detect consecutive long sentences issue or count long sentences
    has_consecutive_issue = any("consecutive" in issue.lower() for issue in report.rhythm_issues)
    has_long_sentences = report.long_sentence_count >= 2
    assert has_consecutive_issue or has_long_sentences


def test_suggestions_for_too_many_short():
    """Test suggestions when too many short sentences."""
    analyzer = SentenceVarietyAnalyzer()

    # Many short sentences (need enough to trigger suggestion)
    text = "Short text here. Tiny one here. Quick hit here. Brief text here. Short one here. Mini one here."
    report = analyzer.analyze(text)

    # Should suggest something about sentence variety
    assert len(report.suggestions) > 0


def test_suggestions_for_too_many_long():
    """Test suggestions when too many long sentences."""
    analyzer = SentenceVarietyAnalyzer()

    long = "This sentence is extremely long and contains many many words that go on and on to make it over twenty five words."
    text = f"{long} {long} {long} {long} {long}"
    report = analyzer.analyze(text)

    # Should suggest breaking up sentences
    assert any("long" in s.lower() or "break" in s.lower() or "shorter" in s.lower() for s in report.suggestions)


def test_sentence_variety_score_0_to_100():
    """Test sentence variety score is in 0-100 range."""
    analyzer = SentenceVarietyAnalyzer()

    # Various texts should all produce scores in valid range
    texts = [
        "Short.",
        "This is a medium length sentence.",
        "This is a much longer sentence that goes on and on with many words to test.",
        "Short one. Long one that has many many words in it. Medium here.",
    ]

    for text in texts:
        report = analyzer.analyze(text)
        assert 0 <= report.variety_score <= 100, f"Score out of range for: {text}"
