# Создание нового проекта из шаблона _Instruments\templates\project.
# Запуск: new-project.bat в корне AI Projects (двойной щелчок или с аргументами).
param(
    [string]$Branch,
    [string]$Name,
    [switch]$NoPrompt,   # для агента: ничего не спрашивать, при ошибке выйти с кодом 2
    [string]$ProjectsRoot
)
$ErrorActionPreference = 'Stop'
if ($NoPrompt -and $Branch -notin @('Claude', 'Antigravity', 'Local', 'Codex')) {
    Write-Host "  Ветка '$Branch' не подходит: Claude, Antigravity, Local или Codex." -ForegroundColor Yellow; exit 2
}

$repoRoot = Split-Path $PSScriptRoot -Parent
if (-not $ProjectsRoot) {
    $ProjectsRoot = Split-Path $repoRoot -Parent
    if ((Split-Path $ProjectsRoot -Leaf) -in @('Claude', 'Antigravity', 'Local', 'Codex')) {
        $ProjectsRoot = Split-Path $ProjectsRoot -Parent
    }
}
$root     = $ProjectsRoot
$template = Join-Path $repoRoot 'templates\project'
$overlay  = Join-Path $repoRoot 'templates\project-local'
if (-not (Test-Path -LiteralPath $template -PathType Container)) {
    throw "Project template not found: $template"
}
$utf8     = New-Object System.Text.UTF8Encoding($false)

# Ветка: кто ведёт проект
while ($Branch -notin @('Claude', 'Antigravity', 'Local', 'Codex')) {
    $ans = Read-Host 'Кто ведёт проект? 1 - Claude, 2 - Antigravity, 3 - Local, 4 - Codex [1]'
    switch ($ans) {
        { $_ -in @('', '1', 'Claude', 'claude') }           { $Branch = 'Claude' }
        { $_ -in @('2', 'Antigravity', 'antigravity') }     { $Branch = 'Antigravity' }
        { $_ -in @('3', 'Local', 'local') }                 { $Branch = 'Local' }
        { $_ -in @('4', 'Codex', 'codex') }                 { $Branch = 'Codex' }
        default { Write-Host 'Введите 1, 2, 3 или 4.' -ForegroundColor Yellow }
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

# Для Local — поверх копии шаблона кладём оверлей
if ($Branch -eq 'Local') {
    Copy-Item -Path (Join-Path $overlay '*') -Destination $dest -Recurse -Force
}

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
if ($Branch -eq 'Local') {
    # Сразу связать с Open WebUI, если он запущен; иначе - подсказка на потом
    $sync = Join-Path $root 'Antigravity\local-gpt\scripts\sync_webui_project.py'
    $up = $false
    try { $up = (Invoke-WebRequest 'http://127.0.0.1:3000/health' -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch {}
    if ($up -and (Test-Path $sync)) {
        Write-Host 'Связываю с Open WebUI...'
        & { $ErrorActionPreference = 'Continue'; python -X utf8 $sync $dest }
    } else {
        Write-Host 'Open WebUI не запущен. Запусти его (local-gpt\scripts\start_webui.ps1),'
        Write-Host "потом двойной щелчок по sync-webui.bat в папке проекта."
    }
    Write-Host 'Дальше: в Open WebUI выбрать модель с именем проекта и написать «Собираем контекст».'
    Write-Host 'После ручной правки CLAUDE.md или STATE.md - sync-webui.bat в папке проекта.'
} elseif ($Branch -eq 'Codex') {
    Write-Host 'Дальше: открыть эту папку в Codex и написать «Собираем контекст».'
} else {
    Write-Host 'Дальше: открыть эту папку в Claude Code и написать «Собираем контекст».'
}
