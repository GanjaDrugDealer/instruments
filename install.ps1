# Lays out shared Claude skills and rules on this Windows machine:
#   skills\shared\*, skills\claude\* -> %USERPROFILE%\.claude\skills\<name>   (directory junctions, no admin needed)
#   skills\vendor\shared\*, skills\vendor\claude\* -> %USERPROFILE%\.claude\skills\<name>   (third-party, vendor-skills.txt)
#   project-skills.txt       -> %USERPROFILE%\.claude\skills\<name>   (junctions to project skills)
#   rules\CLAUDE.global.md   -> %USERPROFILE%\.claude\CLAUDE.md       (copy: file links need admin; re-run after git pull)
#   skills\shared\*, skills\vendor\shared\* -> %USERPROFILE%\.gemini\config\skills\<name> (Antigravity IDE; only if %USERPROFILE%\.gemini exists)
#                            -> %USERPROFILE%\.gemini\antigravity-cli\skills\<name> (agy; only if that folder exists)
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
Write-Host "Done."
