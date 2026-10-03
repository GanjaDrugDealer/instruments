#!/usr/bin/env python3
"""Слежение за проектом: одна строка на событие — новый коммит или изменение файлов задач.

  py watch-tasks.py <папка проекта> [путь ...]      (Mac: python3)   пути относительно проекта

По умолчанию — только docs/tasks, без папки отчётов (экономия токенов, 2026-09-28:
каждое событие = ход сессии).
  WATCH_MATCH=<рег. выражение> — сообщать только о файлах, чьё имя подходит (свой ID задачи: _CM, _T2 ...).
  WATCH_COMMITS=1              — ещё и коммиты.
  WATCH_INTERVAL=<сек>         — интервал опроса (по умолчанию 10).
  WATCH_BOARD=<файл>           — доска задач (по умолчанию docs/tasks/README.md).
Никогда не выходит сам: остановка — снаружи (TaskStop / Ctrl+C / таймаут монитора).
Только стандартная библиотека; работает на Windows и Mac (замена watch-tasks.sh).
"""
import glob
import os
import re
import subprocess
import sys
import time


def out(*parts):
    print(*parts, flush=True)


def git(*args):
    r = subprocess.run(["git", "-c", "core.quotepath=off", *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def snap(paths, match):
    """{путь: (mtime_ns, размер)} — файлы под paths, кроме папок reports/, с фильтром WATCH_MATCH."""
    res = {}
    for p in paths:
        p = p.replace("\\", "/")
        if os.path.isfile(p):
            files = [p]
        elif os.path.isdir(p):
            files = []
            for root, _dirs, names in os.walk(p):
                for n in names:
                    files.append(os.path.join(root, n).replace("\\", "/"))
        else:
            continue
        for f in files:
            if "/reports/" in f:
                continue
            if match and not re.search(match, f):
                continue
            try:
                st = os.stat(f)
            except OSError:
                continue
            res[f] = (st.st_mtime_ns, st.st_size)
    return res


def pending_tasks(match):
    """Выдано, пока слежение было выключено: своя задача без отчёта и без «принято» на доске."""
    board = os.environ.get("WATCH_BOARD") or "docs/tasks/README.md"
    if not os.path.isfile(board):
        return
    with open(board, encoding="utf-8", errors="replace") as fh:
        rows = fh.read().splitlines()
    for f in sorted(glob.glob("docs/tasks/*.md")):
        f = f.replace("\\", "/")
        name = f.rsplit("/", 1)[-1]
        if name == "README.md":
            continue
        if match and not re.search(match, f):
            continue
        tid = name.split("_", 1)[1] if "_" in name else name   # убрать дату до первого «_»
        tid = tid.split("_", 1)[0]                              # ID — до следующего «_»
        if tid.endswith(".md"):
            tid = tid[:-3]
        row = next((r for r in rows if r.startswith(f"| {tid} |")), None)
        if row is None or "принято" in row:
            continue
        if glob.glob(f"docs/tasks/reports/*_{glob.escape(tid)}_report.md"):
            continue
        out(f"ЗАДАЧА ЖДЁТ {f}")


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
    paths = sys.argv[2:] or ["docs/tasks"]
    iv = os.environ.get("WATCH_INTERVAL") or "10"
    match = os.environ.get("WATCH_MATCH") or ""

    isgit = os.environ.get("WATCH_COMMITS") == "1" and git("rev-parse", "--is-inside-work-tree") is not None
    head = (git("rev-parse", "HEAD") or "").strip() if isgit else ""
    prev = snap(paths, match)
    out(f"СЛЕЖУ: {os.path.basename(os.getcwd())} → {' '.join(paths)}"
        f"{f' (только {match})' if match else ''}{' + коммиты' if isgit else ''}, каждые {iv} с")
    pending_tasks(match)

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
        cur = snap(paths, match)
        if cur != prev:
            for f in sorted(cur):
                if f not in prev:
                    out(f"НОВЫЙ ФАЙЛ {f}")
                elif prev[f] != cur[f]:
                    out(f"ИЗМЕНЁН {f}")
            for f in sorted(prev):
                if f not in cur:
                    out(f"УДАЛЁН {f}")
            prev = cur


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
