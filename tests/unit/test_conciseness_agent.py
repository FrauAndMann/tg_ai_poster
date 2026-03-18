"""Tests for ConcisenessAgent - automatic text conciseness improvement."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict
from pathlib import Path

from pipeline.agents.conciseness_agent import (
    ConcisenessAgent,
    ConcisenessResult,
)


class TestConcisenessResult:
    """Tests for ConcisenessResult dataclass."""

    def test_result_creation(self):
        """Test basic result creation."""
        result = ConcisenessResult(
            original_text="This is the original text.",
            rewritten_text="Original text.",
            reduction_percentage=33.3,
            preserved_facts=["original text"],
            changes_made=["Removed redundant words"],
        )

        assert result.original_text == "This is the original text."
        assert result.rewritten_text == "Original text."
        assert result.reduction_percentage == 33.3
        assert len(result.preserved_facts) == 1
        assert len(result.changes_made) == 1

    def test_result_to_dict(self):
        """Test conversion to dictionary."""
        result = ConcisenessResult(
            original_text="Original",
            rewritten_text="Short",
            reduction_percentage=50.0,
            preserved_facts=["fact1"],
            changes_made=["change1"],
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["original_text"] == "Original"
        assert result_dict["rewritten_text"] == "Short"
        assert result_dict["reduction_percentage"] == 50.0

    def test_result_is_valid_reduction(self):
        """Test validation of reduction percentage."""
        # Valid reduction
        valid_result = ConcisenessResult(
            original_text="Original text here",
            rewritten_text="Short text",
            reduction_percentage=25.0,
            preserved_facts=[],
            changes_made=[],
        )
        assert valid_result.is_valid_reduction(max_reduction=0.3) is True

        # Invalid reduction (too aggressive)
        invalid_result = ConcisenessResult(
            original_text="Original text here",
            rewritten_text="Short",
            reduction_percentage=50.0,
            preserved_facts=[],
            changes_made=[],
        )
        assert invalid_result.is_valid_reduction(max_reduction=0.3) is False


class TestConcisenessAgentInit:
    """Tests for ConcisenessAgent initialization."""

    def test_default_initialization(self):
        """Test default initialization values."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(llm_adapter=mock_llm)

        assert agent.model == "gpt-4o-mini"
        assert agent.max_reduction == 0.3
        assert agent.preserve_key_facts is True

    def test_custom_initialization(self):
        """Test custom initialization values."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(
            llm_adapter=mock_llm,
            model="gpt-4",
            max_reduction=0.5,
            preserve_key_facts=False,
        )

        assert agent.model == "gpt-4"
        assert agent.max_reduction == 0.5
        assert agent.preserve_key_facts is False


class TestRewrite:
    """Tests for the rewrite method."""

    @pytest.mark.asyncio
    async def test_rewrite_shortens_text(self):
        """Test that rewrite produces shorter text."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.return_value = MagicMock(
            content='{"rewritten_text": "Shorter text.", "changes_made": ["Removed redundancy"], "preserved_facts": []}',
            model="gpt-4o-mini",
            usage={"total_tokens": 100},
        )

        agent = ConcisenessAgent(llm_adapter=mock_llm)
        original = "This is a very long and redundant text that repeats the same ideas multiple times."

        result = await agent.rewrite(original)

        assert len(result.rewritten_text) <= len(original)
        assert result.reduction_percentage >= 0

    @pytest.mark.asyncio
    async def test_rewrite_preserves_key_facts(self):
        """Test that rewrite preserves key facts."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.return_value = MagicMock(
            content='{"rewritten_text": "Microsoft acquired OpenAI for $10 billion in 2024.", "changes_made": ["Removed filler words"], "preserved_facts": ["Microsoft", "OpenAI", "$10 billion", "2024"]}',
            model="gpt-4o-mini",
            usage={"total_tokens": 100},
        )

        agent = ConcisenessAgent(
            llm_adapter=mock_llm,
            preserve_key_facts=True,
        )
        original = "Microsoft, the tech giant, has officially acquired OpenAI for a staggering $10 billion in 2024."

        result = await agent.rewrite(original)

        # Key facts should be preserved
        assert "Microsoft" in result.rewritten_text
        assert "OpenAI" in result.rewritten_text
        assert "$10 billion" in result.rewritten_text or "10 billion" in result.rewritten_text
        assert "2024" in result.rewritten_text
        assert len(result.preserved_facts) > 0

    @pytest.mark.asyncio
    async def test_rewrite_converts_passive_voice(self):
        """Test that passive voice is converted to active."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.return_value = MagicMock(
            content='{"rewritten_text": "The team wrote the code yesterday.", "changes_made": ["Convert passive to active voice"], "preserved_facts": []}',
            model="gpt-4o-mini",
            usage={"total_tokens": 100},
        )

        agent = ConcisenessAgent(llm_adapter=mock_llm)
        original = "The code was written by the team yesterday."

        result = await agent.rewrite(original)

        # Check that passive construction is gone
        assert "was written by" not in result.rewritten_text.lower()
        assert "convert passive to active" in result.changes_made or "passive" in str(result.changes_made).lower()

    @pytest.mark.asyncio
    async def test_rewrite_removes_redundancy(self):
        """Test that redundant phrases are removed."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.return_value = MagicMock(
            content='{"rewritten_text": "AI changes everything. Machine learning transforms industries.", "changes_made": ["Merged duplicate ideas"], "preserved_facts": []}',
            model="gpt-4o-mini",
            usage={"total_tokens": 100},
        )

        agent = ConcisenessAgent(llm_adapter=mock_llm)
        original = (
            "AI changes everything in the modern world today. "
            "AI transforms everything. "
            "Machine learning is changing industries."
        )

        result = await agent.rewrite(original)

        # Result should be shorter
        assert len(result.rewritten_text) < len(original)
        assert result.reduction_percentage > 0

    @pytest.mark.asyncio
    async def test_rewrite_respects_max_reduction(self):
        """Test that rewrite does not exceed max reduction."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.return_value = MagicMock(
            content='{"rewritten_text": "Brief.", "changes_made": ["Shortened"], "preserved_facts": []}',
            model="gpt-4o-mini",
            usage={"total_tokens": 100},
        )

        agent = ConcisenessAgent(
            llm_adapter=mock_llm,
            max_reduction=0.3,  # Max 30% reduction
        )
        original = "This is a moderately long text with important information."

        result = await agent.rewrite(original)

        # If reduction is too aggressive, should flag it
        if result.reduction_percentage > 30:
            assert result.is_valid_reduction(max_reduction=0.3) is False

    @pytest.mark.asyncio
    async def test_rewrite_handles_empty_text(self):
        """Test handling of empty text."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(llm_adapter=mock_llm)

        result = await agent.rewrite("")

        assert result.rewritten_text == ""
        assert result.reduction_percentage == 0.0
        assert len(result.changes_made) == 0

    @pytest.mark.asyncio
    async def test_rewrite_handles_short_text(self):
        """Test handling of already concise text."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.return_value = MagicMock(
            content='{"rewritten_text": "OK", "changes_made": [], "preserved_facts": []}',
            model="gpt-4o-mini",
            usage={"total_tokens": 50},
        )

        agent = ConcisenessAgent(llm_adapter=mock_llm)
        original = "OK"

        result = await agent.rewrite(original)

        # Short text should not be modified much
        assert result.reduction_percentage < 50


