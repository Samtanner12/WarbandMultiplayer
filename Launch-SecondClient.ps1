[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot 'runtime\Game'
$pinned = Join-Path $PSScriptRoot 'tools\upstream-runtime\mb_warband_wse2.exe'
$source = Join-Path $runtime 'mb_warband_wse2.exe'
$destination = Join-Path $runtime 'mb_warband_wse2_multiclient.exe'
if (-not (Test-Path -LiteralPath $source)) { throw 'Stage the private runtime with Setup.ps1 first.' }
if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $pinned).Hash) {
    throw 'The staged client differs from the pinned release. Refusing to patch an unknown executable.'
}
$bytes = [IO.File]::ReadAllBytes($source)
# Upstream's rev-1145 development-only mutex check. This affects opening
# another window, not serial activation, network authentication or player IDs.
$offset = 0x21dcb9
if ($bytes[$offset] -ne 0x75) { throw 'Unexpected mutex instruction in pinned client.' }
$bytes[$offset] = 0xeb
if (Test-Path -LiteralPath $destination) {
    $existing = [IO.File]::ReadAllBytes($destination)
    if ($existing.Length -ne $bytes.Length) { throw 'Existing test executable has an unexpected size.' }
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        if ($existing[$i] -ne $bytes[$i]) { throw 'Existing test executable differs from the expected mutex-only patch.' }
    }
} else {
    [IO.File]::WriteAllBytes($destination, $bytes)
}
Write-Host 'Opening an additional client at its main menu.'
Write-Host 'For independent test characters, use Setup-LocalTest.ps1 and Launch-LocalTest.ps1 instead of connecting both clients to your regular campaign.'
Start-Process -FilePath $destination -WorkingDirectory $runtime -ArgumentList @('--module','NativeCoop','--no-intro') | Out-Null
