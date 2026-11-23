---
name: deepseek-api
description: Вызывает официальный API DeepSeek из скриптов и автоматизаций. Используй для проверки ключа, просмотра моделей, обработки текста и получения JSON через DeepSeek.
---

# DeepSeek API

Для автоматизаций используй `scripts/deepseek.py` с Python 3.10+ без сторонних библиотек. Передавай запрос через stdin. Утилита выводит результат в stdout, ошибки в stderr и возвращает ненулевой код при сбое. По умолчанию модель `deepseek-flash`, режим рассуждения выключен. Модель меняется через `--model`, лимит вывода через `--max-tokens`.

## Ключ

На Windows из папки скилла запусти в личном PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\save-key.ps1
```

Вставь ключ в скрытое поле `DeepSeek API key` и нажми Enter. Хранилище Windows шифрует ключ для текущего пользователя на этой машине. Скрипт расшифровывает его сам, через `CryptUnprotectData`, без запуска дочерних процессов: в ограниченных сессиях (песочница dsh, служба, задача под другим маркером) запуск `powershell` с перехватом вывода запрещён, и прежняя схема с дочерним процессом там падала с «Cannot open the saved DeepSeek key» при живом и исправном ключе.

Порядок поиска ключа:

1. переменная окружения `DEEPSEEK_API_KEY` — приоритет, для Mac, сервера и задач под другой учётной записью;
2. сохранённый ключ Windows (`%LOCALAPPDATA%\DeepSeek\api-key.xml`);
3. текстовый файл `~/.config/deepseek/api-key.txt` (или путь из `DEEPSEEK_API_KEY_FILE`) — на случай, когда DPAPI недоступен: другой пользователь Windows, перенос на другую машину, служба без профиля. Файл заводить вручную, права оставить только своему пользователю.

## Проверка и вызов

Примеры из папки скилла:

```powershell
python -X utf8 scripts/deepseek.py models
'Reply with exactly: API OK' | python -X utf8 scripts/deepseek.py chat --max-tokens 32
'Верни JSON-объект с полем ok и значением true.' | python -X utf8 scripts/deepseek.py chat --json
```

В режиме `--json` укажи в запросе нужные поля. Скрипт запрашивает JSON-объект и проверяет, что ответ можно разобрать. При `401` проверь ключ, при `402` баланс, при `429` ограничения запросов.

[Список моделей](https://api-docs.deepseek.com/api/list-models/) · [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
