# Ночной перенос проектов с Mac на Windows — план и ТЗ (2026-10-03 → 04)

Основа — `Claude/youtube-shorts-cs/docs/2026-09-30_pereezd-windows.md` (T17). Этот файл — раздача по исполнителям
и общие правила ночи. Архитектор (главная сессия) ведёт, принимает по диффу, пишет итоговый отчёт.

## Что уже сделано архитектором (вечер 03.10)

- Удалено 23 165 AppleDouble `._*` и 14 `.DS_Store` (C:\AI Projects и J:\YotubeСНГ; каждый сверен по сигнатуре 00 05 16 07).
- Флешка `J:\AI Projects` сверена с `C:\AI Projects` по хешам: потерь нет; 2 файла не перезаписались при копировании
  (`_Instruments\README.md`, `hh-ru-automation\.gitignore`) — восстановлены с флешки.
- Git: рабочие деревья `content-manager`, `photo-pic`, `youtube-shorts-cs`, `hh-ru-automation`, `_Instruments` = маковский HEAD.
- `_Instruments`: ветка `t17-windows`, в репозиторий добавлен Windows-контур (стандарт, шаблон, утилиты); `install.ps1` прогнан —
  все общие скиллы и `template-montage` подключены junction-ами, `~/.claude/CLAUDE.md` разложен.
- `youtube-shorts-cs`: ветка `t17-windows`; `.env` → `MEDIA_ROOT=J:/YotubeСНГ/CS СНГ`; `pending_ch*.json` → `secrets/_mac-pending/`;
  `pool.py`, `navigator.py`, `match.py --help` — работают (шаг 6 ok).
