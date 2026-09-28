#!/bin/zsh
# Регрессионные тесты уникализатора. Запуск: zsh scripts/2026-09-25_uniquifier-tests.sh
# Одна строка на тест + итог. Код выхода 0 — всё прошло.

HERE=${0:A:h}
SCRIPT="$HERE/2026-09-22_uniquifier-mac.command"
FF="$HOME/.uniquifier/bin/ffmpeg"; FP="$HOME/.uniquifier/bin/ffprobe"
[[ -x $FF && -x $FP ]] || { print "Нет ffmpeg/ffprobe в ~/.uniquifier/bin — запусти основной скрипт один раз"; exit 2 }

T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
pass=0; fail=0
ok()  { print "PASS  $1"; (( ++pass )) }
bad() { print "FAIL  $1 — $2"; (( ++fail )) }

run()   { zsh "$SCRIPT" "$@" >"$T/last.log" 2>&1 }
mp4s()  { reply=("$1"/*.mp4(N)) }
dims()  { "$FP" -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$1" }
audio() { "$FP" -v error -select_streams a:0 -show_entries stream=index -of csv=p=0 "$1" }
dur()   { "$FP" -v error -show_entries format=duration -of csv=p=0 "$1" }
ctime() { "$FP" -v error -show_entries format_tags=creation_time -of csv=p=0 "$1" }
luma()  { "$FF" -v error -i "$1" -vf "crop=8:8:$2:$3,format=gray" -frames:v 1 -f rawvideo - |
          od -An -tu1 | awk '{for(i=1;i<=NF;i++){s+=$i;n++}} END{print int(s/n)}' }

# ---------- фикстуры ----------
gen() { "$FF" -v error -y "$@" }
gen -f lavfi -i testsrc=size=640x360:rate=25:duration=2 -f lavfi -i sine=frequency=440:duration=2 \
    -c:v libx264 -c:a aac -shortest "$T/a.mp4"
gen -f lavfi -i testsrc=size=640x360:rate=25:duration=2 -c:v libx264 "$T/noaudio.mp4"
gen -i "$T/a.mp4" -c copy "$T/clip.mov"
gen -f lavfi -i color=white:size=640x360:duration=1:rate=5 -c:v libx264 "$T/white.mp4"
gen -f lavfi -i color=black:size=640x360:duration=1:rate=5 \
    -vf drawbox=x=0:y=0:w=60:h=360:color=white:t=fill -c:v libx264 "$T/marker.mp4"
mkdir -p "$T/Папка с пробелами"; cp "$T/a.mp4" "$T/Папка с пробелами/ролик 1.mp4"
print "not a video" > "$T/broken.mp4"

# ---------- тесты ----------
zsh -n "$SCRIPT" && ok "синтаксис" || bad "синтаксис" "zsh -n"

run -o "$T/o1" "$T/a.mp4"; mp4s "$T/o1"
if (( ${#reply} == 1 )) && [[ $(dims $reply[1]) == 1080x1920 && -n $(audio $reply[1]) ]]
then ok "все функции: 1080x1920, звук есть"; else bad "все функции" "$(tail -1 $T/last.log)"; fi

run -o "$T/o2" "$T/noaudio.mp4"; mp4s "$T/o2"
if (( ${#reply} == 1 )) && [[ -z $(audio $reply[1]) ]]
then ok "видео без звука"; else bad "видео без звука" "$(tail -1 $T/last.log)"; fi

run -o "$T/o3" "$T/clip.mov"; mp4s "$T/o3"
if (( ${#reply} == 1 )) && [[ $(dims $reply[1]) == 1080x1920 ]]
then ok ".mov на входе"; else bad ".mov на входе" "$(tail -1 $T/last.log)"; fi

run -o "$T/выход с пробелом" "$T/Папка с пробелами/ролик 1.mp4"; mp4s "$T/выход с пробелом"
(( ${#reply} == 1 )) && ok "кириллица и пробелы в путях" || bad "кириллица и пробелы" "$(tail -1 $T/last.log)"

run --only=color,rotate -o "$T/o5" "$T/a.mp4"; mp4s "$T/o5"
d=$(dims "$reply[1]" 2>/dev/null); w=${d%x*}; h=${d#*x}
if (( ${#reply} == 1 )) && [[ $d != 1080x1920 ]] && (( w % 2 == 0 && h % 2 == 0 ))
then ok "--only=color,rotate ($d, чётные стороны)"; else bad "--only=color,rotate" "dims=$d"; fi

run --skip=scale -o "$T/o6" "$T/a.mp4"; mp4s "$T/o6"
d=$(dims "$reply[1]" 2>/dev/null)
(( ${#reply} == 1 )) && [[ $d != 1080x1920 ]] && ok "--skip=scale ($d)" || bad "--skip=scale" "dims=$d"

run --only=flip -o "$T/o7" "$T/marker.mp4"; mp4s "$T/o7"
if (( ${#reply} == 1 )); then
  l=$(luma $reply[1] 5 170); r=$(luma $reply[1] 620 170)
  (( l < 50 && r > 200 )) && ok "flip: блок слева ушёл вправо" || bad "flip" "лево=$l право=$r"
else bad "flip" "$(tail -1 $T/last.log)"; fi

rot_bad=""
for i in {1..5}; do
  run --only=rotate -o "$T/o8_$i" "$T/white.mp4"; mp4s "$T/o8_$i"
  (( ${#reply} == 1 )) || { rot_bad="прогон $i упал"; break }
  d=$(dims $reply[1]); w=${d%x*}; h=${d#*x}
  for xy in "0 0" "$((w-8)) 0" "0 $((h-8))" "$((w-8)) $((h-8))"; do
    v=$(luma $reply[1] ${=xy}); (( v > 200 )) || rot_bad="прогон $i, угол ($xy) яркость $v"
  done
done
[[ -z $rot_bad ]] && ok "rotate: нет чёрных углов (5 случайных углов)" || bad "rotate" "$rot_bad"

run --only=speed -o "$T/o9" "$T/a.mp4" "$T/a.mp4" "$T/broken.mp4" "$T/a.mp4" "$T/a.mp4"; mp4s "$T/o9"
batch=("${reply[@]}")
if (( ${#batch} == 4 )) && grep -q broken.mp4 "$T/o9/errors.log" 2>/dev/null
then ok "батч: 4 из 5, битый файл в errors.log"; else bad "батч" "файлов ${#batch}"; fi

distinct=$(for f in $batch; do dur $f; done | sort -u | wc -l | tr -d ' ')
(( distinct >= 2 )) && ok "батч: разная рандомизация ($distinct разных длительностей из 4)" \
                     || bad "батч: рандомизация" "все длительности одинаковые"

date_bad=""
for f in $batch; do
  ct=$(ctime $f); ct=${ct%%.*}
  [[ $ct > 2026-02-01 && $ct < 2026-09-02 ]] || date_bad="creation_time вне диапазона: $ct"
  ce=$(date -j -u -f "%Y-%m-%dT%H:%M:%S" "$ct" +%s 2>/dev/null)
  [[ $ce == $(stat -f %m $f) ]] || date_bad="mtime ≠ creation_time у ${f:t}"
done
[[ -z $date_bad ]] && ok "даты: в диапазоне, mtime = creation_time" || bad "даты" "$date_bad"

run --only=teleport -o "$T/o10" "$T/a.mp4"
(( $? == 1 )) && grep -q "неизвестная функция" "$T/last.log" && ok "ошибка: неизвестная функция" \
                                                              || bad "неизвестная функция" "не упал"

run --only=color --skip=noise -o "$T/o11" "$T/a.mp4"
(( $? == 1 )) && grep -q "одновременно" "$T/last.log" && ok "ошибка: --only вместе с --skip" \
                                                       || bad "--only + --skip" "не упал"

run --keep-name --only=color -o "$T/o12" "$T/clip.mov" "$T/Папка с пробелами/ролик 1.mp4"
[[ -f "$T/o12/clip.mp4" && -f "$T/o12/ролик 1.mp4" ]] && ok "--keep-name: исходные имена сохранены" \
                                                     || bad "--keep-name" "$(ls "$T/o12")"

print "\nИтог: $pass прошло, $fail упало"
(( fail == 0 ))
