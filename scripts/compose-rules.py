"""Собирает файл правил агентов на этой машине и раскладывает его Claude, Codex и Antigravity.

Состав (по порядку):
  1. базовые правила - rules/CLAUDE.global.md (общие для всех людей и машин);
  2. личные правила из репозитория - rules/personal/<профиль>.md, профиль машины - одно слово
     в ~/.config/ai-rules/profile (нет файла - этой части нет);
  3. личные правила этой машины - ~/.config/ai-rules/personal.md (в git не едут).
Куда: ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md, ~/.gemini/GEMINI.md (последнее - если есть ~/.gemini).

Чужой файл правил (написанный руками, не этой сборкой) не теряется: при первой сборке он
переезжает в ~/.config/ai-rules/personal.md, если того ещё нет, иначе - в резервную копию.
Старая копия базовых правил (от прежнего установщика) просто заменяется.

Запускают install.ps1 / install.sh и автосинхронизация на каждом прогоне. Повторный запуск
безопасен: файл переписывается, только если состав изменился.
Задать профиль машины: compose-rules.py --profile artem   (снять: --profile -)
"""
import shutil
import sys
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


args = sys.argv[1:]
if args[:1] == ["--profile"] and len(args) == 2:
    CONF.mkdir(parents=True, exist_ok=True)
    if args[1] == "-":
        PROFILE_FILE.unlink(missing_ok=True)
        say("profile removed")
    else:
        PROFILE_FILE.write_text(args[1].strip() + "\n", encoding="utf-8")
        say(f"profile: {args[1].strip()}")

profile = PROFILE_FILE.read_text(encoding="utf-8").strip() if PROFILE_FILE.exists() else ""
parts = [MARK, BASE.read_text(encoding="utf-8").strip()]
if profile:
    personal = REPO / "rules" / "personal" / f"{profile}.md"
    if personal.exists():
        parts.append(personal.read_text(encoding="utf-8").strip())
    else:
        say(f"! no rules/personal/{profile}.md - personal part skipped")

targets = [HOME / ".claude" / "CLAUDE.md", HOME / ".codex" / "AGENTS.md"]
if (HOME / ".gemini").is_dir():
    targets.append(HOME / ".gemini" / "GEMINI.md")

# Сначала - чужие файлы правил: первый становится личными правилами машины, остальные - в резерв.
backup = CONF / ("backup-" + time.strftime("%Y%m%d-%H%M%S"))
for t in targets:
    if t.is_symlink() or not t.exists():
        continue
    text = t.read_text(encoding="utf-8-sig", errors="replace")
    if text.startswith(MARK) or text.lstrip().startswith(BASE_TITLE):
        continue                                   # наша сборка или старая копия базовых правил
    if not LOCAL.exists():
        CONF.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t, LOCAL)
        say(f"own rules from {t.parent.name}/{t.name} kept as ~/.config/ai-rules/personal.md")
    elif text.strip() != LOCAL.read_text(encoding="utf-8-sig").strip():
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t, backup / f"{t.parent.name.lstrip('.')}-{t.name}")
        say(f"! own rules in {t.parent.name}/{t.name} differ from personal.md - saved to {backup.name}, merge by hand")

if LOCAL.exists():
    local = LOCAL.read_text(encoding="utf-8-sig").strip()
    if local:
        parts.append(local)
content = "\n\n".join(parts) + "\n"

for t in targets:
    if t.is_symlink():
        t.unlink()                                  # прежняя раскладка на Mac - ссылка на исходник
    if t.exists() and t.read_text(encoding="utf-8-sig", errors="replace") == content:
        continue
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text(content, encoding="utf-8")
    say(f"rules -> {t.parent.name}/{t.name}")

say("rules: base" + (f" + {profile}" if profile else "") + (" + personal.md" if LOCAL.exists() else ""))
