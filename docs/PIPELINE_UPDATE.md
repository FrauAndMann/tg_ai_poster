# Обновление системы генерации постов

## Дата обновления: 2026-03-09

---

## 1. СПИСОК ИЗМЕНЁННЫХ ФАЙЛОВ

### Новые файлы:
- `pipeline/source_verification.py` - модуль верификации источников
- `pipeline/editor_review.py` - модуль редакторского прохода и генерации медиапромптов
- `llm/prompts/source_verifier.txt` - промпт для верификации источников
- `llm/prompts/editor_review.txt` - промпт для редакторского прохода
- `llm/prompts/media_generator.txt` - промпт для генерации изображений

### Обновлённые файлы:
- `llm/prompts/system_prompt.txt` - новый системный промпт (журналистский подход)
- `llm/prompts/post_generator.txt` - новая структура поста
- `pipeline/orchestrator.py` - интеграция новых модулей
- `pipeline/prompt_builder.py` - поддержка новых промптов
- `pipeline/formatter.py` - валидация структуры поста
- `pipeline/__init__.py` - экспорт новых модулей

---

## 2. АРХИТЕКТУРНЫЕ ИЗМЕНЕНИЯ

### 2.1 Новый Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     ENHANCED PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. SOURCE COLLECTION                                           │
│     └─> RSS feeds, HackerNews, ProductHunt                      │
│                                                                  │
│  2. TOPIC SELECTION                                             │
│     └─> AI-powered topic selection from articles                │
│                                                                  │
│  3. SOURCE VERIFICATION [NEW]                                   │
│     └─> Credibility scoring                                     │
│     └─> Cross-reference checking                                │
│     └─> Trust domain validation                                 │
│                                                                  │
│  4. POST GENERATION                                             │
│     └─> Journalistic system prompt                              │
│     └─> Structured output format                                │
│     └─> Source-based facts only                                 │
│                                                                  │
│  5. EDITORIAL REVIEW [NEW]                                      │
│     └─> Style improvement                                       │
│     └─> AI-phrase removal                                       │
│     └─> Readability check                                       │
│                                                                  │
│  6. QUALITY CHECK                                               │
│     └─> Length validation                                       │
│     └─> Structure validation                                    │
│     └─> Duplicate detection                                     │
│                                                                  │
│  7. MEDIA GENERATION [NEW]                                      │
│     └─> Image prompt for Flux/SD/Midjourney                     │
│                                                                  │
│  8. FORMATTING & PUBLISHING                                     │
│     └─> Telegram MarkdownV2                                     │
│     └─> Structure validation                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Source Verification Module

**Функции:**
- Проверка доверия домена (95+ доменов в базе)
- Кросс-референс между источниками
- Оценка credibility (0-100%)
- Рекомендации: publish / needs_review / reject

**Приоритет источников:**
- TechCrunch, The Verge, Ars Technica (95%)
- Nature, Science, ArXiv (95-98%)
- OpenAI, Anthropic, DeepMind (95%)
- GitHub, HuggingFace (90%)
- Reuters, Bloomberg (90-95%)

### 2.3 Editorial Review Module

**Функции:**
- Удаление AI-клише ("в современном мире", "стоит отметить")
- Проверка generic openings
- Улучшение читаемости
- Валидация структуры поста

### 2.4 Media Prompt Generator

**Функции:**
- Генерация промптов для изображений
- Стиль: cinematic, futuristic, professional
- Совместимость с Flux, Midjourney, Stable Diffusion

---

## 3. НОВЫЙ ФОРМАТ ПОСТА

```
🤖 [HEADLINE - max 120 chars, 1-2 emojis]

[HOOK - 1-2 sentences explaining the core news]

[MAIN CONTENT - 800-1500 chars, short paragraphs]
- What happened
- Who is involved
- Key technology/approach
- Industry implications

🔍 Что важно знать:
• [fact 1]
• [fact 2]
• [fact 3]
• [fact 4]

🧠 Почему это важно:
[1-2 sentences of analysis]

🔗 Источники:
• [Source Name] — [URL]
• [Source Name] — [URL]

⚡ Полезные ссылки:
• [Official site] — [URL]
• [GitHub/Docs] — [URL]

💡 TL;DR: [one sentence summary]

#hashtags #here
```

