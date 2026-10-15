[CmdletBinding()]
param([ValidateSet('Host','Client')][string]$Mode)
$ErrorActionPreference='Stop'
$folder=Join-Path $PSScriptRoot "runtime\$Mode"
$exe=Join-Path $folder 'mb_warband_wse2_multiclient.exe'
if(-not(Test-Path -LiteralPath $exe)){throw 'Run Setup.cmd first.'}
if(Get-Process -ErrorAction SilentlyContinue | Where-Object Path -EQ $exe){throw "This $Mode instance is already running."}
$process=Start-Process -FilePath $exe -WorkingDirectory $folder -ArgumentList @('--module','NativeCoopProbe','--config-path','portable_config.ini','--no-intro') -PassThru
[ordered]@{id=$process.Id;executable=$exe;startedAt=$process.StartTime.ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot "process-$Mode.json") -Encoding UTF8
Write-Host "Started $Mode (PID $($process.Id))."
