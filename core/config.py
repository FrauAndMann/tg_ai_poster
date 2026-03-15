"""
Configuration module using Pydantic BaseSettings.

Loads configuration from both config.yaml and environment variables.
Environment variables take precedence over config file values.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file at module level
load_dotenv()


class TelegramConfig(BaseSettings):
    """Telegram bot configuration."""

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")

    bot_token: str = Field(default="", description="Telegram bot token from @BotFather")
    channel_id: str = Field(default="", description="Target channel ID or username")
    posting_mode: Literal["bot", "telethon"] = Field(
        default="bot",
        description="Publishing mode: 'bot' for Bot API, 'telethon' for user account"
    )
    proxy: str = Field(
        default="",
        description="Proxy URL for Telegram API (e.g., http://127.0.0.1:7890 or socks5://127.0.0.1:1080)"
    )


class TelethonConfig(BaseSettings):
    """Telethon (user account) configuration."""

    model_config = SettingsConfigDict(env_prefix="TELETHON_")

    api_id: int = Field(default=0, description="Telegram API ID from my.telegram.org")
    api_hash: str = Field(default="", description="Telegram API Hash from my.telegram.org")
    phone: str = Field(default="", description="Phone number for user account")
    session_path: str = Field(
        default="sessions/user.session",
        description="Path to store Telethon session file"
    )


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")

    provider: Literal["openai", "claude", "deepseek", "glm", "claude-cli"] = Field(
        default="claude-cli",
        description="LLM provider to use (claude-cli uses GLM Coding Plan)"
    )
    model: str = Field(default="glm-5", description="Model name")
    api_key: str = Field(default="", description="API key for the LLM provider")
    base_url: str = Field(
        default="https://api.z.ai/api/paas/v4",
        description="API base URL (for OpenAI-compatible APIs)"
    )
    max_tokens: int = Field(default=2000, ge=100, le=4000, description="Max tokens in response")
    temperature: float = Field(
        default=0.9,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for generation"
    )

    # Provider-specific API URLs (fallbacks)
    glm_base_url: str = Field(
        default="https://api.z.ai/api/paas/v4",
        description="GLM-5 API base URL"
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL"
    )
    claude_base_url: str = Field(
        default="https://api.anthropic.com/v1",
        description="Claude API base URL"
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API base URL"
    )

    def get_base_url(self) -> str:
        """Get the base URL for the current provider."""
        if self.base_url and self.base_url != "https://api.z.ai/api/paas/v4":
            return self.base_url
        urls = {
            "glm": self.glm_base_url,
            "openai": self.openai_base_url,
            "claude": self.claude_base_url,
            "deepseek": self.deepseek_base_url,
        }
        return urls.get(self.provider, self.glm_base_url)


class ChannelConfig(BaseSettings):
    """Channel content configuration."""

    model_config = SettingsConfigDict(env_prefix="CHANNEL_")

    topic: str = Field(
        default="AI technologies and future of automation",
        description="Main topic/niche of the channel"
    )
    style: str = Field(
        default="Expert but accessible. Think pieces. No hype.",
        description="Writing style instructions"
    )
    language: str = Field(default="ru", description="Content language")
    post_length_min: int = Field(default=200, ge=50, description="Minimum post length")
    post_length_max: int = Field(default=900, le=4096, description="Maximum post length")
    emojis_per_post: int = Field(default=3, ge=0, le=10, description="Target emoji count")
    hashtags_count: int = Field(default=2, ge=0, le=5, description="Target hashtag count")


class ScheduleConfig(BaseSettings):
    """Posting schedule configuration."""

    model_config = SettingsConfigDict(env_prefix="SCHEDULE_", extra="ignore")

    type: Literal["interval", "fixed", "random"] = Field(
        default="fixed",
        description="Schedule type: interval, fixed times, or random"
    )
    interval_hours: int = Field(default=4, ge=1, le=24, description="Hours between posts")
    fixed_times: list[str] = Field(
        default=["09:30", "14:00", "20:00"],
        description="Fixed posting times in HH:MM format"
    )
    timezone: str = Field(default="Europe/Moscow", description="Timezone for scheduling")
    random_window_start: str = Field(
        default="10:00",
        description="Random window start time"
    )
    random_window_end: str = Field(
        default="22:00",
        description="Random window end time"
    )

    @field_validator("fixed_times")
    @classmethod
    def validate_fixed_times(cls, v: list[str]) -> list[str]:
        """Validate time format in fixed_times."""
        import re
        time_pattern = re.compile(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$")
        for time in v:
            if not time_pattern.match(time):
                raise ValueError(f"Invalid time format: {time}. Expected HH:MM format.")
        return v


class SourcesConfig(BaseSettings):
    """Content sources configuration."""

    model_config = SettingsConfigDict(env_prefix="SOURCES_", extra="ignore")

    rss_feeds: list[str] = Field(
        default_factory=lambda: [
            "https://feeds.feedburner.com/oreilly/radar",
            "https://rss.cnn.com/rss/edition_technology.rss",
        ],
        description="List of RSS feed URLs"
    )
    enable_rss: bool = Field(default=True, description="Enable RSS feed collection")
    rss_fetch_interval_hours: int = Field(
        default=6,
        ge=1,
        description="Hours between RSS fetches"
    )


class SafetyConfig(BaseSettings):
    """Safety and moderation configuration."""

    model_config = SettingsConfigDict(env_prefix="SAFETY_")

    manual_approval: bool = Field(
        default=False,
        description="Require manual approval before posting"
    )
    max_daily_posts: int = Field(default=6, ge=1, le=50, description="Maximum posts per day")
    min_interval_minutes: int = Field(
        default=60,
        ge=1,
        description="Minimum minutes between posts"
    )
    forbidden_words: list[str] = Field(
        default_factory=list,
        description="Words that should not appear in posts"
    )
    similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for duplicate detection"
    )
    max_regeneration_attempts: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Max attempts to regenerate failed posts"
    )


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = Field(
        default="sqlite:///./data/tg_poster.db",
        description="Database connection URL"
    )
    echo: bool = Field(default=False, description="Echo SQL queries for debugging")

    @field_validator("url")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        """Ensure database directory exists for SQLite."""
        if v.startswith("sqlite:///"):
            db_path = v.replace("sqlite:///", "")
            # Handle relative paths
            if not os.path.isabs(db_path):
                db_path = os.path.abspath(db_path)
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
        return v


class RedisConfig(BaseSettings):
    """Redis configuration for queuing (optional)."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    enabled: bool = Field(default=False, description="Enable Redis queue")
    url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")


