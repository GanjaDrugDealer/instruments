# Перенос на Windows — отчёт A1 «Инструменты» (2026-10-03 → 04)

Папка: `C:\AI Projects\_Instruments`, ветка `t17-windows`. Автор коммитов — artemganza, следов ИИ нет, push не делался.

## Сделано

### 1. T17.9 — zsh-скрипты общих скиллов на Python (коммит «feat: слежение и листы кадров на Python для Windows и Mac»)

- `skills/shared/watch-tasks/scripts/watch-tasks.py` — те же аргументы, переменные (`WATCH_MATCH`, `WATCH_COMMITS`,
  `WATCH_INTERVAL`, `WATCH_BOARD`) и те же строки вывода: `СЛЕЖУ`, `ЗАДАЧА ЖДЁТ`, `НОВЫЙ ФАЙЛ`, `ИЗМЕНЁН`, `УДАЛЁН`, `КОММИТ`.
- `skills/shared/watch-executors/scripts/watch-executors.py` — `СЛЕЖУ ЗА ИСПОЛНИТЕЛЯМИ`, `СДАЧА (до старта)`, `СДАЧА`,
  `В РАБОТЕ`, `КОММИТ`; `WATCH_WIP`, `WATCH_INTERVAL`, `WATCH_BOARD`.
- `skills/shared/video-frame-sheets/scripts/make-sheets.py` — те же позиционные аргументы (папка, роликов на лист, кадров);
  дополнительно `--ffmpeg` и `--out`. ffmpeg: `--ffmpeg` -> `$FFMPEG` -> `bin/ffmpeg(.exe)` -> PATH. Правки против оригинала:
  строки разной ширины добиваются чёрным до самой широкой (иначе `vstack` падает на роликах разного формата);
  одинаковый id у двух роликов не затирает кадры; сбой одного ролика не роняет всю партию.
- `motion-peaks.py`: ищет `bin/ffmpeg.exe`, читает вывод ffmpeg как UTF-8 (мелкая правка под Windows).
- `.sh` не удалялись. В трёх `SKILL.md` основной командой стал Python (`py -X utf8` / `python3`), `.sh` помечен как старая
  мак-версия. В `video-frame-sheets/SKILL.md` убрана устаревшая фраза про `mdls` (скрипт её не использовал).
- Только стандартная библиотека. Вывод принудительно UTF-8, `flush` на каждой строке (нужно для Monitor).

**Проверка make-sheets** (из пустой папки `%TEMP%\a1-run`, вывод вне J:):

```
py -X utf8 ...\make-sheets.py "J:/YotubeСНГ/CS СНГ/REACTIONS/Source/1" 2 4 --out %TEMP%\a1-sheets
готово: 3 лист(ов) в ...\Temp\a1-sheets\sheets        (16 с, 5 роликов, код выхода 0)
лист 1, строка 1: IMG_9476  [5.75 9.50 16.75 23.75]
лист 1, строка 2: IMG_9477  [10.25 15.75 18.75 22.75]
лист 2, строка 1: IMG_9478  ... лист 3, строка 1: IMG_9480
```

`sheet_1.jpg` открыт через Read: сетка 2 строки x 4 кадра (по строке на ролик, разные моменты, жесты видны).
Путь с кириллицей и пробелом сработал. Отдельно прогнан синтетический случай: два ролика 640x360 и 360x640,
папка с кириллицей и пробелом в пути, вывод по умолчанию (`data/frames`, `out/sheets` в cwd) — лист 1386x520, без ошибок.
Медиа на J: только читалось.

**Проверка watch-*** (временный git-проект `%TEMP%\a1 заглушка`, интервал 1 с, процессы затем убиты, `tasklist` пуст):

```
watch-tasks (WATCH_MATCH=_CM, WATCH_COMMITS=1):
  СЛЕЖУ: a1 заглушка → docs/tasks (только _CM) + коммиты, каждые 1 с
  ЗАДАЧА ЖДЁТ docs/tasks/2026-10-03_CM1_zadacha.md       (CM2 «принято» и T2 не свой — не показаны)
  ИЗМЕНЁН docs/tasks/2026-10-03_CM1_zadacha.md
  НОВЫЙ ФАЙЛ docs/tasks/2026-10-03_CM3_новая.md
  КОММИТ f6e8018 задача CM3
  УДАЛЁН docs/tasks/2026-10-03_CM3_новая.md
watch-executors (WATCH_WIP=1):
  СДАЧА (до старта) docs/tasks/reports/2026-10-03_T2_report.md
  В РАБОТЕ docs/tasks/2026-10-03_CM1_zadacha.md docs/tasks/2026-10-03_CM3_новая.md
  СДАЧА docs/tasks/reports/2026-10-03_CM1_report.md
  КОММИТ f6e8018 задача CM3
  В РАБОТЕ — всё закоммичено
```

Не проверялись: реальный запуск через инструмент `Monitor` внутри сессии Claude (проверен только как обычный фоновый процесс);
оригинальные `.sh` на Mac с Windows не сравнивались построчно — вывод повторён по тексту скриптов.

### 2. Формат ссылок Windows (коммит «docs: формат ссылок на файлы для Windows зафиксирован»)

`rules/CLAUDE.global.md` и `skills/shared/file-links/SKILL.md`: `[имя](file:///C:/AI%20Projects/…)`, прямые слэши, пробелы `%20`,
кириллица как есть. Пометка «проверить при первом запуске» убрана, Mac-формат оставлен. Фактически в приложении формат
не открывался (ночью, без экрана) — зафиксирован по заданию владельца.

### 3. check-structure

`python -X utf8 scripts/check-structure.py` — ничего не чинилось. Итог: «по стандарту 13, замечания 5, расхождения 10».
Расхождения (`[!]`): api_automation_youtube, content-manager, cut-and-render, mac-local, photo-pic, reaction-tagger,
reloacate-projects (нет CLAUDE/AGENTS/GUARDRAILS/.env.example/.claude/skills), VPN-main и `youtube-` (имя папки не kebab-case),
youtube-shorts-cs (следы Google Диска/K: в `AGENTS.md:67` и `docs/2026-09-30_pereezd-windows.md`).
Замечания (`[~]`): content-unifier, hh-ru-automation, pc-automation, photo-pipeline, smm-planner (абсолютные пути наружу).
Полный вывод — командой выше (66 строк). Папки `youtube-` и `reloacate-projects` выглядят как мусор/опечатки — решать владельцу.

### 4. install.ps1

Прогнан после коммитов 1–2: «CLAUDE.md copied», `~/.claude/CLAUDE.md` содержит новую строку про `file:///`, старой пометки нет;
junction-ы скиллов на месте (Claude и Antigravity).

## Осталось / нужно от владельца

- Сами `.sh` остаются для мака; на Mac проверить `python3 make-sheets.py` и `watch-*.py` при случае (код кроссплатформенный,
  но на Mac не запускался).
- Копии `video-frame-sheets` в проектах (`content-manager`, `reaction-tagger`) — синхронизирует архитектор.
- Файл `docs/2026-10-04_windows-port-plan.md` не тронут и не закоммичен (по заданию).
