[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root 'tools\python27-extract\SourceDir\python.exe'
$compilerSetup = Join-Path $root 'tools\msvc-bootstrap\msvc\setup_x86.bat'
$release = Join-Path $root 'tools\upstream-runtime'
$module = Join-Path $root 'build\Modules\NativeCoop'
$logs = Join-Path $root 'logs'
foreach ($required in @($python, $compilerSetup, "$release\Modules\NativeCoop\module.ini")) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing build dependency: $required" }
}
New-Item -ItemType Directory -Force -Path $module,$logs | Out-Null
$manifestPath = Join-Path $root 'build\build-manifest.json'
if (Test-Path -LiteralPath $manifestPath) { Remove-Item -LiteralPath $manifestPath }
Copy-Item -Path "$release\Modules\NativeCoop\*" -Destination $module -Recurse -Force
$oldExport = $env:WARBAND_EXPORT_DIR
try {
    $env:WARBAND_EXPORT_DIR = $module
    & $python -B "$root\WarbandTogether\wse2work\Native-Coop-master\run_module_build.py" 2>&1 | Tee-Object -FilePath "$logs\module-build.log"
    if ($LASTEXITCODE -ne 0) { throw 'Module compilation failed; see logs\module-build.log.' }
    & "$root\scripts\compile-native.bat" 2>&1 | Tee-Object -FilePath "$logs\native-build.log"
    if ($LASTEXITCODE -ne 0) { throw 'Native compilation failed; see logs\native-build.log.' }
} finally {
    $env:WARBAND_EXPORT_DIR = $oldExport
}
$files = @('warband_coop.asi','CoopWSEPlugin.dll','winmm.dll','dinput8.dll')
$artifacts = foreach ($file in $files) {
    $path = Join-Path $root "build\bin\$file"
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing artifact: $file" }
    $stream = [IO.File]::OpenRead($path)
    $reader = New-Object IO.BinaryReader($stream)
    try {
        if ($reader.ReadUInt16() -ne 0x5a4d) { throw "Invalid PE file: $file" }
        $stream.Position = 0x3c
        $peOffset = $reader.ReadUInt32()
        $stream.Position = $peOffset
        if ($reader.ReadUInt32() -ne 0x4550 -or $reader.ReadUInt16() -ne 0x14c) { throw "Expected x86 PE file: $file" }
    } finally { $reader.Dispose(); $stream.Dispose() }
    [ordered]@{ name = $file; sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash; size = (Get-Item -LiteralPath $path).Length }
}
$revision = & git -C "$root\WarbandTogether" rev-parse HEAD
$moduleFiles = @(Get-ChildItem -LiteralPath $module -File -Recurse | ForEach-Object {
    [ordered]@{ path = $_.FullName.Substring($module.Length + 1); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
})
[ordered]@{
    builtAt = (Get-Date).ToUniversalTime().ToString('o')
    upstreamRevision = $revision
    runtimePackage = 'WarbandTogether-v0.0.82'
    wse2Revision = 1145
    moduleBuildSteps = 29
    nativeArtifacts = @($artifacts)
    moduleFiles = $moduleFiles
    gameplayVerified = $false
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Host "Build succeeded. Artifacts: $root\build"
