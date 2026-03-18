"""Tests for Editor Agent - style, tone, and flow improvements."""
from __future__ import annotations

import pytest
from dataclasses import dataclass
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.agents.editor_agent import EditorAgent, EditResult, EditChange


class TestEditChange:
    """Tests for EditChange dataclass."""

    def test_edit_change_creation(self):
        """Test EditChange dataclass is created correctly."""
        change = EditChange(
            type="tone",
            original="важно отметить",
            edited="",
            reason="Removed filler phrase"
        )

        assert change.type == "tone"
        assert change.original == "важно отметить"
        assert change.edited == ""
        assert change.reason == "Removed filler phrase"

    def test_edit_change_types(self):
        """Test different types of edit changes."""
        valid_types = ["tone", "flow", "hook", "clarity"]

        for change_type in valid_types:
            change = EditChange(
                type=change_type,
                original="test",
                edited="improved test",
                reason=f"Improved {change_type}"
            )
            assert change.type == change_type


class TestEditResult:
    """Tests for EditResult dataclass."""

    def test_edit_result_creation(self):
        """Test EditResult is created correctly."""
        result = EditResult(
            original_text="Original text",
            edited_text="Edited text",
            changes=[
                EditChange(type="tone", original="test", edited="improved", reason="test")
            ],
            style_score=85.0
        )

        assert result.original_text == "Original text"
        assert result.edited_text == "Edited text"
        assert len(result.changes) == 1
        assert result.style_score == 85.0

    def test_edit_result_default_changes(self):
        """Test EditResult with empty changes list."""
        result = EditResult(
            original_text="Original",
            edited_text="Edited",
            changes=[],
            style_score=100.0
        )

        assert result.changes == []
        assert result.style_score == 100.0


