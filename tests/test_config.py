"""
Tests for configuration module.

Tests settings loading, YAML parsing, and environment variables.
"""

import pytest

from core.config import (
    Settings,
    TelegramConfig,
    LLMConfig,
    ScheduleConfig,
    export_config_schema,
    diff_settings_from_defaults,
    validate_startup_config,
)


class TestTelegramConfig:
    """Tests for TelegramConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = TelegramConfig()
        assert config.posting_mode == "bot"
        # bot_token may be set from .env, so we just check the type
        assert isinstance(config.bot_token, str)

    def test_env_prefix(self):
        """Test environment variable prefix."""
        # TelegramConfig uses env_prefix="TELEGRAM_", so telegram_bot_token
        # is an extra field not in the model
        config = TelegramConfig(bot_token="test_token")
        assert config.bot_token == "test_token"


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LLMConfig()
        # Defaults are for claude-cli/GLM provider
        assert config.provider == "claude-cli"
        assert config.model == "glm-5"
        assert config.temperature == 0.9

    def test_get_base_url(self):
        """Test base URL getter."""
        config = LLMConfig()
        url = config.get_base_url()
        # Default provider is claude-cli, which uses glm_base_url
        assert url == "https://api.z.ai/api/paas/v4"

    def test_custom_base_url(self):
        """Test custom base URL."""
        config = LLMConfig(base_url="https://custom.api.com")
        url = config.get_base_url()
        assert url == "https://custom.api.com"

    def test_openai_provider_url(self):
        """Test OpenAI provider URL."""
        config = LLMConfig(provider="openai")
        url = config.get_base_url()
        assert url == "https://api.openai.com/v1"


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
        # Invalid time format should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            ScheduleConfig(fixed_times=["09:00", "14:00", "invalid"])


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
realtime:
  enabled: false
media:
  enabled: true
sources:
  max_articles_per_feed: 15
"""
        yaml_path = tmp_path / "create_config.yaml"
        yaml_path.write_text(yaml_content)

        settings = Settings.create(yaml_path)

        assert settings.telegram.bot_token == "test_token"
        assert settings.llm.model == "gpt-4-turbo"
        assert settings.realtime.enabled is False
        assert settings.media.enabled is True
        assert settings.sources.max_articles_per_feed == 15

    def test_export_config_schema_contains_new_sections(self):
        """Test config schema export helper."""
        schema = export_config_schema()

        assert "sources" in schema
        assert "realtime" in schema
        assert "request_retries" in schema["sources"]
        assert "entity_cooldown_minutes" in schema["realtime"]

    def test_diff_settings_from_defaults(self):
        """Test default diff helper."""
        settings = Settings()
        settings.sources.request_retries = 4
        settings.realtime.entity_cooldown_minutes = 60

        diff = diff_settings_from_defaults(settings)

        assert diff["sources"]["request_retries"] == 4
        assert diff["realtime"]["entity_cooldown_minutes"] == 60

    def test_validate_startup_config_detects_aggressive_disable_policy(self):
        """Test startup validation for conflicting source settings."""
        settings = Settings()
        settings.sources.request_retries = 3
        settings.sources.disable_after_failures = 2

        issues = validate_startup_config(settings, dry_run=True)

        assert any("disable_after_failures" in issue for issue in issues)
