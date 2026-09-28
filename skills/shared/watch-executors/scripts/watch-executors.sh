#!/bin/zsh
# Слежение архитектора за исполнителями: одна строка на событие.
#   zsh watch-executors.sh <папка проекта> [папка отчётов=docs/tasks/reports]
# СДАЧА <файл>        — новый или изменённый отчёт исполнителя (главный сигнал: пора принимать)
# В РАБОТЕ <файлы>    — изменился набор незакоммиченных файлов (исполнитель что-то правит)
# КОММИТ <hash> <msg> — новый коммит (свой или чужой — разобрать)
# Интервал — WATCH_INTERVAL (сек, по умолчанию 10). Сам не выходит: остановка снаружи.

cd "$1" 2>/dev/null || { echo "ОШИБКА: нет папки $1"; exit 1; }
rep=${2:-docs/tasks/reports}
iv=${WATCH_INTERVAL:-10}
mkdir -p "$rep"

snap() { find "$rep" -type f ! -name '.gitkeep' -exec stat -f '%N	%m' {} + 2>/dev/null | sort; }
wip()  { git status --porcelain -uall 2>/dev/null | grep -v " $rep/" | awk '{print $2}' | sort | tr '\n' ' '; }
isgit=0; git rev-parse --is-inside-work-tree >/dev/null 2>&1 && isgit=1
head=""; (( isgit )) && head=$(git rev-parse HEAD 2>/dev/null)
prev=$(snap); pw=""; (( isgit )) && pw=$(wip)
echo "СЛЕЖУ ЗА ИСПОЛНИТЕЛЯМИ: ${PWD:t} → отчёты в $rep$( (( isgit )) && echo ' + рабочие файлы + коммиты'), каждые ${iv} с"
[[ -n $pw ]] && echo "В РАБОТЕ (на старте) $pw"

while true; do
  sleep $iv
  if (( isgit )); then
    h=$(git rev-parse HEAD 2>/dev/null)
    if [[ -n $h && $h != $head ]]; then
      git log --format='КОММИТ %h %s' ${head:+$head..}$h 2>/dev/null | head -20
      head=$h
    fi
    w=$(wip)
    if [[ $w != $pw ]]; then echo "В РАБОТЕ ${w:-— всё закоммичено}"; pw=$w; fi
  fi
  cur=$(snap)
  if [[ $cur != $prev ]]; then
    typeset -A old new; old=(); new=()
    for l in ${(f)prev}; do old[${l%%$'\t'*}]=${l##*$'\t'}; done
    for l in ${(f)cur};  do new[${l%%$'\t'*}]=${l##*$'\t'}; done
    for f in ${(k)new}; do
      [[ -z ${old[$f]} || ${old[$f]} != ${new[$f]} ]] && echo "СДАЧА $f"
    done
    prev=$cur
  fi
done
