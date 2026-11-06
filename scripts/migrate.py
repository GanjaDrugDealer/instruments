"""Разовые переезды на любой машине (ПК, Mac, другие): переименование папок проектов,
новые адреса репозиториев после переименования на GitHub, перенос памяти Claude.

Запускают install.ps1 / install.sh и автосинхронизация (sync.ps1 / sync.sh) при каждом
прогоне. Повторный запуск безопасен: сделанное пропускается. Вывод - по-английски
(его читает PowerShell 5.1 в консоли CP866), пути - только внутри AI Projects.

Код выхода: 0 - всё сделано или делать нечего; 2 - что-то не вышло (причина в выводе),
повторится при следующем прогоне.

Новый переезд - строка в RENAMES / REMOTES с датой. Старые строки не удалять:
машина, которая долго не включалась, догонит все по порядку.
"""
import re
import subprocess
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[2]          # папка «AI Projects»

# Папки проектов: (старый путь, новый путь) от AI Projects.
RENAMES = [
    ("Claude/ai-instruments", "Claude/ai-workshop"),        # 2026-11-06
]
# Адрес origin: папка -> имя репозитория GanjaDrugDealer, если сейчас стоит одно из старых имён.
REMOTES = {
    "_Instruments": ("instruments", {"ai-instruments"}),        # 2026-11-06
    "Claude/ai-workshop": ("ai-workshop", {"ai-instruments"}),  # 2026-11-06
}

problems = []


def say(text):
    print("  " + text)


def claude_slug(path):
    """Имя папки проекта в ~/.claude/projects: всё, кроме латиницы и цифр, - дефис."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def move_claude_memory(old, new):
    projects = Path.home() / ".claude" / "projects"
    src = projects / claude_slug(old) / "memory"
    dst = projects / claude_slug(new) / "memory"
    if not src.is_dir() or not any(src.iterdir()):
        return
    if dst.exists() and any(dst.iterdir()):
        problems.append(f"Claude memory exists for both {claude_slug(old)} and {claude_slug(new)} - merge by hand")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.rmdir()
    src.rename(dst)
    say(f"Claude memory moved to {claude_slug(new)}")


for old_rel, new_rel in RENAMES:
    old, new = AI / old_rel, AI / new_rel
    if old.exists() and new.exists():
        problems.append(f"both {old_rel} and {new_rel} exist - merge by hand")
        continue
    if old.exists():
        try:
            old.rename(new)
        except OSError as e:
            problems.append(f"cannot rename {old_rel} -> {new_rel} (folder busy? close sessions/editors there): {e.strerror}")
            continue
        say(f"renamed {old_rel} -> {new_rel}")
    if new.exists():
        move_claude_memory(old, new)

for rel, (target, old_names) in REMOTES.items():
    repo = AI / rel
    if not (repo / ".git").exists():
        continue
    r = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"], capture_output=True, text=True)
    url = r.stdout.strip()
    m = re.search(r"(github\.com[:/]GanjaDrugDealer/)([\w.-]+?)(\.git)?$", url)
    if r.returncode or not m or m.group(2) not in old_names:
        continue
    new_url = url[:m.start(2)] + target + (m.group(3) or "")
    if subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", new_url]).returncode:
        problems.append(f"cannot set origin of {rel} to {new_url}")
    else:
        say(f"{rel}: origin -> {new_url}")

for p in problems:
    say("! " + p)
sys.exit(2 if problems else 0)
