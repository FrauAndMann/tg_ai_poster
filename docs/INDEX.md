# TG AI Poster - Документация

## Содержание

1. [Введение](#введение)
2. [Архитектура](#архитектура)
3. [Установка](#установка)
4. [Конфигурация](#конфигурация)
5. [Использование](#использование)
6. [API Reference](#api-reference)
7. [Тестирование](#тестирование)
8. [Развертывание](#развертывание)
9. [Устранение неполадок](#устранение-неполадок)

---

## Введение

TG AI Poster - это автономная система для управления Telegram-каналом с использованием LLM (GPT-4o, Claude, DeepSeek).

### Ключевые возможности

- **Автогенерация постов**: Создание уникального контента с помощью AI
- **Умный выбор тем**: AI анализирует источники и выбирает лучшие темы
- **Проверка качества**: Автоматическая валидация постов перед публикацией
- **Дедупликация**: Избежание повторов на основе similarity analysis
- **Гибкое расписание**: Интервалы, фиксированное время или случайное
- **Два режима публикации**: Bot API (безопасно) или Telethon (аккаунт)

### Системные требования

- Python 3.11+
- 512MB RAM минимум
- Доступ к API LLM (OpenAI/Claude/DeepSeek)
- Telegram Bot Token или аккаунт

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      MAIN.PY (Entry Point)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────▼──────────────────┐
        │            SCHEDULER                 │
        │    (APScheduler: interval/fixed)    │
        └──────────────────┬──────────────────┘
                           │
        ┌──────────────────▼──────────────────┐
        │         PIPELINE ORCHESTRATOR        │
        └──────────────────┬──────────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    │                      │                      │
┌───▼───┐  ┌───────────┐  ┌─▼──────┐  ┌─────────▼─────┐
│Source │─▶│  Content  │─▶│ Topic  │─▶│    Prompt     │
│Collect│  │  Filter   │  │Select  │  │   Builder     │
└───────┘  └───────────┘  └────────┘  └───────────────┘
                                              │
                           ┌──────────────────▼──────────────────┐
                           │          LLM GENERATOR              │
                           │   (OpenAI / Claude / DeepSeek)      │
                           └──────────────────┬──────────────────┘
                                              │
                           ┌──────────────────▼──────────────────┐
                           │        QUALITY CHECKER              │
                           └──────────────────┬──────────────────┘
                                              │
                           ┌──────────────────▼──────────────────┐
                           │           FORMATTER                 │
                           │      (Telegram MarkdownV2)          │
                           └──────────────────┬──────────────────┘
                                              │
        ┌─────────────────────────────────────┴─────────────────────┐
        │                                                           │
┌───────▼────────┐                                    ┌─────────────▼───────┐
│  BOT PUBLISHER │                                    │ TELETHON PUBLISHER  │
│  (Mode A)      │                                    │ (Mode B)            │
│  Safe, Official│                                    │ Risky, Full Access  │
└────────────────┘                                    └─────────────────────┘
        │                                                           │
        └──────────────────────────┬────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      MEMORY / STORAGE       │
                    │  (SQLite / PostgreSQL)      │
                    │  - Posts History            │
                    │  - Topics & Embeddings      │
                    │  - Sources & Metrics        │
                    └─────────────────────────────┘
```

### Модули

| Модуль | Назначение |
|--------|------------|
| `core/` | Конфигурация, логирование, планировщик |
| `pipeline/` | Генерация контента (8 этапов) |
| `publisher/` | Публикация в Telegram |
| `memory/` | База данных и хранилища |
| `llm/` | Адаптеры для LLM провайдеров |
| `utils/` | Retry, rate limiting, валидация |

---

## Установка

### Локальная установка

```bash
# 1. Клонирование
git clone https://github.com/your-repo/tg-ai-poster.git
cd tg-ai-poster

# 2. Виртуальное окружение
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate

# 3. Установка зависимостей
pip install -r requirements.txt

# 4. Создание директорий
mkdir -p data logs sessions
```

### Docker установка

```bash
# Сборка образа
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
# Полный стек с PostgreSQL и Redis
docker-compose up -d

# Логи
docker-compose logs -f app
```

---

## Конфигурация

### Переменные окружения (.env)

```bash
# === TELEGRAM BOT (Mode A) ===
# Получить у @BotFather
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# ID канала: @username или -1001234567890
TELEGRAM_CHANNEL_ID=@your_channel

# === TELETHON (Mode B) ===
# Получить на my.telegram.org
TELETHON_API_ID=12345678
TELETHON_API_HASH=abcdef1234567890abcdef1234567890
TELETHON_PHONE=+79991234567

# === LLM API ===
OPENAI_API_KEY=sk-...

# === ADMIN ===
# Ваш Telegram ID для уведомлений (узнать у @userinfobot)
ADMIN_TELEGRAM_ID=123456789
```

### config.yaml

```yaml
# Режим публикации
telegram:
  posting_mode: "bot"  # или "telethon"

# LLM настройки
llm:
  provider: "openai"   # openai, claude, deepseek
  model: "gpt-4o"
  temperature: 0.85
  max_tokens: 800

# Контент канала
channel:
  topic: "Ваша тема канала"
  style: "Стиль написания"
  language: "ru"
  post_length_min: 200
  post_length_max: 900
  emojis_per_post: 3
  hashtags_count: 2

# Расписание
schedule:
  type: "fixed"        # interval, fixed, random
  fixed_times:
    - "09:30"
    - "14:00"
    - "20:00"
  timezone: "Europe/Moscow"

# Источники контента
sources:
  rss_feeds:
    - "https://example.com/feed.rss"

# Безопасность
safety:
  max_daily_posts: 6
  min_interval_minutes: 60
  manual_approval: false
```

---

## Использование

### Команды

```bash
# Обычный запуск (по расписанию)
python main.py

# Один пост и выход
python main.py --once

# Тестовый режим (без публикации)
python main.py --dry-run --once

# Инициализация БД
python main.py --init-db

# Отладка
python main.py --debug

# Свой конфиг
python main.py --config my-config.yaml
```

### Примеры использования

#### Тестирование без публикации

```bash
python main.py --dry-run --once --debug
```

#### Запуск на VPS

```bash
# В screen/tmux
screen -S tg-poster
python main.py

# Или через systemd
sudo systemctl start tg-ai-poster
```

#### Docker

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск
docker-compose restart app

# Логи
docker-compose logs -f app
```

---

## API Reference

### Core

#### Settings

```python
from core.config import Settings, get_settings

# Загрузка настроек
settings = get_settings()

# Доступ к параметрам
print(settings.telegram.bot_token)
print(settings.channel.topic)
print(settings.schedule.type)
```

#### Scheduler

```python
from core.scheduler import Scheduler

scheduler = Scheduler(settings, job_func)
scheduler.start()           # Запуск
scheduler.stop()            # Остановка
scheduler.pause()           # Пауза
scheduler.resume()          # Продолжить
scheduler.run_job_now()     # Запустить сейчас
```

### Pipeline

#### PipelineOrchestrator

```python
from pipeline.orchestrator import PipelineOrchestrator

orchestrator = PipelineOrchestrator(settings, db, publisher)

# Запуск pipeline
result = await orchestrator.run(dry_run=False)

print(result.success)       # True/False
print(result.post_id)       # ID поста
print(result.content)       # Контент
print(result.quality_score) # Оценка качества
```

### Publisher

#### BotPublisher

```python
from publisher import BotPublisher

publisher = BotPublisher(
    bot_token="token",
    channel_id="@channel"
)

await publisher.start()
message_id = await publisher.send_post("Hello!")
await publisher.stop()
```

### Memory

#### PostStore

```python
from memory.post_store import PostStore

store = PostStore(db)

# Создать пост
post = await store.create(content="...", topic="...")

# Получить последние
posts = await store.get_recent(limit=10)

# Статистика
stats = await store.get_stats(days=30)
```

---

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=. --cov-report=html

# Конкретный файл
pytest tests/test_validators.py

# Подробный вывод
pytest -v
```

### Структура тестов

```
tests/
├── conftest.py           # Фикстуры
├── test_config.py        # Тесты конфигурации
├── test_validators.py    # Тесты валидаторов
├── test_pipeline.py      # Тесты pipeline
├── test_publisher.py     # Тесты publisher
└── test_memory.py        # Тесты БД
```

---

## Развертывание

### VPS (Ubuntu 22.04)

```bash
# 1. Подготовка сервера
sudo apt update
sudo apt install python3.11 python3.11-venv

# 2. Создание пользователя
sudo useradd -m -s /bin/bash tg-poster

# 3. Копирование проекта
sudo -u tg-poster git clone ... /opt/tg-ai-poster

# 4. Установка
cd /opt/tg-ai-poster
sudo -u tg-poster python3.11 -m venv venv
sudo -u tg-poster venv/bin/pip install -r requirements.txt

# 5. Systemd сервис
sudo nano /etc/systemd/system/tg-ai-poster.service
```

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
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
# 6. Запуск
sudo systemctl daemon-reload
sudo systemctl enable tg-ai-poster
sudo systemctl start tg-ai-poster

# Логи
sudo journalctl -u tg-ai-poster -f
```

---

## Устранение неполадок

### Частые проблемы

#### Bot не может опубликовать

```
Ошибка: ChatNotFound / Forbidden
```

**Решение:**
1. Проверьте, что бот добавлен в канал
2. Проверьте, что бот - администратор
3. Проверьте право "Публикация сообщений"

#### Ошибка LLM API

```
Ошибка: Rate limit exceeded
```

**Решение:**
1. Проверьте баланс API
2. Уменьшите частоту запросов
3. Добавьте задержку между запросами

#### Telethon не подключается

```
Ошибка: SessionPasswordNeededError
```

**Решение:**
1. Введите пароль 2FA
2. Или отключите 2FA временно

#### База данных заблокирована

```
Ошибка: database is locked
```

**Решение:**
1. Используйте PostgreSQL для продакшена
2. Или увеличьте timeout SQLite

### Логирование

```bash
# Просмотр логов
tail -f logs/tg_poster_*.log

# Только ошибки
grep ERROR logs/tg_poster_*.log
```

### Диагностика

```bash
# Проверка конфигурации
python -c "from core.config import get_settings; s=get_settings(); print(s.model_dump())"

# Проверка БД
python main.py --init-db

# Тестовый пост
python main.py --dry-run --once --debug
```