class TestEditorAgent:
    """Tests for EditorAgent class."""

    @pytest.fixture
    def mock_llm_adapter(self):
        """Create mock LLM adapter."""
        adapter = AsyncMock()
        adapter.generate = AsyncMock()
        return adapter

    @pytest.fixture
    def editor_agent(self, mock_llm_adapter):
        """Create EditorAgent with mock LLM."""
        return EditorAgent(model="gpt-4o-mini", llm_adapter=mock_llm_adapter)

    def test_editor_agent_initialization(self):
        """Test EditorAgent initializes correctly."""
        agent = EditorAgent(model="gpt-4o-mini")

        assert agent.model == "gpt-4o-mini"
        assert agent.llm is None

    def test_editor_agent_with_llm(self, mock_llm_adapter):
        """Test EditorAgent initialization with LLM adapter."""
        agent = EditorAgent(model="gpt-4o-mini", llm_adapter=mock_llm_adapter)

        assert agent.model == "gpt-4o-mini"
        assert agent.llm is mock_llm_adapter

    def test_edit_without_llm(self, editor_agent):
        """Test editing without LLM returns basic improvements."""
        agent = EditorAgent(model="gpt-4o-mini")  # No LLM

        text = "Это тестовый текст."
        result = agent.edit(text)

        assert isinstance(result, EditResult)
        assert result.original_text == text
        # Without LLM, text should remain mostly unchanged
        assert result.edited_text is not None

    def test_extract_changes_identifies_removals(self, editor_agent):
        """Test _extract_changes identifies removed content."""
        original = "Это важно отметить тест."
        edited = "Это тест."

        changes = editor_agent._extract_changes(original, edited)

        assert isinstance(changes, list)
        # Should detect changes (removals are detected as word differences)
        # The word "важно" and "отметить" should be detected as removed
        assert len(changes) > 0

    def test_extract_changes_identifies_additions(self, editor_agent):
        """Test _extract_changes identifies added content."""
        original = "Текст."
        edited = "Улучшенный текст."

        changes = editor_agent._extract_changes(original, edited)

        assert isinstance(changes, list)
        # Should detect the addition
        assert len(changes) > 0

    def test_calculate_style_score_high_quality(self, editor_agent):
        """Test _calculate_style_score returns high score for good text."""
        # Good text: specific, active voice, no fillers
        text = """
        OpenAI выпустила GPT-5 15 марта 2026.
        Модель работает в 3 раза быстрее GPT-4.
        Компания инвестировала $10 млрд в разработку.
        """

        score = editor_agent._calculate_style_score(text)

        assert isinstance(score, float)
        assert 0 <= score <= 100
        # Good text should have decent score
        assert score >= 60

    def test_calculate_style_score_low_quality(self, editor_agent):
        """Test _calculate_style_score returns low score for poor text."""
        # Poor text: fillers, passive voice, vague
        text = """
        В современном мире важно отметить, что AI меняет всё.
        Следует подчеркнуть, что безусловно это весьма важно.
        """

        score = editor_agent._calculate_style_score(text)

        assert isinstance(score, float)
        assert 0 <= score <= 100
        # Poor text should have lower score
        assert score < 80

    def test_style_score_empty_text(self, editor_agent):
        """Test _calculate_style_score handles empty text."""
        score = editor_agent._calculate_style_score("")

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_edit_with_llm(self, mock_llm_adapter):
        """Test edit with LLM adapter calls the LLM."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.content = "Улучшенный текст без воды."
        mock_llm_adapter.generate.return_value = mock_response

        agent = EditorAgent(model="gpt-4o-mini", llm_adapter=mock_llm_adapter)

        text = "Это важно отметить тест."
        result = await agent.edit_async(text)

        assert isinstance(result, EditResult)
        assert result.original_text == text
        assert mock_llm_adapter.generate.called

    @pytest.mark.asyncio
    async def test_edit_async_returns_edit_result(self, editor_agent, mock_llm_adapter):
        """Test edit_async returns EditResult."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.content = "Edited test text."
        mock_llm_adapter.generate.return_value = mock_response

        text = "Test text"
        result = await editor_agent.edit_async(text)

        assert isinstance(result, EditResult)
        assert result.original_text == text

    def test_load_prompt_template(self, editor_agent):
        """Test prompt template is loaded."""
        # Prompt should be loaded from file
        assert editor_agent.prompt_template is not None
        assert len(editor_agent.prompt_template) > 0

    def test_prompt_template_contains_guidelines(self, editor_agent):
        """Test prompt template contains required style guidelines."""
        prompt = editor_agent.prompt_template.lower()

        # Should contain key concepts
        assert "style" in prompt or "стиль" in prompt
        assert "tone" in prompt or "тон" in prompt
        assert "flow" in prompt or "поток" in prompt or "переход" in prompt


class TestEditorAgentIntegration:
    """Integration tests for EditorAgent."""

    @pytest.fixture
    def editor_agent(self):
        """Create EditorAgent without LLM for rule-based tests."""
        return EditorAgent(model="gpt-4o-mini")

    def test_edit_removes_ai_phrases(self, editor_agent):
        """Test edit removes AI-typical phrases."""
        text = "Важно отметить, что GPT-5 вышел."
        result = editor_agent.edit(text)

        # AI phrase should be removed
        assert "важно отметить" not in result.edited_text.lower()
        # Check that change was tracked
        assert any(c.type == "tone" for c in result.changes)

    def test_edit_improves_hook(self, editor_agent):
        """Test edit improves weak hook."""
        text = "Знаете ли вы, что GPT-5 вышел?"
        result = editor_agent.edit(text)

        # Generic opening should be improved
        assert "знаете ли вы" not in result.edited_text.lower() or len(result.changes) > 0

    def test_edit_tracks_multiple_changes(self, editor_agent):
        """Test edit tracks multiple changes."""
        text = """
        В современном мире важно отметить, что AI меняет всё.
        Следует подчеркнуть значимость этого события.
        Безусловно, это крайне необходимо.
        """
        result = editor_agent.edit(text)

        # Multiple changes should be tracked
        assert len(result.changes) >= 1

    def test_style_score_after_edit(self, editor_agent):
        """Test style score is calculated after edit."""
        text = "Это тестовый текст."
        result = editor_agent.edit(text)

        assert 0 <= result.style_score <= 100

    def test_edit_preserves_meaning(self, editor_agent):
        """Test edit preserves core meaning of text."""
        text = "OpenAI выпустила GPT-5 15 марта 2026 года."
        result = editor_agent.edit(text)

        # Key facts should be preserved
        assert "OpenAI" in result.edited_text
        assert "GPT-5" in result.edited_text or "gpt-5" in result.edited_text.lower()
        assert "2026" in result.edited_text

    def test_edit_improves_flow(self, editor_agent):
        """Test edit improves text flow."""
        # Text with poor flow
        text = """
        OpenAI выпустила GPT-5.
        GPT-5 работает быстро.
        GPT-5 стоит дорого.
        """
        result = editor_agent.edit(text)

        # Should still contain key information
        assert "GPT-5" in result.edited_text or "gpt-5" in result.edited_text.lower()


