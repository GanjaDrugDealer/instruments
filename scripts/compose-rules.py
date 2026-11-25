"""Собирает файл правил агентов на этой машине и раскладывает его Claude, Codex и Antigravity.

Состав (по порядку):
  1. базовые правила - rules/CLAUDE.global.md (общие для всех людей и машин);
  2. личные правила из репозитория - rules/personal/<профиль>.md, профиль машины - одно слово
     в ~/.config/ai-rules/profile (нет файла - этой части нет);
  3. личные правила этой машины - ~/.config/ai-rules/personal.md (в git не едут).
Куда: ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md, ~/.gemini/GEMINI.md (последнее - если есть ~/.gemini),
~/.agents/AGENTS.md (оттуда её читает dsh - см. скилл project-structure, «dsh»).

Чужой файл правил (написанный руками, не этой сборкой) не теряется: при первой сборке он
переезжает в ~/.config/ai-rules/personal.md, если того ещё нет, иначе - в резервную копию.
Старая копия базовых правил (от прежнего установщика) просто заменяется.

Запускают install.ps1 / install.sh и автосинхронизация на каждом прогоне. Повторный запуск
безопасен: файл переписывается, только если состав изменился.
Проверить размер без записи: compose-rules.py --check-size [--profile имя].
Задать профиль машины: compose-rules.py --profile artem   (снять: --profile -)
"""
import argparse
import os
import shutil
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()
CONF = HOME / ".config" / "ai-rules"
PROFILE_FILE = CONF / "profile"
LOCAL = CONF / "personal.md"
BASE = REPO / "rules" / "CLAUDE.global.md"
BASE_TITLE = "# Общие правила для всех проектов"
MARK = ("<!-- Собрано из _instruments (scripts/compose-rules.py), здесь не править. Базовые правила - "
        "_instruments/rules/CLAUDE.global.md; личные - _instruments/rules/personal/<профиль>.md "
        "или ~/.config/ai-rules/personal.md. -->")


def say(text):
    print("  " + text)


parser = argparse.ArgumentParser(description="Сборка общих правил агентов")
parser.add_argument("--profile", help="выбрать профиль, '-' — без профиля")
parser.add_argument("--check-size", action="store_true", help="проверить бюджет без записи файлов")
args = parser.parse_args()
profile = PROFILE_FILE.read_text(encoding="utf-8").strip() if PROFILE_FILE.exists() else ""
if args.profile is not None:
    profile = "" if args.profile == "-" else args.profile.strip()

if args.profile is not None and not args.check_size:
    CONF.mkdir(parents=True, exist_ok=True)
    if not profile:
        PROFILE_FILE.unlink(missing_ok=True)
        say("profile removed")
    else:
        PROFILE_FILE.write_text(profile + "\n", encoding="utf-8")
        say(f"profile: {profile}")

parts = [MARK, BASE.read_text(encoding="utf-8").strip()]
if profile:
    personal = REPO / "rules" / "personal" / f"{profile}.md"
    if personal.exists():
        parts.append(personal.read_text(encoding="utf-8").strip())
    else:
        say(f"! no rules/personal/{profile}.md - personal part skipped")

targets = [HOME / ".claude" / "CLAUDE.md", HOME / ".codex" / "AGENTS.md",
           HOME / ".agents" / "AGENTS.md"]           # .agents - общий корень агентов, его читает dsh
if (HOME / ".gemini").is_dir():
    targets.append(HOME / ".gemini" / "GEMINI.md")

# Сначала - чужие файлы правил: первый становится личными правилами машины, остальные - в резерв.
backup = CONF / ("backup-" + time.strftime("%Y%m%d-%H%M%S"))
local_source = LOCAL
for t in targets:
    if t.is_symlink() or not t.exists():
        continue
    text = t.read_text(encoding="utf-8-sig", errors="replace")
    if text.startswith(MARK) or text.lstrip().startswith(BASE_TITLE):
        continue                                   # наша сборка или старая копия базовых правил
    if args.check_size:
        if not local_source.exists():
            local_source = t  # при обычной сборке этот файл станет personal.md
        continue
    if not LOCAL.exists():
        CONF.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t, LOCAL)
        say(f"own rules from {t.parent.name}/{t.name} kept as ~/.config/ai-rules/personal.md")
    elif text.strip() != LOCAL.read_text(encoding="utf-8-sig").strip():
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t, backup / f"{t.parent.name.lstrip('.')}-{t.name}")
        say(f"! own rules in {t.parent.name}/{t.name} differ from personal.md - saved to {backup.name}, merge by hand")

if local_source.exists():
    local = local_source.read_text(encoding="utf-8-sig").strip()
    if local:
        parts.append(local)
content = "\n\n".join(parts) + "\n"

# Размер базы на диске и размер полной копии при записи UTF-8 на этой ОС.
base_bytes = BASE.stat().st_size
installed_bytes = content.replace("\n", os.linesep).encode("utf-8")
over_budget = False
for label, size, limit_kib in (("база", base_bytes, 8), ("сборка", len(installed_bytes), 12)):
    exceeded = size > limit_kib * 1024
    if exceeded or args.check_size:
        prefix = "! " if exceeded else ""
        say(f"{prefix}{label}: {size} Б / {limit_kib} КиБ")
    over_budget |= exceeded
if over_budget:
    say("! Вынеси подробности в профильный скилл и повтори --check-size.")
if args.check_size:
    raise SystemExit(1 if over_budget else 0)

for t in targets:
    if t.is_symlink():
        t.unlink()                                  # прежняя раскладка на Mac - ссылка на исходник
    if t.exists() and t.read_text(encoding="utf-8-sig", errors="replace") == content:
        continue
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_bytes(installed_bytes)
    say(f"rules -> {t.parent.name}/{t.name}")

say("rules: base" + (f" + {profile}" if profile else "") + (" + personal.md" if LOCAL.exists() else ""))
