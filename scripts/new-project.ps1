# Создание нового проекта из шаблона _Instruments\templates\project.
# Запуск: new-project.bat в корне AI Projects (двойной щелчок или с аргументами).
param(
    [string]$Branch,
    [string]$Name,
    [switch]$NoPrompt   # для агента: ничего не спрашивать, при ошибке выйти с кодом 2
)
$ErrorActionPreference = 'Stop'
if ($NoPrompt -and $Branch -notin @('Claude', 'Antigravity')) {
    Write-Host "  Ветка '$Branch' не подходит: Claude или Antigravity." -ForegroundColor Yellow; exit 2
}

$root     = Split-Path $PSScriptRoot -Parent | Split-Path -Parent
$template = Join-Path $root '_Instruments\templates\project'
$utf8     = New-Object System.Text.UTF8Encoding($false)

# Ветка: кто ведёт проект
while ($Branch -notin @('Claude', 'Antigravity')) {
    $ans = Read-Host 'Кто ведёт проект? 1 - Claude, 2 - Antigravity [1]'
    switch ($ans) {
        { $_ -in @('', '1', 'Claude', 'claude') }           { $Branch = 'Claude' }
        { $_ -in @('2', 'Antigravity', 'antigravity') }     { $Branch = 'Antigravity' }
        default { Write-Host 'Введите 1 или 2.' -ForegroundColor Yellow }
    }
}

# Имя папки: латиница в нижнем регистре, цифры, дефис
while ($true) {
    if (-not $Name) { $Name = (Read-Host 'Название папки проекта (латиница, kebab-case, например logo-script)').Trim() }
    $dest = Join-Path (Join-Path $root $Branch) $Name
    if ($Name -cnotmatch '^[a-z0-9]+(-[a-z0-9]+)*$') {
        Write-Host "  '$Name' не подходит: только a-z, 0-9 и дефис между словами." -ForegroundColor Yellow
    } elseif ((Test-Path $dest) -and (Get-ChildItem $dest -Force | Select-Object -First 1)) {
        Write-Host "  Папка уже существует и не пустая: $dest" -ForegroundColor Yellow
    } else { break }
    if ($NoPrompt) { exit 2 }
    $Name = $null
}

New-Item -ItemType Directory -Force $dest | Out-Null
Copy-Item -Path (Join-Path $template '*') -Destination $dest -Recurse -Force

# Подстановки в живых файлах
$subs = @{
    'CLAUDE.md' = @{ '<project-name>' = $Name }
    'STATE.md'  = @{ '<date>' = (Get-Date -Format 'yyyy-MM-dd') }
}
foreach ($file in $subs.Keys) {
    $path = Join-Path $dest $file
    if (-not (Test-Path $path)) { continue }
    $text = [IO.File]::ReadAllText($path, $utf8)
    foreach ($k in $subs[$file].Keys) { $text = $text.Replace($k, $subs[$file][$k]) }
    [IO.File]::WriteAllText($path, $text, $utf8)
}

Write-Host ''
Write-Host "Создан проект: $dest" -ForegroundColor Green
Write-Host 'Дальше: открыть эту папку в Claude Code и написать «Собираем контекст».'