class AdminConfig(BaseSettings):
    """Admin notification configuration."""

    model_config = SettingsConfigDict(env_prefix="ADMIN_", extra="ignore")

    telegram_id: int = Field(
        default=0,
        description="Admin Telegram ID for notifications"
    )
    notify_on_error: bool = Field(default=True, description="Send notifications on errors")
    notify_on_post: bool = Field(
        default=False,
        description="Send notifications after each post"
    )


class AdminBotConfig(BaseSettings):
    """Admin Bot configuration."""

    model_config = SettingsConfigDict(env_prefix="ADMIN_BOT_", extra="ignore")

    enabled: bool = Field(default=False, description="Enable admin bot")
    bot_token: str = Field(default="", description="Admin bot token")
    authorized_users: list[int] = Field(
        default_factory=list,
        description="List of authorized Telegram user IDs"
    )


class CircuitBreakerConfig(BaseSettings):
    """Circuit Breaker configuration."""

    model_config = SettingsConfigDict(env_prefix="CIRCUIT_BREAKER_", extra="ignore")


    llm_failure_threshold: int = Field(default=5, description="LLM failures before circuit opens")
    llm_recovery_timeout: float = Field(default=60.0, description="LLM recovery timeout in seconds")
    telegram_failure_threshold: int = Field(default=10, description="Telegram failures before circuit opens")
    telegram_recovery_timeout: float = Field(default=30.0, description="Telegram recovery timeout in seconds")
    sources_failure_threshold: int = Field(default=3, description="Source failures before circuit opens")
    sources_recovery_timeout: float = Field(default=120.0, description="Sources recovery timeout in seconds")


class BackupConfig(BaseSettings):
    """Backup configuration."""

    model_config = SettingsConfigDict(env_prefix="BACKUP_", extra="ignore")

    enabled: bool = Field(default=True, description="Enable automatic backups")
    backup_dir: str = Field(default="./backups", description="Backup directory path")
    include_chroma: bool = Field(default=True, description="Include ChromaDB in backups")


class MediaConfig(BaseSettings):
    """Media provider configuration."""

    model_config = SettingsConfigDict(env_prefix="MEDIA_", extra="ignore")

    enabled: bool = Field(default=False, description="Enable media fetching")
    unsplash_access_key: str = Field(default="", description="Unsplash API access key")
    pexels_api_key: str = Field(default="", description="Pexels API key (fallback)")


