#!/usr/bin/env python3
"""Моменты всплесков движения в ролике — для выбора кадров под оценку эмоции.

Жест (рука к лицу, «ОК», палец вверх) даёт резкий скачок разницы между
соседними кадрами. Берём N самых сильных пиков, разнесённых во времени,
и сдвигаем каждый чуть вперёд — к моменту, когда жест уже зафиксирован.

Запуск (из корня проекта; Windows: py): python3 <скилл>/scripts/motion-peaks.py <ролик> [N] [срез_конца_сек]
Печатает времена (сек) через пробел, по возрастанию.
"""
import os, re, subprocess, sys

import shutil

# ffmpeg: $FFMPEG → ./bin/ffmpeg(.exe) (корень проекта) → PATH
FF = (os.environ.get("FFMPEG")
      or next((os.path.abspath(p) for p in ("bin/ffmpeg.exe", "bin/ffmpeg") if os.path.isfile(p)), None)
      or shutil.which("ffmpeg") or "ffmpeg")

FPS = 4          # частота анализа движения
GAP = 3.0        # минимальный разрыв между выбранными пиками, сек
SHIFT = 0.5      # сдвиг вперёд от начала движения к удержанию жеста, сек


def scores(path):
    out = subprocess.run(
        [FF, "-v", "error", "-i", path, "-an", "-vf",
         f"fps={FPS},scale=160:-2,select='gte(scene,0)',metadata=print:file=-",
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    t, res = None, []
    for line in out.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"scene_score=([\d.]+)", line)
        if m and t is not None:
            res.append((t, float(m.group(1))))
    return res


def main():
    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    tail = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
    sc = scores(path)
    if not sc:
        sys.exit("нет данных о движении")
    end = sc[-1][0] - tail
    cand = sorted((s for s in sc if 0.5 < s[0] < end), key=lambda x: -x[1])
    picked = []
    for t, _ in cand:
        if all(abs(t - p) >= GAP for p in picked):
            picked.append(t)
        if len(picked) == n:
            break
    # мало движения — добиваем равномерно
    k = 1
    while len(picked) < n:
        t = end * k / (n + 1)
        if all(abs(t - p) >= GAP / 2 for p in picked):
            picked.append(t)
        k += 1
        if k > 50:
            break
    print(" ".join(f"{min(t + SHIFT, end):.2f}" for t in sorted(picked)))


if __name__ == "__main__":
    main()
