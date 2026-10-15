[CmdletBinding()]
param(
    # Savegame slot for the host (sg08.sav = 8). Default: the newest NativeCoopProbe save.
    [ValidateRange(0,99)][int]$SaveSlot = -1,
    # Open the windows at the main menu without auto-loading or auto-joining.
    [switch]$Manual,
    # Ask the open test windows to close, then exit.
    [switch]$Stop,
    # Repair links, configs and the plugin without opening any game windows.
    [switch]$PrepareOnly,
    [int]$HostTimeoutSeconds = 300
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$probe = Join-Path $root 'runtime\NativeMissionProbe'
$instances = @(
    @{ Mode='Host';    Folder='Game';    Config='full_host_config.ini'; Record='full-host-probe-process.json' },
    @{ Mode='Client';  Folder='Client';  Config='client_config.ini';    Record='full-host-probe-client.json' },
    @{ Mode='Client2'; Folder='Client2'; Config='client_config.ini';    Record='full-host-probe-client2.json' }
)
foreach ($i in $instances) {
    $i.Directory  = Join-Path $probe $i.Folder
    $i.Executable = Join-Path $i.Directory 'mb_warband_wse2_multiclient.exe'
}

function Get-Running($instance) {
    Get-Process -Name 'mb_warband_wse2_multiclient' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $instance.Executable }
}

if ($Stop) {
    foreach ($i in $instances) {
        foreach ($p in @(Get-Running $i)) {
            if ($p.CloseMainWindow()) { Write-Host "Asked $($i.Mode) (PID $($p.Id)) to close." }
            else { Write-Warning "$($i.Mode) (PID $($p.Id)) has no closable window; close it manually." }
        }
    }
    return
}

$running = @($instances | Where-Object { Get-Running $_ })
if ($running) {
    throw ("Already running: {0}. Close those windows (or run .\Start-CoopTest.ps1 -Stop) first." -f
        (($running | ForEach-Object { $_.Mode }) -join ', '))
}

# Copying the project turns its asset junctions into empty folders; relink only empty ones.
function Repair-Link([string]$link, [string]$target) {
    if (-not (Test-Path -LiteralPath $target)) { throw "Missing game files: $target. Run Setup.ps1 / Setup-LocalTest.ps1 first." }
    $item = Get-Item -LiteralPath $link -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType) { return }
    if ($item) {
        if (Get-ChildItem -LiteralPath $link -Recurse -File -Force -ErrorAction SilentlyContinue | Select-Object -First 1) { return }
        Remove-Item -LiteralPath $link -Recurse -Force
    }
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Host "Linked $link -> $target"
}
$assets = @('CommonRes','Data','Languages','Music','Sounds','Textures')
foreach ($name in $assets) {
    Repair-Link (Join-Path $instances[0].Directory $name) (Join-Path $root "runtime\LocalTest\Host\$name")
}
foreach ($i in $instances[1..2]) {
    foreach ($name in $assets + 'Modules') {
        Repair-Link (Join-Path $i.Directory $name) (Join-Path $instances[0].Directory $name)
    }
}

# This copy's configs must not read or write another project folder's characters.
foreach ($i in $instances) {
    $config = Join-Path $i.Directory $i.Config
    $storage = Join-Path $i.Directory 'WSE\'
    $text = [IO.File]::ReadAllText($config)
    $updated = [regex]::Replace($text, '(?m)^sStoragePath=[^\r\n]*', "sStoragePath=$($storage.Replace('$','$$'))")
    if ($updated -ne $text) {
        [IO.File]::WriteAllText($config, $updated, [Text.Encoding]::ASCII)
        Write-Host "$($i.Mode): character storage now $storage"
    }
}

$plugin = Join-Path $root 'build\bin\warband_coop.asi'
if (Test-Path -LiteralPath $plugin) {
    $hash = (Get-FileHash -LiteralPath $plugin).Hash
    foreach ($i in $instances) {
        $target = Join-Path $i.Directory 'warband_coop.asi'
        if (-not (Test-Path -LiteralPath $target) -or (Get-FileHash -LiteralPath $target).Hash -ne $hash) {
            Copy-Item -LiteralPath $plugin -Destination $target -Force
            Write-Host "$($i.Mode): updated warband_coop.asi from build\bin"
        }
    }
}

