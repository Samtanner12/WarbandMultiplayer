$ErrorActionPreference = 'Stop'
$records = Join-Path $PSScriptRoot 'build\running-servers.json'
if (-not (Test-Path -LiteralPath $records)) { Write-Host 'No recorded host processes.'; exit }
$runtime = Join-Path $PSScriptRoot 'runtime\Game'
foreach ($record in @(Get-Content -LiteralPath $records -Raw | ConvertFrom-Json)) {
    $process = Get-Process -Id $record.id -ErrorAction SilentlyContinue
    if ($process -and $process.Path -eq $record.executable -and
        $process.StartTime.ToUniversalTime().Ticks -eq ([datetime]$record.startedAt).ToUniversalTime().Ticks -and
        $process.Path.StartsWith($runtime + '\', [StringComparison]::OrdinalIgnoreCase)) {
        # Close the dedicated server's window first; avoid interrupting save writes.
        if (-not $process.CloseMainWindow()) {
            Write-Warning "PID $($process.Id) has no closable window. Close it through Task Manager after saving; it was not forcibly terminated."
        }
    }
}
