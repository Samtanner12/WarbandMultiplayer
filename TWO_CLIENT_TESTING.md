# Current two-client test — October 14

## One-click start

Double-click `Start-CoopTest.cmd` (or run `.\Start-CoopTest.ps1`). It opens the
host, loads the newest NativeCoopProbe save, waits for the campaign listener,
then opens Client and Client2, which join automatically from the main menu.

- `-SaveSlot 8` loads `sg08.sav` instead of the newest save.
- `-Manual` opens all three windows at the main menu with no automation.
- `-Stop` asks the three test windows to close.
- `-PrepareOnly` repairs asset/module junctions, character storage paths and
  the plugin copy without starting the game.

Automation is test-only. The plugin acts on `WARBAND_COOP_AUTOLOAD_SLOT` and
`WARBAND_COOP_AUTOJOIN` set by the launcher, only for NativeCoopProbe on
loopback with Steam off. A normal launch is unchanged.

## Vanilla rework to check in-game (branch `vanilla-rework`, untested)

Native's own encounter and post-battle menus now run on the host for each
player. See `VANILLA_ARCHITECTURE.md` for what changed and how to roll back.

- Meeting a hostile AI party opens Native's "simple_encounter" menu (Attack,
  Leave, and so on), not the old "Your party encounters a hostile force!".
- After a battle: Native's debrief ("battle_debrief"), then total victory with
  Native's loot screen and the prisoner/rescued-troops exchange screen.
- Defeat leads to Native's total-defeat menu.
- Soldiers rout when their morale breaks (never in the first 45 seconds). A
  side whose remaining soldiers are all fleeing loses.
- B no longer opens the old battle-server list. Use the camp menu, F10, or
  walk onto a battle.

## Retained battle fixes to check in-game

- Camp button opens Native's camp menu; "Join a nearby battle." is listed.
- Moving onto an active battle opens "You come across a battle between..."
  once per battle, even when another player is fighting in it.
- Kills during the fight add XP to the killer (hero or troop stack).
- After any outcome (including defeat or retreat), nearby AI armies move again
  and an AI army with no fit troops left is removed, its lords escaping.
- A 3-second cooldown applies before either army can start another battle.

Use **NativeCoopProbe / CoopNativePvPTest**, port 7440. The isolated runtime has
one graphical host and two playable clients. The older NativeCoopTest build
described in the historical notes below still uses battle workers.

Start only instances that are stopped, from Desktop/WarbandMod:

```powershell
.\scripts\launch-full-engine-probe.ps1 -Mode Host
.\scripts\launch-full-engine-probe.ps1 -Mode Client
.\scripts\launch-full-engine-probe.ps1 -Mode Client2
```

In the host, Load Game and select the bottom-right saved world (Day 245).
Client uses New_Player; Client2 uses New_Playerb. Both join through Multiplayer
> Join a Campaign > Local Area Network > **CoopNativePvPTest**. Ignore COOP Direct.
Wait for character hydration and the shared campaign date. Keep the host open.

The saved casualties are real test results: New_Player has the player and Ymira
only; New_Playerb retains 132 members. The regulars died during the defeat
regression. Heroes survived wounded and have subsequently healed. Original
NativeCoopTest saves and characters were not reset.

Encounter the opposing human army and choose Charge the enemy. Both clients
enter the field scene through their original campaign connection. After avatar
death, control transfers to a living own-army soldier. Select divisions with
0/all, 1/infantry, 2/archers, 3/cavalry. F1 opens the order menu, then F1 holds,
F2 follows, F3 charges, F4 stands, F5 retreats the division. Tab requests
whole-army retreat: a living controlled character must have no enemy within
15 metres. Up to 2–5 eligible regular soldiers cover the retreat and die.

The playable probe has no immunity timer and no automated damage, movement,
orders or retreat. F9 diagnostic respawn is disabled.

## Verified and outstanding

Verified: user PvP both ways, roster combat after avatar death, repeated
battle/map returns, automated native soldier takeover/order/retreat, matching
casualty rosters, wound-only heroes, character reconnect, saved-world listener
restart, matching campaign clocks and native healing updates to the owner.
Build checks, eight authority tests, nine health tests, six battle-control
tests and the native clock regression pass. Automated handler tests do not
verify every human keyboard gesture.

| Area | Still to test or implement |
|---|---|
| Friendly banners | Visually verify delayed overlays and takeover. |
| Health | Newly broadcast rival hero percentages during healing; wounded-start eligibility; partial surviving hero damage is not yet committed. |
| Equipment | Actual armor, weapons, mounts, modifiers and consumables through combat/reconnect. Native setup still supplies a diagnostic sword. |
| Rewards | XP, upgrade progress, loot, prisoners, wages and capture/release. |
| Realms | In-engine war/peace, companion grants, army recruitment and attacks on rival kingdoms. |
| Settlements | Siege/capture, ownership and garrison synchronization followed by host restart. |
| Recovery | Disconnect during admission, combat and return; reconnect; prevent duplicate results. |
| Independent activity | AI fights while another player stays on map, human-only reinforcements and concurrent missions still need implementation. |
| Scale/network | Large armies, waves, ranged/cavalry orders, long sessions and actual two-PC latency/loss. |

