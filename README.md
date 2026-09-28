# ai-instruments

Общие скиллы и правила для всех проектов из папки «AI Projects». Работает на macOS и Windows.

## Раскладка папок (одинаковая на обеих машинах)

```
AI Projects/
├── _Instruments/            ← этот репозиторий
│   ├── skills/shared/       общие скиллы (file-links, watch-tasks, watch-executors, video-frame-sheets, …)
│   ├── rules/CLAUDE.global.md   глобальные правила (→ ~/.claude/CLAUDE.md)
│   ├── project-skills.txt   скиллы проектов, нужные и вне их папок
│   ├── install.sh / install.ps1
│   └── bin/                 личные инструменты машины (gh и т.п.), не в git
└── Claude/<проект>/         проекты (у каждого свой репозиторий)
```

## Установка / обновление

После `git clone` или `git pull`:

- macOS: `zsh install.sh` — символические ссылки в `~/.claude/skills/` и на `~/.claude/CLAUDE.md`.
- Windows: `powershell -ExecutionPolicy Bypass -File install.ps1` — junction-ссылки на скиллы, `CLAUDE.md` копией
  (после каждого `git pull` запускать снова).

То, что уже лежало на месте не ссылкой, переносится в `~/.claude/_backup-<дата>/`.

## Правила

- Один скилл — одна копия. Общий скилл живёт здесь, проектный — в `.claude/skills/` своего проекта
  (если нужен и вне проекта — строка в `project-skills.txt`).
- В файлах проектов общие скиллы называть по имени (`file-links`, `watch-tasks`), без абсолютных путей.
- Правки глобальных правил — в `rules/CLAUDE.global.md`, не в `~/.claude/CLAUDE.md`.
