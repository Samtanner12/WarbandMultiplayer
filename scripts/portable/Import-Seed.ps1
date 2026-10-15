$ErrorActionPreference='Stop'
$directory=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Mount&Blade Warband WSE2\NativeCoopProbe\Savegames'
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$slot=0..8 | Where-Object {-not(Test-Path -LiteralPath (Join-Path $directory ('sg{0:D2}.sav' -f $_)))} | Select-Object -First 1
if($null -eq $slot){throw 'All nine probe save slots are occupied. Back up a slot manually before importing. Nothing was overwritten.'}
$target=Join-Path $directory ('sg{0:D2}.sav' -f $slot)
Copy-Item -LiteralPath "$PSScriptRoot\seed\fresh-world.sav" -Destination $target
Write-Host "Fresh Day 1 world imported into save slot $slot. Load this on the host only."
