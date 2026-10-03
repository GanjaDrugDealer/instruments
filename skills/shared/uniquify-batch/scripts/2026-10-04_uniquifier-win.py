#!/usr/bin/env python3
"""UNIQUIFIER для Windows (работает и на macOS/Linux, если есть ffmpeg). Тот же CLI и те же функции,
что у 2026-09-22_uniquifier-mac.command; за основу взят content-unifier/src/unifier-win.py.

Запуск (диалоги):  python -X utf8 файл.py
  — сначала чеклист «какие функции применить», потом выбор файлов и папки (tkinter).

Без диалогов:  python -X utf8 файл.py [--only=ФУНКЦИИ | --skip=ФУНКЦИИ] [--keep-name] -o ПАПКА файл1.mp4 файл2.mov ...
  Функции (через запятую): crop, scale, color, noise, rotate, speed, flip
  --only=color,rotate   — применить только цвет и поворот
  --skip=scale          — применить всё, кроме масштабирования
  без --only/--skip     — применяются все функции
  --keep-name           — не менять имя: исходное имя + .mp4
  --encoder=auto|nvenc|x264  — кодировщик (по умолчанию auto: h264_nvenc на видеокарте NVIDIA, иначе libx264)
  --jobs=N              — сколько роликов кодировать одновременно (по умолчанию 1: порядок вывода как на маке)

Дата создания файла и случайное имя (если нет --keep-name) проставляются всегда — это часть уникализации
идентичности файла, а не функция обработки видео.

Подписи кодировщика в выводе нет: без тегов encoder (формат и потоки), без строк Lavf/Lavc, без SEI x264
(-map_metadata -1, bitexact, пустые encoder, filter_units=remove_types=6).

Коды выхода: 1 — ошибка аргументов/окружения (как die() в .command), 0 — иначе (ошибки отдельных роликов —
в errors.log в папке выхода и в строках «ОШИБКА»).
ffmpeg/ffprobe: FFMPEG_DIR, затем PATH, затем download-script/bin (соседний проект), затем ~/.uniquifier/bin.
"""
from __future__ import annotations

import os
import random
import re
import shutil
import string
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

IS_WIN = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HERE = Path(__file__).resolve().parent

START_EPOCH = 1769904000                  # 2026-02-01 00:00:00 UTC
SPAN = 212 * 86400                        # разброс дат: 212 дней
SAFE_SPECIAL = "!@#$%^&()_+-=[]{};,~"     # без \ / : * ? " < > | — их запрещает Windows
SEPS = "_-.~+="
CHARS = string.ascii_lowercase + string.digits
ALL_FUNCS = ["crop", "scale", "color", "noise", "rotate", "speed", "flip"]
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}

ENCODERS = {
    # cq 28 у NVENC по размеру файла ≈ crf 22 у libx264 ultrafast (замер на ролике 576x1024 -> 1080x1920 с шумом:
    # x264 23 МБ, nvenc cq28 18 МБ, cq22 74 МБ — шум раздувает битрейт, поэтому cq выше, чем у x264)
    "nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "28", "-b:v", "0"],
    "x264": ["-c:v", "libx264", "-crf", "22", "-preset", "ultrafast"],
}

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
_print_lock = threading.Lock()


