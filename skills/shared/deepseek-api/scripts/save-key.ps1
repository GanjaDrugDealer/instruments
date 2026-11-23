# Run interactively under the Windows account that will call the API.
$ErrorActionPreference = 'Stop'
if (-not $env:LOCALAPPDATA) {
    throw 'LOCALAPPDATA is unavailable.'
}

$secret = Read-Host 'DeepSeek API key' -AsSecureString
if ($secret.Length -eq 0) {
    throw 'No key entered.'
}

$directory = Join-Path $env:LOCALAPPDATA 'DeepSeek'
$destination = Join-Path $directory 'api-key.xml'
[IO.Directory]::CreateDirectory($directory) | Out-Null
$temporary = Join-Path $directory ([Guid]::NewGuid().ToString() + '.tmp')
try {
    $secret | Export-Clixml -LiteralPath $temporary
    if ([IO.File]::Exists($destination)) {
        [IO.File]::Replace($temporary, $destination, [NullString]::Value)
    } else {
        [IO.File]::Move($temporary, $destination)
    }
    Write-Host 'DeepSeek API key saved for this Windows user.'
} finally {
    $secret.Dispose()
    [IO.File]::Delete($temporary)
}
