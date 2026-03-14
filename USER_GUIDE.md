# Руководство пользователя TG AI Poster

## Содержание

1. [Введение](#введение)
2. [Установка](#установка)
3. [Первая настройка](#первая-настройка)
4. [Конфигурация](#конфигурация)
5. [Запуск системы](#запуск-системы)
6. [Режимы работы](#режимы-работы)
7. [Управление контентом](#управление-контентом)
8. [Мониторинг и логи](#мониторинг-и-логи)
9. [Устранение неполадок](#устранение-неполадок)
10. [Продвинутые настройки](#продвинутые-настройки)

---

## Введение

**TG AI Poster** — автономная система для управления Telegram-каналом, которая:

- Автоматически генерирует уникальный контент с помощью ИИ
- Публикует посты по расписанию без вашего участия
- Учится на реакции аудитории и улучшает контент
- Никогда не повторяется благодаря семантической дедупликации

### Что умеет система

| Функция | Описание |
|---------|----------|
| Сбор тем | RSS-ленты, HackerNews, ProductHunt |
| Генерация | GPT-4o, Claude, DeepSeek на выбор |
| Критика | AI-критик улучшает каждый пост |
| Дедупликация | Семантическая проверка на повторы |
| Обучение | Анализ успешных постов |
| Публикация | Bot API или Telethon |

---

## Установка

### Требования

- Python 3.11 или выше
- Telegram-бот (создается через @BotFather)
- API-ключ OpenAI / Anthropic / DeepSeek

### Шаг 1: Получение зависимостей

```bash
# Клонируйте репозиторий
git clone https://github.com/your-repo/tg-ai-poster.git
cd tg-ai-poster

# Создайте виртуальное окружение
python -m venv venv

# Активируйте окружение
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt
```

### Шаг 2: Создание Telegram-бота

1. Откройте Telegram и найдите **@BotFather**
2. Отправьте команду `/newbot`
3. Придумайте имя бота (например: "My Channel Bot")
4. Придумайте username (например: "mychannel_ai_bot")
5. Скопируйте полученный токен вида `123456789:ABCdefGHI...`

### Шаг 3: Добавление бота в канал

1. Откройте настройки вашего канала
2. Перейдите в "Administrators" → "Add Admin"
3. Найдите вашего бота по username
4. Добавьте бота с правами "Post Messages"

### Шаг 4: Получение ID канала

```
Для публичных каналов:
- Используйте @username (например: @mychannel)

Для приватных каналов:
1. Перешлите любое сообщение из канала боту @userinfobot
2. Бот покажет ID вида -1001234567890
```

---

## Первая настройка

### Автоматическая настройка (рекомендуется)

```bash
python setup.py
```

Мастер настроит:
- Telegram бота и канал
- LLM-провайдера
- Тему и стиль канала
- Расписание публикаций

### Ручная настройка

#### 1. Создайте файл `.env`

```bash
cp .env.example .env
```

#### 2. Заполните `.env`

```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...
TELEGRAM_CHANNEL_ID=@your_channel

# LLM (выберите один)
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# DEEPSEEK_API_KEY=sk-...

# Admin (для уведомлений об ошибках)
ADMIN_TELEGRAM_ID=123456789
```

#### 3. Отредактируйте `config.yaml`

```yaml
channel:
  topic: "Ваша тема канала"
  style: "Ваш стиль (экспертный, развлекательный...)"
  language: "ru"

schedule:
  type: "fixed"
  fixed_times:
    - "09:00"
    - "14:00"
    - "19:00"
  timezone: "Europe/Moscow"
```

---

## Конфигурация

### Основные настройки config.yaml

#### Тема и стиль канала

```yaml
channel:
  # Тема канала — определяет о чём будут посты
  topic: "AI инструменты для бизнеса и фрилансеров"

  # Стиль письма
  style: >
    Эксперт-практик. Без хайпа.
    Реальные кейсы. Дружелюбно, но профессионально.

  # Язык контента
  language: "ru"

  # Длина поста
  post_length_min: 250
  post_length_max: 900

  # Количество эмодзи и хештегов
  emojis_per_post: 3
  hashtags_count: 2
```

#### Расписание публикаций

```yaml
schedule:
  # Тип: "fixed", "interval", или "random"
  type: "fixed"

  # Для fixed — конкретное время
  fixed_times:
    - "09:30"
    - "14:00"
    - "20:00"

  # Для interval — каждые N часов
  # interval_hours: 4

  # Для random — случайное время в окне
  # random_window_start: "10:00"
  # random_window_end: "22:00"

  timezone: "Europe/Moscow"
```

#### Источники контента

```yaml
sources:
  rss_feeds:
    - "https://feeds.feedburner.com/oreilly/radar"
    - "https://hnrss.org/frontpage"
    - "https://www.reddit.com/r/artificial/hot/.rss"
```

#### Безопасность

```yaml
safety:
  # Ручное подтверждение каждого поста
  manual_approval: false

  # Максимум постов в день
  max_daily_posts: 6

  # Минимальный интервал между постами (минуты)
  min_interval_minutes: 60

  # Порог схожести (0.85 = 85%)
  similarity_threshold: 0.85

  # Запрещённые слова
  forbidden_words: []
```

### Переменные окружения .env

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Да | Токен бота от @BotFather |
| `TELEGRAM_CHANNEL_ID` | Да | ID или @username канала |
| `OPENAI_API_KEY` | Да* | Ключ OpenAI |
| `ANTHROPIC_API_KEY` | Нет | Ключ Anthropic (Claude) |
| `DEEPSEEK_API_KEY` | Нет | Ключ DeepSeek |
| `ADMIN_TELEGRAM_ID` | Рекомендуется | Ваш Telegram ID для уведомлений |

\* Нужен хотя бы один LLM-ключ

---

## Запуск системы

### Инициализация базы данных

```bash
python main.py --init-db
```

### Тестовый запуск (без публикации)

```bash
# Сгенерировать пост, но не публиковать
python main.py --dry-run --once
```

Вывод покажет:
- Выбранную тему
- Сгенерированный контент
- Оценку качества
- Результат проверки критика

### Запуск по расписанию

```bash
python main.py
```

Система будет работать 24/7 и публиковать посты по расписанию.

### Однократный запуск

```bash
# Опубликовать один пост и выйти
python main.py --once
```

### Режим отладки

```bash
python main.py --debug
```

---

## Режимы работы

### Режим A: Bot API (рекомендуется)

**Преимущества:**
- Официальный API Telegram
- Нет риска бана
- Стабильная работа

**Недостатки:**
- Посты помечены "via @botname"
- Бот должен быть админом канала

**Настройка:**
```yaml
telegram:
  posting_mode: "bot"
```

### Режим B: Telethon (продвинутый)

**Преимущества:**
- Посты выглядят как личные
- Нет метки бота

**Недостатки:**
- Риск бана аккаунта
- Нарушение ToS Telegram
- Требуется отдельный аккаунт

**Настройка:**
```yaml
telegram:
  posting_mode: "telethon"

telethon:
  api_id: 12345678        # от my.telegram.org
  api_hash: "abc123..."   # от my.telegram.org
  phone: "+79991234567"   # номер аккаунта
```

**Важно:** Используйте ТОЛЬКО специально созданный аккаунт, не основной!

---

## Управление контентом

### Как работает генерация

```
1. Сбор тем → RSS, HackerNews, ProductHunt
2. Фильтрация → Удаление нерелевантного
3. Выбор темы → AI выбирает лучшую тему
4. Генерация → LLM пишет черновик
5. Критика → AI-критик улучшает пост
6. Проверка → Качество, дубликаты, формат
7. Публикация → Отправка в Telegram
8. Обучение → Анализ реакций аудитории
```

### Агент-критик

Критик оценивает каждый пост по 5 критериям (1-10):

| Критерий | Описание |
|----------|----------|
| hook_strength | Цепляет ли первое предложение |
| clarity | Понятность и лаконичность |
| emoji_naturalness | Естественность эмодзи |
| audience_value | Польза для аудитории |
| human_feel | Похоже ли на человека |

Если любой критерий ниже порога (по умолчанию 7), критик переписывает пост.

### Семантическая дедупликация

Система использует ChromaDB для проверки схожести постов по смыслу, а не просто по словам. Это гарантирует, что вы никогда не опубликуете два поста об одном и том же.

### Обучение на метриках

Каждые 7 дней система:
1. Собирает статистику реакций
2. Выбирает топ-5 постов
3. Анализирует их стиль с помощью LLM
4. Обновляет профиль стиля для будущих постов

---

## Мониторинг и логи

### Просмотр логов

```bash
# Логи в реальном времени
tail -f logs/tg_poster.log

# Последние 100 строк
tail -n 100 logs/tg_poster.log

# Поиск ошибок
grep "ERROR" logs/tg_poster.log
```

### Структура логов

```
logs/
├── tg_poster.log       # Основной лог
├── tg_poster.log.1     # Ротированный лог
└── ...
```

### Уведомления администратору

Настройте в `.env`:
```bash
ADMIN_TELEGRAM_ID=123456789
```

В `config.yaml`:
```yaml
admin:
  notify_on_error: true   # Уведомлять об ошибках
  notify_on_post: false   # Уведомлять о каждом посте
```

---

## Устранение неполадок

### Частые проблемы

#### "Bot token invalid"

**Причина:** Неверный токен бота

**Решение:**
1. Проверьте токен в `.env`
2. Получите новый токен у @BotFather

#### "Channel not found"

**Причина:** Бот не добавлен в канал

**Решение:**
1. Добавьте бота в администраторы канала
2. Дайте право "Post Messages"

#### "OpenAI API error"

**Причина:** Проблемы с API-ключом или балансом

**Решение:**
1. Проверьте баланс на platform.openai.com
2. Проверьте валидность ключа
3. Попробуйте уменьшить `max_tokens`

#### "Rate limit exceeded"

**Причина:** Превышен лимит запросов

**Решение:**
1. Увеличьте интервал между постами
2. Уменьшите количество источников

#### "Post too similar"

**Причина:** Семантическая дедупликация заблокировала пост

**Решение:**
1. Это нормально — система защищает от повторов
2. Если проблема частая, уменьшите `similarity_threshold`

### Диагностика

```bash
# Проверка конфигурации
python -c "from core.config import get_settings; s=get_settings(); print(s)"

# Тест подключения к Telegram
python -c "
import asyncio
from telegram import Bot

async def test():
    from core.config import get_settings
    s = get_settings()
    bot = Bot(s.telegram.bot_token)
    me = await bot.get_me()
    print(f'Bot: @{me.username}')

asyncio.run(test())
"
```

---

## Продвинутые настройки

### Смена LLM-провайдера

```yaml
llm:
  provider: "claude"  # openai, claude, deepseek
  model: "claude-3-5-sonnet-20241022"
  temperature: 0.85
  max_tokens: 800
```

### Кастомные промпты

Промпты находятся в `llm/prompts/`:

| Файл | Назначение |
|------|------------|
| `system_prompt.txt` | Базовый системный промпт |
| `post_generator.txt` | Генерация постов |
| `topic_selector.txt` | Выбор темы |
| `agent_critic.txt` | Критика постов |
| `style_analyzer.txt` | Анализ стиля |

### Docker-деплой

```bash
# Сборка
docker build -t tg-ai-poster .

# Запуск
docker run -d \
  --name tg-poster \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.yaml:/app/config.yaml \
  tg-ai-poster

# Или через docker-compose
docker-compose up -d
```

### Systemd-сервис (Linux VPS)

Создайте `/etc/systemd/system/tg-poster.service`:

```ini
[Unit]
Description=TG AI Poster
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/tg-ai-poster
ExecStart=/opt/tg-ai-poster/venv/bin/python main.py
Restart=always
RestartSec=30
EnvironmentFile=/opt/tg-ai-poster/.env

[Install]
WantedBy=multi-user.target
```

Активация:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tg-poster
sudo systemctl start tg-poster
sudo systemctl status tg-poster
```

### PostgreSQL для продакшена

```yaml
database:
  url: "postgresql+asyncpg://user:pass@localhost/tg_poster"
```

Не забудьте создать базу:
```sql
CREATE DATABASE tg_poster;
CREATE USER tg_poster WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE tg_poster TO tg_poster;
```

---

## Командная строка

| Команда | Описание |
|---------|----------|
| `python main.py` | Запуск по расписанию |
| `python main.py --once` | Один пост и выход |
| `python main.py --dry-run` | Тестовый режим |
| `python main.py --dry-run --once` | Один тестовый пост |
| `python main.py --init-db` | Инициализация БД |
| `python main.py --debug` | Режим отладки |
| `python main.py --config my.yaml` | Свой конфиг |
| `python main.py --help` | Справка |
| `python setup.py` | Мастер настройки |

---

## FAQ

**Q: Сколько стоит использование?**
A: Зависит от LLM. GPT-4o: ~$0.01-0.03 за пост. GPT-4o-mini: ~$0.001 за пост.

**Q: Можно ли использовать без RSS?**
A: Да, система сгенерирует темы сама на основе темы канала.

**Q: Как изменить стиль постов?**
A: Отредактируйте `channel.style` в config.yaml.

**Q: Как добавить ручную модерацию?**
A: Установите `safety.manual_approval: true`.

**Q: Что если API недоступен?**
A: Система повторит запрос с экспоненциальной задержкой, затем уведомит админа.

---

## Поддержка

- GitHub Issues: https://github.com/your-repo/tg-ai-poster/issues
- Документация: см. README.md
