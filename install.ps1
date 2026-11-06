# Lays out shared Claude skills and rules on this Windows machine:
#   skills\shared\*, skills\claude\* -> %USERPROFILE%\.claude\skills\<name>   (directory junctions, no admin needed)
#   skills\vendor\shared\*, skills\vendor\claude\* -> %USERPROFILE%\.claude\skills\<name>   (third-party, vendor-skills.txt)
#   project-skills.txt       -> %USERPROFILE%\.claude\skills\<name>   (junctions to project skills)
#   rules: scripts\compose-rules.py builds rules\CLAUDE.global.md + rules\personal\<profile>.md + ~\.config\ai-rules\personal.md
#          -> %USERPROFILE%\.claude\CLAUDE.md, %USERPROFILE%\.codex\AGENTS.md, %USERPROFILE%\.gemini\GEMINI.md
#   skills\shared\*, skills\vendor\shared\* -> %USERPROFILE%\.gemini\config\skills\<name> (Antigravity IDE; only if %USERPROFILE%\.gemini exists)
#                            -> %USERPROFILE%\.gemini\antigravity-cli\skills\<name> (agy; only if that folder exists)
#   auto-sync: Task Scheduler task AI-Instruments-Sync -> scripts\sync.ps1 (at logon, daily 04:00 MSK)
#              + Claude SessionStart hook (scripts\sync-status.ps1) in %USERPROFILE%\.claude\settings.json
# Existing non-link items are moved to %USERPROFILE%\.claude\_backup-<date>\.
# Run:  powershell -ExecutionPolicy Bypass -File install.ps1 [-RulesProfile artem]   (safe to re-run;
#       the profile is remembered in ~\.config\ai-rules\profile, pass it once per machine)
param([string]$RulesProfile = "")
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$AI   = Split-Path -Parent $Here
$Claude = Join-Path $env:USERPROFILE ".claude"
$Dest = Join-Path $Claude "skills"
$Bak  = Join-Path $Claude ("_backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$Py = Get-Command python.exe -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*WindowsApps*" } | Select-Object -First 1

# One-time moves (renamed project folders, new repo URLs): scripts\migrate.py, safe to re-run.
Write-Host "Migrations:"
if ($Py) { & $Py.Source -X utf8 (Join-Path $Here "scripts\migrate.py") } else { Write-Host "  ! python.exe not found - skipped" }

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
# Rules for Claude, Codex and Antigravity: base + personal, built by scripts\compose-rules.py.
Write-Host "Rules:"
if ($Py) {
  $compose = Join-Path $Here "scripts\compose-rules.py"
  if ($RulesProfile) { & $Py.Source -X utf8 $compose --profile $RulesProfile } else { & $Py.Source -X utf8 $compose }
  if ($LASTEXITCODE -ne 0) { throw "compose-rules.py failed" }
} else { Write-Host "  ! python.exe not found - rules not updated" }
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
  if ($Py) {
    & $Py.Source -X utf8 (Join-Path $Here "scripts\claude-hook.py") (Join-Path $Claude "settings.json") (Join-Path $Here "scripts\sync-status.ps1")
    if ($LASTEXITCODE -ne 0) { throw "claude-hook.py failed" }
  } else { Write-Host "  ! python.exe not found - hook not set" }
}
Write-Host "Done."
