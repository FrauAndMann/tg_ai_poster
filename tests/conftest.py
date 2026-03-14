"""
Pytest configuration and fixtures.

Provides common fixtures for testing the TG AI Poster application.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Configure asyncio
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Mock environment
@pytest.fixture
def mock_env(monkeypatch) -> dict:
    """Set up mock environment variables."""
    env_vars = {
        "TELEGRAM_BOT_TOKEN": "123456789:ABCtest_token",
        "TELEGRAM_CHANNEL_ID": "@test_channel",
        "TELETHON_API_ID": "12345678",
        "TELETHON_API_HASH": "abcdef1234567890abcdef1234567890",
        "TELETHON_PHONE": "+79991234567",
        "OPENAI_API_KEY": "sk-test-key",
        "ADMIN_TELEGRAM_ID": "123456789",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


# Sample configuration
@pytest.fixture
def sample_config() -> dict:
    """Sample configuration for testing."""
    return {
        "telegram": {
            "bot_token": "123456789:ABCtest_token",
            "channel_id": "@test_channel",
            "posting_mode": "bot",
        },
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "sk-test-key",
            "max_tokens": 800,
            "temperature": 0.85,
        },
        "channel": {
            "topic": "AI technologies",
            "style": "Expert but accessible",
            "language": "ru",
            "post_length_min": 200,
            "post_length_max": 900,
            "emojis_per_post": 3,
            "hashtags_count": 2,
        },
        "schedule": {
            "type": "fixed",
            "fixed_times": ["09:30", "14:00", "20:00"],
            "timezone": "Europe/Moscow",
        },
        "safety": {
            "max_daily_posts": 6,
            "min_interval_minutes": 60,
            "similarity_threshold": 0.85,
        },
        "database": {
            "url": "sqlite+aiosqlite:///:memory:",
        },
    }


# Sample post content
@pytest.fixture
def sample_post_content() -> str:
    """Sample post content for testing."""
    return """🤖 Искусственный интеллект меняет мир быстрее, чем мы думаем!

За последний год появились модели, которые могут:
• Писать код на уровне junior-разработчика
• Создавать изображения по текстовому описанию
• Анализировать данные и находить паттерны

Что это значит для нас? Нужно адаптироваться.

Главное — не бояться изменений, а учиться использовать новые инструменты.

#AI #технологии"""


# Sample article
@pytest.fixture
def sample_article() -> dict:
    """Sample article for testing."""
    return {
        "title": "GPT-5 Release Date Announced",
        "summary": "OpenAI announces the release date for GPT-5, promising significant improvements in reasoning and multimodal capabilities.",
        "url": "https://example.com/gpt5-announcement",
        "source": "Tech News",
        "tags": ["AI", "OpenAI", "GPT"],
    }


# Mock LLM response
@pytest.fixture
def mock_llm_response() -> str:
    """Mock LLM response for testing."""
    return """🚀 Новая эра AI уже началась!

GPT-5 обещает революцию в возможностях искусственного интеллекта. Главные улучшения:
• Лучшее понимание контекста
• Мультимодальные возможности
• Улучшенная логика рассуждений

Время готовиться к новым инструментам!

#AI #GPT5"""


# Mock OpenAI client
@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = AsyncMock()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Generated post content"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.model = "gpt-4o"
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 200
    mock_response.usage.total_tokens = 300
    mock_response.model_dump = MagicMock(return_value={})

    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_client.close = AsyncMock()

    return mock_client


# Mock Telegram bot
@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot for testing."""
    mock_bot = AsyncMock()

    # Mock get_me
    mock_me = MagicMock()
    mock_me.username = "test_bot"
    mock_bot.get_me = AsyncMock(return_value=mock_me)

    # Mock get_chat
    mock_chat = MagicMock()
    mock_chat.title = "Test Channel"
    mock_bot.get_chat = AsyncMock(return_value=mock_chat)

    # Mock send_message
    mock_message = MagicMock()
    mock_message.message_id = 12345
    mock_bot.send_message = AsyncMock(return_value=mock_message)

    # Mock edit_message_text
    mock_bot.edit_message_text = AsyncMock(return_value=True)

    # Mock delete_message
    mock_bot.delete_message = AsyncMock(return_value=True)

    # Mock pin_chat_message
    mock_bot.pin_chat_message = AsyncMock(return_value=True)

    return mock_bot


# In-memory database fixture
@pytest_asyncio.fixture
async def in_memory_db():
    """Create in-memory database for testing.

    This fixture is function-scoped to ensure test isolation.
    Each test gets its own fresh database instance.
    """
    from memory.database import Database

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # Initialize database
    await db.init()

    yield db

    # Cleanup
    await db.close()


# Settings fixture
@pytest.fixture
def test_settings(mock_env, tmp_path):
    """Create test settings."""
    from core.config import Settings

    # Create temp config file
    config_content = """
telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  channel_id: "${TELEGRAM_CHANNEL_ID}"
  posting_mode: "bot"

llm:
  provider: "openai"
  model: "gpt-4o"
  api_key: "${OPENAI_API_KEY}"
  max_tokens: 800
  temperature: 0.85

channel:
  topic: "Test Topic"
  style: "Test Style"
  language: "ru"
  post_length_min: 200
  post_length_max: 900
  emojis_per_post: 3
  hashtags_count: 2

schedule:
  type: "fixed"
  fixed_times: ["09:30", "14:00", "20:00"]
  timezone: "Europe/Moscow"

safety:
  max_daily_posts: 6
  min_interval_minutes: 60

database:
  url: "sqlite:///./data/test.db"
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)

    # Create temp .env file
    env_path = tmp_path / ".env"
    env_path.write_text("\n".join(f"{k}={v}" for k, v in mock_env.items()))

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    yield Settings.create(config_path)

    os.chdir(original_cwd)


# Pipeline result fixture
@pytest.fixture
def pipeline_result():
    """Sample pipeline result for testing."""
    from pipeline.orchestrator import PipelineResult

    return PipelineResult(
        success=True,
        post_id=1,
        content="Test post content",
        topic="Test topic",
        quality_score=85.0,
        duration=2.5,
    )
