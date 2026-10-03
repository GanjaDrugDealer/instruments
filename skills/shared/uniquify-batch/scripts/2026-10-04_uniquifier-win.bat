@echo off
rem Windows uniquifier launcher.
rem Double click: dialogs (functions, files, output folder).
rem With args: [--only=..|--skip=..] [--keep-name] [--encoder=..] -o FOLDER files...
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% -X utf8 "%~dp0\2026-10-04_uniquifier-win.py" %*
set RC=%ERRORLEVEL%
if "%~1"=="" pause
exit /b %RC%
