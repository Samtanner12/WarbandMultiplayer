[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$version='WarbandCampaign-PrivateTest-2026-10-14'
$destination=Join-Path $root "build\$version"
if(Test-Path -LiteralPath $destination){throw 'Package folder already exists. Rename it before creating a new snapshot.'}
$source=Join-Path $root 'runtime\NativeMissionProbe\Game'
$upstream=Join-Path $root 'tools\upstream-runtime'
$manifest=Get-Content "$root\build\build-manifest.json" -Raw | ConvertFrom-Json
foreach($artifact in $manifest.nativeArtifacts){
    if((Get-FileHash "$root\build\bin\$($artifact.name)" -Algorithm SHA256).Hash -ne $artifact.sha256){throw 'Native build integrity mismatch.'}
}
$triggers=Get-Content "$root\runtime\NativeMissionProbe\Source\module_simple_triggers.py" -Raw
if($triggers -match 'g_autotest_'){throw 'Automated regression fixture still present.'}
if($triggers -notmatch 'PRIVATE_NETWORK_HOST_PASSWORD'){throw 'Run prepare-portable-network.py first.'}
$payload=Join-Path $destination 'payload'
New-Item -ItemType Directory -Force -Path "$payload\Modules" | Out-Null
foreach($name in @('mb_warband_wse2.exe','fmodex_wse2.dll','lua51.dll','msvcr120.dll','steam_api_wse2.dll','Fxaa3_11.h','postFX_WSE2.fx','postFX.fx','steam_appid.txt','winmm.dll','winmm_sys.dll')){
    Copy-Item -LiteralPath (Join-Path $upstream $name) -Destination $payload
}
Copy-Item -LiteralPath "$source\mb_warband_wse2_multiclient.exe" -Destination $payload
foreach($artifact in $manifest.nativeArtifacts){Copy-Item "$root\build\bin\$($artifact.name)" $payload}
Copy-Item -LiteralPath "$upstream\CommonRes" -Destination $payload -Recurse
Copy-Item -LiteralPath "$source\Modules\NativeCoopProbe" -Destination "$payload\Modules" -Recurse
Get-ChildItem "$root\scripts\portable" -File | Copy-Item -Destination $destination
Copy-Item "$root\WarbandTogether\THIRD_PARTY_LICENSES.md" $destination
Copy-Item "$root\build\build-manifest.json" "$destination\native-build-manifest.json"
New-Item -ItemType Directory -Path "$destination\seed" | Out-Null
$seed=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Mount&Blade Warband WSE2\NativeCoopProbe\Savegames\sg00.sav'
Copy-Item -LiteralPath $seed -Destination "$destination\seed\fresh-world.sav"
$files=Get-ChildItem -LiteralPath $payload -Recurse -File | ForEach-Object {
    [ordered]@{path=$_.FullName.Substring($payload.Length+1);sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash}
}
$files | ConvertTo-Json -Depth 4 | Set-Content "$destination\payload-manifest.json" -Encoding UTF8
$zip=Join-Path $root "build\$version.zip"
Compress-Archive -LiteralPath $destination -DestinationPath $zip -CompressionLevel Optimal
$digest=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
"$digest  $version.zip" | Set-Content "$zip.sha256.txt" -Encoding ASCII
Write-Host "Portable package: $zip"
Write-Host "SHA-256: $digest"
