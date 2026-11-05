# Lays out shared Claude skills and rules on this Windows machine:
#   skills\shared\*, skills\claude\* -> %USERPROFILE%\.claude\skills\<name>   (directory junctions, no admin needed)
#   skills\vendor\shared\*, skills\vendor\claude\* -> %USERPROFILE%\.claude\skills\<name>   (third-party, vendor-skills.txt)
#   project-skills.txt       -> %USERPROFILE%\.claude\skills\<name>   (junctions to project skills)
#   rules\CLAUDE.global.md   -> %USERPROFILE%\.claude\CLAUDE.md       (copy: file links need admin; auto-sync re-runs install)
#                            -> %USERPROFILE%\.codex\AGENTS.md, %USERPROFILE%\.gemini\GEMINI.md (same file for all agents)
#   skills\shared\*, skills\vendor\shared\* -> %USERPROFILE%\.gemini\config\skills\<name> (Antigravity IDE; only if %USERPROFILE%\.gemini exists)
#                            -> %USERPROFILE%\.gemini\antigravity-cli\skills\<name> (agy; only if that folder exists)
#   auto-sync: Task Scheduler task AI-Instruments-Sync -> scripts\sync.ps1 (at logon, daily 04:00 MSK)
#              + Claude SessionStart hook (scripts\sync-status.ps1) in %USERPROFILE%\.claude\settings.json
# Existing non-link items are moved to %USERPROFILE%\.claude\_backup-<date>\.
# Run:  powershell -ExecutionPolicy Bypass -File install.ps1   (safe to re-run)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$AI   = Split-Path -Parent $Here
$Claude = Join-Path $env:USERPROFILE ".claude"
$Dest = Join-Path $Claude "skills"
$Bak  = Join-Path $Claude ("_backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

function Link-Dir($src, $dst) {
  if (-not (Test-Path $src)) { Write-Host "  missing $src - skip"; return }
  if (Test-Path $dst) {
    $item = Get-Item $dst -Force
    if ($item.LinkType) { $item.Delete() }
    else { New-Item -ItemType Directory -Force -Path $Bak | Out-Null; Move-Item $dst $Bak; Write-Host "  old $(Split-Path -Leaf $dst) -> $Bak" }
  }
  New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
  Write-Host "  $(Split-Path -Leaf $dst) -> $src"
}

Write-Host "Shared skills:"
Get-ChildItem (Join-Path $Here "skills\shared") -Directory | ForEach-Object { Link-Dir $_.FullName (Join-Path $Dest $_.Name) }
Write-Host "Claude-only skills:"
Get-ChildItem (Join-Path $Here "skills\claude") -Directory | ForEach-Object { Link-Dir $_.FullName (Join-Path $Dest $_.Name) }
Write-Host "Third-party skills (vendor-skills.txt):"
foreach ($sub in "shared", "claude") {
  $vd = Join-Path $Here "skills\vendor\$sub"
  if (Test-Path $vd) { Get-ChildItem $vd -Directory | ForEach-Object { Link-Dir $_.FullName (Join-Path $Dest $_.Name) } }
}
Write-Host "Project skills:"
Get-Content -Encoding UTF8 (Join-Path $Here "project-skills.txt") | Where-Object { $_ -and -not $_.TrimStart().StartsWith("#") } | ForEach-Object {
  $src = Join-Path $AI ($_.Trim() -replace "/", "\")
  Link-Dir $src (Join-Path $Dest (Split-Path -Leaf $src))
}
Write-Host "Rules:"
$rules = Join-Path $Claude "CLAUDE.md"
if ((Test-Path $rules) -and -not (Get-Item $rules -Force).LinkType) {
  New-Item -ItemType Directory -Force -Path $Bak | Out-Null; Copy-Item $rules $Bak
}
Copy-Item (Join-Path $Here "rules\CLAUDE.global.md") $rules -Force
Write-Host "  CLAUDE.md copied (re-run install.ps1 after git pull)"
$Gemini = Join-Path $env:USERPROFILE ".gemini"
if (Test-Path $Gemini) {
  Write-Host "Antigravity (shared skills):"
  $GDest = Join-Path $Gemini "config\skills"
  New-Item -ItemType Directory -Force -Path $GDest | Out-Null
  Get-ChildItem (Join-Path $Here "skills\shared") -Directory | ForEach-Object { Link-Dir $_.FullName (Join-Path $GDest $_.Name) }
  $vd = Join-Path $Here "skills\vendor\shared"
  if (Test-Path $vd) { Get-ChildItem $vd -Directory | ForEach-Object { Link-Dir $_.FullName (Join-Path $GDest $_.Name) } }
}
$AgyCli = Join-Path $Gemini "antigravity-cli"
if (Test-Path $AgyCli) {
  Write-Host "Antigravity CLI agy (shared skills):"
  $CDest = Join-Path $AgyCli "skills"
  New-Item -ItemType Directory -Force -Path $CDest | Out-Null
  Get-ChildItem (Join-Path $Here "skills\shared") -Directory | ForEach-Object { Link-Dir $_.FullName (Join-Path $CDest $_.Name) }
  $vd = Join-Path $Here "skills\vendor\shared"
  if (Test-Path $vd) { Get-ChildItem $vd -Directory | ForEach-Object { Link-Dir $_.FullName (Join-Path $CDest $_.Name) } }
}
# Codex: user skills in ~/.agents/skills (directory junctions).
$CodexDest = Join-Path $env:USERPROFILE ".agents\skills"
New-Item -ItemType Directory -Force -Path $CodexDest | Out-Null
# Keep Codex backups separate from Claude backups, including same-name skills.
$Bak = Join-Path $env:USERPROFILE (".codex\_backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
Write-Host "Codex skills:"
foreach ($sub in "shared", "vendor\shared", "vendor\claude", "codex") {
  $source = Join-Path $Here "skills\$sub"
  if (Test-Path $source) { Get-ChildItem $source -Directory | ForEach-Object { Link-Dir $_.FullName (Join-Path $CodexDest $_.Name) } }
}
Get-Content -Encoding UTF8 (Join-Path $Here "project-skills.txt") | Where-Object { $_ -and -not $_.TrimStart().StartsWith("#") } | ForEach-Object {
  $src = Join-Path $AI ($_.Trim() -replace "/", "\")
  Link-Dir $src (Join-Path $CodexDest (Split-Path -Leaf $src))
}
$CodexRoot = Join-Path $env:USERPROFILE ".codex"
New-Item -ItemType Directory -Force -Path $CodexRoot | Out-Null
$CodexRules = Join-Path $CodexRoot "AGENTS.md"
if (Test-Path $CodexRules) {
  New-Item -ItemType Directory -Force -Path $Bak | Out-Null
  Copy-Item -LiteralPath $CodexRules -Destination $Bak
}
Copy-Item -LiteralPath (Join-Path $Here "rules\CLAUDE.global.md") -Destination $CodexRules -Force
Write-Host "  Codex AGENTS.md copied (same rules file as Claude)"
# Antigravity: global rules in ~/.gemini/GEMINI.md (same rules file).
if (Test-Path $Gemini) {
  $GRules = Join-Path $Gemini "GEMINI.md"
  if (Test-Path $GRules) {
    $GBak = Join-Path $Gemini ("_backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Force -Path $GBak | Out-Null
    Copy-Item -LiteralPath $GRules -Destination $GBak
  }
  Copy-Item -LiteralPath (Join-Path $Here "rules\CLAUDE.global.md") -Destination $GRules -Force
  Write-Host "  Antigravity GEMINI.md copied (same rules file as Claude)"
}
# Auto-sync (scripts\sync.ps1). Skipped when install.ps1 is run by the sync itself.
if (-not $env:INSTRUMENTS_SYNC) {
  Write-Host "Auto-sync (Task Scheduler: at logon, daily 04:00 MSK):"
  $TaskName = "AI-Instruments-Sync"
  $ps = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
  $syncArgs = "--headless `"$ps`" -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Here\scripts\sync.ps1`""
  $action = New-ScheduledTaskAction -Execute "conhost.exe" -Argument $syncArgs
  $atLogon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
  $nightly = New-ScheduledTaskTrigger -Daily -At "04:00"
  # Fixed +03:00 offset: 04:00 Moscow time whatever the PC time zone is.
  $nightly.StartBoundary = (Get-Date).AddDays(1).ToString("yyyy-MM-dd") + "T04:00:00+03:00"
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
  $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $atLogon, $nightly -Settings $settings `
    -Principal $principal -Force | Out-Null
  Start-ScheduledTask -TaskName $TaskName
  Write-Host "  task $TaskName registered and started"
  Write-Host "Claude SessionStart hook:"
  $py = Get-Command python.exe -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*WindowsApps*" } | Select-Object -First 1
  if ($py) {
    & $py.Source -X utf8 (Join-Path $Here "scripts\claude-hook.py") (Join-Path $Claude "settings.json") (Join-Path $Here "scripts\sync-status.ps1")
    if ($LASTEXITCODE -ne 0) { throw "claude-hook.py failed" }
  } else { Write-Host "  ! python.exe not found - hook not set" }
}
Write-Host "Done."
