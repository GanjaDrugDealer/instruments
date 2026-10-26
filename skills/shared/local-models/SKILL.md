---
name: local-models
description: Локальные LLM на рабочей станции (Ollama, RTX 5080). Применять, когда проекту нужна локальная модель, массовая или приватная обработка данных без облака, вопрос «какую модель взять» или «как вызвать из кода». Только Windows-ПК; на Mac моделей нет, скилл неприменим.
---

# Локальные модели (Ollama)

Рабочая станция: NVIDIA GeForce RTX 5080 (16 GB VRAM, Blackwell), 64 GB RAM.
Бэкенд: Ollama (порт 11434), OpenAI-совместимый API `http://127.0.0.1:11434/v1`.
Веса хранятся на внешнем SSD Samsung T7: `OLLAMA_MODELS = J:\AI Projects\models\ollama`.

## Модели и назначение

| Имя | База | Назначение | ток/с | контекст | где |
|---|---|---|---|---|---|
| `fast:9b` | Qwen3.5 9B | быстрая универсальная, картинки, инструменты | 108 | 131 072 | GPU |
| `fast-abl:9b` | Qwen3.5 abliterated | то же, без отказов | 121 | 131 072 | GPU |
| `gemma:12b` | Gemma 4 12B | тексты, картинки | 123 | 131 072 | GPU |
| `gemma-abl:12b` | Gemma 4 abliterated | то же, без отказов | 93 | 131 072 | GPU |
| `coder:14b` | Qwen2.5-Coder 14B | код, автодополнение в IDE | 88 | 16 384 | GPU |
| `gptoss:20b` | gpt-oss 20B | строгий JSON, инструменты | 175 | 131 072 | GPU |
| `smart:35b` | Qwen3.6 MoE 35B-A3B | самая умная | 79 | 131 072 | 58% GPU / 42% CPU |
| `smart-abl:35b` | Qwen3.6 abliterated | то же, без отказов | 74 | 131 072 | 59% GPU / 41% CPU |

Замеры на контексте 16k, все ответили верно. Загрузка 9–34 с (SSD T7, 950 МБ/с).

## Когда локальная модель, когда облачная

| Критерий | Локальная | agy / Claude |
|---|---|---|
| Массовая обработка (сотни/тысячи вызовов) | ✔ бесплатно, без квот | ✘ квоты, 429 |
| Приватные / чувствительные данные | ✔ не покидают ПК | ✘ облако |
| Бесплатная работа без подписки | ✔ | ✘ |
| Лучшее качество рассуждений | — | ✔ Claude Opus / Gemini 3.8 |
| Длинный контекст >128k | — | ✔ до 1M+ |
| Задача для агента с инструментами IDE | — | ✔ Claude Code / agy |

Правило: массовое, приватное, бесплатное → локальная модель.
Сложное рассуждение, длинный контекст, агентный цикл → облако.

## Вызов из кода

Библиотека `openai` (Python), не `ollama`:

```python
from openai import OpenAI
import os

client = OpenAI(
    base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
    api_key="ollama",
)

resp = client.chat.completions.create(
    model=os.getenv("LOCAL_LLM_MODEL", "fast:9b"),
    messages=[{"role": "user", "content": "Привет"}],
)
print(resp.choices[0].message.content)
```

Переменные окружения (`.env`):

```
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=fast:9b
```

### Ответ JSON по схеме

```python
resp = client.chat.completions.create(
    model="gptoss:20b",
    messages=[{"role": "user", "content": "Опиши кота JSON: name, color, age"}],
    response_format={"type": "json_object"},
)
```

Альтернатива (Ollama-специфичная) — поле `format` в API:

```python
import requests
r = requests.post("http://127.0.0.1:11434/api/chat", json={
    "model": "gptoss:20b",
    "messages": [{"role": "user", "content": "Опиши кота JSON"}],
    "format": {"type": "object", "properties": {"name": {"type": "string"}}},
    "stream": False,
})
```

## Проверки перед работой

1. **Ollama отвечает**: `curl http://127.0.0.1:11434/api/version` → JSON с версией.
   Нет ответа → Ollama не запущена или не установлена.
2. **Диск J: подключён**: `Test-Path J:\` → True. Без J: Ollama молча смотрит
   в пустую папку на C: и не найдёт моделей (см. грабли).

## Грабли

- **Без ярлыка (Modelfile) контекст = 4096**. Ollama по умолчанию даёт 4096 токенов.
  Модели с большим контекстом (131072) работают только через ярлыки
  (`fast:9b`, `smart:35b` и т. д.), где прописан `num_ctx`.
- **gpt-oss: `think: "low"` и запас токенов**. Модель не выключает рассуждения
  (`think: false` игнорируется): при малом `num_predict` весь лимит уходит
  в `<think>` и ответ пустой. Задавать `think: "low"` и запас токенов.
- **Одна модель в VRAM**: переключение модели — выгрузка старой + загрузка новой
  (9–34 с). Частые переключения снижают производительность.
- **Ollama, запущенная без J:, молча смотрит в пустую папку на C:**.
  `ollama list` пуст, «model not found». Лечится перезапуском Ollama
  при подключённом J:.

## Закрытые проекты (Local)

Проекты, которые ведёт только локальная модель. Данные не покидают ПК.
Подробности — скилл `project-structure`, раздел «Закрытые проекты (Local)».

## Mac

На Mac локальных моделей нет. Этот скилл там неприменим.
