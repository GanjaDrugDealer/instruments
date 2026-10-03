#!/usr/bin/env python3
"""Регрессионные тесты Windows-уникализатора. Запуск: python -X utf8 scripts\\2026-10-04_uniquifier-tests.py
Одна строка на тест + итог. Код выхода 0 — всё прошло. Аналог 2026-09-25_uniquifier-tests.sh (+ проверки
подписи кодировщика, обоих кодировщиков, видео с матрицей поворота, --jobs).
Временные файлы — в %TEMP%, удаляются в конце."""
from __future__ import annotations

import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "2026-10-04_uniquifier-win.py"

sys.path.insert(0, str(HERE))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("uniq", SCRIPT)
uniq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uniq)
uniq.get_tools()
FF, FP = uniq.FFMPEG, uniq.FFPROBE

T = Path(tempfile.mkdtemp(prefix="a3-uniq-tests-"))
passed = failed = 0
last = {"out": "", "rc": 0}


def ok(name):
    global passed
    print(f"PASS  {name}")
    passed += 1


def bad(name, why):
    global failed
    print(f"FAIL  {name} — {why}")
    failed += 1


def run_u(*args):
    r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), *map(str, args)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    last["out"] = (r.stdout + r.stderr).strip()
    last["rc"] = r.returncode
    return r


def tail():
    return last["out"].splitlines()[-1] if last["out"] else ""


def mp4s(d):
    return sorted(Path(d).glob("*.mp4"))


