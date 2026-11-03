@echo off
setlocal
title New Codex project
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\new-project.ps1" -Branch Codex %*
if errorlevel 1 echo Project creation failed. See the message above.
echo.
pause