class TestEditorAgentEdgeCases:
    """Edge case tests for EditorAgent."""

    @pytest.fixture
    def editor_agent(self):
        """Create EditorAgent."""
        return EditorAgent(model="gpt-4o-mini")

    def test_empty_text(self, editor_agent):
        """Test editing empty text."""
        result = editor_agent.edit("")

        assert result.original_text == ""
        assert result.edited_text == ""
        assert result.style_score == 0.0

    def test_whitespace_only_text(self, editor_agent):
        """Test editing whitespace-only text."""
        result = editor_agent.edit("   \n\n   ")

        assert result.style_score < 50

    def test_very_long_text(self, editor_agent):
        """Test editing very long text."""
        long_text = "Тест. " * 1000
        result = editor_agent.edit(long_text)

        assert len(result.edited_text) > 0
        assert result.style_score >= 0

    def test_special_characters_preserved(self, editor_agent):
        """Test special characters are preserved."""
        text = "GPT-5 (версия 1.0) — новая модель! Цена: $20/мес."
        result = editor_agent.edit(text)

        # Special chars should be preserved
        assert "(" in result.edited_text
        assert ")" in result.edited_text
        assert "$" in result.edited_text

    def test_emoji_preserved(self, editor_agent):
        """Test emojis are preserved during edit."""
        text = "🚀 GPT-5 вышел! 💡 Новая модель."
        result = editor_agent.edit(text)

        assert "🚀" in result.edited_text
        assert "💡" in result.edited_text

    def test_links_preserved(self, editor_agent):
        """Test links are preserved during edit."""
        text = "Подробнее: https://openai.com/gpt5"
        result = editor_agent.edit(text)

        assert "https://openai.com/gpt5" in result.edited_text

    def test_numbers_preserved(self, editor_agent):
        """Test numbers and metrics are preserved."""
        text = "Скорость: 3x. Цена: $20. Дата: 15.03.2026. 85% довольны."
        result = editor_agent.edit(text)

        # Numbers should be preserved
        assert "3x" in result.edited_text
        assert "$20" in result.edited_text
        assert "85%" in result.edited_text


class TestEditChangeTracking:
    """Tests for change tracking functionality."""

    @pytest.fixture
    def editor_agent(self):
        """Create EditorAgent."""
        return EditorAgent(model="gpt-4o-mini")

    def test_change_has_reason(self, editor_agent):
        """Test each change has a reason."""
        original = "Это важно отметить тест."
        edited = "Это тест."

        changes = editor_agent._extract_changes(original, edited)

        for change in changes:
            assert change.reason is not None
            assert len(change.reason) > 0

    def test_change_type_categorization(self, editor_agent):
        """Test changes are categorized by type."""
        # Tone change (removing filler)
        text_with_filler = "Важно отметить, что AI важен."
        result = editor_agent.edit(text_with_filler)

        # Should have at least one change with a type
        if len(result.changes) > 0:
            valid_types = ["tone", "flow", "hook", "clarity"]
            for change in result.changes:
                assert change.type in valid_types

    def test_no_false_positives_on_good_text(self, editor_agent):
        """Test good text doesn't generate false change reports."""
        good_text = "OpenAI выпустила GPT-5 15 марта 2026. Модель работает в 3 раза быстрее."
        result = editor_agent.edit(good_text)

        # Good text should have minimal changes
        # Style score should be relatively high
        assert result.style_score >= 50
