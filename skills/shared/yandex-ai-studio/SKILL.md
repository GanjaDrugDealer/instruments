---
name: yandex-ai-studio
description: Получает и обновляет IAM-токен Yandex Cloud CLI для подписки Yandex AI Studio. Используй для вызовов DeepSeek по подписке, проверки профиля yc и запуска локальных клиентов с токеном.
---

# Yandex AI Studio по подписке

Подписка Yandex AI Studio должна быть назначена пользователю, который входит в `yc`. Используй каталог из облака с подпиской. В подписке есть скользящие лимиты на 5 часов и неделю. [Модели и лимиты](https://aistudio.yandex.ru/ru/docs/ai-studio/manage/concepts/subscription)

Для подписки используй `https://apps.ai.api.cloud.yandex.net/v1` и пользовательский IAM-токен в `Authorization: Bearer …`. Запросы к `https://ai.api.cloud.yandex.net/v1` тарифицируются по потреблению. [Аутентификация API](https://aistudio.yandex.ru/ru/docs/ai-studio/api-ref/authentication)

## Вход

Установи [Yandex Cloud CLI](https://yandex.cloud/ru/docs/cli/operations/install-cli) или используй портативный `yc`. Скрипт ищет `yc` в PATH и в `bin/yandex-cloud` общей библиотеки. Для другого расположения передай путь через `--yc`.

Пользователь запускает команду ниже в своём терминале из папки скилла, входит в браузере под владельцем подписки и выбирает её облако и каталог.

```text
python -X utf8 scripts/yandex_ai.py init
```

Проверяй вход командой `check`: дашборд Yandex Cloud подтверждает веб-сеанс, а профиль CLI проверяется выпуском IAM-токена. Если журнал содержит `failed to open browser`, диагностируй запуск браузера из `yc`. Для ручного входа нужна полная ссылка авторизации, сформированная самим `yc`, с параметрами текущего сеанса. [Вход без графического интерфейса](https://yandex.cloud/ru/docs/cli/operations/authentication/auth-without-gui)

На Windows скрипт задаёт для портативного `yc` временную папку рядом с бинарником. Если создан локальный каталог `bin/yandex-cloud/profile`, он служит домашним каталогом процесса `yc` для всех подкоманд, а временные файлы идут в его подпапку `tmp`. Создавай этот каталог только при необходимости и ограничивай доступ к нему текущим пользователем, SYSTEM и администраторами. `bin/` исключён из Git.

Указывай `--profile ИМЯ` перед подкомандой, если нужен конкретный профиль. Если сессия входа истекла, снова запусти `init`. Для длительной работы без повторных входов проверь условия refresh-токенов и `yc init --dpop`. [Вход пользователем](https://yandex.cloud/ru/docs/cli/operations/authentication/user) · [Refresh-токены](https://yandex.cloud/ru/docs/iam/concepts/authorization/refresh-token)

## Проверка и запрос

Из папки скилла, Python 3.10+:

```text
python -X utf8 scripts/yandex_ai.py check
python -X utf8 scripts/yandex_ai.py ask --prompt "Reply with exactly: API OK"
python -X utf8 scripts/yandex_ai.py --profile work ask --folder-id "ВАШ_FOLDER_ID" --prompt "Reply with exactly: API OK"
```

`check` проверяет выпуск токена и выводит только результат проверки. `ask` обращается к DeepSeek V4.1 Flash через Responses API. По умолчанию берёт каталог из профиля. Для многострочного запроса передай его через stdin вместо `--prompt`. Успешный вывод — текст ответа, ошибка — ненулевой код и сообщение в stderr.

Скрипт вызывает `yc iam create-token` перед каждым запуском клиента или запросом. При первом HTTP 401 повторно вызывает `yc` и повторяет запрос один раз. IAM-токен живёт до 12 часов. Если `yc` требует вход, повторно авторизуйся через `yc init`. При 403 проверь владельца подписки, каталог и права. При 429 проверь лимиты подписки. [Выпуск IAM-токена](https://yandex.cloud/ru/docs/iam/operations/iam-token/create) · [Ошибки AI Studio](https://aistudio.yandex.ru/ru/docs/ai-studio/qa/)

Если отдельная установка `yc` сообщает об ошибке создания `yc_logs`, запусти скрипт через портативный CLI из общей библиотеки с параметром `--yc` или задай `TEMP` и `TMP` в текущем окружении на доступную для записи папку.

## Другие клиенты

```text
python -X utf8 scripts/yandex_ai.py run -- python app.py
```

`run` передаёт токен дочернему процессу как `YC_IAM_TOKEN`. Настрой клиент на адрес подписки; запускай таким способом только доверенный клиент. Новый запуск заново обращается к `yc`. Для уже запущенного процесса значение переменной фиксируется на старте. Из долгоживущего Python-процесса вызывай `get_iam_token()` из `scripts/yandex_ai.py` при обновлении учётных данных или `ask_deepseek()` для готового запроса. Токен передавай в памяти, держи его вне конфига, stdout и журналов.

Для профиля Codex используй настройки модели, провайдера и каталога из документации Яндекса. В TOML укажи `env_key = "YC_IAM_TOKEN"`, запуск клиента оберни в `run`. [Подписка в Codex CLI](https://aistudio.yandex.ru/ru/docs/ai-studio/manage/concepts/subscription-usage)
