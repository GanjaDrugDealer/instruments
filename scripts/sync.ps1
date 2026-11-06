# Auto-sync of _instruments on Windows: fast-forward from origin/main, then install.ps1
# if new commits arrived. Started by:
#   - Task Scheduler task "AI-Instruments-Sync" (registered by install.ps1): at logon and
#     daily at 04:00 MSK (if the PC was off, at the next start);
#   - the Claude SessionStart hook (sync-status.ps1) when the last check is older than 15 min.
# Never forces anything: on local edits, unpushed commits or another branch it only
# writes the reason to the status file.
# Status: %LOCALAPPDATA%\instruments-sync\status  (ok|warn|fail<TAB>unix-time<TAB>text)
# Log:    %LOCALAPPDATA%\instruments-sync\sync.log (MSK time)
$ErrorActionPreference = "Continue"
# Python runs with -X utf8: read its output as UTF-8, not the console code page (CP866).
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:GIT_TERMINAL_PROMPT = "0"
$env:GCM_INTERACTIVE = "never"
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$State = Join-Path $env:LOCALAPPDATA "instruments-sync"
New-Item -ItemType Directory -Force -Path $State | Out-Null
$StatusFile = Join-Path $State "status"
$Log = Join-Path $State "sync.log"

# One run at a time: an exclusive handle is released automatically when the process exits.
try { $LockStream = [System.IO.File]::Open((Join-Path $State "lock"), "OpenOrCreate", "ReadWrite", "None") } catch { exit 0 }
if ((Test-Path $Log) -and (Get-Item $Log).Length -gt 1MB) { Move-Item $Log "$Log.old" -Force }

function Get-Msk {
  [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, "Russian Standard Time").ToString("yyyy-MM-dd HH:mm:ss")
}
function Write-Log($text) {
  [IO.File]::AppendAllText($Log, "$(Get-Msk) MSK $text`r`n", (New-Object Text.UTF8Encoding $false))
}
function Finish($state, $text) {
  # One-time moves (scripts\migrate.py) on every run: a folder that was busy last time is
  # renamed next time; new moves arrive with the pulled commits.
  $mig = Join-Path $Repo "scripts\migrate.py"
  $py = Get-Command python.exe -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*WindowsApps*" } | Select-Object -First 1
  if ($py -and (Test-Path $mig)) {
    $out = @(& $py.Source -X utf8 $mig 2>&1 | ForEach-Object { "$_" })
    $code = $LASTEXITCODE
    if ($out.Count -gt 0) { Write-Log ("migrate: " + ($out -join " |")) }
    if ($code -eq 2 -and $state -eq "ok") {
      $state = "warn"
      $text = "$text; migration failed: " + ((@($out | Where-Object { $_ -like "*!*" }) | ForEach-Object { $_.Trim().TrimStart("!").Trim() }) -join "; ")
    }
  }
  # Rules on every run too: picks up edits of ~\.config\ai-rules\personal.md without a new commit.
  $compose = Join-Path $Repo "scripts\compose-rules.py"
  if ($py -and (Test-Path $compose)) {
    $out = @(& $py.Source -X utf8 $compose 2>&1 | ForEach-Object { "$_" })
    if (@($out | Where-Object { $_ -like "*!*" -or $_ -like "*rules ->*" }).Count -gt 0) { Write-Log ("rules: " + ($out -join " |")) }
  }
  $unix = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  [IO.File]::WriteAllText($StatusFile, "$state`t$unix`t$text", (New-Object Text.UTF8Encoding $false))
  Write-Log "${state}: $text"
  $LockStream.Close()
  exit 0
}
function Invoke-Git {
  $out = & git.exe -C $Repo @args 2>&1 | ForEach-Object { "$_" }
  $script:GitCode = $LASTEXITCODE
  return $out
}
function Last-Line($lines) { (@($lines) | Where-Object { $_ } | Select-Object -Last 1) }

if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { Finish "fail" "git.exe not found in PATH" }
$branch = "$(Invoke-Git symbolic-ref --quiet --short HEAD)"
if ($GitCode -ne 0) { Finish "fail" "_instruments has a detached HEAD - sync paused" }
if ($branch -ne "main") { Finish "fail" "_instruments is on branch '$branch', not main - sync paused" }
$out = Invoke-Git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30 fetch --quiet origin
if ($GitCode -ne 0) { Finish "fail" "cannot reach GitHub: $(Last-Line $out)" }

$dirty = @(Invoke-Git status --porcelain | Where-Object { $_ })
$dirtyList = (@($dirty | Select-Object -First 3 | ForEach-Object { $_.Substring(3) })) -join ", "
$ahead = [int]"$(Invoke-Git rev-list --count origin/main..HEAD)"
$behind = [int]"$(Invoke-Git rev-list --count HEAD..origin/main)"

if ($behind -eq 0) {
  if ($ahead -gt 0) { Finish "warn" "$ahead local commit(s) not pushed to GitHub" }
  if ($dirty.Count -gt 0) { Finish "warn" "uncommitted changes: $dirtyList" }
  Finish "ok" "up to date ($(Invoke-Git rev-parse --short HEAD))"
}
if ($ahead -gt 0) { Finish "fail" "diverged: $ahead local and $behind new GitHub commit(s) - needs a manual merge" }
if ($dirty.Count -gt 0) { Finish "fail" "$behind new commit(s) on GitHub, but uncommitted changes here: $dirtyList" }

$old = "$(Invoke-Git rev-parse --short HEAD)"
$out = Invoke-Git merge --ff-only --quiet origin/main
if ($GitCode -ne 0) { Finish "fail" "fast-forward failed: $(Last-Line $out)" }
$new = "$(Invoke-Git rev-parse --short HEAD)"
Write-Log "pulled $old..$new"
$env:INSTRUMENTS_SYNC = "1"
$ps = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
$out = & $ps -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $Repo "install.ps1") 2>&1 | Out-String
$code = $LASTEXITCODE
Write-Log $out.TrimEnd()
if ($code -ne 0) { Finish "fail" "install.ps1 failed, see $Log" }
Finish "ok" "updated $old -> $new ($behind commit(s))"
