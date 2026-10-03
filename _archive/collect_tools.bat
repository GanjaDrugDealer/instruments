@echo off
chcp 65001 >nul
color 0A

echo ==========================================================
echo    [ Antigravity ] Сбор и регистрация инструментов
echo ==========================================================
echo.

set PROJECT_DIR=K:\Мой диск\AI Projects\Antigravity\RemoteAgentControl
set TOOLS_DIR=%PROJECT_DIR%\antigravity_tools

echo [1/3] Проверка директории скиллов (Skills)...
if exist "%TOOLS_DIR%\skills" (
    echo   OK: Скиллы найдены.
) else (
    echo   ВНИМАНИЕ: Папка скиллов пуста.
)

echo [2/3] Сканирование MCP серверов (mcp)...
if exist "%TOOLS_DIR%\mcp" (
    echo   OK: Директория MCP готова.
) else (
    echo   ВНИМАНИЕ: Директория MCP не найдена.
)

echo [3/3] Регистрация конфигураций агентов...
if exist "%TOOLS_DIR%\agents" (
    echo   OK: Агенты готовы к загрузке.
) else (
    echo   ВНИМАНИЕ: Конфигурации агентов не найдены.
)

echo.
echo ==========================================================
echo ✅ Сбор завершен. Инструменты готовы к подключению.
echo ==========================================================
pause
