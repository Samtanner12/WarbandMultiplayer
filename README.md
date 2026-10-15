# Private Warband campaign multiplayer project

## Portable private internet test

The latest isolated seamless army battle prototype is packaged by
`Package-Portable.ps1` into `build/WarbandCampaign-PrivateTest-2026-10-14.zip`.
The ZIP includes WSE2, the compiled NativeCoopProbe module, installer/launchers,
a fresh seed world, integrity hashes and a complete setup README. No compiler
or personal character dictionaries are required. Each PC supplies its own
installed and activated Warband assets.

PrivateNetworkTest explicitly enables the existing native mission hooks for
non-localhost addresses; generated host configuration binds all interfaces.
Installation, relocated startup, seed loading and UDP binding were checked
locally. Second-PC internet admission/combat remains unverified. The package
README explains direct IPv4/VPN setup, UDP 7440, manual firewall approval,
passwords and saving/migrating host progress. The full campaign is unfinished.

The older production build instructions below retain the legacy worker route.

The upstream baseline now builds locally: 29 module-system stages and four x86 native components. This is a compiled WarbandTogether prototype, not the completed rival-kingdom/PvP mod. Its battle-server transfers do not meet the required single persistent connection. That transport must be replaced; see PROJECT_DESIGN.md.

The current source adds account-owned realms, host-validated war declarations, mutual peace consent, and settlement grants that promote companions through Native's lord/army routines. After deployment, these appear under Camp. Native AI searches include allocated player realms; there is no separate companion army system. New captures retain the owner's account ID and world faction. Reconnecting rulers reclaim their faction and fiefs; companion lords keep their own grants. The host broadcasts campaign clock samples to correct client dates without changing the trigger timer. These features have compiled and passed authority/math checks; actual companion wars, capture/restart persistence, and exact clock agreement still need gameplay validation. Existing open clients retain the earlier build.

Saved global-variable IDs are preserved in campaign_global_ids.txt and new IDs append after successful builds. This protects the current local test save's 1,519 original global IDs. It does not establish compatibility with every older upstream save.

## Build

Run PowerShell in this folder:

```powershell
.\Build.ps1
.\scripts\Test-Build.ps1
.\Package.ps1
```

The local Python 2.7 and MSVC x86 toolchain are under tools/. Build outputs, a SHA-256 manifest, and verification reports are under build/. Compiler logs are under logs/. Nothing automatically deploys into your installed game.

The runtime uses the exact WSE2 revision bundled by WarbandTogether v0.0.82. Do not replace it with the newest WSE2: the hooks depend on this specific binary layout. Native plugins use a static C runtime so a separate modern Visual C++ redistributable is not required for these rebuilt plugins.

## Set up the installed game

Provide the folder containing mb_warband.exe. Stage a private copy with:

```powershell
.\Setup.ps1 -GamePath 'D:\SteamLibrary\steamapps\common\MountBlade Warband'
```

Use your actual installation path. Setup reads that installation and copies its assets into runtime/Game inside this project, then overlays the pinned runtime and freshly compiled module/plugins. Your installed game is not modified. A second copy needs additional disk space.

## Play the baseline

- Double-click Launch-Host.cmd to start a campaign server, two battle servers, and the client.
- Double-click Launch-Client.cmd on a client installation to run the client only.
- In the game, select Multiplayer → Join a Campaign, then connect to CoopCampaign in the LAN browser. Join a Game is the ordinary battle-server browser.
- Configure HostIP in runtime/Game/coop.ini on remote clients; set matching Password values for automatic battle-server transitions.
- The baseline ports are campaign UDP 7240, internal campaign/battle IPC 7242, and battle UDP 7241/7243/7245/7247 depending on the number of servers.
- PowerShell supports `.\Launch.ps1 -Mode Servers -BattleServers 2` and `.\Launch.ps1 -Mode Host -SaveSlot 0`.
- Stop-Host.ps1 requests graceful closure only for recorded project server processes. Save first; if a server has no closable window, close it manually after saving.