---

## 4. ПРИМЕР НОВОГО ПОСТА

```
🚀 OpenAI представила GPT-5 с принципиально новой архитектурой

Компания OpenAI анонсировала выход пятого поколения своей языковой модели. GPT-5 использует гибридную архитектуру, объединяющую трансформеры с механизмами рекуррентной памяти, что позволяет обрабатывать контекст длиной до 1 миллиона токенов.

Новая модель демонстрирует значительный прогресс в логическом мышлении и планировании. По внутренним бенчмаркам, GPT-5 превосходит предыдущую версию на 40% в задачах, требующих многошагового рассуждения.

Ключевые улучшения включают расширенную мультимодальность с нативной поддержкой видео, а также усовершенствованные механизмы следования инструкциям. API станет доступен для разработчиков в следующем месяце.

🔍 Что важно знать:
• Контекстное окно увеличено до 1M токенов
• Производительность в reasoning +40%
• Нативная поддержка видео в мультимодальности
• API для разработчиков в апреле 2026

🧠 Почему это важно:
Это серьёзный шаг к AGI-способностям. Увеличенное контекстное окно и улучшенное reasoning делают модель пригодной для сложных профессиональных задач — от анализа кода до научных исследований.

🔗 Источники:
• OpenAI Blog — https://openai.com/blog/gpt-5
• TechCrunch — https://techcrunch.com/2026/03/09/openai-gpt5

⚡ Полезные ссылки:
• OpenAI Platform — https://platform.openai.com
• Documentation — https://platform.openai.com/docs

💡 TL;DR: OpenAI выпустила GPT-5 с контекстом до 1M токенов и улучшенным reasoning.

#AI #GPT5 #OpenAI #LLM #MachineLearning
```

---

## 5. КОНФИГУРАЦИЯ

Новые параметры в `config.yaml`:

```yaml
pipeline:
  enable_source_verification: true
  enable_editorial_review: true
  enable_media_generation: true
  
source_verification:
  min_sources: 2
  min_trust_score: 50.0
  min_credibility: 70.0
  
editorial:
  min_score: 70.0
  remove_ai_phrases: true
```

---

## 6. ИСПОЛЬЗОВАНИЕ

### Запуск с новыми модулями:

```python
from pipeline import PipelineOrchestrator

orchestrator = PipelineOrchestrator(
    settings=settings,
    db=db,
    publisher=publisher,
    enable_source_verification=True,   # Включить верификацию
    enable_editorial_review=True,      # Включить редактуру
    enable_media_generation=True,      # Включить генерацию медиа
)

result = await orchestrator.run()

print(f"Post: {result.content}")
print(f"Media prompt: {result.media_prompt}")
print(f"Verification score: {result.verification_score}")
print(f"Editor score: {result.editor_score}")
```

### Только генерация (без публикации):

```python
content, metadata = await orchestrator.run_generation_only()

print(f"Generated: {content}")
print(f"Media prompt: {metadata['media_prompt']}")
print(f"Sources: {metadata['sources']}")
```

---

## 7. ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ

1. **Source Verification** — только проверенные источники
2. **Structured Output** — обязательные блоки с источниками
3. **Editorial Review** — проверка фактов и стиля
4. **Forbidden Phrases** — удаление AI-клише
5. **Trust Scoring** — рейтинги доверия доменов

---

## 8. СЛЕДУЮЩИЕ ШАГИ

1. Добавить интеграцию с API генерации изображений (Flux/SD)
2. Добавить автоматическую загрузку изображений в Telegram
3. Расширить базу доверенных доменов
4. Добавить A/B тестирование форматов постов
5. Интегрировать аналитику просмотров для оптимизации

---

*Обновление выполнено CLI-агентом 2026-03-09*