class TestExtractKeyFacts:
    """Tests for _extract_key_facts method."""

    def test_extract_numbers_and_dates(self):
        """Test extraction of numbers and dates."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(llm_adapter=mock_llm)

        text = "Sales grew 45% in Q1 2024, reaching $5 million."
        facts = agent._extract_key_facts(text)

        assert any("45%" in fact or "45" in fact for fact in facts)
        assert any("2024" in fact for fact in facts)
        assert any("5 million" in fact.lower() or "$5" in fact for fact in facts)

    def test_extract_names_and_entities(self):
        """Test extraction of names and entities."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(llm_adapter=mock_llm)

        text = "OpenAI released GPT-4 with Microsoft partnership."
        facts = agent._extract_key_facts(text)

        # Should extract key entities
        assert len(facts) > 0
        facts_str = " ".join(facts).lower()
        assert "openai" in facts_str or "gpt" in facts_str or "microsoft" in facts_str

    def test_extract_empty_text(self):
        """Test extraction from empty text."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(llm_adapter=mock_llm)

        facts = agent._extract_key_facts("")

        assert facts == []


class TestValidateResult:
    """Tests for _validate_result method."""

    def test_validate_acceptable_reduction(self):
        """Test validation of acceptable reduction."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(llm_adapter=mock_llm, max_reduction=0.3)

        original = "This is a longer text with lots of content here."
        rewritten = "This is shorter text with content."

        is_valid = agent._validate_result(original, rewritten)

        assert is_valid is True

    def test_validate_excessive_reduction(self):
        """Test validation rejects excessive reduction."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(llm_adapter=mock_llm, max_reduction=0.3)

        original = "This is a very long piece of text with many words and lots of content."
        rewritten = "Short."

        is_valid = agent._validate_result(original, rewritten)

        # 80%+ reduction should fail 30% limit
        assert is_valid is False

    def test_validate_same_length(self):
        """Test validation passes for no reduction."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(llm_adapter=mock_llm, max_reduction=0.3)

        text = "Same length text."

        is_valid = agent._validate_result(text, text)

        assert is_valid is True


