[CmdletBinding()]
param([ValidateSet('Host','Client','Client2')][string]$Mode)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if ($Mode -eq 'Host') {
    $folder = 'Game'; $config = 'full_host_config.ini'; $recordName = 'full-host-probe-process.json'
} elseif ($Mode -eq 'Client') {
    $folder = 'Client'; $config = 'client_config.ini'; $recordName = 'full-host-probe-client.json'
} else {
    $folder = 'Client2'; $config = 'client_config.ini'; $recordName = 'full-host-probe-client2.json'
}
$directory = Join-Path $root "runtime\NativeMissionProbe\$folder"
$executable = Join-Path $directory 'mb_warband_wse2_multiclient.exe'
if (Get-Process -ErrorAction SilentlyContinue | Where-Object Path -EQ $executable) {
    throw 'This isolated probe instance is already running.'
}
$process = Start-Process $executable -WorkingDirectory $directory -ArgumentList @(
    '--module','NativeCoopProbe','--config-path',$config,'--no-intro'
) -PassThru
[ordered]@{id=$process.Id; startedAt=$process.StartTime.ToUniversalTime().ToString('o'); executable=$executable} |
    ConvertTo-Json | Set-Content (Join-Path $root "build\$recordName") -Encoding UTF8
Write-Host "Started isolated $Mode probe (PID $($process.Id))."
