---
name: mac-standalone-tools
description: Как ставить инструменты (yt-dlp, deno, ffmpeg и подобные) на Intel-мак пользователя без Homebrew — готовые официальные бинарники внутрь bin/ проекта, со сверкой контрольной суммы. Применять, когда проекту нужна внешняя программа, когда тянет сказать «brew install», и при уборке следов Homebrew.
---

# Инструменты на Intel-маке: без Homebrew

## Почему не Homebrew

Мак пользователя — Intel, macOS 15. Для Homebrew это Tier 3: готовых сборок
нет, всё компилируется из исходников. `brew install yt-dlp ffmpeg` шёл
10+ минут, упал и оставил мусор (десятки зависимостей, 1.4 ГБ кэша).
Так было дважды (22.09 и 25.09.2026). Не повторять.

## Как ставить

Готовый официальный бинарник → в `bin/` проекта. `bin/` закрыт `.gitignore`.
Проект самодостаточен: скрипт добавляет `"$ROOT/bin"` в начало `PATH`.

| Что | Откуда | Сверка |
|---|---|---|
| yt-dlp | `github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos` (universal, внутри свой python и curl_cffi) | строка из `SHA2-256SUMS` того же релиза |
| deno | `github.com/denoland/deno/releases/latest/download/deno-x86_64-apple-darwin.zip` (на Apple Silicon — `aarch64`) | файл `.zip.sha256sum` рядом |
| ffmpeg, ffprobe | сборка evermeet.cx (есть libx264); уже лежит в `~/.uniquifier/bin` — копировать оттуда, не качать заново | — |

Порядок: скачать → `shasum -a 256` сверить → `chmod +x` → `--version`.
Скачивание — только с разрешения пользователя, с названием, источником и
размером. Форки и зеркала (пример: `Cliply/yt-dlp` — копия без изменений,
отстаёт на 500+ коммитов) не брать — проверять через GitHub API
(`compare` с оригиналом).

Копировать, а не ссылаться: никаких симлинков на чужие папки.

## Обновление

`bin/yt-dlp_macos -U` — сам себя. Остальное — перекачать тем же способом.

## Python

Проектам на этом маке python не нужен. Если понадобится — `.venv` в проекте,
но не на brew-питоне (brew-питон удалён). Системный `python3` — 3.9.6 из
Command Line Tools, для служебных однострочников годится.

## Уборка Homebrew

Перед удалением: `brew uses --installed <pkg>`, `brew leaves`,
`brew list --installed-on-request`, поиск имён в скриптах пользователя,
LaunchAgents, crontab. Сам пользователь ставил только `exiftool` — его не трогать.
Кэш: `brew cleanup --prune=all`. Сейчас в brew только exiftool.

`~/.zprofile` подключает brew циклом по `/opt/homebrew` и `/usr/local` —
работает на обоих типах маков (бэкап `~/.zprofile.bak-2026-09-25`).
