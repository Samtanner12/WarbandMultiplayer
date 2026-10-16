# Issue tracker: playing Native Warband with other players

Branch: `vanilla-rework`. Goal: the campaign plays exactly like single-player
Native Warband, with other players added. The host runs the single-player world.
Native menus, conversations and battle results run on the host "as" each player
and are mirrored to that player's game.

Last updated: 2026-10-15.

Each issue below is in one of four groups:
- **Working:** confirmed in game by a player.
- **Fixed, not yet confirmed:** the code is changed and the automated tests pass,
  but no player has checked it in game.
- **Open:** a known problem that hasn't been fixed yet.
- **Not started:** larger features still to build.

---

## Working (confirmed in game)

| Area | What works |
| --- | --- |
| Map encounters | Walking into a party or lord opens Native's encounter menu. |
| Conversations | You can talk to parties and lords on the map, including bandit "fight or pay" dialogue. |
| Player against player | Battles between players, with or against each other. |
| Battle results | Correct battle summary; beaten enemy armies disappear from the map. |
| Towns | Both players can enter and leave the same town. |
| Battle maps | Native generated terrain maps; players spawn on the ground. |
| Enemy troops | Enemy soldiers spawn and fight. |

---

## Fixed, not yet confirmed in game

These changes are in the latest build (commits `c13b2e1`, `e834a94` and the one
that adds this file). Each still needs someone to try it in game.

1. **Stuck in the menu after retreating or losing.** The party you just fought
   could start a new encounter before the after-battle menus had finished. Now
   nobody can start a fight with you while one of your menus is open or your
   after-battle screens are still running.
2. **"Continue" on the battle report looped.** A leftover conversation state
   made the click count as a dialogue answer. That state is now cleared whenever
   a menu opens or a battle starts.
3. **Friendly troops never spawned.** Neither test character had troops, and
   the F11 test troops never reached the host. Now:
   - the camp menu has **"Test build: add 15 troops to my army."**;
   - the host logs every request (`test troops: request from player N`);
   - a held prisoner's party can also take the troops (it used to be skipped).
4. **The lord who captured you stayed stuck on the map.** The captor now
   patrols near the closest town or castle, and Native's AI picks its next aim.
5. **Armies spawned too close together.** On generated maps the two armies
   now start about 200 m apart.
6. **Generated map didn't match the map location.** The battle-map seed is
   worked out from the battle's position on the world map. It is shared with
   every player before the battle starts.

## Open

| # | Problem | Notes |
| --- | --- | --- |
| O1 | **No camp menu while held prisoner.** | Your party is hidden for the hours of captivity, so the Camp button has nothing to open. Native then offers an escape (`captivity_wilderness_check`). F11 still sends the test-troops request while you are held. A clear "you are a prisoner for N more hours" notice on the client would help. |
| O2 | **Retreat (Tab) counts as a loss when an enemy is close.** | Retreating is refused if an enemy is within about 15 m. Check whether Native's own retreat rules should apply instead. |
| O3 | **Friendly troops spawning with an army.** | Waiting on a test with the new test troops (see fix 3). |
| O4 | **"Order attack" option in the encounter menu.** | Hidden for now (`UNSUPPORTED_OPTIONS`): sending your troops in without you is not supported yet. |
| O5 | **Short pauses on the campaign map.** | The host runs the whole world. Long frames are logged by the plugin (`hitch_probe`), so they can be traced if they come back. |

## Not started

| # | Feature | Notes |
| --- | --- | --- |
| N1 | **Seeing other players inside a town scene.** | Each player's town visit is their own single-player scene. To share one, the host would have to run town scenes as multiplayer missions, like battles. That is a big change. |
| N2 | **3D model of the person you are talking to.** | Conversations are mirrored as menus, so there is no 3D talk scene on clients yet. A separate task for this has been proposed. |

---

## How to test

1. Close any running copies:
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-CoopTest.ps1 -Stop`
2. Delete the old trace files, so the next one starts clean:
   - `runtime\NativeMissionProbe\Game\WSE\NativeCoopProbe\coop menu trace.ini`
     (host)
   - `runtime\NativeMissionProbe\Client\WSE\NativeCoopProbe\coop menu trace.ini`
     (client)
3. Start the host and two clients on save slot 2:
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-CoopTest.ps1 -SaveSlot 2`
4. On each player, use Camp → "Test build: add 15 troops to my army" (or press F11).
5. Fight a battle, then try retreating from another one, away from the enemy.
6. Read the host trace. It records:
   - each menu shown and each option chosen;
   - conversation steps;
   - each army's spawn position and soldier count;
   - "battle over" and each army's losses;
   - test-troop requests.

## Recovery keys (test build)

- **F8:** moves a player's party off sea or mountains and releases them from a
  stuck town.
- **F11:** asks the host for 15 test troops.

## Saves

- Testing uses `sg02`.
- `sg08` was damaged by an old plugin bug and is kept in
  `build\save-backups\broken-clock-2026-10-15\`. The original `sg02` backup is
  in the same folder.
