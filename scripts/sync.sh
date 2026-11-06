#!/bin/zsh
# Автосинхронизация _instruments на Mac: fast-forward из origin/main и, если пришли
# новые коммиты, install.sh. Кто запускает:
#   - launchd (ставит install.sh) с ключом --scheduled: при входе в систему и каждый час,
#     но прогон идёт только в 04 часа по МСК (пояс Мака в поездке может быть другим),
#     после загрузки системы или если последней проверке больше суток (Мак спал ночью);
#   - хук Claude при старте сессии, если последняя проверка старше 15 минут.
# Ничего не форсирует: при своих правках, незапушенных коммитах или другой ветке
# только пишет причину в файл состояния и показывает уведомление.
# Состояние: ~/.local/state/instruments-sync/status  (ok|warn|fail<TAB>unix-время<TAB>текст)
# Журнал:    ~/.local/state/instruments-sync/sync.log  (время МСК)
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:$PATH
export GIT_TERMINAL_PROMPT=0
HERE=${0:A:h}
REPO=${HERE:h}
STATE=$HOME/.local/state/instruments-sync
STATUS=$STATE/status
LOG=$STATE/sync.log
LOCK=$STATE/lock
mkdir -p "$STATE"

if [[ $1 == --scheduled ]]; then
  # Прогон, если: 04 часа МСК, или с загрузки системы ещё не проверяли, или проверке больше суток.
  hour=$(TZ=Europe/Moscow date +%H); last=0
  [[ -f $STATUS ]] && last=$(cut -f2 "$STATUS")
  boot=$(sysctl -n kern.boottime | sed -E 's/.*sec = ([0-9]+).*/\1/')
  (( ${hour#0} != 4 && ${last:-0} > ${boot:-0} && $(date +%s) - ${last:-0} < 86400 )) && exit 0
fi

# Один прогон за раз; замок старше 30 минут остался от упавшего прогона.
if ! mkdir "$LOCK" 2>/dev/null; then
  [[ -n $(find "$LOCK" -maxdepth 0 -mmin +30 2>/dev/null) ]] || exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
[[ -f $LOG && $(stat -f%z "$LOG") -gt 1000000 ]] && mv -f "$LOG" "$LOG.old"

log() { print -r -- "$(TZ=Europe/Moscow date '+%F %T') МСК $*" >> "$LOG" }

finish() {   # finish <ok|warn|fail> <текст> — переезды, записать состояние и выйти
  local st=$1 text=$2 prev="" mig mcode
  # Разовые переезды (scripts/migrate.py) — на каждом прогоне: занятая в прошлый раз папка
  # переименуется в следующий; новые переезды приходят вместе с подтянутыми коммитами.
  if [[ -f $REPO/scripts/migrate.py ]] && xcode-select -p >/dev/null 2>&1 && [[ -x /usr/bin/python3 ]]; then
    mig=$(/usr/bin/python3 "$REPO/scripts/migrate.py" 2>&1); mcode=$?
    [[ -n $mig ]] && log "переезды: ${mig//$'\n'/ |}"
    if (( mcode == 2 )) && [[ $st == ok ]]; then
      st=warn; text="$text; переезд не прошёл: $(print -r -- "$mig" | grep '!' | sed 's/^ *! *//' | paste -sd';' -)"
    fi
    # Правила — тоже на каждом прогоне: правка ~/.config/ai-rules/personal.md доходит без нового коммита.
    mig=$(/usr/bin/python3 "$REPO/scripts/compose-rules.py" 2>&1)
    [[ $mig == *'!'* || $mig == *'rules ->'* ]] && log "правила: ${mig//$'\n'/ |}"
  fi
  [[ -f $STATUS ]] && prev=$(<"$STATUS")
  print -r -- "$st	$(date +%s)	$text" > "$STATUS"
  log "$st: $text"
  # Уведомление — только когда проблема новая, чтобы не сыпать при каждом прогоне.
  if [[ $st != ok && ${prev#*	*	} != "$text" ]]; then
    osascript - "$text" >/dev/null 2>&1 <<'EOF'
on run argv
  display notification (item 1 of argv) with title "_instruments не синхронизирован"
end run
EOF
  fi
  exit 0
}

cd "$REPO" 2>/dev/null || finish fail "нет доступа к $REPO (если папка на Рабочем столе — дать /bin/zsh доступ: Настройки → Конфиденциальность → Полный доступ к диску)"
git rev-parse --git-dir >/dev/null 2>&1 || finish fail "git не читает $REPO (нет git или нет доступа к папке)"
branch=$(git symbolic-ref --quiet --short HEAD) || finish fail "в _instruments отсоединённый HEAD — синхронизация остановлена"
[[ $branch == main ]] || finish fail "_instruments на ветке $branch, а не main — синхронизация остановлена"
err=$(git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30 fetch --quiet origin 2>&1) \
  || finish fail "нет связи с GitHub: ${${(f)err}[-1]}"

dirty=$(git status --porcelain)
dirty_list=$(print -r -- "$dirty" | head -3 | cut -c4- | paste -sd, - | sed 's/,/, /g')
ahead=$(git rev-list --count origin/main..HEAD)
behind=$(git rev-list --count HEAD..origin/main)

if (( behind == 0 )); then
  (( ahead > 0 )) && finish warn "$ahead коммит(ов) не отправлено в GitHub"
  [[ -n $dirty ]] && finish warn "незакоммиченные правки: $dirty_list"
  finish ok "актуально ($(git rev-parse --short HEAD))"
fi
(( ahead > 0 )) && finish fail "ветки разошлись: здесь $ahead своих коммитов, в GitHub $behind новых — нужен ручной разбор"
[[ -n $dirty ]] && finish fail "в GitHub $behind новых коммитов, но здесь незакоммиченные правки: $dirty_list"

old=$(git rev-parse --short HEAD)
err=$(git merge --ff-only --quiet origin/main 2>&1) || finish fail "fast-forward не прошёл: ${${(f)err}[-1]}"
new=$(git rev-parse --short HEAD)
log "подтянуто $old..$new"
INSTRUMENTS_SYNC=1 zsh "$REPO/install.sh" >> "$LOG" 2>&1 || finish fail "install.sh упал, журнал: $LOG"
finish ok "обновлено $old → $new ($behind коммит(ов))"
