# -*- coding: utf-8 -*-
"""Приёмка работы агента по диффу без git.

  python -X utf8 snapdiff.py snap <папка-проекта>          снимок до выдачи ТЗ
  python -X utf8 snapdiff.py diff <папка-проекта> [снимок]  дифф против снимка
                                                            (по умолчанию последний)

Снимки: Windows — %LOCALAPPDATA%\\agent-snapshots\\<проект>\\ГГГГ-ММ-ДД_ЧЧММСС,
        Mac — ~/Library/Caches/agent-snapshots/<проект>/ГГГГ-ММ-ДД_ЧЧММСС
Пропускает junction и симлинки, .git, .venv, node_modules, __pycache__,
secrets.json, .env, файлы больше 5 МБ. Код выхода diff: 0 — изменений нет, 1 — есть.
"""
import os
import sys
import shutil
import difflib
from datetime import datetime

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__"}
SKIP_FILES = {"secrets.json", ".env"}
MAX_BYTES = 5 * 1024 * 1024
ROOT = os.path.join(os.environ.get("LOCALAPPDATA")
                    or os.path.expanduser("~/Library/Caches"), "agent-snapshots")


def is_link(p):
    return os.path.islink(p) or (hasattr(os.path, "isjunction") and os.path.isjunction(p))


def files(base):
    out = {}
    for cur, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not is_link(os.path.join(cur, d))]
        for n in names:
            p = os.path.join(cur, n)
            if n in SKIP_FILES or is_link(p) or os.path.getsize(p) > MAX_BYTES:
                continue
            out[os.path.relpath(p, base)] = p
    return out


def snap(proj):
    dst = os.path.join(ROOT, os.path.basename(os.path.abspath(proj)),
                       datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    for rel, src in files(proj).items():
        t = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(t), exist_ok=True)
        shutil.copy2(src, t)
    print(dst)


def lines(p):
    with open(p, "rb") as f:
        b = f.read()
    if b"\0" in b:
        return None
    return b.decode("utf-8", errors="replace").replace("\r\n", "\n").splitlines(True)


def diff(proj, snapdir=None):
    if not snapdir:
        d = os.path.join(ROOT, os.path.basename(os.path.abspath(proj)))
        runs = sorted(os.listdir(d)) if os.path.isdir(d) else []
        if not runs:
            sys.exit("снимков нет: сначала snap")
        snapdir = os.path.join(d, runs[-1])
    old, new = files(snapdir), files(proj)
    changed = 0
    for rel in sorted(set(old) | set(new)):
        a, b = old.get(rel), new.get(rel)
        la = lines(a) if a else []
        lb = lines(b) if b else []
        if la is None or lb is None:
            tag = "+" if not a else "-" if not b else "~"
            if not a or not b or open(a, "rb").read() != open(b, "rb").read():
                print("%s %s (двоичный)" % (tag, rel)); changed += 1
            continue
        if la == lb and a and b:
            continue
        changed += 1
        tag = "+" if not a else "-" if not b else "~"
        print("%s %s" % (tag, rel))
        sys.stdout.writelines(difflib.unified_diff(
            la, lb, "до/" + rel, "после/" + rel))
        print()
    print("снимок: %s\nизменено файлов: %d" % (snapdir, changed))
    sys.exit(1 if changed else 0)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("snap", "diff"):
        sys.exit(__doc__)
    (snap if sys.argv[1] == "snap" else diff)(*sys.argv[2:4])
