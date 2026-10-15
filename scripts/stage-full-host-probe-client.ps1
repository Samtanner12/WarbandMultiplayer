param([ValidateSet('Client','Client2')][string]$Directory = 'Client')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$source = Join-Path $root 'runtime\NativeMissionProbe\Game'
$client = Join-Path $root "runtime\NativeMissionProbe\$Directory"
if (Test-Path -LiteralPath (Join-Path $client 'rgl_log.txt')) {
    throw 'An existing probe client must be inspected before restaging.'
}
New-Item -ItemType Directory -Force -Path $client | Out-Null
Get-ChildItem -LiteralPath $source -File | Where-Object {
    $_.Extension -in @('.exe','.dll','.asi','.fx','.fxo','.pp','.h','.bmp','.txt','.ini','.lua') -and
    $_.Name -notmatch 'log'
} | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $client $_.Name) }
foreach ($name in @('Modules','CommonRes','Data','Languages','Music','Sounds','Textures')) {
    $target = Join-Path $source $name
    $link = Join-Path $client $name
    if (-not (Test-Path -LiteralPath $link)) {
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    }
}
Set-Content -LiteralPath (Join-Path $client 'coop.ini') -Encoding ascii -Value @"
[Coop]
HostIP=127.0.0.1
Port=7440
Module=NativeCoopProbe
[Steam]
SteamHost=0
"@
Set-Content -LiteralPath (Join-Path $client 'client_config.ini') -Encoding ascii -Value @"
[General]
iMaxFrameRate=60
bPauseWhenMinimized=false
sStoragePath=$client\WSE\
[Network]
bLoopbackServer=false
bAutoSelectClientPort=true
iNumPlayersLimit=250
iServerPort=7440
"@
Write-Output 'Isolated client staged; host and client logs are separate.'
