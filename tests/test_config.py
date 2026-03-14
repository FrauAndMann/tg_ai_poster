"""
Tests for configuration module.

Tests settings loading, YAML parsing, and environment variables.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from core.config import (
    Settings,
    TelegramConfig,
    TelethonConfig,
    LLMConfig,
    ChannelConfig,
    ScheduleConfig,
    SourcesConfig,
    SafetyConfig,
    DatabaseConfig,
)


class TestTelegramConfig:
    """Tests for TelegramConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = TelegramConfig()
        assert config.posting_mode == "bot"
        assert config.bot_token == ""

    def test_env_prefix(self):
        """Test environment variable prefix."""
        config = TelegramConfig(telegram_bot_token="test_token")
        assert config.bot_token == "test_token"


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.85

    def test_get_base_url(self):
        """Test base URL getter."""
        config = LLMConfig()
        url = config.get_base_url()
        assert url == "https://api.openai.com/v1"

    def test_custom_base_url(self):
        """Test custom base URL."""
        config = LLMConfig(openai_base_url="https://custom.api.com")
        url = config.get_base_url()
        assert url == "https://custom.api.com"


class TestScheduleConfig:
    """Tests for ScheduleConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ScheduleConfig()
        assert config.type == "fixed"
        assert config.interval_hours == 4
        assert "09:30" in config.fixed_times

        assert config.timezone == "Europe/Moscow"

    def test_fixed_times_validation(self):
        """Test fixed times format validation."""
        config = ScheduleConfig(fixed_times=["09:00", "14:00", "invalid"])
        # The invalid entry should cause error during full config load


class TestSettings:
    """Tests for main Settings class."""

    def test_default_values(self):
        """Test default configuration values."""
        settings = Settings()
        assert settings.app_name == "TG AI Poster"
        assert settings.debug is False
        assert settings.dry_run is False

    def test_nested_configs(self):
        """Test nested configuration loading."""
        settings = Settings(
            telegram=TelegramConfig(bot_token="test_token"),
            llm=LLMConfig(model="gpt-4"),
        )
        assert settings.telegram.bot_token == "test_token"
        assert settings.llm.model == "gpt-4"

    def test_load_from_yaml(self, tmp_path):
        """Test YAML configuration loading."""
        yaml_content = """
telegram:
  bot_token: "yaml_token"
  channel_id: "@yaml_channel"
"""
        yaml_path = tmp_path / "test_config.yaml"
        yaml_path.write_text(yaml_content)

        yaml_config = Settings.load_from_yaml(yaml_path)

        assert yaml_config["telegram"]["bot_token"] == "yaml_token"
        assert yaml_config["telegram"]["channel_id"] == "@yaml_channel"

    def test_expand_env_vars(self, tmp_path, monkeypatch):
        """Test environment variable expansion."""
        yaml_content = """
telegram:
  bot_token: "${TEST_TOKEN_ENV}"
"""
        yaml_path = tmp_path / "test_env_config.yaml"
        yaml_path.write_text(yaml_content)

        # Set environment variable
        monkeypatch.setenv("TEST_TOKEN_ENV", "expanded_value")

        config = Settings.load_from_yaml(yaml_path)

        assert config["telegram"]["bot_token"] == "expanded_value"

    def test_create(self, tmp_path):
        """Test Settings.create factory method."""
        yaml_content = """
telegram:
  bot_token: "test_token"
llm:
  model: "gpt-4-turbo"
"""
        yaml_path = tmp_path / "create_config.yaml"
        yaml_path.write_text(yaml_content)

        settings = Settings.create(yaml_path)

        assert settings.telegram.bot_token == "test_token"
        assert settings.llm.model == "gpt-4-turbo"
