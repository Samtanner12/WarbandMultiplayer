[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$GamePath)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$game = (Resolve-Path -LiteralPath $GamePath).Path.TrimEnd('\')
$runtime = Join-Path $root 'runtime\Game'
if (-not (Test-Path -LiteralPath "$game\mb_warband.exe")) { throw 'GamePath must point to the Warband installation containing mb_warband.exe.' }
foreach ($folder in @('CommonRes','Data','Textures')) {
    if (-not (Test-Path -LiteralPath "$game\$folder")) { throw "Incomplete Warband installation: missing $folder." }
}
if ($game.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw 'Supply the original Warband installation, outside this project.' }
if (-not (Test-Path -LiteralPath "$root\build\overlay-manifest.json")) { throw 'Run Build.ps1 and Package.ps1 first.' }
$overlay = Join-Path $root 'build\overlay'
$manifest = Get-Content -LiteralPath "$root\build\overlay-manifest.json" -Raw | ConvertFrom-Json
foreach ($file in $manifest) {
    if ((Get-FileHash -LiteralPath (Join-Path $overlay $file.path) -Algorithm SHA256).Hash -ne $file.sha256) {
        throw "Runtime overlay integrity check failed: $($file.path)"
    }
}
$running = Get-Process | Where-Object {
    $_.Path -and $_.Path.StartsWith($runtime + '\', [StringComparison]::OrdinalIgnoreCase)
}
if ($running) { throw 'Close the project game and servers before updating their files.' }
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
# Read the original installation; copy only into this project. No /MIR or deletion.
& robocopy $game $runtime /E /XJ /XD Modules Logs /R:1 /W:1 /NFL /NDL /NP /LOG:"$root\logs\stage-game.log"
if ($LASTEXITCODE -ge 8) { throw 'Game asset copy failed; see logs\stage-game.log.' }
& robocopy $overlay $runtime /E /XJ /R:1 /W:1 /NFL /NDL /NP /LOG:"$root\logs\stage-overlay.log"
if ($LASTEXITCODE -ge 8) { throw 'Mod copy failed; see logs\stage-overlay.log.' }
if (-not (Test-Path -LiteralPath "$runtime\coop.ini")) {
    Copy-Item -LiteralPath "$runtime\coop.ini.example" -Destination "$runtime\coop.ini"
}
[ordered]@{ originalGame = $game; runtime = $runtime; stagedAt = (Get-Date).ToUniversalTime().ToString('o'); gameplayVerified = $false } |
    ConvertTo-Json | Set-Content -LiteralPath "$root\build\installation.json" -Encoding UTF8
Write-Host 'Setup complete. Use Launch-Host.cmd or Launch-Client.cmd.'
