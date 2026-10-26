@echo off
rem Update this closed project in Open WebUI: preset local-<folder> (system prompt = CLAUDE.md)
rem and its knowledge base (STATE.md, GUARDRAILS.md, docs\context). Run after editing these files by hand.
rem Optional: sync-webui.bat --model fast:9b   (change the base model)
chcp 65001 >nul
python -X utf8 "C:\AI Projects\Antigravity\local-gpt\scripts\sync_webui_project.py" "%~dp0." %*
pause
