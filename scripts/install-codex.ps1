# Install repository skills for Codex only, without changing global agent rules.
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$skillDestination = Join-Path $env:USERPROFILE '.agents\skills'
$backupRoot = Join-Path $env:USERPROFILE ('.codex\_backup-ai-instruments-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $skillDestination | Out-Null
foreach ($group in @('shared', 'vendor\shared', 'vendor\claude', 'codex')) {
    $sourceRoot = Join-Path $repoRoot "skills\$group"
    if (-not (Test-Path -LiteralPath $sourceRoot)) { continue }
    foreach ($skill in Get-ChildItem -LiteralPath $sourceRoot -Directory) {
        $destination = Join-Path $skillDestination $skill.Name
        $existing = Get-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
        if ($existing) {
            if ($existing.LinkType -and ($existing.Target -contains $skill.FullName)) { continue }
            New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
            Move-Item -LiteralPath $destination -Destination (Join-Path $backupRoot $skill.Name)
        }
        New-Item -ItemType Junction -Path $destination -Target $skill.FullName | Out-Null
        Write-Host "Connected: $($skill.Name)"
    }
}
Write-Host 'Codex skills installed. Global agent rules were preserved.'
