# instruments

Общие скиллы и правила для всех проектов из папки «AI Projects». Работает на macOS и Windows.

Здесь только рабочее: то, что раскладывает установщик, и служебные скрипты. Планы, ТЗ, черновики новых скиллов,
отчёты и архив — в мастерской `Claude/ai-workshop` (репозиторий `GanjaDrugDealer/ai-workshop`).
Новый скилл пишется там черновиком и приезжает сюда одним коммитом; мелкие правки готовых — сразу здесь.

## Раскладка папок (одинаковая на обеих машинах)

```
AI Projects/
├── _instruments/            ← этот репозиторий
│   ├── skills/shared/       общие скиллы (file-links, watch-tasks, watch-executors, video-frame-sheets, channel-banner, …)
│   ├── rules/CLAUDE.global.md   базовые правила для всех людей и машин
│   ├── rules/personal/<профиль>.md   личные правила человека (artem — Артём)
│   ├── project-skills.txt   скиллы проектов, нужные и вне их папок
│   ├── templates/project/   шаблон нового проекта (стандарт — скилл project-structure)
│   ├── templates/project-local/   оверлей шаблона для закрытых (Local) проектов
│   ├── scripts/             new-project.sh / .ps1, snapdiff.py (приёмка по диффу), check-structure.py (линтер),
│   │                        sync.sh / .ps1 (автосинхронизация)
│   ├── install.sh / install.ps1
│   └── bin/                 личные инструменты машины (gh и т.п.), не в git
├── new-project.command      Mac: двойной щелчок — новый проект
├── new-project.bat          Windows: двойной щелчок или new-project.bat [Claude|Antigravity|Local|Codex] [name]
├── Claude/<проект>/         проекты, которые ведёт Claude (у каждого свой репозиторий)
├── Antigravity/<проект>/    проекты, которые ведёт Antigravity
├── Codex/<проект>/          проекты, которые ведёт Codex
└── Local/<проект>/          закрытые проекты: только локальная модель, без облака
```

## Новый проект

- Mac: двойной щелчок по `AI Projects/new-project.command` или
  `zsh _instruments/scripts/new-project.sh Claude <имя> --no-prompt`.
- Windows: `new-project.bat` в корне `C:\AI Projects`.
- Агенту — скилл `new-project`. Проверка всех проектов на стандарт (ничего не меняет):
  `python3 -X utf8 _instruments/scripts/check-structure.py`.

## Установка / обновление

Один раз на машину после `git clone` (дальше — автосинхронизация):

- macOS: `zsh install.sh [--profile artem]` — символические ссылки в `~/.claude/skills/`.
- Antigravity: оба установщика подключают общие скиллы и в `~/.gemini/config/skills/` (IDE), если папка `~/.gemini` есть,
  и в `~/.gemini/antigravity-cli/skills/` (CLI `agy`), если есть `~/.gemini/antigravity-cli`.
- Windows: `powershell -ExecutionPolicy Bypass -File install.ps1 [-RulesProfile artem]` — junction-ссылки на скиллы.
- Правила собирает `scripts/compose-rules.py` и кладёт одну копию Claude (`~/.claude/CLAUDE.md`), Codex
  (`~/.codex/AGENTS.md`) и Antigravity (`~/.gemini/GEMINI.md`): базовые `rules/CLAUDE.global.md` + личные
  `rules/personal/<профиль>.md` (профиль машины — `~/.config/ai-rules/profile`, задаётся ключом установщика один раз)
  + личные правила машины `~/.config/ai-rules/personal.md` (в git не едут). Уже лежавший там свой файл правил
  при первой сборке переезжает в `personal.md` — ничего не теряется. Машина без профиля получает базовые + свои.

То, что уже лежало на месте не ссылкой, переносится в `~/.claude/_backup-<дата>/`.

## Автосинхронизация

Установщик один раз ставит её на машину, дальше `git pull` и повторный установщик руками не нужны.

- **Когда:** при входе в систему, ночью в 04:00 МСК (пропущено — при следующем включении или пробуждении)
  и хуком Claude при старте сессии, если последняя проверка старше 15 минут.