class Settings(BaseSettings):
    """
    Main application settings.

    Loads configuration from:
    1. config.yaml file (if exists)
    2. Environment variables (take precedence)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="TG AI Poster", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    dry_run: bool = Field(
        default=False,
        description="Dry run mode - don't actually post"
    )

    # Nested configurations
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    telethon: TelethonConfig = Field(default_factory=TelethonConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    channel: ChannelConfig = Field(default_factory=ChannelConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    media: MediaConfig = Field(default_factory=MediaConfig)
    admin_bot: AdminBotConfig = Field(default_factory=AdminBotConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)

    @classmethod
    def load_from_yaml(cls, config_path: str | Path = "config.yaml") -> dict[str, Any]:
        """Load configuration from YAML file."""
        config_path = Path(config_path)
        if not config_path.exists():
            return {}

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        # Expand environment variables in the config
        return cls._expand_env_vars(config_data)

    @staticmethod
    def _expand_env_vars(config: Any) -> Any:
        """Recursively expand environment variables in config values."""
        import re

        if isinstance(config, dict):
            return {k: Settings._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [Settings._expand_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Match ${VAR_NAME} pattern
            pattern = r"\$\{([^}]+)\}"

            def replace_env_var(match: re.Match) -> str:
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))

            return re.sub(pattern, replace_env_var, config)
        return config

    @classmethod
    def create(cls, config_path: str | Path = "config.yaml") -> "Settings":
        """
        Create settings instance from YAML file and environment variables.

        Environment variables take precedence over YAML values.
        """
        yaml_config = cls.load_from_yaml(config_path)

        # Build kwargs for nested models
        # Map top-level keys to nested structure
        kwargs = {}

        # Map of yaml keys to Settings field names
        key_mapping = {
            "telegram_bot_token": ("telegram", "bot_token"),
            "telegram_channel_id": ("telegram", "channel_id"),
            "telegram_posting_mode": ("telegram", "posting_mode"),
            "telethon_api_id": ("telethon", "api_id"),
            "telethon_api_hash": ("telethon", "api_hash"),
            "telethon_phone": ("telethon", "phone"),
            "telethon_session_path": ("telethon", "session_path"),
            "llm_provider": ("llm", "provider"),
            "llm_model": ("llm", "model"),
            "llm_api_key": ("llm", "api_key"),
            "llm_max_tokens": ("llm", "max_tokens"),
            "llm_temperature": ("llm", "temperature"),
            "llm_glm_base_url": ("llm", "glm_base_url"),
            "llm_openai_base_url": ("llm", "openai_base_url"),
            "llm_claude_base_url": ("llm", "claude_base_url"),
            "llm_deepseek_base_url": ("llm", "deepseek_base_url"),
            "channel_topic": ("channel", "topic"),
            "channel_style": ("channel", "style"),
            "channel_language": ("channel", "language"),
            "channel_post_length_min": ("channel", "post_length_min"),
            "channel_post_length_max": ("channel", "post_length_max"),
            "channel_emojis_per_post": ("channel", "emojis_per_post"),
            "channel_hashtags_count": ("channel", "hashtags_count"),
            "schedule_type": ("schedule", "type"),
            "schedule_interval_hours": ("schedule", "interval_hours"),
            "schedule_fixed_times": ("schedule", "fixed_times"),
            "schedule_timezone": ("schedule", "timezone"),
            "schedule_random_window_start": ("schedule", "random_window_start"),
            "schedule_random_window_end": ("schedule", "random_window_end"),
            "sources_rss_feeds": ("sources", "rss_feeds"),
            "sources_enable_rss": ("sources", "enable_rss"),
            "safety_manual_approval": ("safety", "manual_approval"),
            "safety_max_daily_posts": ("safety", "max_daily_posts"),
            "safety_min_interval_minutes": ("safety", "min_interval_minutes"),
            "safety_forbidden_words": ("safety", "forbidden_words"),
            "safety_similarity_threshold": ("safety", "similarity_threshold"),
            "database_url": ("database", "url"),
            "database_echo": ("database", "echo"),
            "admin_telegram_id": ("admin", "telegram_id"),
            "admin_notify_on_error": ("admin", "notify_on_error"),
            "admin_notify_on_post": ("admin", "notify_on_post"),
            "admin_bot_enabled": ("admin_bot", "enabled"),
            "admin_bot_token": ("admin_bot", "bot_token"),
            "admin_bot_authorized_users": ("admin_bot", "authorized_users"),
            "circuit_breaker_llm_failure_threshold": ("circuit_breaker", "llm_failure_threshold"),
            "circuit_breaker_llm_recovery_timeout": ("circuit_breaker", "llm_recovery_timeout"),
            "backup_enabled": ("backup", "enabled"),
            "backup_schedule": ("backup", "schedule"),
            "backup_backup_dir": ("backup", "backup_dir"),
        }

        # Process nested config from YAML (primary source)
        for section in ["telegram", "telethon", "llm", "channel", "schedule", "sources", "safety", "database", "redis", "admin", "admin_bot", "circuit_breaker", "backup"]:
            if section in yaml_config:
                if section not in kwargs:
                    kwargs[section] = {}
                # Merge with existing kwargs
                if isinstance(yaml_config[section], dict):
                    kwargs[section].update(yaml_config[section])

        return cls(**kwargs)


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings.create()


def reload_settings() -> Settings:
    """Force reload settings (clears cache)."""
    get_settings.cache_clear()
    return get_settings()
