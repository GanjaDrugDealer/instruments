#!/bin/zsh
# Раскладывает общие скиллы и правила для Claude на этом Mac:
#   skills/shared/*            → ~/.claude/skills/<имя>      (символические ссылки)
#   project-skills.txt         → ~/.claude/skills/<имя>      (ссылки на скиллы проектов)
#   rules/CLAUDE.global.md     → ~/.claude/CLAUDE.md         (ссылка)
#   skills/shared/*            → ~/.gemini/config/skills/<имя> (Antigravity; только если ~/.gemini есть)
# Что уже лежит на месте не ссылкой — переносится в ~/.claude/_backup-<дата>/.
# Запуск: zsh install.sh   (повторный запуск безопасен)
set -e
HERE=${0:A:h}
AI=${HERE:h}                          # папка «AI Projects»
DEST=$HOME/.claude/skills
BAK=$HOME/.claude/_backup-$(date +%Y%m%d-%H%M%S)
mkdir -p "$DEST"

link() {   # link <источник> <куда>
  local src=$1 dst=$2
  [[ -e $src ]] || { echo "  нет $src — пропуск"; return; }
  if [[ -L $dst ]]; then rm "$dst"
  elif [[ -e $dst ]]; then mkdir -p "$BAK"; mv "$dst" "$BAK/"; echo "  старое ${dst:t} → $BAK/"
  fi
  ln -s "$src" "$dst"; echo "  ${dst:t} → $src"
}

echo "Общие скиллы:"
for d in "$HERE"/skills/shared/*(/); do link "$d" "$DEST/${d:t}"; done
echo "Скиллы проектов:"
grep -v '^\s*#' "$HERE/project-skills.txt" | grep -v '^\s*$' | while read -r rel; do
  link "$AI/$rel" "$DEST/${rel:t}"
done
echo "Правила:"
link "$HERE/rules/CLAUDE.global.md" "$HOME/.claude/CLAUDE.md"
if [[ -d $HOME/.gemini ]]; then
  echo "Antigravity (общие скиллы):"
  mkdir -p "$HOME/.gemini/config/skills"
  for d in "$HERE"/skills/shared/*(/); do link "$d" "$HOME/.gemini/config/skills/${d:t}"; done
fi
echo "Готово."
