#!/usr/bin/env python3
"""Слежение архитектора за исполнителями: одна строка на событие.

  py watch-executors.py <папка проекта> [папка отчётов=docs/tasks/reports]      (Mac: python3)

СДАЧА <файл>        — новый или изменённый отчёт исполнителя (главный сигнал: пора принимать)
В РАБОТЕ <файлы>    — изменился набор незакоммиченных файлов (исполнитель что-то правит)
КОММИТ <hash> <msg> — новый коммит (свой или чужой — разобрать)
По умолчанию — только СДАЧА (экономия токенов, 2026-09-28: каждое событие = ход сессии архитектора);
WATCH_WIP=1 — ещё В РАБОТЕ и КОММИТ. Интервал — WATCH_INTERVAL (сек, по умолчанию 10).
WATCH_BOARD=<файл> — доска задач (по умолчанию docs/tasks/README.md). Сам не выходит.
Только стандартная библиотека; работает на Windows и Mac (замена watch-executors.sh).
"""
import glob
import os
import subprocess
import sys
import time


def out(*parts):
    print(*parts, flush=True)


def git(*args):
    r = subprocess.run(["git", "-c", "core.quotepath=off", *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def snap(rep):
    """{путь: (mtime_ns, размер)} для файлов отчётов, кроме .gitkeep."""
    res = {}
    for root, _dirs, names in os.walk(rep):
        for n in names:
            if n == ".gitkeep":
                continue
            f = os.path.join(root, n).replace("\\", "/")
            try:
                st = os.stat(f)
            except OSError:
                continue
            res[f] = (st.st_mtime_ns, st.st_size)
    return res


def wip(rep):
    """Незакоммиченные файлы проекта (кроме папки отчётов), отсортированные."""
    text = git("status", "--porcelain", "-uall") or ""
    pref = rep.replace("\\", "/").rstrip("/") + "/"
    files = set()
    for line in text.splitlines():
        p = line[3:]
        if " -> " in p:                       # переименование: берём новый путь
            p = p.split(" -> ", 1)[1]
        if len(p) > 1 and p.startswith('"') and p.endswith('"'):
            p = p[1:-1]
        if p.startswith(pref):
            continue
        files.add(p)
    return " ".join(sorted(files))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        out("ОШИБКА: укажи папку проекта")
        return 1
    try:
        os.chdir(sys.argv[1])
    except OSError:
        out(f"ОШИБКА: нет папки {sys.argv[1]}")
        return 1
    rep = sys.argv[2] if len(sys.argv) > 2 else "docs/tasks/reports"
    iv = os.environ.get("WATCH_INTERVAL") or "10"
    os.makedirs(rep, exist_ok=True)

    isgit = os.environ.get("WATCH_WIP") == "1" and git("rev-parse", "--is-inside-work-tree") is not None
    head = (git("rev-parse", "HEAD") or "").strip() if isgit else ""
    prev = snap(rep)
    pw = wip(rep) if isgit else ""
    out(f"СЛЕЖУ ЗА ИСПОЛНИТЕЛЯМИ: {os.path.basename(os.getcwd())} → отчёты в {rep}"
        f"{' + рабочие файлы + коммиты' if isgit else ''}, каждые {iv} с")
    if pw:
        out(f"В РАБОТЕ (на старте) {pw}")

    # Сдано до старта или в окне между перезапусками (2026-10-03: CM12 сдан за минуты до включения
    # слежения и не замечен): отчёт, чья задача есть на доске и ещё не «принято», — тоже СДАЧА.
    board = os.environ.get("WATCH_BOARD") or "docs/tasks/README.md"
    if os.path.isfile(board):
        with open(board, encoding="utf-8", errors="replace") as fh:
            rows = fh.read().splitlines()
        base = rep.replace("\\", "/").rstrip("/")
        for f in sorted(glob.glob(f"{glob.escape(rep)}/*_report.md")):
            name = os.path.basename(f)
            tid = name.split("_", 1)[1] if "_" in name else name   # убрать дату
            if tid.endswith("_report.md"):
                tid = tid[:-len("_report.md")]
            row = next((r for r in rows if r.startswith(f"| {tid} |")), None)
            if row is not None and "принято" not in row:
                out(f"СДАЧА (до старта) {base}/{name}")

    while True:
        time.sleep(float(iv))
        if isgit:
            h = (git("rev-parse", "HEAD") or "").strip()
            if h and h != head:
                rng = f"{head}..{h}" if head else h
                log = git("log", "--format=КОММИТ %h %s", rng) or ""
                for line in log.splitlines()[:20]:
                    out(line)
                head = h
            w = wip(rep)
            if w != pw:
                out(f"В РАБОТЕ {w or '— всё закоммичено'}")
                pw = w
        cur = snap(rep)
        if cur != prev:
            for f in sorted(cur):
                if f not in prev or prev[f] != cur[f]:
                    out(f"СДАЧА {f}")
            prev = cur


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