def die(msg: str):
    print(f"ОШИБКА: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, **kw)


# ---------- инструменты ----------

def find_tool(name: str) -> str | None:
    exe = name + (".exe" if IS_WIN else "")
    dirs = []
    if os.environ.get("FFMPEG_DIR"):
        dirs.append(Path(os.environ["FFMPEG_DIR"]))
    on_path = shutil.which(name)
    if on_path:
        return on_path
    dirs += [HERE.parent.parent / "download-script" / "bin", Path.home() / ".uniquifier" / "bin"]
    for d in dirs:
        if (d / exe).is_file():
            return str(d / exe)
    return None


def get_tools() -> None:
    global FFMPEG, FFPROBE
    if os.environ.get("FFMPEG_DIR"):
        d = Path(os.environ["FFMPEG_DIR"])
        exe = ".exe" if IS_WIN else ""
        if (d / f"ffmpeg{exe}").is_file() and (d / f"ffprobe{exe}").is_file():
            FFMPEG, FFPROBE = str(d / f"ffmpeg{exe}"), str(d / f"ffprobe{exe}")
    if FFMPEG == "ffmpeg":
        f, p = find_tool("ffmpeg"), find_tool("ffprobe")
        if not f or not p:
            die("не найдены ffmpeg/ffprobe (winget install --id Gyan.FFmpeg -e, либо FFMPEG_DIR)")
        FFMPEG, FFPROBE = f, p
    if run([FFMPEG, "-hide_banner", "-version"]).returncode != 0:
        die(f"ffmpeg не запускается: {FFMPEG}")
    if run([FFPROBE, "-hide_banner", "-version"]).returncode != 0:
        die(f"ffprobe не запускается: {FFPROBE}")


def nvenc_available() -> bool:
    r = run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "color=c=black:s=256x256:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"])
    return r.returncode == 0


# ---------- имена и даты ----------

def rstr(n: int) -> str:
    return "".join(random.choice(CHARS) for _ in range(n))


def gen_name(outdir: Path, taken: set) -> str:
    while True:
        n = rstr(random.randint(0, 12) + 3)
        if random.randint(0, 3) > 0:
            n += random.choice(SEPS) + rstr(random.randint(0, 3) + 3)
        if random.randint(0, 9) >= 7:
            n += random.choice(SAFE_SPECIAL)
        name = n + ".mp4"
        if n.lower() in RESERVED or name.lower() in taken or (outdir / name).exists():
            continue
        taken.add(name.lower())
        return name


if IS_WIN:
    import ctypes
    from ctypes import wintypes
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _k32.SetFileTime.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 3
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _INVALID = wintypes.HANDLE(-1).value


def set_file_times(path: str, epoch: int) -> None:
    """Дата изменения везде; на Windows ещё и дата создания (аналог touch -t)."""
    os.utime(path, (epoch, epoch))
    if not IS_WIN:
        return
    v = int((epoch + 11644473600) * 10_000_000)
    ft = wintypes.FILETIME(v & 0xFFFFFFFF, v >> 32)
    h = _k32.CreateFileW(path, 0x100, 0, None, 3, 0x80, None)   # FILE_WRITE_ATTRIBUTES, OPEN_EXISTING
    if h in (None, _INVALID):
        return
    try:
        _k32.SetFileTime(h, ctypes.byref(ft), ctypes.byref(ft), ctypes.byref(ft))
    finally:
        _k32.CloseHandle(h)


# ---------- обработка ----------