class TestLoadPrompt:
    """Tests for prompt loading."""

    def test_load_default_prompt(self):
        """Test loading default prompt when file not found."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(
            llm_adapter=mock_llm,
            prompts_dir=Path("/nonexistent/path"),
        )

        prompt = agent._load_prompt("nonexistent.txt")

        assert "{text}" in prompt
        assert "{max_reduction}" in prompt

    def test_prompt_contains_rules(self):
        """Test that prompt contains key rules."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(llm_adapter=mock_llm)

        prompt = agent._load_prompt("conciseness_rewriter.txt")

        # Check for key rules in prompt
        assert "redundant" in prompt.lower() or "repetition" in prompt.lower()
        assert "active" in prompt.lower()
        assert "preserve" in prompt.lower()


class TestIntegration:
    """Integration tests with mocked LLM responses."""

    @pytest.mark.asyncio
    async def test_full_rewrite_workflow(self):
        """Test complete rewrite workflow."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.return_value = MagicMock(
            content='{"rewritten_text": "Google released Gemini 2.0 with improved reasoning. The model processes complex queries faster.", "changes_made": ["Removed redundancy", "Merged duplicate mentions"], "preserved_facts": ["Google", "Gemini 2.0"]}',
            model="gpt-4o-mini",
            usage={"total_tokens": 150},
        )

        agent = ConcisenessAgent(
            llm_adapter=mock_llm,
            model="gpt-4o-mini",
            max_reduction=0.3,
            preserve_key_facts=True,
        )

        original = (
            "Google has officially announced the release of their new Gemini 2.0 model "
            "which comes with significantly improved reasoning capabilities. "
            "This new Gemini 2.0 model is able to process complex queries much faster than before. "
            "The model was released by Google recently."
        )

        result = await agent.rewrite(original)

        # Verify result structure
        assert isinstance(result, ConcisenessResult)
        assert result.original_text == original
        assert len(result.rewritten_text) < len(original)
        assert result.reduction_percentage > 0
        assert isinstance(result.changes_made, list)
        assert isinstance(result.preserved_facts, list)

    @pytest.mark.asyncio
    async def test_llm_called_with_correct_prompt(self):
        """Test that LLM is called with correctly formatted prompt."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.return_value = MagicMock(
            content='{"rewritten_text": "Rewritten text.", "changes_made": [], "preserved_facts": []}',
            model="gpt-4o-mini",
            usage={"total_tokens": 100},
        )

        agent = ConcisenessAgent(
            llm_adapter=mock_llm,
            max_reduction=0.25,
        )

        original = "Original text to rewrite."
        await agent.rewrite(original)

        # Verify LLM was called
        mock_llm.generate.assert_called_once()
        call_args = mock_llm.generate.call_args

        # Check prompt contains original text and max_reduction
        prompt = call_args[0][0]  # positional argument
        assert "Original text to rewrite." in prompt
        assert "25%" in prompt or "0.25" in prompt

    @pytest.mark.asyncio
    async def test_handles_llm_error(self):
        """Test handling of LLM errors."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM error"))

        agent = ConcisenessAgent(llm_adapter=mock_llm)
        original = "Text to process."

        result = await agent.rewrite(original)

        # Should return original text on error
        assert result.rewritten_text == original
        assert result.reduction_percentage == 0.0
        assert "error" in str(result.changes_made).lower()


class TestConcisenessAgentRepr:
    """Tests for string representation."""

    def test_repr(self):
        """Test string representation of agent."""
        mock_llm = MagicMock()
        agent = ConcisenessAgent(
            llm_adapter=mock_llm,
            model="gpt-4o-mini",
            max_reduction=0.3,
        )

        repr_str = repr(agent)

        assert "ConcisenessAgent" in repr_str
        assert "gpt-4o-mini" in repr_str
        assert "0.3" in repr_str
