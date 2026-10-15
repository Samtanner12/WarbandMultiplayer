[CmdletBinding()]
param([ValidateSet('Host','Client1','Client2')][string]$Mode = 'Host', [ValidateRange(0,9)][int]$SaveSlot = 1)
$ErrorActionPreference = 'Stop'
$base = Join-Path $PSScriptRoot "runtime\LocalTest\$Mode"
if (-not (Test-Path "$base\Modules\NativeCoopTest\module.ini")) { throw 'Run Setup-LocalTest.ps1 first.' }
if ($Mode -eq 'Host') {
    if (Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Where-Object LocalPort -In @(7340,7342)) { throw 'Local test ports are already occupied.' }
    $executable = "$base\mb_warband_wse2_dedicated_campaign.exe"
    $process = Start-Process $executable -WorkingDirectory $base -ArgumentList @('--config-path','local_config.ini','-r','Configs\LocalCampaign.txt','--module','NativeCoopTest','--load-game','--save-no',"$SaveSlot") -WindowStyle Hidden -PassThru
} else {
    $executable = "$base\mb_warband_wse2_multiclient.exe"
    $process = Start-Process $executable -WorkingDirectory $base -ArgumentList @('--config-path','local_config.ini','--module','NativeCoopTest','--no-intro') -PassThru
}
[ordered]@{ id=$process.Id; startedAt=$process.StartTime.ToUniversalTime().ToString('o'); executable=$executable } |
    ConvertTo-Json | Set-Content "$PSScriptRoot\build\local-process-$Mode.json" -Encoding UTF8
Write-Host "Started $Mode (PID $($process.Id))."