def build_cmd(src: Path, out: Path, active: list, has_audio: bool, encoder: str, epoch: int):
    """Собирает команду ffmpeg. Размеры и сдвиг crop считает сам ffmpeg от настоящего кадра (iw/ih уже
    после разворота по матрице поворота телефона): числа из ffprobe для вертикального ролика с
    матрицей 90° дают crop больше кадра (см. content-unifier, правка v7.6)."""
    vf = []
    speed = 1.000

    def is_active(f):
        return f in active

    # Кроп: 1/1.1 по ширине со случайным сдвигом X, запас 2% по высоте для сдвига Y
    if is_active("crop"):
        rx, ry = random.random(), random.random()
        vf.append("crop=floor(iw*10/11/2)*2:floor((ih-floor(ih*0.02))/2)*2:"
                  f"floor((iw-ow)*{rx:.4f}):floor((ih-oh)*{ry:.4f})")
    # Поворот: случайный угол ±1.5°, с обрезкой запаса, чтобы не было чёрных уголков
    if is_active("rotate"):
        rot = f"{random.randint(0, 300) / 100.0 - 1.50:.2f}"
        vf.append(f"rotate={rot}*PI/180:fillcolor=black:ow=rotw({rot}*PI/180):oh=roth({rot}*PI/180),"
                  "crop=trunc(iw*0.88/2)*2:trunc(ih*0.88/2)*2")
    if is_active("scale"):
        vf.append("scale=1080:1920")
    if is_active("color"):
        vf.append(f"eq=brightness={random.uniform(-0.03, 0.03):.4f}:saturation={random.uniform(0.9, 1.1):.4f}")
    if is_active("noise"):
        vf.append(f"noise=alls={random.randint(3, 5)}:allf=t")
    if is_active("speed"):
        speed = round(random.uniform(0.96, 1.04), 3)
        vf.append(f"setpts=PTS/{speed:.3f}")
    if is_active("flip"):
        vf.append("hflip")
    vf.append("format=yuv420p")

    meta = datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cmd = [FFMPEG, "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-vf", ",".join(vf), *ENCODERS[encoder],
           # без подписи кодировщика: ни метаданных, ни encoder-тегов, ни SEI x264, ни Lavf/Lavc
           "-map_metadata", "-1", "-map_chapters", "-1",
           "-metadata:s:v:0", "encoder=", "-metadata:s:a:0", "encoder=",
           "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
           "-bsf:v", "filter_units=remove_types=6",
           "-metadata", f"creation_time={meta}"]
    if has_audio:
        if is_active("speed"):
            cmd += ["-filter:a", f"atempo={speed:.3f}"]
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(out)]
    return cmd


def process(src: Path, out: Path, active: list, encoder: str):
    """-> (ok, ошибка). Один ролик."""
    v = run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=s=x:p=0", str(src)])
    if not re.match(r"^\d+x\d+", v.stdout.strip()):
        return False, "не удалось прочитать размеры видео"
    a = run([FFPROBE, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index",
             "-of", "csv=p=0", str(src)])
    has_audio = bool(a.stdout.strip())
    epoch = START_EPOCH + random.randint(0, SPAN)
    r = run(build_cmd(src, out, active, has_audio, encoder, epoch))
    if r.returncode != 0 and encoder == "nvenc":
        # например, упёрлись в лимит сессий NVENC — повторяем на CPU
        r = run(build_cmd(src, out, active, has_audio, "x264", epoch))
    if r.returncode != 0:
        out.unlink(missing_ok=True)
        return False, r.stderr.strip()[-600:]
    set_file_times(str(out), epoch)
    return True, ""


# ---------- диалоги (когда файлов не передали) ----------