# The host needs a multiplayer profile to start its campaign server.
$profiles = Join-Path $env:APPDATA 'Mount&Blade Warband WSE2\profiles.dat'
if (-not (Test-Path -LiteralPath $profiles)) {
    $sandboxed = Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Packages') -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName 'LocalCache\Roaming\Mount&Blade Warband WSE2\profiles.dat' } |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($sandboxed) {
        New-Item -ItemType Directory -Force -Path (Split-Path $profiles) | Out-Null
        Copy-Item -LiteralPath $sandboxed -Destination $profiles
        Write-Host "Copied multiplayer profiles from $sandboxed"
    } else {
        Write-Warning 'No multiplayer profile exists. Run with -Manual, open Multiplayer in each window and create a profile, then close and relaunch.'
    }
}

if ($PrepareOnly) { Write-Host 'Test folders prepared.'; return }

$saves = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Mount&Blade Warband WSE2\NativeCoopProbe\Savegames'
if (-not $Manual) {
    if ($SaveSlot -lt 0) {
        $newest = Get-ChildItem -LiteralPath $saves -Filter 'sg??.sav' -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $newest) { throw "No savegames found in $saves. Start a world manually with -Manual first." }
        $SaveSlot = [int]$newest.BaseName.Substring(2)
    }
    $saveFile = Join-Path $saves ('sg{0:D2}.sav' -f $SaveSlot)
    if (-not (Test-Path -LiteralPath $saveFile)) { throw "Savegame not found: $saveFile" }
    Write-Host ("Host will load {0} (saved {1})." -f (Split-Path $saveFile -Leaf), (Get-Item $saveFile).LastWriteTime)
}

function Start-Instance($instance, [hashtable]$environment) {
    $previous = @{}
    foreach ($key in $environment.Keys) {
        $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $environment[$key], 'Process')
    }
    try {
        $process = Start-Process $instance.Executable -WorkingDirectory $instance.Directory -PassThru -ArgumentList @(
            '--module','NativeCoopProbe','--config-path',$instance.Config,'--no-intro')
    } finally {
        foreach ($key in $environment.Keys) {
            [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process')
        }
    }
    [ordered]@{ id=$process.Id; startedAt=$process.StartTime.ToUniversalTime().ToString('o'); executable=$instance.Executable } |
        ConvertTo-Json | Set-Content (Join-Path $root "build\$($instance.Record)") -Encoding UTF8
    Write-Host "Started $($instance.Mode) (PID $($process.Id))."
    $process
}

$hostInstance = $instances[0]
$hostLog = Join-Path $hostInstance.Directory 'warband_coop.log'
$logStart = 0
if (Test-Path -LiteralPath $hostLog) { $logStart = (Get-Item -LiteralPath $hostLog).Length }

$hostEnv = @{}
if (-not $Manual) { $hostEnv['WARBAND_COOP_AUTOLOAD_SLOT'] = [string]$SaveSlot }
$hostProcess = Start-Instance $hostInstance $hostEnv

if (-not $Manual) {
    Write-Host 'Waiting for the host to load the world and open the campaign listener...'
    $deadline = (Get-Date).AddSeconds($HostTimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if ($hostProcess.HasExited) { throw "Host exited (code $($hostProcess.ExitCode)). See $hostLog and rgl_log.txt." }
        if (-not (Test-Path -LiteralPath $hostLog)) { continue }
        $stream = [IO.File]::Open($hostLog, 'Open', 'Read', 'ReadWrite')
        try {
            if ($stream.Length -lt $logStart) { $logStart = 0 }
            $stream.Position = $logStart
            $tail = (New-Object IO.StreamReader($stream)).ReadToEnd()
        } finally { $stream.Dispose() }
        if ($tail -match 'native campaign listener started') { $ready = $true; break }
        if ($tail -match 'autostart load (skipped|faulted)') {
            Write-Warning 'The host could not auto-load the save. Use Load Game in the host window; players will start once it is listening.'
            $logStart = 0
        }
    }
    if (-not $ready) { Write-Warning "Host was not listening after $HostTimeoutSeconds s; starting players anyway." }
}

$clientEnv = @{}
if (-not $Manual) { $clientEnv['WARBAND_COOP_AUTOJOIN'] = '1' }
foreach ($i in $instances[1..2]) {
    Start-Instance $i $clientEnv | Out-Null
    Start-Sleep -Seconds 3
}

if ($Manual) {
    Write-Host 'Manual mode: Load Game in the host, then Multiplayer > Join a Campaign > LAN > CoopNativePvPTest in each player window.'
} else {
    Write-Host 'Players will join automatically from the main menu. If one stays at the menu, join manually: Multiplayer > Join a Campaign > LAN > CoopNativePvPTest.'
}
