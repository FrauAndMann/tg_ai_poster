# TG AI Poster

[![Tests](https://github.com/FrauAndMann/tg_ai_poster/actions/workflows/test.yml/badge.svg)](https://github.com/FrauAndMann/tg_ai_poster/actions/workflows/test.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-orange.svg)](https://github.com/astral-sh/ruff)

Автономная AI-система для управления Telegram-каналом 24/7 без участия человека.

## Возможности

- **Автоматическая генерация постов** с использованием GPT-4o, Claude, DeepSeek или GLM-5
- **Планировщик постов** с поддержкой интервалов, фиксированного времени и случайного расписания
- **Сбор контента** из RSS-лент, HackerNews и ProductHunt
- **AI-выбор тем** с анализом релевантности
- **Агент-критик** для улучшения качества постов перед публикацией
- **Строгая валидация контента** - защита от LLM-артефактов и некорректных постов
- **Семантическая дедупликация** через ChromaDB - никогда не повторяется по смыслу
- **Обучение на метриках** - система учится на лучших постах
- **Два режима публикации**: Bot API (безопасно) и Telethon (аккаунт пользователя)
- **Мастер настройки** для быстрого старта

## Быстрый старт

### 1. Установка

```bash
# Клонирование
git clone https://github.com/FrauAndMann/tg_ai_poster.git
cd tg_ai_poster

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Настройка через мастер

```bash
# Интерактивный мастер настройки
python setup.py
```

Мастер поможет:
- Настроить Telegram бота
- Выбрать LLM провайдера
- Указать тему и стиль канала
- Настроить расписание
- Создать конфигурационные файлы

### 3. Или ручная настройка

```bash
# Копирование шаблона окружения
cp .env.example .env

# Редактирование .env
# Заполните:
# - TELEGRAM_BOT_TOKEN (от @BotFather)
# - TELEGRAM_CHANNEL_ID (ваш канал)
# - OPENAI_API_KEY (от platform.openai.com)
```

### 4. Запуск

```bash
# Инициализация базы данных
python main.py --init-db

# Тестовый запуск (без публикации)
python main.py --dry-run --once

# Запуск по расписанию
python main.py
```

## Режимы публикации

### Mode A: Bot API (Рекомендуется)

**Как работает:**
- Использует официальный Telegram Bot API
- Бот должен быть администратором канала
- Посты помечаются "via @botname"

**Настройка:**
1. Создайте бота через @BotFather
2. Получите токен бота
3. Добавьте бота в канал как администратора
4. Выдайте право "Публикация сообщений"

**Плюсы:**
- Официальный API, нет риска бана
- Простая настройка
- Надежность

**Минусы:**
- Видна метка бота
- Бот должен быть админом

### Mode B: Telethon (Аккаунт пользователя)

> **ВНИМАНИЕ:** Используйте ТОЛЬКО на отдельном аккаунте!

**Как работает:**
- Подключается как обычный пользователь
- Посты выглядят как личные сообщения
- Требуется авторизация по телефону

**Настройка:**
1. Получите API ID и Hash на my.telegram.org
2. При первом запуске введите код из SMS
3. Сессия сохраняется для повторных запусков

**Плюсы:**
- Посты выглядят как личные
- Полный доступ к функциям

**Минусы:**
- Риск бана аккаунта
- Нарушение ToS Telegram
- Сложнее настройка

## Конфигурация

### config.yaml

```yaml
telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  channel_id: "@your_channel"
  posting_mode: "bot"

llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.85

channel:
  topic: "AI технологии и автоматизация"
  style: "Экспертно, но доступно"
  language: "ru"

schedule:
  type: "fixed"
  fixed_times: ["09:30", "14:00", "20:00"]
  timezone: "Europe/Moscow"
```

### Переменные окружения (.env)

```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHANNEL_ID=@your_channel

# LLM
OPENAI_API_KEY=sk-...

# Admin (для уведомлений)
ADMIN_TELEGRAM_ID=123456789
```

## Развертывание

### Docker

```bash
# Сборка
docker build -t tg-ai-poster .

# Запуск
docker run -d \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.yaml:/app/config.yaml \
  tg-ai-poster
```

### Docker Compose

```bash
# Запуск с PostgreSQL и Redis
docker-compose up -d

# Просмотр логов
docker-compose logs -f app
```

### VPS (Systemd)

1. Создайте сервис `/etc/systemd/system/tg-ai-poster.service`:

```ini
[Unit]
Description=TG AI Poster
After=network.target

[Service]
Type=simple
User=tg-poster
WorkingDirectory=/opt/tg-ai-poster
ExecStart=/opt/tg-ai-poster/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. Активация:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tg-ai-poster
sudo systemctl start tg-ai-poster
```

## Команды

```bash
python main.py              # Запуск по расписанию
python main.py --dry-run    # Тестовый режим
python main.py --once       # Один пост и выход
python main.py --init-db    # Инициализация БД
python main.py --debug      # Режим отладки
```

## Тестирование

```bash
# Запуск всех тестов
pytest

# Запуск с покрытием кода
pytest --cov=. --cov-report=html

# Запуск конкретного теста
pytest tests/test_content_validator.py -v
```

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                         │
│              core/scheduler.py — APScheduler                │
└──────────────────────────┬──────────────────────────────────┘
                           │ triggers pipeline every N hours
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT PIPELINE                         │
│                                                             │
│  [1] SourceCollector   — RSS, HackerNews, ProductHunt      │
│         ↓                                                   │
│  [2] ContentFilter     — dedup, relevance scoring          │
│         ↓                                                   │
│  [3] TopicSelector     — Agent picks best topic via LLM    │
│         ↓                                                   │
│  [4] PromptBuilder     — injects style, history, examples  │
│         ↓                                                   │
│  [5] LLMGenerator      — Agent-Editor writes draft         │
│         ↓                                                   │
│  [6] ContentValidator  — LLM meta-text detection           │
│         ↓                                                   │
│  [7] AgentCritic       — Agent-Critic improves draft       │
│         ↓                                                   │
│  [8] QualityChecker    — length, emoji, markdown, dedup    │
│         ↓                                                   │
│  [9] Formatter         — Telegram MarkdownV2 formatting    │
│         ↓                                                   │
│ [10] ApprovalGate      — auto or manual (Telegram DM)      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      PUBLISHER                              │
│                                                             │
│  Mode A: BotPublisher    — python-telegram-bot              │
│  Mode B: TelethonPublisher — user account session           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   MEMORY & LEARNING                         │
│                                                             │
│  SQLAlchemy DB  — post history, topics, engagement          │
│  ChromaDB       — vector embeddings for semantic dedup      │
│  FeedbackLoop   — learns from reactions, updates style      │
└─────────────────────────────────────────────────────────────┘
```

### Структура проекта

```
tg_ai_poster/
├── main.py              # Точка входа
├── setup.py             # Мастер настройки
├── config.yaml          # Конфигурация
│
├── core/                # Ядро
│   ├── config.py        # Загрузка настроек
│   ├── logger.py        # Логирование
│   └── scheduler.py     # Планировщик
│
├── pipeline/            # Pipeline генерации
│   ├── orchestrator.py  # Координатор
│   ├── source_collector.py  # RSS, HN, ProductHunt
│   ├── content_filter.py
│   ├── content_validator.py # Валидация LLM контента
│   ├── topic_selector.py
│   ├── prompt_builder.py
│   ├── llm_generator.py
│   ├── agent_critic.py  # AI-критик для улучшения
│   ├── quality_checker.py
│   └── formatter.py
│
├── publisher/           # Публикация
│   ├── base.py          # Абстрактный класс
│   ├── bot_publisher.py
│   └── telethon_publisher.py
│
├── memory/              # Хранение
│   ├── models.py        # SQLAlchemy модели
│   ├── database.py
│   ├── post_store.py
│   ├── topic_store.py
│   ├── vector_store.py  # ChromaDB дедупликация
│   └── feedback_loop.py # Обучение на метриках
│
├── llm/                 # LLM провайдеры
│   ├── base.py          # Абстрактный адаптер
│   ├── openai_adapter.py
│   ├── claude_adapter.py
│   ├── deepseek_adapter.py
│   └── prompts/
│       ├── system_prompt.txt
│       ├── post_generator.txt
│       ├── topic_selector.txt
│       ├── agent_critic.txt
│       └── style_analyzer.txt
│
├── tests/               # Тесты
│   ├── conftest.py      # Фикстуры pytest
│   ├── test_memory.py
│   └── test_content_validator.py
│
└── utils/               # Утилиты
    ├── retry.py
    ├── rate_limiter.py
    └── validators.py
```

## Безопасность

1. **Никогда не коммитьте .env файл**
2. Используйте Bot API вместо Telethon для продакшена
3. Ограничьте daily_posts для избежания спама
4. Настройте manual_approval для контроля контента

## Contributing

1. Fork репозитория
2. Создайте ветку для фичи (`git checkout -b feature/amazing-feature`)
3. Закоммитьте изменения (`git commit -m 'Add amazing feature'`)
4. Запушьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## Лицензия

MIT License - см. [LICENSE](LICENSE) файл.
