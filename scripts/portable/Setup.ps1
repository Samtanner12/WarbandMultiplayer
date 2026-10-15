[CmdletBinding()]
param(
    [string]$GamePath,
    [ValidateSet('Host','Client')][string]$Role,
    [string]$HostIP,
    [ValidateRange(1,65535)][int]$Port=7440,
    [string]$Password=''
)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
if (-not $GamePath) {
    $GamePath=Read-Host 'Warband installation folder (Enter for default Steam path)'
    if (-not $GamePath) {$GamePath='C:\Program Files (x86)\Steam\steamapps\common\MountBlade Warband'}
}
if (-not $Role) {$Role=Read-Host 'Role: Host or Client'}
if ($Role -notin @('Host','Client')) {throw 'Role must be Host or Client.'}
if (-not $HostIP) {
    if ($Role -eq 'Host') {$HostIP='127.0.0.1'}
    else {$HostIP=Read-Host 'Host IPv4 address (public, LAN, or private VPN address)'}
}
$address=$null
if (-not [Net.IPAddress]::TryParse($HostIP,[ref]$address) -or $address.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or $HostIP -in @('0.0.0.0','255.255.255.255')) {throw 'Supply a usable IPv4 address, not a hostname.'}
if ($Password -match '[\r\n\[\];]' -or $Password.Length -gt 47) {throw 'Password must be at most 47 characters without newlines, brackets or semicolons.'}
$game=(Resolve-Path -LiteralPath $GamePath).Path.TrimEnd('\')
foreach($required in @('mb_warband.exe','Data','Textures','CommonRes')) {
    if(-not(Test-Path -LiteralPath (Join-Path $game $required))){throw "Incomplete Warband installation: $required"}
}
$runtimeRoot=Join-Path $root 'runtime'
if($game.StartsWith($runtimeRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Use the original Warband installation, not this package runtime.'}
$files=Get-Content -LiteralPath "$root\payload-manifest.json" -Raw | ConvertFrom-Json
foreach($file in $files){
    $path=Join-Path "$root\payload" $file.path
    if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $file.sha256){throw "Package integrity failed: $($file.path)"}
}
$running=Get-Process -ErrorAction SilentlyContinue | Where-Object {$_.Path -and $_.Path.StartsWith($runtimeRoot+'\',[StringComparison]::OrdinalIgnoreCase)}
if($running){throw 'Close this package host and clients before setup.'}
$folders=if($Role -eq 'Host'){@('Host','Client')}else{@('Client')}
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
foreach($folder in $folders){
    $target=Join-Path $runtimeRoot $folder
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    & robocopy $game $target /E /XJ /XD Modules Logs /R:1 /W:1 /NFL /NDL /NP "/LOG:$root\logs\setup-$folder-game.log" | Out-Null
    if($LASTEXITCODE -ge 8){throw "Game asset copy failed for $folder; inspect logs."}
    & robocopy "$root\payload" $target /E /XJ /R:1 /W:1 /NFL /NDL /NP "/LOG:$root\logs\setup-$folder-mod.log" | Out-Null
    if($LASTEXITCODE -ge 8){throw "Mod copy failed for $folder; inspect logs."}
    $isHost=$folder -eq 'Host'
    $endpoint=if($Role -eq 'Host'){'127.0.0.1'}else{$HostIP}
    $development=if($isHost){'FullHostProbe=1'}else{'FullClientProbe=1'}
    @"
[Coop]
HostIP=$endpoint
Port=$Port
Module=NativeCoopProbe
Password=$Password
[Steam]
SteamHost=0
[Development]
ExpectedPeers=2
PrivateNetworkTest=1
$development
CharacterSlot=0
"@ | Set-Content -LiteralPath "$target\coop.ini" -Encoding ASCII
    @"
[General]
bPauseWhenMinimized=false
iMaxFrameRate=60
sStoragePath=$target\WSE\
[Network]
bAutoSelectClientPort=true
bLoopbackServer=false
iNumPlayersLimit=250
iServerPort=$Port
"@ | Set-Content -LiteralPath "$target\portable_config.ini" -Encoding ASCII
}
[ordered]@{role=$Role; host=$HostIP; port=$Port; setupAt=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath "$root\installation.json" -Encoding UTF8
Write-Host 'Setup complete. Host PC: Start-Host.cmd, then Start-Client.cmd. Friend: Start-Client.cmd.'
Write-Host 'Configure firewall/routing yourself as described in README.md. Setup changes neither.'