- ffmpeg/ffprobe 9.0.2 (gyan.dev, тот же, что в PATH через winget) — `bin\*.exe` в youtube-shorts-cs, content-manager,
  reaction-tagger, download-script; маковские бинарники перенесены в `bin\_mac\`. Windows сама дописывает `.exe`
  к вызову `bin\ffprobe`.
- `setx PYTHONUTF8 1`.

## Машина

Windows 11, Python 3.14.6 (`py`), Git, gh, Node, Chrome в Program Files, ffmpeg в PATH, RTX 5080 (драйвер 610.88).
numpy/opencv в системном Python НЕТ — ставить только в `.venv` проекта. C: свободно 83 ГБ.
`J:` — флешка с медиа (`J:\YotubeСНГ\CS СНГ`, 9,1 ГБ) и копией проектов (`J:\AI Projects`, только чтение).
На J: chkdsk 03.10 22:26 нашёл ошибки (`J:\FOUND.000`) — массово на J: не писать, тестовый вывод — в `_work`/`out`.

## Общие правила для всех исполнителей

1. Сначала прочитать: скилл `windows-ru-scripting` (`C:\AI Projects\_Instruments\skills\shared\windows-ru-scripting\SKILL.md`),
   `CLAUDE.md`/`AGENTS.md`, `STATE.md`, `GUARDRAILS.md` своих проектов.
2. Трогать только свои папки (таблица ниже). Чужое сломано — записать в отчёт, не чинить.
3. Git: ветка `t17-windows` (создать от текущего `main`), коммит на задачу. Автор — пользователь (как в истории),
   **никаких следов ИИ**: без `Co-Authored-By`, без слов Claude/AI в сообщениях. **Не пушить** — на ПК gh вошёл
   под `ganjadrugdealer-prog`, приватные репозитории `GanjaDrugDealer/*` ему не видны.
   Проекты без git — до первой правки `python -X utf8 "C:\AI Projects\_Instruments\scripts\snapdiff.py" snap "<папка>"`.
4. Ночной режим: без установщиков с правами администратора, без входа в аккаунты, без выкладки, без Google Диска,
   без боевой сборки и `handoff.py` с записью в журнал (только `render.py --test`). Скачивать можно официальные
   сборки с GitHub releases со сверкой SHA-256 и пакеты pip в `.venv` проекта.
5. Мак-скрипты (`.sh`, `.command`) не удалять — мак остаётся пультом. Замена — Python (одна версия на обе ОС) или
   `.ps1`/`.bat`-обёртка. `.ps1` — UTF-8 с BOM.
6. Абсолютные маковские пути в коде и CSV → относительные (от `MEDIA_ROOT` / от папки проекта). В исторических
   документах (`docs/` с датой) пути не переписывать.
7. Лимиты могут оборвать сессию: после каждой законченной задачи — коммит/снимок и строка в отчёте
   `<проект>/docs/2026-10-04_windows-port.md` (сделано, чем проверено — команда и вывод, что осталось).
   В конце — обновить `STATE.md` проекта (раздел «Сейчас»/«Следующий шаг»).
8. Итоговое сообщение архитектору — до 15 строк: сделано и проверено (команды), не сделано и почему, что нужно от владельца.

## Раздача

| Исполнитель | Модель | Папки (только они) | Задачи | Когда |
|---|---|---|---|---|
| A1 «Инструменты» | Sonnet | `_Instruments` (ветка `t17-windows` уже есть) | T17.9: `watch-tasks.sh`, `watch-executors.sh`, `video-frame-sheets/scripts/make-sheets.sh` → Python (обе ОС), SKILL.md обновить; `file-links` и `rules/CLAUDE.global.md` — проверенный формат ссылок Windows; `check-structure.py` прогнать | сразу |
| A3 «Загрузчик и уникализатор» | Sonnet | `download-script`, `mac-local`, `content-unifier` (только чтение) | T17.2: `yt-dlp.exe`, `deno.exe` в `bin\` (SHA-256), `.command` → `.py` + `.bat`, `fix-timebase.sh` → `.py`; проверка: скачать 1–2 ролика в `_work`. T17.3: `content-unifier\src\unifier-win.py` → `mac-local\scripts\` как Windows-уникализатор с тем же CLI, что у `.command` (скилл `uniquify-batch`), NVENC + фолбэк x264; проверка на 1 ролике (длина/цвет/шум отличаются, подписи кодировщика нет) | сразу |
| A2 «Конвейер» | Opus | `youtube-shorts-cs` (ветка `t17-windows` уже есть) | T17.1 `montage.sh`/`seam-view.sh` → `src/montage.py`, `render.py` зовёт его; T17.5 `shutil.move` вместо `Path.replace` между дисками (+ `SHARE_ROOT` по инструкции); T17.6 навигатор; T17.4 сводка через `schtasks` (`scripts/windows/install-daily.ps1`, **не регистрировать** — только скрипт); `config.py`: `UNIQUIFIER`/`TB_CHECK` по умолчанию на Windows-версии от A3; шаг 8 — `render.py --test` на уже собранном плане, сравнение ffprobe + листы кадров | после 1:10 |
| A4 «Роли и прочее» | Sonnet | `content-manager`, `cut-and-render`, `reaction-tagger`, `api_automation_youtube`, `hh-ru-automation`, `photo-pic`, `mac-local` — **нет** | T17.7 `content-plan.py` относительные ссылки; `avatar-frames.sh` → Python; `design-render.py` Chrome по ОС; `cut-and-render/montage.sh` и AGENTS.md (пути); `reaction-tagger`: 104 маковских пути в данных → от `MEDIA_ROOT`; `api_automation_youtube`: `.venv` под Windows + Playwright (профиль Chrome с мака на Windows не расшифруется — отметить вход владельцу); `hh-ru-automation`, `photo-pic`: собрать/запустить проверки под Windows, доложить | после 1:10 |

Порядок зависимостей: A3 → (путь Windows-уникализатора и `yt-dlp.exe`) → A2 подставляет в `config.py`.
Архитектор после всех: синхронизация копий общих скиллов в проектах (`content-manager`, `reaction-tagger`
`.claude/skills/video-frame-sheets`), память ролей, итоговый отчёт.

## Нужно от владельца (собирается в отчёт)

- `gh auth login` под `GanjaDrugDealer` (или доступ коллаборатора для `ganjadrugdealer-prog`) → push веток `t17-windows`.
- Память Claude с мака (`~/.claude/projects/-Users-artemganza-Desktop-AI-Projects*`) не перенесена.
- Медиа на флешке J: с ошибками ФС — решение: оставить на J: или скопировать на диск ПК.

## Сдано и принято (ночь)

- **A1** — принято: `_Instruments` t17-windows `b0119cc..27faf44`; отчёт `docs/2026-10-04_windows-port-A1.md`.
- **A3** — принято (снимок-дифф только в своих папках, тесты уникализатора 19/19 перепрогнаны архитектором).
  Пути для `youtube-shorts-cs/src/config.py` (A2), вызов — `[sys.executable, "-X", "utf8", <скрипт>, ...]`:
  - `YTDLP` = `download-script\bin\yt-dlp.exe` (как есть, без интерпретатора)
  - `TB_CHECK` = `download-script\scripts\2026-10-04_fix-timebase.py` → `check ФАЙЛ`; вывод `ok|x2|broken|nosound ОТНОШЕНИЕ`
  - `UNIQUIFIER` = `mac-local\scripts\2026-10-04_uniquifier-win.py` → `--only=color,noise,speed --keep-name -o ПАПКА ФАЙЛ`;
    код выхода всегда 0 — проверять наличие файла `ПАПКА\<имя>.mp4`; вывод читать `encoding="utf-8"`
  - `LOADER` = `download-script\scripts\2026-10-04_video-download.py` → `--to ПАПКА URL`; `tiktok_collections.py` сейчас зовёт `zsh` — заменить
  - На маке пути по умолчанию остаются прежними (`.command`/`.sh`) — ветвление по `WINDOWS` в `config.py`.
- Архитектору утром: перенести Windows-часть `uniquify-batch` из `mac-local/.claude/skills` в `_Instruments/skills/shared`,
  синхронизировать копии `video-frame-sheets` в проектах.
