# Деплой TG AI Poster на Fly.io

Fly.io — облачная платформа для Docker-приложений.
- Работает в Беларуси
- Бесплатно: $5/месяц кредита
- Простой деплой одной командой

---

## Шаг 1: Установка Fly CLI

### Windows (PowerShell)

```powershell
# Скачай и установи
iwr https://fly.io/install.ps1 -useb | iex
```

Или вручную:
1. Скачай с https://github.com/superfly/flyctl/releases
2. Распакуй `flyctl.exe` в папку из PATH (например `C:\Windows`)

### Проверка

```powershell
fly version
```

---

## Шаг 2: Регистрация и логин

```powershell
# Регистрация (откроет браузер)
fly auth signup

# Или логин если уже есть аккаунт
fly auth login
```

---

## Шаг 3: Создание приложения

В папке проекта:

```powershell
cd D:\tg_ai_poster

# Создать приложение (выбери уникальное имя)
fly apps create tg-ai-poster

# Или при первом деплое fly сам предложит создать
```

---

## Шаг 4: Настройка секретов

Загрузи переменные окружения как секреты:

```powershell
# Telegram
fly secrets set TELEGRAM_BOT_TOKEN=123456789:ABCdef...
fly secrets set TELEGRAM_CHANNEL_ID=@your_channel

# Telethon (если нужен)
fly secrets set TELETHON_API_ID=12345678
fly secrets set TELETHON_API_HASH=abcdef...
fly secrets set TELETHON_PHONE=+37529123456

# LLM
fly secrets set OPENAI_API_KEY=sk-...
fly secrets set GLM_API_KEY=your_key

# Admin
fly secrets set ADMIN_TELEGRAM_ID=123456789
```

> Секреты применяются автоматически при следующем деплое.

---

## Шаг 5: Деплой

```powershell
cd D:\tg_ai_poster

# Первый деплой (создаст приложение если нужно)
fly deploy

# С_FOLLOWING логами
fly logs
```

Деплой занимает 2-5 минут.

---

## Шаг 6: Проверка

```powershell
# Статус приложения
fly status

# Логи в реальном времени
fly logs -f

# Информация о приложении
fly info

# Открыть в браузере (если есть HTTP endpoint)
fly open
```

---

## Полезные команды

| Команда | Описание |
|---------|----------|
| `fly deploy` | Деплой изменений |
| `fly logs -f` | Логи в реальном времени |
| `fly status` | Статус приложения |
| `fly ssh console` | SSH в контейнер |
| `fly secrets list` | Список секретов |
| `fly secrets set KEY=value` | Добавить секрет |
| `fly scale vm shared-cpu-1x` | Изменить размер VM |
| `fly scale count 1` | Количество инстансов |
| `fly machines list` | Список машин |
| `fly restart` | Перезапуск |

---

## Управление ресурсами

### Посмотреть текущие ресурсы

```powershell
fly scale show
```

### Изменить размер VM

```powershell
# Самый дешёвый (подходит для бота)
fly scale vm shared-cpu-1x --memory 256

# Средний
fly scale vm shared-cpu-1x --memory 512

# Более мощный
fly scale vm shared-cpu-2x --memory 512
```

### Количество инстансов

```powershell
# Один инстанс (для бота достаточно)
fly scale count 1
```

---

## Persistent Volumes

Бот использует volumes для хранения данных (БД, сессии):

```powershell
# Создать volume для данных
fly volumes create tg_poster_data -s 1

# Создать volume для логов
fly volumes create tg_poster_logs -s 1

# Создать volume для сессий Telethon
fly volumes create tg_poster_sessions -s 1
```

> Размер `-s 1` = 1GB. Бесплатно до 3GB суммарно.

---

## Мониторинг расходов

```powershell
# Посмотреть использование ресурсов
fly status

# Посмотреть dashboard
fly dashboard
```

Бесплатные $5/месяц покрывают примерно:
- 1 x shared-cpu-1x VM (24/7)
- 3GB volumes
- ~160GB traffic

---

## Решение проблем

### Приложение не стартует

```powershell
fly logs
fly vm status
```

### Ошибка "not enough memory"

```powershell
fly scale vm shared-cpu-1x --memory 512
```

### Проблема с секретами

```powershell
fly secrets list
fly secrets set KEY=new_value
fly deploy
```

### SSH доступ

```powershell
fly ssh console
# Внутри контейнера:
ls -la /app/data
cat /app/.env  # секреты не видны напрямую
```

---

## Обновление кода

При изменении кода просто:

```powershell
fly deploy
```

Fly.io автоматически:
1. Соберёт новый Docker-образ
2. Заменит старый контейнер
3. Сохранит volumes

---

## Остановка приложения

```powershell
# Остановить
fly scale count 0

# Запустить снова
fly scale count 1

# Удалить приложение полностью
fly apps destroy tg-ai-poster
```

---

## Альтернативы если Fly.io не подойдёт

| Платформа | Цена | Примечание |
|-----------|------|------------|
| **Hetzner** | ~4€/мес | Немецкий хостинг, работает в BY |
| **Contabo** | ~5€/мес | Много ресурсов |
| **Timeweb** | ~200₽/мес | РФ хостинг |
| **Aeza** | ~150₽/мес | РФ, крипто-оплата |
