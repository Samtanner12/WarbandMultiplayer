# Private synchronous campaign test

This package contains the current **experimental two-player battle build**,
including its pinned WSE2 runtime. Extract the entire ZIP on both Windows PCs.
Each player needs their own installed and activated Mount & Blade: Warband.
You do not need Python, a compiler, the source repository, or a separate WSE2
download. Setup reads your installation and creates a separate runtime here;
it does not modify the Steam installation.

This is not the finished full campaign mod. Two-player army fights and return
to the map have been tested on one PC. A real internet match has not yet been
verified. AI encounters, sieges, human-only reinforcements, simultaneous battles,
and unrelated players remaining on the map still need implementation. Some
equipment/reward and diplomacy features remain unverified. Treat this as a
private test session rather than a permanent campaign.

## 1. Install on the hosting PC

1. Extract the ZIP into a writable folder, for example Desktop\WarbandCampaign.
   Do not run it inside the ZIP, Program Files, or the installed game's folder.
2. Double-click **Setup.cmd**. Enter your Warband installation directory, or
   press Enter for `C:\Program Files (x86)\Steam\steamapps\common\MountBlade Warband`.
3. Enter **Host**. Setup creates both `runtime\Host` and `runtime\Client`.
4. Double-click **Import-Seed.cmd** once to install the included fresh Day 1
   world into an empty probe save slot. It never overwrites an occupied slot.
   If all nine slots are occupied, use an existing compatible probe world or
   back up a slot yourself before importing.
5. Double-click **Start-Host.cmd**. In this window choose Load Game and load
   the imported Day 1 world. The campaign listener starts after the save loads.
6. Keep this host window running. It is the world server. Play in the separate
   window opened by **Start-Client.cmd**.

The host PC runs two game processes; the included second-instance executable
contains the previously tested mutex-only patch. Activation and native
multiplayer authentication remain in place. If activation is required, complete
it directly in Warband. Do not send anyone your serial key.

## 2. Make the host reachable

Choose one route. No router or firewall settings are changed by this package.

- **Private VPN:** put both PCs on the same trusted virtual network. The friend
  uses the host's IPv4 address on that network. Automatic LAN discovery may not
  cross a VPN; use **COOP Direct** as described below. Allow the host game/UDP
  port through Windows Firewall on the relevant network profile.
- **Direct internet:** reserve the hosting PC's LAN IPv4 address in your router,
  forward **UDP 7440** to that address, and allow the host executable/UDP 7440
  through Windows Firewall. Give the friend your public IPv4 address privately.
  If your ISP uses carrier-grade NAT or you cannot forward ports, use a private
  VPN instead. You do not need a battle-worker port range for this prototype.
- **Same LAN:** the friend uses the host's LAN IPv4 address. No router port
  forward is needed. Normal firewall access is still needed.

Use the same port on both setups. The host's own client uses `127.0.0.1`, so
it does not need to connect through the router's public address.

To set a shared join password or a different port, run this from PowerShell in
the extracted package, with the games closed:

```powershell
.\Setup.ps1 -GamePath 'C:\Program Files (x86)\Steam\steamapps\common\MountBlade Warband' -Role Host -Port 7440 -Password 'choose-a-shared-test-password'
```

The friend supplies the same password in their Client setup. Passwords are
stored locally in the generated coop.ini files, so share the original ZIP,
not your configured runtime folder. The graphical host applies its configured
password; password admission still needs verification in the two-PC test.

## 3. Install and join on the friend's PC

1. Extract the same ZIP and run **Setup.cmd** with role **Client**.
2. Enter the hosting PC's reachable IPv4 address from step 2. Use an IP address,
   not a hostname. Do not enter `127.0.0.1` on the friend's PC.
3. Run **Start-Client.cmd**. Each player selects a different multiplayer profile
   name and keeps that name on later joins. Internet setup uses normal character
   identification; it does not assign the reserved one-PC test character slots.
4. Choose **Multiplayer > Join a Campaign**. Wait for scanning to finish.
5. Select **COOP Direct**, which points at the configured host IP and port, then
   Connect. If the actual **CoopNativePvPTest** row is visible on a local network,
   that row also works. Do not use Join a Game.
6. Create your campaign character if prompted. Wait until your army, roster and
   the host's campaign date load. These will be fresh characters; the two old
   local diagnostic character dictionaries are not included.

An explicit Client setup with a password looks like this:

```powershell
.\Setup.ps1 -GamePath 'D:\SteamLibrary\steamapps\common\MountBlade Warband' -Role Client -HostIP '100.100.10.20' -Port 7440 -Password 'choose-a-shared-test-password'
```

Replace the example IP with your host's actual address. Setup may take a few
minutes while it copies installed game assets. Allow both copies to finish.

## 4. First internet test

1. Move both armies separately. Check that both players see movement and the
   same date/time. Test with one window unfocused as well.
2. Recruit troops, equip both characters, and use Camp's player-realm relations
   to declare war. War/peace menus and companion armies still need live coverage.
3. Encounter the other human army and choose **Charge the enemy**. Both should
   enter the field automatically, over their original campaign connections.
   A battle-server browser or unavailable-worker message means the wrong build
   or a regression; it is not the expected flow.
4. Check movement, damage, troops, orders and friendly banners from both PCs.
   Soldiers should keep fighting after a player falls; control should move to
   a living own-army soldier. Players and companions survive as wounded.
5. Finish the fight. Both must return to visible, movable armies on the map.
   Compare rosters and wounded counts, then reconnect and compare again.
6. Save the world in the host, close the session, restart the host with that
   save, and reconnect both players. Check characters, realms and casualties.
   Captured settlements, loot/XP/prisoners and real equipment are additional
   acceptance tests, not verified promises in this package.

Orders: 0 all, 1 infantry, 2 archers, 3 cavalry. Press F1, then within five
seconds F1 hold, F2 follow, F3 charge, F4 stand, or F5 division retreat.
**Tab** requests whole-army retreat when no enemy is within 15 metres of the
living controlled character. Eligible regular soldiers cover the retreat;
up to 2–5 die, limited by available soldiers. No immunity timer or automated
damage/movement/retreat is included. A diagnostic sword remains in native setup.

## Saves, relocation and troubleshooting

The host owns campaign progress. Back up both:

- `runtime\Host\WSE\NativeCoopProbe` — character dictionaries and realm data.
- Your Documents folder's `Mount&Blade Warband WSE2\NativeCoopProbe\Savegames`
  — world saves.

Close the host and clients before copying those files. Keeping only the .sav
does not preserve all multiplayer character data. The initial ZIP contains a
fresh seed world and no personal character dictionaries. To move to another
PC, install the same package there and copy both backup locations to their
corresponding paths. Use the same multiplayer profile/account identity.

If you move the extracted package to another directory, rerun Setup with the
same role/address/port to regenerate storage paths. Existing WSE data remains
inside runtime unless you explicitly replace it. Do not update WSE2 separately:
the engine hooks require the bundled version (1.1.4.5 / revision 1145).

If joining fails, first confirm the host loaded a world, both use this exact
ZIP/module, the friend configured the correct IPv4/port, and routing/firewall
access permits UDP 7440. A displayed synthetic COOP Direct row alone does not
prove reachability. Try the LAN first if both PCs are available there. Stock
Warband activation/authentication errors must be resolved in the original game.

For a failure report, preserve `rgl_log.txt` and `warband_coop.log` from each
runtime folder before relaunching (logs are overwritten). Note which step
failed and whether one or both clients failed. There are no separate battle
servers in this package. The loopback restriction has an explicit opt-in
`PrivateNetworkTest=1`; real WAN behavior remains the next test.
