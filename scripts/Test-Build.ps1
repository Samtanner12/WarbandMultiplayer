$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$checks = New-Object 'System.Collections.Generic.List[string]'
Get-ChildItem -LiteralPath $root -Filter '*.ps1' -File | ForEach-Object {
    $tokens = $null; $parseErrors = $null
    [Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors) { throw ($parseErrors | Out-String) }
}
$checks.Add('PowerShell entry points parse successfully.')
$release = Get-Content -LiteralPath "$root\downloads\upstream-release.json" -Raw | ConvertFrom-Json
$asset = $release.assets | Where-Object name -EQ 'WarbandTogether-v0.0.82.zip'
$expectedHash = $asset.digest -replace '^sha256:', ''
if ((Get-FileHash -LiteralPath "$root\downloads\WarbandTogether-v0.0.82.zip" -Algorithm SHA256).Hash -ne $expectedHash) { throw 'Upstream archive hash does not match GitHub release metadata.' }
$checks.Add('Pinned runtime archive matches the GitHub SHA-256 digest.')
$client = [IO.File]::ReadAllBytes("$root\tools\upstream-runtime\mb_warband_wse2.exe")
foreach ($patch in @(
    @{ offset = 0x1ae; bytes = @(0x00,0x81) },
    @{ offset = 0x26c; bytes = @(0x20,0x00,0x00,0xe0) },
    @{ offset = 0xd3d86; bytes = @(0x90,0x90,0x90,0x90,0x90,0x90,0x90) },
    @{ offset = 0x14868d; bytes = @(0xe9,0xf7,0xeb,0x26,0x00,0x90,0x90) },
    @{ offset = 0x148803; bytes = @(0xe9,0xaa,0xea,0x26,0x00) }
)) {
    for ($index = 0; $index -lt $patch.bytes.Count; $index++) {
        if ($client[$patch.offset + $index] -ne $patch.bytes[$index]) { throw "Unexpected runtime patch bytes at $($patch.offset)." }
    }
}
$checks.Add('Pinned client contains the documented campaign connection and LAN patches.')
$manifest = Get-Content -LiteralPath "$root\build\build-manifest.json" -Raw | ConvertFrom-Json
if ($manifest.moduleBuildSteps -ne 29 -or -not $manifest.moduleFiles) { throw 'Incomplete build manifest.' }
foreach ($file in $manifest.moduleFiles) {
    if ((Get-FileHash -LiteralPath (Join-Path "$root\build\Modules\NativeCoop" $file.path) -Algorithm SHA256).Hash -ne $file.sha256) { throw "Module hash mismatch: $($file.path)" }
}
foreach ($file in $manifest.nativeArtifacts) {
    if ((Get-FileHash -LiteralPath (Join-Path "$root\build\bin" $file.name) -Algorithm SHA256).Hash -ne $file.sha256) { throw "Native hash mismatch: $($file.name)" }
}
$checks.Add('Compiled module and native artifacts match their successful-build hashes.')
$headers = @{
    'scripts.txt' = 'scriptsfile version 1'
    'troops.txt' = 'troopsfile version 2'
    'mission_templates.txt' = 'missionsfile version 1'
    'item_kinds1.txt' = 'itemsfile version 3'
}
foreach ($file in $headers.Keys) {
    $lines = Get-Content -LiteralPath "$root\build\Modules\NativeCoop\$file" -TotalCount 2
    if ($lines[0].Trim() -ne $headers[$file] -or [int]$lines[1].Trim() -lt 1) { throw "Invalid compiled module header: $file" }
}
$checks.Add('Core compiled module files have valid headers and nonempty object tables.')
$probe = Join-Path $root 'build\loader-probe'
New-Item -ItemType Directory -Force -Path $probe | Out-Null
if (Get-ChildItem -LiteralPath $probe -Filter '*.asi') { throw 'The loader probe directory must contain no ASI plugins.' }
$oldLocation = Get-Location
try {
    Set-Location -LiteralPath $probe
    & "$root\tools\python27-extract\SourceDir\python.exe" -c 'import ctypes,sys; dll=ctypes.WinDLL(sys.argv[1]); assert dll.DirectInput8Create; print("x86 loader LoadLibrary/export probe passed")' "$root\build\bin\dinput8.dll"
    if ($LASTEXITCODE -ne 0) { throw 'Compiled x86 ASI loader failed its isolated loading probe.' }
} finally { Set-Location $oldLocation }
$checks.Add('Compiled x86 ASI loader loads successfully and exports DirectInput8Create.')
$seedIds = @(Get-Content -LiteralPath "$root\WarbandTogether\wse2work\Native-Coop-master\campaign_global_ids.txt")
$moduleIds = @(Get-Content -LiteralPath "$root\build\Modules\NativeCoop\variables.txt")
if (($seedIds -join "`n") -cne ($moduleIds -join "`n")) { throw 'Compiled campaign global IDs differ from the saved positional registry.' }
$checks.Add('Campaign global IDs match the persistent append-only registry.')
& "$root\tools\python27-extract\SourceDir\python.exe" -B "$root\scripts\test-campaign-realms.py"
if ($LASTEXITCODE -ne 0) { throw 'Campaign realm authority tests failed.' }
$checks.Add('Eight campaign authority checks pass, including mutual peace, paired recovery, and active-battle protection.')
& "$root\tools\python27-extract\SourceDir\python.exe" -B "$root\scripts\test-character-health.py"
if ($LASTEXITCODE -ne 0) { throw 'Character health persistence regression failed.' }
$checks.Add('Nine character health checks pass, including persistence, shared native healing refresh, and battle guards.')
& "$root\scripts\test-campaign-clock.bat"
if ($LASTEXITCODE -ne 0) { throw 'Campaign clock checks failed.' }
$checks.Add('Native clock ordering, bounds, prediction, stall, and timer wrap checks pass.')
[ordered]@{ testedAt = (Get-Date).ToUniversalTime().ToString('o'); passed = @($checks.ToArray()); gameplayVerified = $false } |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$root\build\verification.json" -Encoding UTF8
$checks | ForEach-Object { Write-Host "PASS: $_" }
Write-Host 'These checks verify build integrity; separate characters and persistent multiplayer battles still require gameplay validation.'
