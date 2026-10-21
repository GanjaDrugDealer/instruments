# agy без диалога: формат вызова, ответа и ошибок

Проверено на agy 1.4.2 (сервер Netcup, 19–21.10.2026). Реализация — `scripts/agy.py`.

## Ключи (`agy --help`, главное)

| Ключ | Зачем |
|---|---|
| `-p` / `--print` | один запрос без диалога; `-p=` — пустой, сам запрос придёт через stdin (stream-json) |
| `--input-format stream-json` | stdin — по строке NDJSON на сообщение; требует `--output-format stream-json` |
| `--output-format text\|json\|stream-json` | `json` — один объект (картинки), `stream-json` — события построчно (тексты) |
| `--model` | `agy models`: `gemini-3.8-flash-high\|medium\|low`, `claude-sonnet-4-6`, `claude-opus-4-6-thinking`, `gpt-oss-120b-medium` |
| `--effort low\|medium\|high\|xhigh\|max` | глубина рассуждений; больше — дольше и дороже |
| `--json-schema` | схема строкой или путём к файлу; в stream-json действует на итоговый ответ |
| `--print-timeout 280s` | предел времени agy (по умолчанию 0 — ждать сколько угодно) |
| `--disable-slash-commands` | не раскрывать `/команды` и скиллы в тексте промпта |
| `--dangerously-skip-permissions` | **не использовать** в автоматике |

Подкоманды: `agy models`, `agy update`, `agy changelog`. `/usage` — как запрос: `agy -p /usage`.

## Текст по схеме

```
agy -p= --input-format stream-json --output-format stream-json \
    --model gemini-3.8-flash-medium --effort medium --json-schema "$SCHEMA" --print-timeout 280s
```

stdin — одна строка: `{"event":"user","message":{"content":"<промпт целиком>"}}`.

stdout — события по строке. Нужные:

```
{"event":"step_update","step_update":{"step_index":6,"state":"DONE","step_type":"tool","tool_name":"view_file"}}
{"event":"result","result":{"conversation_id":"…","status":"SUCCESS","response":"{\"claims\": []}",
 "num_turns":1,"usage":{"input_tokens":14290,"output_tokens":429,"thinking_tokens":0}}}
```

- `result` **вложен** (`{"event":"result","result":{…}}`) — 20.10 исполнитель написал плоский разбор и тесты под
  него, всё было зелёным и не работало.
- Ответ — `result.structured_output` или `result.response`; часто JSON строкой, иногда в ```` ```json ````.
- Пустой ответ при событии `finish` с `tool_info.parameters` — ответ там.
- `step_type: tool` (кроме `finish`) или `num_turns > 1` — модель звала инструменты: в журнал `tools_used`.
- `status`: `SUCCESS` / `ERROR`; ошибка — `result.error` и stderr.
- Нет строки `result` — agy не дошёл до ответа: вход, сеть, таймаут. Хвост событий (без `user_input`, ≤ 4 КБ) —
  в журнал для разбора.

## Промпт

- Весь контекст — в промпте: документы, тексты источников (скачивает код), вывод проверок. Ссылки модель не
  открывает.
- Запрет инструментов — в начале и в конце:
  «Ты работаешь без инструментов: всё нужное — ниже. Не открывай, не ищи, не запускай и не записывай. Где роль
  велит прочитать или запустить — результат уже приведён ниже. Сразу верни JSON по схеме». Хвост:
  «=== ОТВЕТ === Инструментов нет: … Сразу верни JSON по схеме: поле X — …».
- Роли, написанные для агента с инструментами, — через адаптер: «прочитай файл» → «раздел ниже», «запиши файл» →
  «верни в поле `post`» (образец — smm-planner `agents/_agy-adapter.md`).
- Итог («чисто / есть ошибки») считает код по полям ответа; модельный `status` в ответе игнорировать
  (Sonnet при двух расхождениях ответил `CLEAN`).

## Картинка

```
agy -p "<промпт>" --model gemini-3.8-flash-low --effort low --output-format json --print-timeout 280s
→ {"conversation_id":"<uuid>","status":"SUCCESS","response":"…","usage":{"total_tokens":…}}
```

Файл — новейший `~/.gemini/antigravity-cli/brain/<uuid>/*.{jpg,jpeg,png,webp}`. Генератор работает субагентом;
его 429 — `RESOURCE_EXHAUSTED` в `brain/*/.system_generated/logs/transcript.jsonl` с текстом «reset after ~N hours»
или «reset after 4h29m54s» (оба вида; 20.10 второй не разбирался — блок ставился на 24 ч).

## Ошибки и квота

- 429-признаки: `\b429\b`, `RESOURCE_EXHAUSTED`, `exhausted your capacity`, `rate limit` — **только в stderr и
  `result.error`**. В ответе и счётчиках «429» встречается само (14290 токенов) — ложный блок.
- Блок — файл `{"until": <unix>, "reason": …}`; пока не истёк, agy не звать. Срок: сброс группы из `/usage`, если
  остаток там < 5 %; иначе «reset after …» из ошибки; иначе 6 ч (текст) / 24 ч (картинки).
- `/usage` кэшировать 10 мин; нет строк «Limit Remaining» — считать «нет данных» и не звать (обычно слетел вход).

## Замеры расхода (Pro, если не сказано иное)

| Что | Токены | Время | Квота |
|---|---|---|---|
| Фактчек поста, Gemini 3.8 Flash high | ~35 тыс. | 138 с | не сдвинулась |
| То же, Flash medium | ~18 тыс. | 38 с | не сдвинулась |
| То же на Starter | ~47 тыс. | 59 с | 3 % недели |
| Claude Sonnet 4.6 | ~18 тыс. | 22 с | 3 % окна 5 ч, 2 % недели |
| Код по ТЗ (agy-dev, Flash high, 8,7 мин) | — | — | 3 % окна 5 ч Gemini |
| Наценка любого вызова | ~11,8 тыс. входных | — | — |
| Картинка | — | — | своя скрытая квота (Pro — окно 5 ч, Starter — ~7 в неделю) |
