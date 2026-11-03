#!/bin/zsh
# Раскладывает общие скиллы и правила для Claude на этом Mac:
#   skills/shared/*            → ~/.claude/skills/<имя>      (символические ссылки)
#   skills/vendor/{shared,claude}/* → ~/.claude/skills/<имя> (сторонние, vendor-skills.txt)
#   project-skills.txt         → ~/.claude/skills/<имя>      (ссылки на скиллы проектов)
#   rules/CLAUDE.global.md     → ~/.claude/CLAUDE.md         (ссылка)
#                              → ~/.codex/AGENTS.md, ~/.gemini/GEMINI.md (тот же файл для всех агентов)
#   skills/shared/*, skills/vendor/shared/* → ~/.gemini/config/skills/<имя> (Antigravity IDE; только если ~/.gemini есть)
#                                           → ~/.gemini/antigravity-cli/skills/<имя> (agy; если есть эта папка)
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
echo "Сторонние скиллы (vendor-skills.txt):"
for d in "$HERE"/skills/vendor/{shared,claude}/*(N/); do link "$d" "$DEST/${d:t}"; done
echo "Скиллы проектов:"
grep -v '^\s*#' "$HERE/project-skills.txt" | grep -v '^\s*$' | while read -r rel; do
  link "$AI/$rel" "$DEST/${rel:t}"
done
echo "Правила:"
link "$HERE/rules/CLAUDE.global.md" "$HOME/.claude/CLAUDE.md"
if [[ -d $HOME/.gemini ]]; then
  echo "Antigravity (общие скиллы):"
  mkdir -p "$HOME/.gemini/config/skills"
  for d in "$HERE"/skills/shared/*(/) "$HERE"/skills/vendor/shared/*(N/); do link "$d" "$HOME/.gemini/config/skills/${d:t}"; done
fi
if [[ -d $HOME/.gemini/antigravity-cli ]]; then
  echo "Antigravity CLI agy (общие скиллы):"
  mkdir -p "$HOME/.gemini/antigravity-cli/skills"
  for d in "$HERE"/skills/shared/*(/) "$HERE"/skills/vendor/shared/*(N/); do link "$d" "$HOME/.gemini/antigravity-cli/skills/${d:t}"; done
fi
# Codex: user skills; preserve old files in a separate backup.
CODEX_DEST=$HOME/.agents/skills
BAK=$HOME/.codex/_backup-$(date +%Y%m%d-%H%M%S)
mkdir -p "$CODEX_DEST" "$HOME/.codex"
echo "Codex skills:"
for d in "$HERE"/skills/shared/*(N/) "$HERE"/skills/vendor/{shared,claude}/*(N/) "$HERE"/skills/codex/*(N/); do
  link "$d" "$CODEX_DEST/${d:t}"
done
grep -v '^\s*#' "$HERE/project-skills.txt" | grep -v '^\s*$' | while read -r rel; do
  link "$AI/$rel" "$CODEX_DEST/${rel:t}"
done
link "$HERE/rules/CLAUDE.global.md" "$HOME/.codex/AGENTS.md"
# Antigravity: общие правила в ~/.gemini/GEMINI.md — тот же файл.
if [[ -d $HOME/.gemini ]]; then
  BAK=$HOME/.gemini/_backup-$(date +%Y%m%d-%H%M%S)
  link "$HERE/rules/CLAUDE.global.md" "$HOME/.gemini/GEMINI.md"
fi
echo "Готово."
