@echo off
chcp 65001 >nul
set "ProjectName=%~1"
if "%ProjectName%"=="" (
    echo =========================================
    echo         NEW ANTIGRAVITY PROJECT
    echo =========================================
    set /p "ProjectName=Please enter the project name: "
)

if "%ProjectName%"=="" (
    echo [Error] Project name cannot be empty.
    pause
    exit /b 1
)

python "Instruments\scripts\bootstrap_project.py" "%ProjectName%"

echo.
echo Press any key to close this window...
pause >nul
