# -*- coding: utf-8 -*-
"""
Линтер структуры проектов. НИЧЕГО НЕ МЕНЯЕТ — только показывает расхождения
со стандартом (скилл project-structure). Решение всегда за человеком.

Запуск:  Windows — python -X utf8 "C:\\AI Projects\\_instruments\\scripts\\check-structure.py"
         Mac     — python3 -X utf8 ~/Desktop/"AI Projects"/_instruments/scripts/check-structure.py
"""
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # папка «AI Projects»
BRANCHES = ["Claude", "Antigravity", "Local", "Codex"]
MUST_FILES = ["CLAUDE.md", "AGENTS.md", "GUARDRAILS.md", ".env.example"]
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SECRETS = {".env", "secrets.json", "credentials.json"}
SKIP = {".git", ".venv", "node_modules", "__pycache__", "build", "dist",
        "pipeline", "site-packages", "_archive", "data", "logs"}

# Следы архитектуры на Google Диске, от которой отказались 16.09.2026.
STALE = re.compile(r"Google\s*Диск|гуглодиск|Google Drive|Мой диск|\bK:\\", re.I)
# Строки, где эти слова законны: описание текущего состояния и чужие сервисы.
BENIGN = re.compile(
    r"облачной синхронизации нет|больше не используется|не используется с|"
    r"Яндекс\.Диск|Nextcloud|OneDrive", re.I)
# Документы, которые описывают прошлое и должны упоминать Диск.
HISTORICAL = {
    "docs/2026-09-16_work-plan.md",
    "docs/2026-09-09_hh-bot-actual.md",
    "docs/2026-09-15_hh-agent-local-vs-git.md",
}

LOCAL_MARKER = "ЗАКРЫТЫЙ ПРОЕКТ"

out = []
bad = warn = ok = 0
def p(s): out.append(s)


def check(prj: Path, *, is_local: bool = False):
    issues, hints = [], []

    if not KEBAB.match(prj.name):
        issues.append("имя папки не kebab-case латиницей")

    for f in MUST_FILES:
        if not (prj / f).exists():
            issues.append(f"нет {f}")
    if not (prj / ".claude" / "skills").exists():
        issues.append("нет .claude/skills/")

    if (prj / "skills").exists():
        issues.append("вторая папка skills/ рядом с .claude/skills/")

    # секреты без .gitignore
    for s in SECRETS:
        if (prj / s).exists():
            gi = prj / ".gitignore"
            covered = gi.exists() and s in gi.read_text(encoding="utf-8", errors="replace")
            if not covered:
                issues.append(f"{s} есть, но не закрыт .gitignore")

    # скиллы: ровно один уровень
    sk = prj / ".claude" / "skills"
    if sk.exists():
        for x in sk.iterdir():
            if x.is_dir() and not (x / "SKILL.md").exists():
                nested = any((y / "SKILL.md").exists() for y in x.iterdir() if y.is_dir())
                issues.append(
                    f"скилл {x.name}: " +
                    ("SKILL.md на уровень глубже — не загрузится" if nested
                     else "нет SKILL.md"))

    # --- Проверки, специфичные для Local ---
    if is_local:
        # Маркер ЗАКРЫТЫЙ ПРОЕКТ в первых 3 строках CLAUDE.md
        claude_md = prj / "CLAUDE.md"
        if claude_md.exists():
            try:
                head = claude_md.read_text(encoding="utf-8", errors="ignore").splitlines()[:3]
                if not any(LOCAL_MARKER in line for line in head):
                    issues.append(f"нет маркера «{LOCAL_MARKER}» в первых 3 строках CLAUDE.md")
            except Exception:
                pass

        # Удалённый репозиторий у закрытого проекта
        git_config = prj / ".git" / "config"
        if git_config.exists():
            try:
                gc_text = git_config.read_text(encoding="utf-8", errors="ignore")
                if "[remote" in gc_text:
                    issues.append("у закрытого проекта удалённый репозиторий")
            except Exception:
                pass

        return issues, hints

    # --- Проверки только для не-Local проектов ---
    # абсолютные пути наружу
    pat = re.compile(r"[A-Z]:\\(?!AI Projects)|/Users/[^/\s]+/(?!Desktop/AI Projects)")
    hits = []
    for dp, dn, fn in os.walk(prj):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            fp = Path(dp) / f
            if fp.suffix.lower() not in {".md", ".py", ".bat", ".ps1", ".json", ".sh", ".command"}:
                continue
            try:
                if fp.stat().st_size > 200_000:
                    continue
                t = fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if pat.search(t):
                hits.append(str(fp.relative_to(prj)))
    if hits:
        hints.append(f"абсолютные пути наружу: {len(hits)} файлов "
                     f"({', '.join(hits[:3])}{'…' if len(hits) > 3 else ''})")

    # следы старой архитектуры (Google Диск, том K:)
    stale = []
    for dp, dn, fn in os.walk(prj):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            if not f.lower().endswith(".md"):
                continue
            fp = Path(dp) / f
            rel = fp.relative_to(prj).as_posix()
            if rel in HISTORICAL:
                continue
            try:
                lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue
            for n, line in enumerate(lines, 1):
                if STALE.search(line) and not BENIGN.search(line):
                    stale.append(f"{rel}:{n}")
    if stale:
        issues.append(f"следы старой архитектуры (Google Диск / K:): "
                      f"{', '.join(stale[:4])}{'…' if len(stale) > 4 else ''}")

    return issues, hints


for branch in BRANCHES:
    b = ROOT / branch
    if not b.exists():
        continue
    p(f"\n=== {branch}/ ===")
    is_local = (branch == "Local")
    for prj in sorted(b.iterdir()):
        if not prj.is_dir():
            continue
        issues, hints = check(prj, is_local=is_local)
        if issues:
            bad += 1
            p(f"\n  [!] {prj.name}")
            for i in issues:
                p(f"        {i}")
            for h in hints:
                p(f"        ~ {h}")
        elif hints:
            warn += 1
            p(f"\n  [~] {prj.name}")
            for h in hints:
                p(f"        {h}")
        else:
            ok += 1
            p(f"  [ok] {prj.name}")

p(f"\n\nИтог: по стандарту {ok}, замечания {warn}, расхождения {bad}")
p("Скрипт ничего не изменил. Что чинить — решать человеку.")

report = "\n".join(out)
print(report)
Path(ROOT / "_instruments" / "scripts" / "check-structure.log").write_text(
    report, encoding="utf-8")