Steam needs to be running for Steam authentication/invites. LAN and internet sessions still require in-game validation on the installed game. No firewall or router changes are made by these scripts.

Development files and the staged runtime stay here. WSE2 may use its normal Documents user-data/save folder; save-path relocation has not yet been verified.

## Verification limits

The private runtime is staged from the installed Steam game. The campaign server and two battle servers start, their native plugins initialize, both battle slots connect to the campaign host, and the client discovers CoopCampaign. Activation succeeded: the client enters the campaign map, displays its character and army, and accepts map movement commands. Campaign date advances while the Party screen is open. The isolated two-client test additionally restores distinct saved characters and two 132-troop armies, and movement of the second army has been observed in the first client. Multiplayer battle behavior remains unverified.

Compilation and server startup do not establish that the campaign is playable. Distinct identities, army movement, character persistence and reconnect restoration have passed in the isolated test. Remaining gates include synchronized battle entry, return with authoritative casualties, and stable campaign/mission event routing. PvP teams, independent kingdoms, and the rule blocking additional AI parties from an active battle are not implemented yet.

The ASI loader was corrected to reserve enough stack space for alignment of its 512-byte FPU/SSE save buffer.

A battle-entry crash was captured in logs/battle-entry-crash-20261013.txt. An earlier diagnostic client plugin incorrectly forced the ordinary battle browser into campaign mode. The diagnostic code was removed, the client plugin rebuilt and staged, and campaign reconnection plus Reyvadin town entry passed afterward. Battle entry has not yet been retested successfully; the crash is not marked fixed.

## Single-PC development testing

Launch-SecondClient.ps1 prepares a separate executable using upstream's documented rev-1145 single-instance mutex patch. The user explicitly approved this method and two windows launched successfully. The source executable is unchanged. The campaign plugin now recognizes the test executable name as well as the standard client name.

For separate test characters, close existing LocalTest processes, then run:

```powershell
.\Setup-LocalTest.ps1
.\Launch-LocalTest.ps1 -Mode Host
.\Launch-LocalTest.ps1 -Mode Client1
.\Launch-LocalTest.ps1 -Mode Client2
```

These use runtime/LocalTest/Host, Client1 and Client2, module NativeCoopTest, campaign port 7340 and IPC port 7342. Client slots 1 and 2 publish different reserved character-save identifiers. This is restricted to the test module, localhost, and a disabled Steam tunnel; game authentication is unchanged. Both clients initialize their plugins, publish distinct save identifiers (2113929217/2113929218), restore different characters (XP48/584) and show independent 132-troop armies. Moving player two away from Ismirala Castle changes that army position on player one. An earlier host out-of-memory crash and hydration fallback were captured; the fresh slot-1 test with engine pool 250 resolved hydration. Keep the engine pool at 250; the advertised gameplay limit is ten.

Setup-LocalTest.ps1 -PersistentMissionExit opts into an experimental local mission-exit hook that retains the campaign receive thread and bypasses the multiplayer frontend return. It verifies pinned continuation bytes before enabling. A local castle visit and exit logged receive-thread retention without arming a return hop; the host kept that player session until a later manual reconnect. The test also exposed campaign request handling on the client during a local scene. A host-only request guard is now compiled for the next runtime test. This experiment provides no synchronized combat replication. Normal builds do not enable it. No battle workers are launched in this isolated map test, and the module's legacy battle-port constants still refer to the baseline pool.

## Sources

- WarbandTogether: https://github.com/Night1099/WarbandTogether
- WSE2: https://github.com/Ruslan-700/WSE2-Releases
- Portable MSVC download helper: https://gist.github.com/mmozeiko/7f3162ec2988e81e56d5c4e22cde9977 (adapted to use file extraction instead of Windows Installer)
- lessmsi: https://github.com/activescott/lessmsi
- Python 2.7.18: https://www.python.org/downloads/release/python-2718/