def dialogs(only: list, skip: list):
    """-> (only, files, out). Окна tkinter; на маке без tkinter — ошибка с подсказкой про флаги."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        die("использование: -o ПАПКА [--only=...|--skip=...] файлы... (tkinter недоступен)")
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    if not only and not skip:
        labels = {"crop": "Кроп", "scale": "Масштаб (1080×1920)", "color": "Цвет (яркость/насыщенность)",
                  "noise": "Шум", "rotate": "Поворот", "speed": "Скорость", "flip": "Отражение (зеркально)"}
        win = tk.Toplevel(root)
        win.title("Уникализатор")
        tk.Label(win, text="Какие функции применить ко всем файлам?").pack(anchor="w", padx=12, pady=(12, 4))
        vars_ = {}
        for k in ALL_FUNCS:
            vars_[k] = tk.BooleanVar(value=True)
            tk.Checkbutton(win, text=labels[k], variable=vars_[k]).pack(anchor="w", padx=20)
        res = {"ok": False}

        def ok():
            res["ok"] = True
            win.destroy()
        bar = tk.Frame(win)
        bar.pack(fill="x", padx=12, pady=10)
        tk.Button(bar, text="OK", width=10, command=ok).pack(side="right")
        tk.Button(bar, text="Отмена", width=10, command=win.destroy).pack(side="right", padx=8)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        root.wait_window(win)
        if not res["ok"]:
            die("выбор функций отменён")
        only = [k for k in ALL_FUNCS if vars_[k].get()]
        if not only:
            die("не выбрано ни одной функции")
    files = filedialog.askopenfilenames(title="Select video files", parent=root,
                                        filetypes=[("Video", "*.mp4 *.mov *.m4v"), ("All", "*.*")])
    if not files:
        die("выбор файлов отменён")
    out = filedialog.askdirectory(title="Output folder", parent=root)
    if not out:
        die("папка не выбрана")
    root.destroy()
    return only, list(files), out


# ---------- main ----------

def main(argv: list) -> int:
    only, skip, files, out_arg, keep_name = [], [], [], "", False
    encoder_opt, jobs = os.environ.get("UNIQ_ENCODER", "auto"), 1
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--only="):
            only = [x for x in a[7:].split(",") if x]
        elif a.startswith("--skip="):
            skip = [x for x in a[7:].split(",") if x]
        elif a == "--keep-name":
            keep_name = True
        elif a.startswith("--encoder="):
            encoder_opt = a[10:]
        elif a.startswith("--jobs="):
            try:
                jobs = max(1, int(a[7:]))
            except ValueError:
                die(f"--jobs: нужно число, а не {a[7:]}")
        elif a == "-o":
            i += 1
            out_arg = argv[i] if i < len(argv) else ""
        else:
            files.append(a)
        i += 1

    get_tools()
    if only and skip:
        die("нельзя одновременно --only и --skip")
    for f in only + skip:
        if f not in ALL_FUNCS:
            die(f"неизвестная функция: {f} (доступно: {', '.join(ALL_FUNCS)})")
    if encoder_opt not in ("auto", "nvenc", "x264"):
        die(f"--encoder: auto, nvenc или x264, а не {encoder_opt}")

    interactive = False
    if not files:
        interactive = True
        only, files, chosen_out = dialogs(only, skip)
        out_arg = out_arg or chosen_out
    if not files:
        die("файлы не выбраны")

    if only:
        active = [f for f in ALL_FUNCS if f in only]
    elif skip:
        active = [f for f in ALL_FUNCS if f not in skip]
    else:
        active = list(ALL_FUNCS)
    if not active:
        die("не выбрано ни одной функции")
    print(f"Функции: {', '.join(active)}")

    if not out_arg:
        die("не указана папка выхода (-o ПАПКА)")
    outdir = Path(out_arg.rstrip("/\\") if len(out_arg) > 3 else out_arg)
    try:
        outdir.mkdir(parents=True, exist_ok=True)
    except OSError:
        die(f"не удалось создать папку {outdir}")

    if encoder_opt == "auto":
        encoder = "nvenc" if nvenc_available() else "x264"
    else:
        encoder = encoder_opt
    print(f"Кодировщик: {'h264_nvenc (GPU NVIDIA)' if encoder == 'nvenc' else 'libx264 (CPU)'}")

    total = len(files)
    taken: set = set()
    plan = []
    for n, f in enumerate(files, 1):
        src = Path(f)
        out = outdir / (src.stem + ".mp4") if keep_name else outdir / gen_name(outdir, taken)
        plan.append((n, src, out))

    results = {"ok": 0}

    def work(item):
        n, src, out = item
        ok, err = process(src, out, active, encoder)
        with _print_lock:
            if ok:
                results["ok"] += 1
                print(f"[{n}/{total}] {src.name} ... OK -> {out.name}", flush=True)
            else:
                print(f"[{n}/{total}] {src.name} ... ОШИБКА (подробности в errors.log)", flush=True)
                with open(outdir / "errors.log", "a", encoding="utf-8") as lf:
                    lf.write(f"{src}\n{err}\n\n")

    if jobs == 1:
        for item in plan:
            work(item)
    else:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            list(ex.map(work, plan))

    print(f"\nГотово: {results['ok']} из {total}")
    if interactive and IS_WIN:
        try:
            os.startfile(str(outdir))  # type: ignore[attr-defined]
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main(sys.argv[1:]))