def probe(*a):
    return subprocess.run([FP, "-v", "error", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout.strip()


def dims(f):
    return probe("-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(f)).split("\n")[0]


def audio(f):
    return probe("-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(f))


def dur(f):
    return probe("-show_entries", "format=duration", "-of", "csv=p=0", str(f))


def ctime(f):
    return probe("-show_entries", "format_tags=creation_time", "-of", "csv=p=0", str(f))


def luma(f, x, y):
    r = subprocess.run([FF, "-v", "error", "-i", str(f), "-vf", f"crop=8:8:{x}:{y},format=gray", "-frames:v", "1",
                        "-f", "rawvideo", "-"], capture_output=True)
    return sum(r.stdout) // max(1, len(r.stdout))


def gen(*a):
    subprocess.run([FF, "-v", "error", "-y", *map(str, a)], check=True)


# ---------- фикстуры ----------
gen("-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
    "-c:v", "libx264", "-c:a", "aac", "-shortest", T / "a.mp4")
gen("-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=2", "-c:v", "libx264", T / "noaudio.mp4")
gen("-i", T / "a.mp4", "-c", "copy", T / "clip.mov")
gen("-f", "lavfi", "-i", "color=white:size=640x360:duration=1:rate=5", "-c:v", "libx264", T / "white.mp4")
gen("-f", "lavfi", "-i", "color=black:size=640x360:duration=1:rate=5", "-vf", "drawbox=x=0:y=0:w=60:h=360:color=white:t=fill",
    "-c:v", "libx264", T / "marker.mp4")
(T / "Папка с пробелами").mkdir()
shutil.copy(T / "a.mp4", T / "Папка с пробелами" / "ролик 1.mp4")
(T / "broken.mp4").write_text("not a video")
# вертикальный ролик с телефона: в файле 1920x1080 + матрица поворота 90° (правка v7.6 — crop считает ffmpeg)
gen("-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=25:duration=2", "-f", "lavfi", "-i", "sine=frequency=330:duration=2",
    "-c:v", "libx264", "-c:a", "aac", "-shortest", T / "land.mp4")
gen("-display_rotation", "90", "-i", T / "land.mp4", "-c", "copy", T / "phone.mp4")

# ---------- тесты ----------
try:
    py_compile.compile(str(SCRIPT), cfile=str(T / "x.pyc"), doraise=True)
    ok("синтаксис")
except py_compile.PyCompileError as e:
    bad("синтаксис", e)

run_u("-o", T / "o1", T / "a.mp4")
r = mp4s(T / "o1")
if len(r) == 1 and dims(r[0]) == "1080x1920" and audio(r[0]):
    ok("все функции: 1080x1920, звук есть")
else:
    bad("все функции", tail())

run_u("-o", T / "o2", T / "noaudio.mp4")
r = mp4s(T / "o2")
ok("видео без звука") if len(r) == 1 and not audio(r[0]) else bad("видео без звука", tail())

run_u("-o", T / "o3", T / "clip.mov")
r = mp4s(T / "o3")
ok(".mov на входе") if len(r) == 1 and dims(r[0]) == "1080x1920" else bad(".mov на входе", tail())

run_u("-o", T / "выход с пробелом", T / "Папка с пробелами" / "ролик 1.mp4")
ok("кириллица и пробелы в путях") if len(mp4s(T / "выход с пробелом")) == 1 else bad("кириллица и пробелы", tail())

run_u("--only=color,rotate", "-o", T / "o5", T / "a.mp4")
r = mp4s(T / "o5")
d = dims(r[0]) if r else ""
if len(r) == 1 and d != "1080x1920" and all(int(x) % 2 == 0 for x in d.split("x")):
    ok(f"--only=color,rotate ({d}, чётные стороны)")
else:
    bad("--only=color,rotate", f"dims={d}")

run_u("--skip=scale", "-o", T / "o6", T / "a.mp4")
r = mp4s(T / "o6")
d = dims(r[0]) if r else ""
ok(f"--skip=scale ({d})") if len(r) == 1 and d != "1080x1920" else bad("--skip=scale", f"dims={d}")

run_u("--only=flip", "-o", T / "o7", T / "marker.mp4")
r = mp4s(T / "o7")
if len(r) == 1:
    l, rr = luma(r[0], 5, 170), luma(r[0], 620, 170)
    ok("flip: блок слева ушёл вправо") if l < 50 and rr > 200 else bad("flip", f"лево={l} право={rr}")
else:
    bad("flip", tail())

rot_bad = ""
for i in range(1, 6):
    run_u("--only=rotate", "-o", T / f"o8_{i}", T / "white.mp4")
    r = mp4s(T / f"o8_{i}")
    if len(r) != 1:
        rot_bad = f"прогон {i} упал"
        break
    w, h = map(int, dims(r[0]).split("x"))
    for x, y in ((0, 0), (w - 8, 0), (0, h - 8), (w - 8, h - 8)):
        v = luma(r[0], x, y)
        if v <= 200:
            rot_bad = f"прогон {i}, угол ({x} {y}) яркость {v}"
ok("rotate: нет чёрных углов (5 случайных углов)") if not rot_bad else bad("rotate", rot_bad)

run_u("--only=speed", "-o", T / "o9", T / "a.mp4", T / "a.mp4", T / "broken.mp4", T / "a.mp4", T / "a.mp4")
batch = mp4s(T / "o9")
el = T / "o9" / "errors.log"
if len(batch) == 4 and el.exists() and "broken.mp4" in el.read_text(encoding="utf-8"):
    ok("батч: 4 из 5, битый файл в errors.log")
else:
    bad("батч", f"файлов {len(batch)}")

distinct = len({dur(f) for f in batch})
ok(f"батч: разная рандомизация ({distinct} разных длительностей из 4)") if distinct >= 2 else bad(
    "батч: рандомизация", "все длительности одинаковые")

date_bad = ""
for f in batch:
    ct = ctime(f)
    ce = int(datetime.strptime(ct.split(".")[0].rstrip("Z"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    if not ("2026-02-01" < ct < "2026-09-02"):
        date_bad = f"creation_time вне диапазона: {ct}"
    if ce != int(f.stat().st_mtime):
        date_bad = f"mtime != creation_time у {f.name}"
ok("даты: в диапазоне, mtime = creation_time") if not date_bad else bad("даты", date_bad)

run_u("--only=teleport", "-o", T / "o10", T / "a.mp4")
ok("ошибка: неизвестная функция") if last["rc"] == 1 and "неизвестная функция" in last["out"] else bad(
    "неизвестная функция", "не упал")

run_u("--only=color", "--skip=noise", "-o", T / "o11", T / "a.mp4")
ok("ошибка: --only вместе с --skip") if last["rc"] == 1 and "одновременно" in last["out"] else bad(
    "--only + --skip", "не упал")

run_u("--keep-name", "--only=color", "-o", T / "o12", T / "clip.mov", T / "Папка с пробелами" / "ролик 1.mp4")
names = sorted(p.name for p in (T / "o12").glob("*"))
ok("--keep-name: исходные имена сохранены") if names == ["clip.mp4", "ролик 1.mp4"] else bad("--keep-name", str(names))

# --- новое для Windows ---
run_u("-o", T / "o13", T / "phone.mp4")
r = mp4s(T / "o13")
ok(f"видео с матрицей поворота 90° ({dims(r[0]) if r else ''})") if len(r) == 1 and dims(r[0]) == "1080x1920" else bad(
    "матрица поворота", tail())


def signature_problems(f):
    tags = probe("-show_entries", "format_tags:stream_tags", "-of", "compact", str(f))
    probs = []
    if re.search(r"encoder", tags, re.I):
        probs.append("тег encoder: " + tags.replace("\n", " | "))
    b = Path(f).read_bytes()
    m = re.search(rb"(Lav[fc]|x264 - core|x264|nvenc|NVIDIA)", b)
    if m:
        probs.append("строка в файле: " + m.group(1).decode())
    return probs


encs = ["x264"] + (["nvenc"] if uniq.nvenc_available() else [])
for enc in encs:
    run_u(f"--encoder={enc}", "-o", T / f"enc_{enc}", T / "a.mp4", T / "noaudio.mp4")
    r = mp4s(T / f"enc_{enc}")
    if len(r) != 2:
        bad(f"кодировщик {enc}", tail())
        continue
    codec = probe("-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt", "-of", "csv=p=0", str(r[0]))
    probs = [p for f in r for p in signature_problems(f)]
    decode = subprocess.run([FF, "-v", "error", "-i", str(r[0]), "-f", "null", "-"], capture_output=True).returncode
    if probs or decode != 0 or not codec.startswith("h264,yuv420p"):
        bad(f"кодировщик {enc}: нет подписи, декодируется", f"{codec}; decode={decode}; {probs}")
    else:
        ok(f"кодировщик {enc}: h264/yuv420p, декодируется, без подписи (нет encoder/Lavf/Lavc/x264/nvenc)")
if "nvenc" not in encs:
    print("SKIP  nvenc: h264_nvenc недоступен на этой машине")

run_u("--jobs=3", "--only=color", "-o", T / "o14", T / "a.mp4", T / "a.mp4", T / "noaudio.mp4")
ok("--jobs=3: 3 из 3") if len(mp4s(T / "o14")) == 3 and "Готово: 3 из 3" in last["out"] else bad("--jobs", tail())

print(f"\nИтог: {passed} прошло, {failed} упало")
shutil.rmtree(T, ignore_errors=True)
sys.exit(0 if failed == 0 else 1)
