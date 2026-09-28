#!/usr/bin/env python3
"""Пиковые моменты в видео: где «что-то происходит» и насколько сильно.

Два режима:
  reaction — пик = всплеск движения (жест, смех, рука к лицу).
             Выход: несколько непересекающихся отрезков 2–6 с на файл.
  source   — пик = громкость + движение/смена сцены.
             Выход: одна строка на файл — главный пик, второй пик, окно 15–30 с вокруг.

Запуск:
  python3 peak_moments.py reaction <файл или папка> [...] [--csv out.csv]
  python3 peak_moments.py source   <файл или папка> [...] [--csv out.csv] [--curve curve.csv]

Без --csv таблица печатается в stdout. Сводка и ошибки — в stderr.
Видео только читается. Только стандартная библиотека Python 3.9+.
ffmpeg/ffprobe: $FFMPEG/$FFPROBE → ./bin/ (папка запуска) → PATH.
Эталон и история решений: youtube-shorts-cs/src/peaks.py (ТЗ T1, T1.1).
"""
import argparse
import bisect
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}

# --- Анализ -------------------------------------------------------------------
MOTION_FPS = 4          # кадров/с для scene_score (шаг 0,25 с)
MOTION_WIDTH = 160      # ширина кадра для анализа, px
AUDIO_WINDOW = 0.1      # окно RMS, с
AUDIO_RATE = 44100
SMOOTH = 3              # скользящее среднее, отсчётов: один дёрганый кадр ≠ пик
SILENCE_DB = -50.0      # нигде не громче → звука нет

# --- reaction -----------------------------------------------------------------
R_HEAD = 0.5            # не брать первые, с
R_TAIL = 5.0            # не брать последние, с (служебная концовка, жест «в комменты»)
R_BEFORE = 1.5          # отрезок: до пика, с
R_AFTER = 2.5           # отрезок: после пика, с
R_MIN_LEN = 2.0
R_MAX_LEN = 6.0
R_GAP = 3.0             # мин. разрыв между пиками, с
R_SCORE_MIN = 0.35      # порог силы (score нормирован внутри файла, лучший = 1)
R_MAX_PER_FILE = 6

# --- source -------------------------------------------------------------------
S_HEAD = 0.3            # не брать первые, с (склейка/заставка)
S_TAIL = 1.0            # не брать последние, с (громкая концовка/склейка)
S_W_AUDIO = 0.6
S_W_MOTION = 0.4
S_GAP = 3.0             # peak2 не ближе к peak, с
CUT_MIN = 15.0          # ролик короче — окно = весь ролик
CUT_TARGET = 20.0       # длина окна
CUT_PEAK_POS = 0.65     # доля окна до пика (подводка длиннее развязки)
ORIENT_TOL = 0.10       # |w/h − 1| ≤ 10% → square

EPS = 0.011             # допуск сравнения после округления до 0,01
WORKERS = min(4, os.cpu_count() or 1)

REACTION_FIELDS = ["file", "fragment", "start", "end", "duration", "peak", "score", "rank"]
SOURCE_FIELDS = ["file", "duration", "width", "height", "orientation", "peak", "peak2",
                 "peak_score", "method", "cut_start", "cut_end"]


def tool(name):
    env = os.environ.get(name.upper())
    if env:
        return env
    local = Path("bin") / (name + (".exe" if os.name == "nt" else ""))
    if local.is_file():
        return str(local.resolve())
    found = shutil.which(name)
    if found:
        return found
    sys.exit(f"{name} не найден: положите его в bin/ или задайте ${name.upper()}.")


FFMPEG = tool("ffmpeg")
FFPROBE = tool("ffprobe")


def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        err = res.stderr.strip().splitlines()
        raise RuntimeError(err[-1] if err else f"код {res.returncode}")
    return res.stdout


