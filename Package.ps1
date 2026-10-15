[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$source = Join-Path $root 'tools\upstream-runtime'
$destination = Join-Path $root 'build\overlay'
$manifestPath = Join-Path $root 'build\build-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Run Build.ps1 successfully first.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($artifact in $manifest.nativeArtifacts) {
    $path = Join-Path $root "build\bin\$($artifact.name)"
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $artifact.sha256) {
        throw "Artifact changed since the successful build: $($artifact.name)"
    }
}
foreach ($file in $manifest.moduleFiles) {
    if ((Get-FileHash -LiteralPath (Join-Path "$root\build\Modules\NativeCoop" $file.path) -Algorithm SHA256).Hash -ne $file.sha256) {
        throw "Module file changed since the successful build: $($file.path)"
    }
}
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Get-ChildItem -LiteralPath $source -File | Where-Object Extension -In '.exe','.dll','.asi','.fx','.h','.txt','.ini' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
}
foreach ($folder in @('CommonRes','languages','Configs')) {
    Copy-Item -LiteralPath (Join-Path $source $folder) -Destination $destination -Recurse -Force
}
New-Item -ItemType Directory -Force -Path "$destination\Modules\NativeCoop" | Out-Null
Copy-Item -Path "$root\build\Modules\NativeCoop\*" -Destination "$destination\Modules\NativeCoop" -Recurse -Force
foreach ($artifact in $manifest.nativeArtifacts) {
    Copy-Item -LiteralPath "$root\build\bin\$($artifact.name)" -Destination $destination -Force
}
Copy-Item -LiteralPath "$source\coop.ini.example" -Destination "$destination\coop.ini.example" -Force
Copy-Item -LiteralPath "$root\WarbandTogether\THIRD_PARTY_LICENSES.md" -Destination $destination -Force
Copy-Item -LiteralPath $manifestPath -Destination $destination -Force
$files = Get-ChildItem -LiteralPath $destination -File -Recurse | ForEach-Object {
    [ordered]@{ path = $_.FullName.Substring($destination.Length + 1); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
}
$files | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$root\build\overlay-manifest.json" -Encoding UTF8
Write-Host "Prepared runtime overlay: $destination"
