# ai-instruments

Общие скиллы и правила для всех проектов из папки «AI Projects». Работает на macOS и Windows.

## Раскладка папок (одинаковая на обеих машинах)

```
AI Projects/
├── _Instruments/            ← этот репозиторий
│   ├── skills/shared/       общие скиллы (file-links, watch-tasks, watch-executors, video-frame-sheets, channel-banner, …)
│   ├── rules/CLAUDE.global.md   глобальные правила (→ ~/.claude/CLAUDE.md)
│   ├── project-skills.txt   скиллы проектов, нужные и вне их папок
│   ├── templates/project/   шаблон нового проекта (стандарт — скилл project-structure)
│   ├── scripts/             new-project.sh / .ps1, snapdiff.py (приёмка по диффу), check-structure.py (линтер)
│   ├── install.sh / install.ps1
│   └── bin/                 личные инструменты машины (gh и т.п.), не в git
├── new-project.command      Mac: двойной щелчок — новый проект (Windows: new-project.bat)
├── Claude/<проект>/         проекты, которые ведёт Claude (у каждого свой репозиторий)
└── Antigravity/<проект>/    проекты, которые ведёт Antigravity
```

## Новый проект

- Mac: двойной щелчок по `AI Projects/new-project.command` или
  `zsh _Instruments/scripts/new-project.sh Claude <имя> --no-prompt`.
- Windows: `new-project.bat` в корне `C:\AI Projects`.
- Агенту — скилл `new-project`. Проверка всех проектов на стандарт (ничего не меняет):
  `python3 -X utf8 _Instruments/scripts/check-structure.py`.

## Установка / обновление

После `git clone` или `git pull`:

- macOS: `zsh install.sh` — символические ссылки в `~/.claude/skills/` и на `~/.claude/CLAUDE.md`.
- Antigravity: оба установщика подключают общие скиллы и в `~/.gemini/config/skills/`, если папка `~/.gemini` есть.
- Windows: `powershell -ExecutionPolicy Bypass -File install.ps1` — junction-ссылки на скиллы, `CLAUDE.md` копией
  (после каждого `git pull` запускать снова).

То, что уже лежало на месте не ссылкой, переносится в `~/.claude/_backup-<дата>/`.

## Сторонние скиллы

- Список — `vendor-skills.txt`: репозиторий, закреплённый коммит, папка скилла, для кого (`shared` / `claude`).
- Копии лежат в `skills/vendor/<shared|claude>/<имя>/`, руками не правятся. Установщики раздают их вместе с остальными.
- Выложить по списку: `python3 -X utf8 scripts/vendor-skills.py`; обновить версии: `… --update`, затем читать `git diff`.
- `npx skills add` не использовать — ставит мимо репозитория.

## Правила

- Один скилл — одна копия. Общий скилл живёт здесь, проектный — в `.claude/skills/` своего проекта
  (если нужен и вне проекта — строка в `project-skills.txt`).
- В файлах проектов общие скиллы называть по имени (`file-links`, `watch-tasks`), без абсолютных путей.
- Правки глобальных правил — в `rules/CLAUDE.global.md`, не в `~/.claude/CLAUDE.md`.

## Стандарт хранения проектов (Windows-контур, 2026-09-15)

- Правило — скилл `skills/shared/project-structure`; шаблон проекта — `templates/project/`, новый проект —
  `new-project.bat <Claude|Antigravity> <имя>` в корне AI Projects (`scripts/new-project.ps1`).
- Скиллы по применимости: `skills/shared/` (все агенты), `skills/claude/` (только Claude), `skills/antigravity/`.
  `install.ps1` раздаёт `shared` и `claude`.
- Утилиты: `scripts/check-structure.py` (линтер, ничего не меняет), `scripts/snapdiff.py` (дифф для приёмки без git).
- `_archive/` — отключённое старое.
