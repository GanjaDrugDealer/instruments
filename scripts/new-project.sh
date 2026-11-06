#!/bin/zsh
# Создание нового проекта из шаблона _instruments/templates/project (Mac).
# Пара к new-project.ps1 (Windows): те же аргументы, проверки и коды выхода.
#   zsh new-project.sh [Claude|Antigravity|Local|Codex] [имя] [--no-prompt]
#   --no-prompt — для агента: ничего не спрашивать, при ошибке выйти с кодом 2.
# Человеку: двойной щелчок по «AI Projects/new-project.command».
set -e
HERE=${0:A:h}
ROOT=${HERE:h:h}                       # папка «AI Projects»
TEMPLATE=$ROOT/_instruments/templates/project
OVERLAY=$ROOT/_instruments/templates/project-local

Branch= Name= NoPrompt=
for a in "$@"; do
  case $a in
    --no-prompt|-y) NoPrompt=1 ;;
    *) if [[ -z $Branch && $a == (Claude|Antigravity|Local|Codex) ]]; then Branch=$a
       elif [[ -z $Name ]]; then Name=$a
       else echo "  Лишний аргумент: $a"; exit 2; fi ;;
  esac
done
[[ -n $NoPrompt && -z $Branch ]] && Branch=Claude   # ветка по умолчанию — Claude

# Ветка: кто ведёт проект
while [[ $Branch != (Claude|Antigravity|Local|Codex) ]]; do
  read "ans?Кто ведёт проект? 1 - Claude, 2 - Antigravity, 3 - Local, 4 - Codex [1]: "
  case $ans in
    ''|1|Claude|claude)       Branch=Claude ;;
    2|Antigravity|antigravity) Branch=Antigravity ;;
    3|Local|local)            Branch=Local ;;
    4|Codex|codex)            Branch=Codex ;;
    *) echo "Введите 1, 2, 3 или 4." ;;
  esac
done

# Имя папки: латиница в нижнем регистре, цифры, дефис
while true; do
  [[ -z $Name ]] && { read "Name?Название папки проекта (латиница, kebab-case, например logo-script): "; Name=${Name// /}; }
  dest=$ROOT/$Branch/$Name
  if [[ ! $Name =~ '^[a-z0-9]+(-[a-z0-9]+)*$' ]]; then
    echo "  '$Name' не подходит: только a-z, 0-9 и дефис между словами."
  elif [[ -d $dest && -n $(ls -A "$dest") ]]; then
    echo "  Папка уже существует и не пустая: $dest"
  else break; fi
  [[ -n $NoPrompt ]] && exit 2
  Name=
done

mkdir -p "$dest"
cp -R "$TEMPLATE"/. "$dest"/

# Для Local — оверлей поверх шаблона
if [[ $Branch == Local ]]; then
  cp -R "$OVERLAY"/. "$dest"/
fi

# Подстановки в живых файлах
python3 - "$dest" "$Name" "$(date +%F)" <<'EOF'
import sys, pathlib
dest, name, date = sys.argv[1:]
for f, subs in {"CLAUDE.md": {"<project-name>": name}, "STATE.md": {"<date>": date}}.items():
    p = pathlib.Path(dest, f)
    if p.exists():
        t = p.read_text(encoding="utf-8")
        for k, v in subs.items(): t = t.replace(k, v)
        p.write_text(t, encoding="utf-8")
EOF

echo
echo "Создан проект: $dest"
if [[ $Branch == Local ]]; then
    echo "⚠ Локальные модели (Ollama) есть только на Windows-ПК."
    echo "Дальше: запустить sync_webui_project.py и выбрать в Open WebUI модель с именем проекта:"
    echo "  python -X utf8 \"C:\\AI Projects\\Antigravity\\local-gpt\\scripts\\sync_webui_project.py\" \"$dest\""
elif [[ $Branch == Codex ]]; then
    echo "Дальше: открыть эту папку в Codex и написать «Собираем контекст»."
else
    echo "Дальше: открыть эту папку в Claude Code и написать «Собираем контекст»."
fi
