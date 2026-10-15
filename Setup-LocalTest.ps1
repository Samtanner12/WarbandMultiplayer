[CmdletBinding()]
param([switch]$PersistentMissionExit)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$overlay = Join-Path $root 'build\overlay'
$base = Join-Path $root 'runtime\LocalTest'
foreach ($name in @('Host','Client1','Client2')) {
    foreach ($file in @('warband_coop.asi','CoopWSEPlugin.dll','mb_warband_wse2_multiclient.exe','mb_warband_wse2_dedicated_campaign.exe')) {
        $path = Join-Path $base "$name\$file"
        if (Test-Path -LiteralPath $path) {
            try { $handle = [IO.File]::Open($path, 'Open', 'ReadWrite', 'None'); $handle.Dispose() }
            catch { throw "Close local test processes before staging; file is in use: $path" }
        }
    }
}
$installation = Get-Content "$root\build\installation.json" -Raw | ConvertFrom-Json
$manifest = Get-Content "$root\build\overlay-manifest.json" -Raw | ConvertFrom-Json
foreach ($file in $manifest) {
    if ((Get-FileHash (Join-Path $overlay $file.path)).Hash -ne $file.sha256) { throw "Overlay hash mismatch: $($file.path)" }
}
$sourceExe = Join-Path $overlay 'mb_warband_wse2.exe'
$bytes = [IO.File]::ReadAllBytes($sourceExe)
if ($bytes[0x21dcb9] -ne 0x75) { throw 'Unexpected pinned mutex instruction.' }
$bytes[0x21dcb9] = 0xeb
foreach ($name in @('Host','Client1','Client2')) {
    $destination = Join-Path $base $name
    New-Item -ItemType Directory -Force $destination | Out-Null
    New-Item -ItemType Directory -Force "$destination\WSE\NativeCoopTest", "$destination\Storage" | Out-Null
    # Preserve saves from the first test configuration (which omitted the
    # trailing storage-path separator) when moving to the native plugin path.
    if (Test-Path "$destination\StorageNativeCoopTest") {
        & robocopy "$destination\StorageNativeCoopTest" "$destination\WSE\NativeCoopTest" /E /XO /XJ /R:1 /W:1 /NFL /NDL /NP /LOG:"$root\logs\local-$name-storage.log"
        if ($LASTEXITCODE -ge 8) { throw "Test save relocation failed for $name." }
    }
    # Copy assets without deleting or changing the user's Steam installation.
    & robocopy $installation.originalGame $destination /E /XJ /XD Modules Logs /R:1 /W:1 /NFL /NDL /NP /LOG:"$root\logs\local-$name-assets.log"
    if ($LASTEXITCODE -ge 8) { throw "Asset copy failed for $name." }
    & robocopy $overlay $destination /E /XJ /R:1 /W:1 /NFL /NDL /NP /LOG:"$root\logs\local-$name-overlay.log"
    if ($LASTEXITCODE -ge 8) { throw "Overlay copy failed for $name." }
    & robocopy "$overlay\Modules\NativeCoop" "$destination\Modules\NativeCoopTest" /E /XJ /R:1 /W:1 /NFL /NDL /NP /LOG:"$root\logs\local-$name-module.log"
    if ($LASTEXITCODE -ge 8) { throw "Test module copy failed for $name." }
    $slot = 0
    $keepConnection = [int]$PersistentMissionExit.IsPresent
    if ($name -eq 'Client1') { $slot = 1 }
    if ($name -eq 'Client2') { $slot = 2 }
    $loopback = 'true'
    if ($slot) { $loopback = 'false' }
    @"
[Coop]
HostIP=127.0.0.1
Port=7340
IpcPort=7342
BattlePort=7341
Module=NativeCoopTest
Password=
[Steam]
SteamHost=0
[Development]
CharacterSlot=$slot
KeepCampaignConnection=$keepConnection
"@ | Set-Content "$destination\coop.ini" -Encoding ASCII
    @"
[General]
iMaxFrameRate=60
bPauseWhenMinimized=false
sStoragePath=$destination\WSE\
[Network]
bLoopbackServer=$loopback
bAutoSelectClientPort=true
iNumPlayersLimit=250
iServerPort=7340
iUdpReceiveBufferSize=1048576
iUdpSendBufferSize=1048576
"@ | Set-Content "$destination\local_config.ini" -Encoding ASCII
    @"
set_max_players 10 10
set_port 7340
set_server_name CoopLocalTest
set_add_to_game_servers_list 0
set_upload_limit 100000000
start
"@ | Set-Content "$destination\Configs\LocalCampaign.txt" -Encoding ASCII
    if ($slot) { [IO.File]::WriteAllBytes("$destination\mb_warband_wse2_multiclient.exe", $bytes) }
}
[ordered]@{ module='NativeCoopTest'; campaignPort=7340; ipcPort=7342; characterSlots=@(1,2); stagedAt=(Get-Date).ToUniversalTime().ToString('o'); twoPlayersVerified=$false; persistentBattlesVerified=$false } |
    ConvertTo-Json | Set-Content "$root\build\local-test.json" -Encoding UTF8
Write-Host 'Isolated local campaign test staged. Battle workers are not started by this setup.'
