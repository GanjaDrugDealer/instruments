"""Ставит или обновляет хук SessionStart Claude Code, который сообщает агенту о сбое
автосинхронизации _Instruments (sync-status.ps1 / sync-status.sh).
Запускают install.ps1 и install.sh. Повторный запуск безопасен: прежняя запись
этого хука заменяется, остальные настройки и хуки не трогаются.

Использование: claude-hook.py <путь к settings.json> <путь к sync-status.ps1|.sh>
"""
import json
import shutil
import sys
import time
from pathlib import Path

MARK = "sync-status."
settings, script = Path(sys.argv[1]), sys.argv[2]
if script.endswith(".ps1"):
    command = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{script}"'
else:
    command = f'zsh "{script}"'

old_text = settings.read_text(encoding="utf-8-sig") if settings.exists() else ""
data = json.loads(old_text) if old_text.strip() else {}
groups = data.setdefault("hooks", {}).setdefault("SessionStart", [])
for group in groups:
    group["hooks"] = [h for h in group.get("hooks", []) if MARK not in h.get("command", "")]
groups[:] = [g for g in groups if g.get("hooks")]
groups.append({"matcher": "startup",
               "hooks": [{"type": "command", "command": command, "timeout": 15}]})

new_text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
if new_text == old_text:
    print("  hook already set")
    sys.exit(0)
if settings.exists():
    shutil.copy2(settings, settings.with_name(settings.name + time.strftime(".bak-%Y%m%d-%H%M%S")))
settings.parent.mkdir(parents=True, exist_ok=True)
settings.write_text(new_text, encoding="utf-8")
print("  SessionStart hook set:", command)
