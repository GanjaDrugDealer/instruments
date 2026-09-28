#!/bin/zsh
# UNIQUIFIER для macOS. Нужен только zsh (есть в системе).
# ffmpeg/ffprobe скачиваются сами при первом запуске в ~/.uniquifier/bin
#
# Запуск (диалоги):  zsh путь/к/файлу.command
#   — сначала чеклист "какие функции применить", потом выбор файлов и папки.
#
# Без диалогов:  zsh файл.command [--only=ФУНКЦИИ | --skip=ФУНКЦИИ] -o ПАПКА файл1.mp4 файл2.mov ...
#   Функции (через запятую): crop, scale, color, noise, rotate, speed, flip
#   --only=color,rotate   — применить только цвет и поворот
#   --skip=scale          — применить всё, кроме масштабирования
#   без --only/--skip     — применяются все функции (как раньше)
#   --keep-name           — не менять имя: исходное имя + .mp4
#
# Дата создания файла и случайное имя (если нет --keep-name) проставляются всегда, это не функция
# видео-обработки, а часть уникализации идентичности файла.

setopt no_nomatch
BIN_DIR="$HOME/.uniquifier/bin"
START_EPOCH=1769904000          # 2026-02-01 00:00:00 UTC
SPAN=$((212 * 86400))           # разброс дат: 212 дней
SAFE_SPECIAL='!@#$%^&()_+-=[]{};,~'
SEPS='_-.~+='
CHARS='abcdefghijklmnopqrstuvwxyz0123456789'
ALL_FUNCS=(crop scale color noise rotate speed flip)

die() { print -u2 "ОШИБКА: $*"; exit 1 }

# случайное целое 0..$1 в REPLY (без подоболочки: в zsh $RANDOM в $(...) повторяется)
rnd() { REPLY=$(( (RANDOM * 32768 + RANDOM) % ($1 + 1) )) }