- **Что делает** (`scripts/sync.sh` / `sync.ps1`): `git fetch`, fast-forward `main` из `origin/main`, при новых
  коммитах — установщик. Ничего не форсирует: свои правки, незапушенные коммиты, другая ветка, нет сети —
  только запись причины в файл состояния (на Mac ещё уведомление).
- **Где:** Mac — launchd `com.ganjadrugdealer.instruments-sync`, состояние и журнал в `~/.local/state/instruments-sync/`;
  Windows — задача Планировщика `AI-Instruments-Sync`, состояние и журнал в `%LOCALAPPDATA%\instruments-sync\`.
- **Переезды** (`scripts/migrate.py`, на каждом прогоне и в установщике): переименованные папки проектов,
  новые адреса репозиториев после переименования на GitHub, перенос памяти Claude. Занятую папку (открыта сессия
  или редактор) переименует в следующий прогон, до тех пор хук об этом напоминает. Новый переезд — строка
  в `RENAMES` / `REMOTES` с датой; старые строки не удалять.
- **Хук** (`scripts/sync-status.*`, `SessionStart` в `~/.claude/settings.json`, ставит `scripts/claude-hook.py`):
  молчит, если всё актуально, иначе одна строка агенту — он скажет пользователю. Свежие скиллы видит следующая сессия.
- Mac: если `AI Projects` на Рабочем столе, launchd может не получить доступ к папке (защита macOS). Тогда
  синхронизацию делает хук из Claude, а в состоянии будет подсказка: дать `/bin/zsh` полный доступ к диску.

## Сторонние скиллы

- Список — `vendor-skills.txt`: репозиторий, закреплённый коммит, папка скилла, для кого (`shared` / `claude`).
- Копии лежат в `skills/vendor/<shared|claude>/<имя>/`, руками не правятся. Установщики раздают их вместе с остальными.
- Выложить по списку: `python3 -X utf8 scripts/vendor-skills.py`; обновить версии: `… --update`, затем читать `git diff`.
- `npx skills add` не использовать — ставит мимо репозитория.

## Правила

- Один скилл — одна копия. Общий скилл живёт здесь, проектный — в `.claude/skills/` своего проекта
  (если нужен и вне проекта — строка в `project-skills.txt`).
- В файлах проектов общие скиллы называть по имени (`file-links`, `watch-tasks`), без абсолютных путей.
- Правки правил — в `rules/CLAUDE.global.md` (для всех) или `rules/personal/<профиль>.md` (про человека),
  не в собранных `~/.claude/CLAUDE.md` и т. п.

## Стандарт хранения проектов (Windows-контур, 2026-09-15)

- Правило — скилл `skills/shared/project-structure`; шаблон проекта — `templates/project/`, новый проект —
  `new-project.bat <Claude|Antigravity|Local|Codex> <имя>` в корне AI Projects (`scripts/new-project.ps1`).
- Скиллы по применимости: `skills/shared/` (все агенты), `skills/claude/` (только Claude), `skills/antigravity/`.
  `install.ps1` раздаёт `shared` и `claude`.
- Утилиты: `scripts/check-structure.py` (линтер, ничего не меняет), `scripts/snapdiff.py` (дифф для приёмки без git).

## Codex

Оба установщика подключают скиллы в `~/.agents/skills/`: `skills/shared/`,
`skills/vendor/shared/`, универсальные сторонние скиллы из `skills/vendor/claude/`,
`skills/codex/` и существующие скиллы из `project-skills.txt`.
Claude-only мост из `skills/claude/` в Codex не устанавливается.
Используются ссылки на единственный исходник; существующие обычные папки
сохраняются в `~/.codex/_backup-<дата>/`.
Правила для Codex и Antigravity — та же сборка, что и для Claude (см. «Установка»). Скиллы доступны со следующего хода; если не появились — перезапустить Codex.

Скилл `git-publish` описывает проверку диффа, коммит, push текущей ветки без force
и проверку удалённого коммита. Публикация в GitHub не означает деплой сайта.
