---
name: yandex-ai-studio
description: Получает и обновляет IAM-токен Yandex Cloud CLI для подписки Yandex AI Studio. Используй для вызовов DeepSeek по подписке, проверки профиля yc и запуска локальных клиентов с токеном.
---

# Yandex AI Studio по подписке

Подписка Yandex AI Studio должна быть назначена пользователю, который входит в `yc`. Используй каталог из облака с подпиской. В подписке есть скользящие лимиты на 5 часов и неделю. [Модели и лимиты](https://aistudio.yandex.ru/ru/docs/ai-studio/manage/concepts/subscription)

Для подписки используй `https://apps.ai.api.cloud.yandex.net/v1` и пользовательский IAM-токен в `Authorization: Bearer …`. Запросы к `https://ai.api.cloud.yandex.net/v1` тарифицируются по потреблению. [Аутентификация API](https://aistudio.yandex.ru/ru/docs/ai-studio/api-ref/authentication)

## Вход

На Windows устанавливай Yandex Cloud CLI в `%USERPROFILE%\yandex-cloud\bin` и запускай вход из обычного PowerShell без повышения прав. Можно распаковать проверенную официальную сборку в эту папку вручную. Скрипт ищет `yc` в `PATH`, затем в стандартной папке Windows, затем в `bin/yandex-cloud` общей библиотеки. Через `--yc` можно задать точный путь, например если в `PATH` осталась портативная копия. [Установка Yandex Cloud CLI](https://yandex.cloud/ru/docs/cli/operations/install-cli)

Запусти команду из папки скилла в интерактивном терминале. Владелец подписки подтверждает вход в браузере. Затем в CLI выбери облако и каталог подписки.

```text
python -X utf8 scripts/yandex_ai.py init
```

Дождись завершения `init` с кодом 0 и проверь, что профиль появился в `yc config profile list`. Команда `check` отдельно проверяет выпуск IAM-токена. Если журнал содержит `failed to open browser`, диагностируй запуск браузера из `yc`. Для ручного входа нужна полная ссылка авторизации, сформированная самим `yc`, с параметрами текущего сеанса. [Вход без графического интерфейса](https://yandex.cloud/ru/docs/cli/operations/authentication/auth-without-gui)

На Windows скрипт задаёт для портативного `yc` временную папку рядом с бинарником. Если создан локальный каталог `bin/yandex-cloud/profile`, он служит домашним каталогом процесса `yc` для всех подкоманд, а временные файлы идут в его подпапку `tmp`. Создавай этот каталог только при необходимости и ограничивай доступ к нему текущим пользователем, SYSTEM и администраторами. `bin/` исключён из Git.

Если Edge сообщает о конфликте прав с запущенным экземпляром, сравни уровни целостности `yc.exe` и основного процесса Edge. Файл с меткой Low запускается на Low даже из PowerShell с уровнем Medium. При таком сбое у портативной копии используй стандартную установку Windows с её обычным профилем. [Документация Microsoft о метках целостности](https://learn.microsoft.com/windows/win32/secauthz/mandatory-integrity-control)

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

Если `yc` сообщает об ошибке создания `yc_logs`, проверь, что запущен нужный `yc.exe` и текущему процессу доступны каталоги `TEMP` и `TMP` для записи.

## Другие клиенты

```text
python -X utf8 scripts/yandex_ai.py run -- python app.py
```

`run` передаёт токен дочернему процессу как `YC_IAM_TOKEN`. Настрой клиент на адрес подписки; запускай таким способом только доверенный клиент. Новый запуск заново обращается к `yc`. Для уже запущенного процесса значение переменной фиксируется на старте. Из долгоживущего Python-процесса вызывай `get_iam_token()` из `scripts/yandex_ai.py` при обновлении учётных данных или `ask_deepseek()` для готового запроса. Токен передавай в памяти, держи его вне конфига, stdout и журналов.

Для профиля Codex используй настройки модели, провайдера и каталога из документации Яндекса. В TOML укажи `env_key = "YC_IAM_TOKEN"`, запуск клиента оберни в `run`. [Подписка в Codex CLI](https://aistudio.yandex.ru/ru/docs/ai-studio/manage/concepts/subscription-usage)