rstr() {
  local s= i
  for i in {1..$1}; do s+=${CHARS[RANDOM % ${#CHARS} + 1]}; done
  REPLY=$s
}

gen_name() {
  local n sep
  while true; do
    rnd 12; rstr $((REPLY + 3)); n=$REPLY
    rnd 3
    if (( REPLY > 0 )); then
      sep=${SEPS[RANDOM % ${#SEPS} + 1]}
      rnd 3; rstr $((REPLY + 3)); n+="$sep$REPLY"
    fi
    (( RANDOM % 10 >= 7 )) && n+=${SAFE_SPECIAL[RANDOM % ${#SAFE_SPECIAL} + 1]}
    [[ -e "$1/$n.mp4" ]] || { REPLY="$n.mp4"; return }
  done
}

# дата из epoch: BSD date (macOS) или GNU date
fmt_date() { date $2 -r "$1" "+$3" 2>/dev/null || date $2 -d "@$1" "+$3" }

is_active() { (( ${ACTIVE[(Ie)$1]} )) }

find_tool() {
  if [[ -x "$BIN_DIR/$1" ]]; then print -r -- "$BIN_DIR/$1"; return; fi
  command -v "$1" 2>/dev/null
}

get_tools() {
  FFMPEG=$(find_tool ffmpeg); FFPROBE=$(find_tool ffprobe)
  if [[ -z $FFMPEG || -z $FFPROBE ]]; then
    [[ $(uname) == Darwin ]] || die "не найдены ffmpeg/ffprobe"
    print "ffmpeg не найден — скачиваю готовую сборку с evermeet.cx (один раз)..."
    mkdir -p "$BIN_DIR"
    local tmp=$(mktemp -d) t url
    for t in ffmpeg ffprobe; do
      url="https://evermeet.cx/ffmpeg/getrelease/zip"
      [[ $t == ffprobe ]] && url="https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"
      if ! { curl -fL --retry 2 --progress-bar -o "$tmp/$t.zip" "$url" &&
             unzip -o -q "$tmp/$t.zip" -d "$tmp" &&
             mv -f "$tmp/$t" "$BIN_DIR/$t" && chmod +x "$BIN_DIR/$t"; }; then
        rm -rf "$tmp"
        die "не удалось скачать $t. Скачай вручную с https://evermeet.cx/ffmpeg/ (ffmpeg и ffprobe) и положи оба файла в $BIN_DIR"
      fi
    done
    rm -rf "$tmp"
    xattr -dr com.apple.quarantine "$BIN_DIR" 2>/dev/null
    FFMPEG="$BIN_DIR/ffmpeg"; FFPROBE="$BIN_DIR/ffprobe"
  fi
  "$FFMPEG" -hide_banner -version >/dev/null 2>&1 || die "ffmpeg не запускается: $FFMPEG"
  "$FFPROBE" -hide_banner -version >/dev/null 2>&1 || die "ffprobe не запускается: $FFPROBE"
}

process() {
  local src=$1 out=$2
  local dims=$("$FFPROBE" -v error -select_streams v:0 -show_entries stream=width,height \
                -of csv=s=x:p=0 "$src" 2>/dev/null | head -1)
  if [[ $dims != <->x<->* ]]; then LAST_ERR="не удалось прочитать размеры видео"; return 1; fi
  local w=${dims%%x*} h=${${dims#*x}%%x*}
  local has_audio=$("$FFPROBE" -v error -select_streams a:0 -show_entries stream=index \
                     -of csv=p=0 "$src" 2>/dev/null)

  local -a vf=()
  local speed=1.000

  # Кроп: 1/1.1 по ширине со случайным сдвигом X, запас 2% по высоте для сдвига Y
  if is_active crop; then
    local nw=$(( w * 10 / 11 )); nw=$(( nw - nw % 2 ))
    local maxx=$(( w - nw )) maxy=$(( h * 2 / 100 ))
    local nh=$(( h - maxy )); nh=$(( nh - nh % 2 ))
    rnd $maxx; local cx=$REPLY
    rnd $maxy; local cy=$REPLY
    vf+="crop=${nw}:${nh}:${cx}:${cy}"
  fi

  # Поворот: небольшой случайный угол ±1.5°, с обрезкой запаса, чтобы не было
  # чёрных уголков (проверено на тестовом видео: край без чёрных пикселей).
  if is_active rotate; then
    rnd 300; local rot=$(awk -v r=$REPLY 'BEGIN{printf "%.2f", (r/100.0)-1.50}')
    vf+="rotate=${rot}*PI/180:fillcolor=black:ow=rotw(${rot}*PI/180):oh=roth(${rot}*PI/180),crop=trunc(iw*0.88/2)*2:trunc(ih*0.88/2)*2"
  fi

  if is_active scale; then
    vf+="scale=1080:1920"
  fi

  if is_active color; then
    rnd 999999; local bs=$(awk -v s=$REPLY 'BEGIN{srand(s); printf "%.4f %.4f", -0.03 + rand()*0.06, 0.9 + rand()*0.2}')
    local bright=${bs% *} sat=${bs#* }
    vf+="eq=brightness=${bright}:saturation=${sat}"
  fi

  if is_active noise; then
    rnd 2; local noise_amt=$((3 + REPLY))
    vf+="noise=alls=${noise_amt}:allf=t"
  fi

  if is_active speed; then
    rnd 999999; speed=$(awk -v s=$REPLY 'BEGIN{srand(s); printf "%.3f", 0.96 + rand()*0.08}')
    vf+="setpts=PTS/${speed}"
  fi

  if is_active flip; then
    vf+="hflip"
  fi

  vf+="format=yuv420p"

  rnd $SPAN; local ep=$(( START_EPOCH + REPLY ))
  local meta=$(fmt_date $ep -u '%Y-%m-%dT%H:%M:%SZ')
  local tt=$(fmt_date $ep '' '%Y%m%d%H%M.%S')

  local -a cmd=("$FFMPEG" -nostdin -y -hide_banner -loglevel error -i "$src"
    -vf "${(j:,:)vf}"
    -c:v libx264 -crf 22 -preset ultrafast
    -metadata "creation_time=$meta")
  if [[ -n $has_audio ]]; then
    if is_active speed; then
      cmd+=(-filter:a "atempo=$speed" -c:a aac -b:a 192k)
    else
      cmd+=(-c:a aac -b:a 192k)
    fi
  else
    cmd+=(-an)
  fi
  cmd+=(-movflags +faststart "$out")

  if ! LAST_ERR=$("${cmd[@]}" 2>&1 >/dev/null); then rm -f "$out"; return 1; fi
  touch -t "$tt" "$out"
}

# ---------- main ----------
get_tools

ONLY_FUNCS=(); SKIP_FUNCS=(); FILES=(); OUT=""; INTERACTIVE=0; KEEP_NAME=0
while (( $# )); do
  case $1 in
    --only=*) ONLY_FUNCS=("${(s:,:)${1#--only=}}") ;;
    --skip=*) SKIP_FUNCS=("${(s:,:)${1#--skip=}}") ;;
    --keep-name) KEEP_NAME=1 ;;
    -o) OUT=$2; shift ;;
    *) FILES+=("$1") ;;
  esac
  shift
done

(( ${#ONLY_FUNCS} && ${#SKIP_FUNCS} )) && die "нельзя одновременно --only и --skip"
for f in $ONLY_FUNCS $SKIP_FUNCS; do
  is_active_all() { (( ${ALL_FUNCS[(Ie)$1]} )) }
  is_active_all "$f" || die "неизвестная функция: $f (доступно: ${(j:, :)ALL_FUNCS})"
done

if (( ${#FILES} == 0 )); then
  [[ $(uname) == Darwin ]] || die "использование: -o ПАПКА [--only=...|--skip=...] файлы..."
  INTERACTIVE=1

  if (( ${#ONLY_FUNCS} == 0 && ${#SKIP_FUNCS} == 0 )); then
    funclist=$(osascript <<'EOF'
set allOpts to {"Кроп", "Масштаб (1080×1920)", "Цвет (яркость/насыщенность)", "Шум", "Поворот", "Скорость", "Отражение (зеркально)"}
set chosen to (choose from list allOpts with title "Уникализатор" with prompt "Какие функции применить ко всем файлам?" default items allOpts with multiple selections allowed)
if chosen is false then error "cancelled"
set out to ""
repeat with c in chosen
  set out to out & c & linefeed
end repeat
return out
EOF
) || die "выбор функций отменён"
    [[ $funclist == *"Кроп"* ]] && ONLY_FUNCS+=crop
    [[ $funclist == *"Масштаб"* ]] && ONLY_FUNCS+=scale
    [[ $funclist == *"Цвет"* ]] && ONLY_FUNCS+=color
    [[ $funclist == *"Шум"* ]] && ONLY_FUNCS+=noise
    [[ $funclist == *"Поворот"* ]] && ONLY_FUNCS+=rotate
    [[ $funclist == *"Скорость"* ]] && ONLY_FUNCS+=speed
    [[ $funclist == *"Отражение"* ]] && ONLY_FUNCS+=flip
    (( ${#ONLY_FUNCS} )) || die "не выбрано ни одной функции"
  fi

  list=$(osascript <<'EOF'
set fl to choose file with prompt "Select video files" of type {"public.mpeg-4", "com.apple.quicktime-movie"} with multiple selections allowed
set out to ""
repeat with f in fl
  set out to out & POSIX path of f & linefeed
end repeat
return out
EOF
) || die "выбор файлов отменён"
  FILES=("${(@f)list}")
  FILES=(${FILES:#})
fi
(( ${#FILES} )) || die "файлы не выбраны"

if (( ${#ONLY_FUNCS} )); then
  ACTIVE=($ONLY_FUNCS)
elif (( ${#SKIP_FUNCS} )); then
  ACTIVE=()
  for f in $ALL_FUNCS; do (( ${SKIP_FUNCS[(Ie)$f]} )) || ACTIVE+=$f; done
else
  ACTIVE=($ALL_FUNCS)
fi
(( ${#ACTIVE} )) || die "не выбрано ни одной функции"
print "Функции: ${(j:, :)ACTIVE}"

if [[ -z $OUT ]]; then
  OUT=$(osascript -e 'POSIX path of (choose folder with prompt "Output folder")') || die "папка не выбрана"
fi
OUT=${OUT%/}
mkdir -p "$OUT" || die "не удалось создать папку $OUT"

total=${#FILES}; ok=0; i=0
for src in "${FILES[@]}"; do
  (( i++ ))
  if (( KEEP_NAME )); then out="$OUT/${src:t:r}.mp4"
  else gen_name "$OUT"; out="$OUT/$REPLY"; fi
  print -n "[$i/$total] ${src:t} ... "
  if process "$src" "$out"; then
    (( ok++ )); print "OK -> ${out:t}"
  else
    print "ОШИБКА (подробности в errors.log)"
    print -rl -- "$src" "$LAST_ERR" "" >> "$OUT/errors.log"
  fi
done

print "\nГотово: $ok из $total"
if (( INTERACTIVE )); then
  open "$OUT"
  osascript -e "display notification \"Done: $ok of $total\" with title \"Uniquifier\"" 2>/dev/null
fi
