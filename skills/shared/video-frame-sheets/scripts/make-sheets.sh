#!/bin/zsh
# Собирает листы-сетки для оценки эмоции: по N кадров (по умолчанию 5) в моменты
# всплесков движения (motion-peaks.py рядом) — чтобы ловить короткие жесты,
# один ролик — одна строка, по 4 ролика на лист.
# Имена файлов на лист не пишутся (слепая оценка) — порядок строк в out/sheets/index.txt.
#
# Запуск из корня проекта: zsh <скилл>/scripts/make-sheets.sh "<папка с .MOV>" [роликов_на_лист] [кадров]

HERE=${0:A:h}      # папка скрипта (внутри скилла)
ROOT=$PWD          # корень проекта: сюда пишутся data/ и out/
if [[ -n $FFMPEG ]]; then FF=$FFMPEG
elif [[ -x $ROOT/bin/ffmpeg ]]; then FF=$ROOT/bin/ffmpeg
else FF=$(command -v ffmpeg) || { echo "ffmpeg не найден: положи в bin/ или задай FFMPEG"; exit 1; }
fi
export FFMPEG=$FF
SRC=${1:?укажи папку с роликами}
PER=${2:-4}
NF=${3:-5}
TAIL=5    # последние 5 с пропускаем: там всегда одинаковый жест «пальцами в комменты»
FR="$ROOT/data/frames"
OUT="$ROOT/out/sheets"
mkdir -p "$FR" "$OUT"
: > "$OUT/index.txt"

files=("$SRC"/*.(MOV|mov|mp4|MP4)(N))
(( ${#files} )) || { echo "нет роликов в $SRC"; exit 1; }

sheet=0; rows=()
for f in $files; do
  id=$(basename "$f" | cut -d_ -f1-2 | sed 's/\.[^.]*$//')   # IMG_9477_WOW.MOV -> IMG_9477
  times=(${=$(python3 "$HERE/motion-peaks.py" "$f" $NF $TAIL)})
  ins=(); i=0
  for t in $times; do
    i=$((i+1))
    "$FF" -v error -y -ss $t -i "$f" -frames:v 1 -vf scale=-2:260 "$FR/${id}_$i.png"
    ins+=(-i "$FR/${id}_$i.png")
  done
  "$FF" -v error -y $ins -filter_complex "hstack=$NF" "$FR/row_$id.png"
  rows+=("$FR/row_$id.png")
  echo "лист $((sheet+1)), строка ${#rows}: $id  [${times}]" >> "$OUT/index.txt"
  if (( ${#rows} == PER )) || [[ $f == ${files[-1]} ]]; then
    sheet=$((sheet+1)); args=(); for r in $rows; do args+=(-i "$r"); done
    if (( ${#rows} > 1 )); then
      "$FF" -v error -y $args -filter_complex "vstack=${#rows}" -q:v 4 "$OUT/sheet_$sheet.jpg"
    else
      "$FF" -v error -y $args -q:v 4 "$OUT/sheet_$sheet.jpg"
    fi
    rows=()
  fi
done
echo "готово: $sheet лист(ов) в $OUT"
