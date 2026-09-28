#!/bin/zsh
# Слежение за проектом: одна строка на событие — новый коммит или изменение файлов задач.
#   zsh watch-tasks.sh <папка проекта> [путь …]     пути относительно проекта
# По умолчанию — только docs/tasks, без папки отчётов (экономия токенов, 2026-09-28: каждое событие = ход сессии).
# WATCH_MATCH=<рег. выражение> — сообщать только о файлах, чьё имя подходит (свой ID задачи: _CM, _T2 …).
# WATCH_COMMITS=1 — ещё и коммиты. Интервал — WATCH_INTERVAL (сек, по умолчанию 10).
# Никогда не выходит сам: остановка — снаружи (TaskStop / Ctrl+C / таймаут монитора).

cd "$1" 2>/dev/null || { echo "ОШИБКА: нет папки $1"; exit 1; }
shift
paths=("$@"); (( $#paths )) || paths=(docs/tasks)
iv=${WATCH_INTERVAL:-10}

# снимок: "путь<TAB>время изменения", отсортирован по пути
snap() { for p in $paths; do [[ -e $p ]] && find "$p" -type f ! -path '*/reports/*' -exec stat -f '%N	%m' {} + 2>/dev/null; done |
  { [[ -n $WATCH_MATCH ]] && grep -E -- "$WATCH_MATCH" || cat; } | sort; }
isgit=0; [[ $WATCH_COMMITS == 1 ]] && git rev-parse --is-inside-work-tree >/dev/null 2>&1 && isgit=1
head=""; (( isgit )) && head=$(git rev-parse HEAD 2>/dev/null)
prev=$(snap)
echo "СЛЕЖУ: ${PWD:t} → ${paths[*]}${WATCH_MATCH:+ (только $WATCH_MATCH)}$( (( isgit )) && echo ' + коммиты'), каждые ${iv} с"

while true; do
  sleep $iv
  if (( isgit )); then
    h=$(git rev-parse HEAD 2>/dev/null)
    if [[ -n $h && $h != $head ]]; then
      git log --format='КОММИТ %h %s' ${head:+$head..}$h 2>/dev/null | head -20
      head=$h
    fi
  fi
  cur=$(snap)
  if [[ $cur != $prev ]]; then
    typeset -A old new; old=(); new=()
    for l in ${(f)prev}; do old[${l%%$'\t'*}]=${l##*$'\t'}; done
    for l in ${(f)cur};  do new[${l%%$'\t'*}]=${l##*$'\t'}; done
    for f in ${(k)new}; do
      if [[ -z ${old[$f]} ]]; then echo "НОВЫЙ ФАЙЛ $f"
      elif [[ ${old[$f]} != ${new[$f]} ]]; then echo "ИЗМЕНЁН $f"; fi
    done
    for f in ${(k)old}; do [[ -z ${new[$f]} ]] && echo "УДАЛЁН $f"; done
    prev=$cur
  fi
done