# --- Сигналы ------------------------------------------------------------------
def probe(path):
    info = json.loads(run([FFPROBE, "-v", "error", "-show_entries",
                           "format=duration:stream=codec_type,width,height:stream_tags=rotate"
                           ":stream_side_data=rotation", "-of", "json", str(path)]))
    duration = float(info.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise RuntimeError("не удалось определить длительность")
    width = height = 0
    has_audio = False
    for st in info.get("streams", []):
        if st.get("codec_type") == "audio":
            has_audio = True
        if st.get("codec_type") == "video" and not width:
            width, height = int(st.get("width") or 0), int(st.get("height") or 0)
            rot = st.get("tags", {}).get("rotate")
            for sd in st.get("side_data_list", []) or []:
                if "rotation" in sd:
                    rot = sd["rotation"]
            if rot is not None and abs(int(float(rot))) % 180 == 90:   # телефонное видео
                width, height = height, width
    if not width:
        raise RuntimeError("нет видеопотока")
    return {"duration": duration, "width": width, "height": height, "has_audio": has_audio}


def parse_metadata(text, key):
    series, t = [], None
    for line in text.splitlines():
        m = re.search(r"pts_time:(-?[\d.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        if t is not None and line.startswith(key + "="):
            try:
                series.append((t, float(line.split("=", 1)[1])))
            except ValueError:
                series.append((t, float("-inf")))
    return series


def motion_series(path):
    out = run([FFMPEG, "-v", "error", "-i", str(path), "-an", "-vf",
               f"fps={MOTION_FPS},scale={MOTION_WIDTH}:-2,select='gte(scene,0)',"
               "metadata=print:file=-", "-f", "null", "-"])
    return parse_metadata(out, "lavfi.scene_score")


def audio_series(path):
    n = int(AUDIO_RATE * AUDIO_WINDOW)
    out = run([FFMPEG, "-v", "error", "-i", str(path), "-vn", "-af",
               f"aresample={AUDIO_RATE},asetnsamples=n={n}:p=0,astats=metadata=1:reset=1,"
               "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level:file=-",
               "-f", "null", "-"])
    db = parse_metadata(out, "lavfi.astats.Overall.RMS_level")
    max_db = max((v for _, v in db), default=float("-inf"))
    return [(t, 0.0 if v == float("-inf") else 10 ** (v / 20)) for t, v in db], max_db


# --- Ряды ---------------------------------------------------------------------
def smooth(values, k=SMOOTH):
    half = k // 2
    return [sum(values[max(0, i - half):i + half + 1]) / len(values[max(0, i - half):i + half + 1])
            for i in range(len(values))]


def local_maxima(times, values, lo, hi, strict=False):
    """Локальные максимумы в [lo, hi] по убыванию силы.

    Соседи — настоящие, даже за границей зоны (иначе край зоны на спаде
    движения ложно становится пиком). strict: строго выше обоих соседей,
    и оба соседа внутри [lo, hi] — пик на самой границе отбрасывается.
    """
    peaks = []
    for i, t in enumerate(times):
        if not lo <= t <= hi:
            continue
        has_l, has_r = i > 0, i + 1 < len(values)
        left = values[i - 1] if has_l else float("-inf")
        right = values[i + 1] if has_r else float("-inf")
        if strict:
            if (has_l and has_r and times[i - 1] >= lo and times[i + 1] <= hi
                    and values[i] > left and values[i] > right):
                peaks.append(i)
        elif values[i] > left and values[i] >= right:
            peaks.append(i)
    return sorted(peaks, key=lambda i: (-values[i], times[i]))


def minmax(values, ref):
    lo, hi = min(ref), max(ref)
    if hi - lo <= 1e-12:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def r2(x):
    return round(x + 0.0, 2)


# --- reaction -----------------------------------------------------------------
def analyze_reaction(path):
    dur = probe(path)["duration"]
    lo, hi = R_HEAD, dur - R_TAIL
    if hi - lo < R_MIN_LEN:
        raise RuntimeError(f"ролик короче {R_HEAD + R_TAIL + R_MIN_LEN:.0f} с")
    series = motion_series(path)
    if not series:
        raise RuntimeError("нет данных о движении")
    times = [t for t, _ in series]
    vals = smooth([v for _, v in series])
    maxima = local_maxima(times, vals, lo, hi, strict=True)
    top = vals[maxima[0]] if maxima else 0.0      # лучший настоящий пик = 1
    if top <= 0:
        return [], dur

    picked = []
    for i in maxima:
        score = vals[i] / top
        if score < R_SCORE_MIN or len(picked) >= R_MAX_PER_FILE:
            break
        if all(abs(times[i] - p) >= R_GAP for p, _ in picked):
            picked.append((times[i], score))

    picked.sort()
    segs = [[max(lo, p - R_BEFORE), min(hi, p + R_AFTER), p, s] for p, s in picked]
    for a, b in zip(segs, segs[1:]):              # соседей делим в пропорции R_BEFORE : R_AFTER
        if a[1] > b[0]:
            cut = a[2] + (b[2] - a[2]) * R_AFTER / (R_BEFORE + R_AFTER)
            if a[0] + R_MIN_LEN <= b[1] - R_MIN_LEN:   # у края окна — чтобы обоим хватило
                cut = min(max(cut, a[0] + R_MIN_LEN), b[1] - R_MIN_LEN)
            a[1] = b[0] = min(max(cut, a[2]), b[2])
    for i, seg in enumerate(segs):                # добор до R_MIN_LEN у краёв
        if seg[1] - seg[0] < R_MIN_LEN:
            seg[0] = max(segs[i - 1][1] if i else lo, seg[1] - R_MIN_LEN)
        if seg[1] - seg[0] < R_MIN_LEN:
            seg[1] = min(segs[i + 1][0] if i + 1 < len(segs) else hi, seg[0] + R_MIN_LEN)
    segs = [s for s in segs if s[1] - s[0] >= R_MIN_LEN - EPS]

    order = sorted(range(len(segs)), key=lambda i: (-segs[i][3], segs[i][2]))
    rank = {i: r for r, i in enumerate(order, 1)}
    rows = []
    for n, (start, end, peak, score) in enumerate(segs, 1):
        start, end = r2(start), r2(end)
        rows.append({"fragment": n, "start": start, "end": end, "duration": r2(end - start),
                     "peak": r2(peak), "score": r2(score), "rank": rank[n - 1]})
    return rows, dur


def check_reaction(rows, dur):
    """Инварианты отрезков одного файла. Пусто = всё верно."""
    errs = []
    for r in rows:
        s, e, p = r["start"], r["end"], r["peak"]
        if not R_MIN_LEN - EPS <= e - s <= R_MAX_LEN + EPS:
            errs.append(f"f{r['fragment']}: длина {e - s:.2f}")
        if not s - EPS <= p <= e + EPS:
            errs.append(f"f{r['fragment']}: пик вне отрезка")
        if s < R_HEAD - EPS or e > dur - R_TAIL + EPS:
            errs.append(f"f{r['fragment']}: отрезок в запретной зоне")
        if p < R_HEAD + 1 / MOTION_FPS - EPS or p > dur - R_TAIL - 1 / MOTION_FPS + EPS:
            errs.append(f"f{r['fragment']}: пик на границе окна")
    for a, b in zip(rows, rows[1:]):
        if a["end"] > b["start"] + EPS:
            errs.append(f"f{a['fragment']} и f{b['fragment']} пересекаются")
        if b["peak"] - a["peak"] < R_GAP - EPS:
            errs.append(f"f{a['fragment']} и f{b['fragment']}: пики ближе {R_GAP:g} с")
    if rows and max(r["score"] for r in rows) < 1 - EPS:
        errs.append("лучший score ≠ 1")
    return errs


# --- source -------------------------------------------------------------------
def orientation(w, h):
    ratio = w / h
    if abs(ratio - 1) <= ORIENT_TOL:
        return "square"
    return "horizontal" if ratio > 1 else "vertical"


def cut_window(peak, dur):
    if dur < CUT_MIN:
        return 0.0, dur
    length = min(CUT_TARGET, dur)
    start = max(0.0, min(peak - CUT_PEAK_POS * length, dur - length))
    return start, start + length


def analyze_source(path):
    info = probe(path)
    dur = info["duration"]
    motion = motion_series(path)
    audio, max_db = audio_series(path) if info["has_audio"] else ([], float("-inf"))
    use_audio = bool(audio) and max_db > SILENCE_DB
    m_times = [t for t, _ in motion]
    m_vals = smooth([v for _, v in motion])
    use_motion = bool(motion) and max(m_vals) > 0
    if use_audio:
        times, a_vals = [t for t, _ in audio], smooth([v for _, v in audio])
    else:
        times, a_vals = m_times, [0.0] * len(m_times)
    if not times:
        raise RuntimeError("нет ни звука, ни движения")

    def motion_at(t):                     # движение (шаг 0,25 с) на сетку звука (0,1 с)
        if not m_times:
            return 0.0
        i = bisect.bisect_left(m_times, t)
        near = [j for j in (i - 1, i) if 0 <= j < len(m_times)]
        return m_vals[min(near, key=lambda j: abs(m_times[j] - t))]

    hi = dur - S_TAIL
    ok = [i for i, t in enumerate(times) if S_HEAD <= t <= hi]
    if not ok:
        raise RuntimeError("ролик короче зоны анализа")
    m_all = [motion_at(t) for t in times]
    a_norm = minmax(a_vals, [a_vals[i] for i in ok]) if use_audio else [0.0] * len(times)
    m_norm = minmax(m_all, [m_all[i] for i in ok]) if use_motion else [0.0] * len(times)
    if use_audio and use_motion:
        wa, wm, method = S_W_AUDIO, S_W_MOTION, "audio+motion"
    elif use_audio:
        wa, wm, method = 1.0, 0.0, "audio"
    else:
        wa, wm, method = 0.0, 1.0, "motion"
    combo = [wa * a + wm * m for a, m in zip(a_norm, m_norm)]

    order = local_maxima(times, combo, S_HEAD, hi) or [max(ok, key=lambda i: combo[i])]
    peak = times[order[0]]
    peak2 = next((times[i] for i in order[1:] if abs(times[i] - peak) >= S_GAP), None)
    cut_start, cut_end = cut_window(peak, dur)
    row = {"duration": r2(dur), "width": info["width"], "height": info["height"],
           "orientation": orientation(info["width"], info["height"]),
           "peak": r2(peak), "peak2": "" if peak2 is None else r2(peak2),
           "peak_score": r2(combo[order[0]]), "method": method,
           "cut_start": r2(cut_start), "cut_end": r2(cut_end)}
    curve = [(r2(t), round(v, 3)) for t, v in zip(times, combo)]
    return row, curve


def check_source(r):
    errs = []
    d, p, cs, ce = r["duration"], r["peak"], r["cut_start"], r["cut_end"]
    if not (-EPS <= cs < ce <= d + EPS and cs - EPS <= p <= ce + EPS):
        errs.append("окно/пик вне ролика")
    if p < S_HEAD - EPS or p > d - S_TAIL + EPS:
        errs.append("пик в запретной зоне")
    if r["peak2"] != "" and abs(r["peak2"] - p) < S_GAP - EPS:
        errs.append("peak2 слишком близко")
    return errs


# --- CLI ----------------------------------------------------------------------
def collect(paths):
    files = []
    for p in map(Path, paths):
        p = p.expanduser()
        if p.is_dir():
            files += sorted(f for f in p.rglob("*")
                            if f.is_file() and f.suffix.lower() in VIDEO_EXTS
                            and not f.name.startswith(("._", ".")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"! нет такого пути: {p}", file=sys.stderr)
    return files


def write_csv(fh, fields, rows):
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    for row in rows:
        w.writerow({k: (f"{v:.2f}" if isinstance(v, float) else v)
                    for k, v in ((k, row.get(k, "")) for k in fields)})


def main():
    ap = argparse.ArgumentParser(description="Пиковые моменты в видео.")
    ap.add_argument("mode", choices=["reaction", "source"])
    ap.add_argument("paths", nargs="+", help="файлы или папки (папки — рекурсивно)")
    ap.add_argument("--csv", help="куда записать таблицу (UTF-8 с BOM, для Excel)")
    ap.add_argument("--curve", help="source: кривая активности 0..1 по времени — в этот CSV")
    args = ap.parse_args()

    files = collect(args.paths)
    if not files:
        sys.exit("видео не найдено")
    fn = analyze_reaction if args.mode == "reaction" else analyze_source
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = [pool.submit(fn, f) for f in files]
    rows, curves, errors = [], [], []
    for f, fut in zip(files, futures):
        name = f.as_posix()
        try:
            a, b = fut.result()
        except Exception as exc:               # битый файл не роняет прогон
            errors.append(f"{name}: {exc}")
            continue
        if args.mode == "reaction":
            bad = check_reaction(a, b)
            rows += [{"file": name, **r} for r in a]
        else:
            bad = check_source(a)
            rows.append({"file": name, **a})
            curves += [{"file": name, "t": t, "activity": v} for t, v in b]
        errors += [f"{name}: ПРОВЕРКА — {e}" for e in bad]

    fields = REACTION_FIELDS if args.mode == "reaction" else SOURCE_FIELDS
    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as fh:
            write_csv(fh, fields, rows)
    else:
        write_csv(sys.stdout, fields, rows)
    if args.curve and args.mode == "source":
        with open(args.curve, "w", encoding="utf-8-sig", newline="") as fh:
            write_csv(fh, ["file", "t", "activity"], curves)

    unit = "отрезков" if args.mode == "reaction" else "строк"
    print(f"{len(files)} файл(ов), {len(rows)} {unit}, ошибок: {len(errors)}", file=sys.stderr)
    for e in errors:
        print("  ✗ " + e, file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
