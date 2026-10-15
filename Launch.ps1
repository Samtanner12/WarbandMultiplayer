[CmdletBinding()]
param(
    [ValidateSet('Host','Client','Servers')][string]$Mode = 'Host',
    [ValidateRange(1,4)][int]$BattleServers = 2,
    [ValidateRange(0,9)][int]$SaveSlot = 0
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$runtime = Join-Path $root 'runtime\Game'
if (-not (Test-Path -LiteralPath "$root\build\installation.json")) { throw 'Warband is not staged. Run Setup.ps1 -GamePath <installation folder> first.' }
foreach ($required in @('mb_warband_wse2.exe','mb_warband_wse2_dedicated_campaign.exe','mb_warband_wse2_dedicated.exe','CoopWSEPlugin.dll','warband_coop.asi','winmm.dll','winmm_sys.dll','dinput8.dll','coop.ini','Modules\NativeCoop\module.ini')) {
    if (-not (Test-Path -LiteralPath (Join-Path $runtime $required))) { throw "Missing runtime file: $required" }
}
$started = @()
$oldSlot = $env:COOP_BATTLE_SLOT
try {
    if ($Mode -ne 'Client') {
        $occupied = @(7240,7242) + @(0..($BattleServers-1) | ForEach-Object { 7241 + 2 * $_ })
        $listeners = Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Where-Object LocalPort -In $occupied
        if ($listeners) { throw 'A required campaign or battle UDP port is already in use. Close the existing host before starting another.' }
        $started += Start-Process -FilePath "$runtime\mb_warband_wse2_dedicated_campaign.exe" -WorkingDirectory $runtime -ArgumentList @('--config-path','server_config.ini','-r','Configs\CampaignCoop.txt','--module','NativeCoop','--load-game','--save-no',"$SaveSlot") -WindowStyle Hidden -PassThru
        Start-Sleep -Seconds 3
        for ($slot = 0; $slot -lt $BattleServers; $slot++) {
            $env:COOP_BATTLE_SLOT = "$slot"
            $started += Start-Process -FilePath "$runtime\mb_warband_wse2_dedicated.exe" -WorkingDirectory $runtime -ArgumentList @('-r',"Configs\BattleServer_$slot.txt",'--module','NativeCoop') -WindowStyle Hidden -PassThru
        }
        Start-Sleep -Seconds 3
        foreach ($process in $started) {
            $process.Refresh()
            if ($process.HasExited) { throw "Server startup failed (PID $($process.Id), exit $($process.ExitCode)); inspect runtime\Game logs." }
        }
        $started | ForEach-Object { [ordered]@{ id = $_.Id; startedAt = $_.StartTime.ToUniversalTime().ToString('o'); executable = $_.Path } } |
            ConvertTo-Json -Depth 3 | Set-Content -LiteralPath "$root\build\running-servers.json" -Encoding UTF8
    }
    if ($Mode -ne 'Servers') {
        Start-Process -FilePath "$runtime\mb_warband_wse2.exe" -WorkingDirectory $runtime -ArgumentList @('--module','NativeCoop','--no-intro') | Out-Null
    }
} catch {
    foreach ($process in $started) { if (-not $process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue } }
    throw
} finally { $env:COOP_BATTLE_SLOT = $oldSlot }
