# -*- coding: utf-8 -*-
"""Меняет шаблонные блоки про Google Диск в CLAUDE.md и GUARDRAILS.md
всех проектов. Только точное совпадение болванки; живой текст не трогает.
Запуск без аргумента - сухой прогон. С аргументом apply - пишет."""
import os, sys

ROOT = r"C:\AI Projects"
APPLY = len(sys.argv) > 1 and sys.argv[1] == "apply"

G_OLD = "5. Не класть в папку `.git`, `.venv`, `node_modules` - она на Google Диске."
G_NEW = ("5. Не коммитить секреты и личные данные: `.env`, токены, профили, базы -\n"
         "   в `data\\`, закрытой `.gitignore`.")

C_OLD = ("Внутри проекта не должно быть: абсолютных путей за пределы папки, `.venv`,\n"
         "`.git`, `node_modules`, реальных секретов. Секреты - в `.env` рядом, он на Диск\n"
         "не синхронизируется и в проект не входит.")
C_NEW = ("Внутри проекта не должно быть абсолютных путей за пределы папки и реальных\n"
         "секретов. `.venv`, `.git`, `node_modules` внутри - нормально: хранилище\n"
         "локальное, облачной синхронизации нет. Секреты - в `.env`, он закрыт\n"
         "`.gitignore`; в репозиторий едет только `.env.example` с именами переменных.")

JOBS = [("GUARDRAILS.md", G_OLD, G_NEW), ("CLAUDE.md", C_OLD, C_NEW)]

changed = skipped = 0
for branch in ("Claude", "Antigravity"):
    base = os.path.join(ROOT, branch)
    for proj in sorted(os.listdir(base)):
        d = os.path.join(base, proj)
        if not os.path.isdir(d):
            continue
        for fname, old, new in JOBS:
            p = os.path.join(d, fname)
            if not os.path.exists(p):
                continue
            txt = open(p, encoding="utf-8").read()
            if old not in txt:
                continue
            n = txt.count(old)
            if n != 1:
                print(f"[!] {branch}\\{proj}\\{fname}: совпадений {n}, пропуск")
                skipped += 1
                continue
            if APPLY:
                open(p, "w", encoding="utf-8", newline="").write(txt.replace(old, new))
            print(f"[{'fix' if APPLY else 'dry'}] {branch}\\{proj}\\{fname}")
            changed += 1

print(f"\n{'Изменено' if APPLY else 'Будет изменено'}: {changed}; пропущено: {skipped}")
if not APPLY:
    print("Сухой прогон. Для записи: patch-stale.py apply")