The full mod is **not complete**. Retained combat is gated to this loopback
prototype; replacing the production worker route remains implementation work.
See logs/NATIVE_COMBAT_PROBE.md and logs/final-army-return-*.json for evidence.
Saved-world/health snapshots are logs/saved-world-health-*.json and
logs/shared-health-live-*.json.

Stop all three verified isolated processes before staging. The client module
directories share the host's compiled module through junctions.
prepare-playable-army-test.py removes finite fixtures without resetting saves.
Do not rerun prepare-native-pvp-probe.py during persistence tests: it copies
baseline character dictionaries and replaces test losses.

## Historical instructions — superseded

The two isolated clients are Client1 and Client2 under runtime/LocalTest. Both use NativeCoopTest and join CoopLocalTest on 127.0.0.1:7340. Their saved character identities are separate, even though this PC has one licensed game installation.

## Current status

- Both saved characters restored after the update, with 132 troops each.
- Both armies moved independently after the failed-encounter recovery.
- Both clients received clock sample 938 with hour 1652 and fraction 472. The host was still advancing normally.
- F8 recovery was confirmed by the user: the client displayed "encounter cleared."
- Shared multiplayer combat over the campaign connection is **not implemented or verified**. The current multiplayer fight option still requests the legacy battle-worker pool. An unavailable-worker rejection is not a successful battle test.
- Current allocation logs show zero online workers, not occupied workers. The latest packaged source distinguishes that condition from a full pool and reports combat unavailable. This message fix is not deployed into the open clients and does not add combat.
- The latest compiled source also transfers local fight results without a browser reconnect, re-arms the result mailbox for later fights, and excludes human armies from the local singleplayer fight option. Those latest result-path changes still require gameplay testing and are newer than the currently open clients.

## Use the current windows

1. Keep one client using New_Player and the other using New_Playerb. Switch with Alt+Tab.
2. Both must use **Multiplayer > Join a Campaign > Local Area Network > CoopLocalTest**. "Join a Game" is the legacy battle browser.
3. Wait until each character's army appears and its saved roster has loaded. This can take several seconds.
4. Click an empty destination in Client1, then switch to Client2. The first army should travel while you give the second army a different destination.
5. Compare dates and time-of-day while switching windows. They should track the shared clock; this world keeps running while a window is unfocused.
6. If a rejected encounter traps an army, press and briefly hold **F8** on the map. The recovery refuses to abort an active dedicated or local fight and applies no victory, loss, or casualties.

If the clients are closed, run these separately in PowerShell from Desktop/WarbandMod:

```powershell
.\Launch-LocalTest.ps1 -Mode Host
.\Launch-LocalTest.ps1 -Mode Client1
.\Launch-LocalTest.ps1 -Mode Client2
```

Start Host only if it is stopped; do not launch duplicate copies. Staging another build requires all three local test processes to be closed. Setup-LocalTest.ps1 must not run against loaded executables.

## What a completed seamless battle must pass

These are acceptance criteria, not features available in the current build:

1. Declare war between the two realms and encounter the opposing human army.
2. Start the fight from that encounter. Both participants enter the same scene automatically, with no battle-server lookup or new campaign login.
3. Move and attack in each window. Each must see the other human's actual actions and matching health, deaths, and troop casualties.
4. End the fight. Both return to their campaign armies through the original session, with matching rewards and rosters.
5. Restart and reconnect. Characters, inventories, faction ownership, and captured settlements must retain the results.
6. Separately, have one player fight AI while the other continues moving on the map. Only human players may bring new armies into that active battle.

Useful logs are runtime/LocalTest/Host/rgl_log.txt and each client's warband_coop.log. A new host IDENT during a purported battle transition is evidence of reconnecting, not proof of a seamless retained session. Agent replication and combat outcomes must also be checked; an unchanged connection alone is insufficient.

The campaign save is stored by WSE2 at Documents/Mount&Blade Warband WSE2/NativeCoopTest/Savegames/sg01.sav. A recovery-time backup of that save and the character dictionaries is under build/save-backups/2026-10-13-recovery.

The isolated NativeCoopProbe full-engine experiment now loads a battle scene
over its original campaign connection. A human avatar spawns, held movement
reaches the host, and host/client position samples agree. Campaign time continues
advancing during that scene. See logs/NATIVE_COMBAT_PROBE.md for evidence and
remaining limitations. This probe still does not provide a PvP fight test for
the two saved NativeCoopTest campaign characters.
