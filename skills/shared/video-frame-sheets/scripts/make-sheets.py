#!/usr/bin/env python3
"""Листы-сетки кадров для оценки эмоции: N кадров (по умолчанию 5) в моменты всплесков
движения (motion-peaks.py рядом); один ролик — одна строка, по 4 ролика на лист.
Имена файлов на лист не пишутся (слепая оценка) — порядок строк в out/sheets/index.txt.

Запуск из корня проекта (Windows: py, Mac: python3):
  py <скилл>/scripts/make-sheets.py "<папка с роликами>" [роликов_на_лист=4] [кадров=5]
                                    [--ffmpeg путь] [--out папка_вывода]

Кадры пишутся в <корень>/data/frames, листы и index.txt — в <корень>/out/sheets.
--out <папка> кладёт и кадры, и листы в эту папку (frames/ и sheets/ внутри) — для проверок вне проекта.
ffmpeg: --ffmpeg -> $FFMPEG -> bin/ffmpeg(.exe) в корне проекта -> PATH.
Только стандартная библиотека; замена make-sheets.sh (zsh) для Windows и Mac.
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

TAIL = 5   # последние 5 с пропускаем: там всегда одинаковый жест «пальцами в комменты»
EXTS = {".mov", ".mp4"}


def say(msg):
    print(msg, flush=True)


def find_ffmpeg(root, arg):
    if arg:
        return arg
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    for name in ("ffmpeg.exe", "ffmpeg"):
        p = root / "bin" / name
        if p.is_file():
            return str(p)
    return shutil.which("ffmpeg")


def run_ff(ff, *args):
    r = subprocess.run([ff, "-v", "error", "-y", *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg завершился с ошибкой: {r.stderr.strip()[:500]}")


def png_width(path):
    """Ширина PNG из заголовка IHDR (без сторонних библиотек)."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    return struct.unpack(">I", head[16:20])[0]


def video_id(path):
    """IMG_9477_WOW.MOV -> IMG_9477 (первые два фрагмента по «_», без расширения)."""
    name = "_".join(path.name.split("_")[:2])
    return re.sub(r"\.[^.]*$", "", name)


def make_sheet(ff, rows, dest):
    """Склеить строки вертикально; разной ширины — добить чёрным до самой широкой."""
    if len(rows) == 1:
        run_ff(ff, "-i", rows[0], "-q:v", 4, dest)
        return
    widths = [png_width(r) for r in rows]
    inputs = []
    for r in rows:
        inputs += ["-i", r]
    if len(set(widths)) == 1:
        graph = f"vstack={len(rows)}"
    else:
        w = max(widths)
        pads = ";".join(f"[{i}:v]pad={w}:ih:0:0[p{i}]" for i in range(len(rows)))
        graph = pads + ";" + "".join(f"[p{i}]" for i in range(len(rows))) + f"vstack={len(rows)}"
    run_ff(ff, *inputs, "-filter_complex", graph, "-q:v", 4, dest)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Листы кадров из роликов (по пикам движения)")
    ap.add_argument("src", help="папка с роликами (.mov/.mp4)")
    ap.add_argument("per", nargs="?", type=int, default=4, help="роликов на лист (4)")
    ap.add_argument("frames", nargs="?", type=int, default=5, help="кадров на ролик (5)")
    ap.add_argument("--ffmpeg", help="путь к ffmpeg (иначе $FFMPEG, bin/, PATH)")
    ap.add_argument("--out", help="куда писать frames/ и sheets/ (по умолчанию data/frames и out/sheets в корне проекта)")
    a = ap.parse_args()

    root = Path.cwd()
    ff = find_ffmpeg(root, a.ffmpeg)
    if not ff:
        say("ffmpeg не найден: положи в bin/, добавь в PATH, задай FFMPEG или --ffmpeg")
        return 1
    os.environ["FFMPEG"] = ff          # motion-peaks.py берёт ffmpeg отсюда
    here = Path(__file__).resolve().parent

    src = Path(a.src)
    if a.out:
        base = Path(a.out)
        fr, outd = base / "frames", base / "sheets"
    else:
        fr, outd = root / "data" / "frames", root / "out" / "sheets"
    fr.mkdir(parents=True, exist_ok=True)
    outd.mkdir(parents=True, exist_ok=True)

    files = sorted((p for p in src.iterdir() if p.is_file() and p.suffix.lower() in EXTS),
                   key=lambda p: p.name) if src.is_dir() else []
    if not files:
        say(f"нет роликов в {src}")
        return 1

    index = []
    sheet, rows, used = 0, [], set()
    for f in files:
        vid = video_id(f)
        while vid in used:             # одинаковый id у двух роликов — не затирать кадры друг друга
            vid += "x"
        used.add(vid)
        pk = subprocess.run([sys.executable, "-X", "utf8", str(here / "motion-peaks.py"),
                             str(f), str(a.frames), str(TAIL)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            env={**os.environ, "PYTHONUTF8": "1"})
        times = pk.stdout.split()
        if pk.returncode != 0 or not times:
            say(f"пропуск {f.name}: {pk.stderr.strip()[-300:] or 'нет пиков движения'}")
            continue
        ins = []
        for i, t in enumerate(times, 1):
            png = fr / f"{vid}_{i}.png"
            run_ff(ff, "-ss", t, "-i", f, "-frames:v", 1, "-vf", "scale=-2:260", png)
            ins += ["-i", png]
        row = fr / f"row_{vid}.png"
        run_ff(ff, *ins, "-filter_complex", f"hstack={len(times)}", row)
        rows.append(row)
        index.append(f"лист {sheet + 1}, строка {len(rows)}: {vid}  [{' '.join(times)}]")
        if len(rows) == a.per or f == files[-1]:
            sheet += 1
            make_sheet(ff, rows, outd / f"sheet_{sheet}.jpg")
            rows = []
    if rows:                           # последний ролик пропущен — не потерять набранные строки
        sheet += 1
        make_sheet(ff, rows, outd / f"sheet_{sheet}.jpg")
    (outd / "index.txt").write_text("\n".join(index) + ("\n" if index else ""), encoding="utf-8")
    say(f"готово: {sheet} лист(ов) в {outd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
