# Claude Code SessionStart hook (set by install.ps1): silent when _instruments is in sync,
# otherwise one line for the agent. If the last check is older than 15 min, starts the
# sync task in the background. Fresh skills reach the next session: the skill list is
# loaded at session start.
$State = Join-Path $env:LOCALAPPDATA "instruments-sync"
$StatusFile = Join-Path $State "status"
$now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$state = "none"; $ts = [long]0; $msg = ""
if (Test-Path $StatusFile) {
  $p = ([IO.File]::ReadAllText($StatusFile)).Split("`t", 3)
  $state = $p[0]; $ts = [long]$p[1]; $msg = $p[2]
}
if ($now - $ts -gt 900) {
  try { Start-ScheduledTask -TaskName "AI-Instruments-Sync" -ErrorAction Stop }
  catch {
    $sync = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "sync.ps1"
    Start-Process -WindowStyle Hidden -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$sync`""
  }
}

function Msk($unix) {
  $utc = [DateTimeOffset]::FromUnixTimeSeconds($unix).UtcDateTime
  [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId($utc, "Russian Standard Time").ToString("dd.MM HH:mm") + " MSK"
}
$tell = "Tell the user in one short line, in Russian."
if ($state -eq "none") {
  "_instruments auto-sync has never run on this machine; started it now. $tell"
} elseif ($now - $ts -gt 172800) {
  "_instruments: last update check was $(Msk $ts), more than two days ago - the scheduled task seems broken. $tell"
} elseif ($state -ne "ok") {
  "_instruments sync ${state}: $msg (checked $(Msk $ts)). $tell"
}
exit 0
