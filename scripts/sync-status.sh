#!/bin/zsh
# Хук SessionStart для Claude Code (ставит install.sh): молчит, если _Instruments
# синхронизирован, иначе пишет агенту одну строку. Если последняя проверка старше
# 15 минут — запускает sync.sh в фоне (из процесса Claude, у которого есть доступ
# к Рабочему столу, даже если launchd его не получил). Свежие скиллы увидит
# следующая сессия: список скиллов грузится при старте.
HERE=${0:A:h}
STATUS=$HOME/.local/state/instruments-sync/status
now=$(date +%s)
state=none; ts=0; msg=""
[[ -f $STATUS ]] && IFS=$'\t' read -r state ts msg < "$STATUS"
(( now - ts > 900 )) && { zsh "$HERE/sync.sh" </dev/null >/dev/null 2>&1 &! }

msk() { TZ=Europe/Moscow date -r "$1" '+%d.%m %H:%M МСК' }
tell="Скажи пользователю об этом одной короткой строкой."
if [[ $state == none ]]; then
  print "_Instruments: автосинхронизация на этой машине ещё не отрабатывала, запущена сейчас. $tell"
elif (( now - ts > 172800 )); then
  print "_Instruments: последняя проверка обновлений $(msk $ts), больше двух суток назад — фоновая задача, похоже, не работает. $tell"
elif [[ $state != ok ]]; then
  print "_Instruments: $msg (проверено $(msk $ts)). $tell"
fi
exit 0
