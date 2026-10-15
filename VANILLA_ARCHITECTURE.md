# Native gameplay with multiplayer on top — architecture proposal

Status: implemented on branch `vanilla-rework` (2026-10-15). It builds and the
unit tests pass, but **none of it has been played in-game yet**. See
"Implementation status" at the end.

Written 2026-10-15 after the retained-battle fixes (camp, joining, loot, XP,
banners, encounter release).

## How it works today

- **Host**: a graphical Warband instance that loads a single-player world and
  runs it as a WSE2 multiplayer-campaign server (gameType 5). The plugin
  (`full_host_probe.h`) starts the server, routes each peer's packets and
  swaps campaign/battle replication tables per peer.
- **Clients**: multiplayer-campaign clients (gameType 4). Parties replicate
  from the engine; each character is saved per account in `.wsedict` files.
  Inventory, trade, party and character screens open locally and send a
  close-diff the host validates.
- **Battles**: one custom multiplayer mission (`native_session_probe`) at a
  time, run inside the host process while the world keeps ticking. Spawning,
  casualties, results, loot, XP and prisoners are bespoke module code.
- **Size of the bespoke layer**: `module_coop_scripts.py` is 17.7k lines with
  229 `coop_*` scripts, 43 client-to-server and 53 server-to-client event
  types, plus the retained battle and reward modules.

## Why it keeps drifting from vanilla

Every gap fixed this week had the same root: Native code was replaced, not run.

1. **Native assumes one player.** Its scripts and menus read `p_main_party`,
   `trp_player`, `$g_encountered_party`, `$players_kingdom`, player relation
   slots and dozens of `$g_player_*` globals. The mod rewrites each feature per
   player, and each rewrite misses something: loot read the wrong inventory
   slots, the camp button had no multiplayer case, "Leave" freed only one army.
2. **Battles are a custom mission.** Native's `lead_charge` family brings
   reinforcement waves, morale and routing, the victory check, retreat, label
   banners and kill bookkeeping. The custom mission strips or re-implements
   these; banners vanished because Native's banner trigger was stripped.
3. **Menus run on the client against a replica.** Any menu option that changes
   the world needs a new event plus a server re-implementation, so Native menus
   (encounter, total victory, camp, taking prisoners) are re-written instead.
4. **The engine runs one mission per process.** Only one battle can be live at
   a time; per-battle state lives in `$g_cycle_*` globals.

## Proposal: run Native unchanged on the host, once per player

### A. Player context (the enabler)

Generalize the existing `coop_player_ctx_begin/end` (today it only swaps
relation slots) into a full context switch, so any Native script or menu can
run "as" player P on the host:

- **Build-time rewrite**: the module system is Python, so the build can walk
  every Native script, menu and trigger and replace the constants
  `p_main_party` and `trp_player` with `$g_ctx_party` and `$g_ctx_troop`.
  Outside a context they hold the real `p_main_party` and `trp_player`, so
  single-player behaviour is unchanged.
- **Per-player global bank**: a generated list of the player-scoped globals
  (encounter variables, kingdom, quest state, battle result, and so on) that
  the plugin copies in and out on context switch, a few hundred integers at
  `modglobals` speed. World globals (AI, sieges, economy) are excluded.
- **Engine-level main party**: hook `mbGame::getMainParty` (0x4B5E70) to
  return the context party, for engine code that uses the main party directly.

### B. Host-run menus, client-rendered

Run Native game menus on the host inside P's context. The client shows a mirror
(menu id, rendered text, option labels, enabled flags) and sends the chosen
option back. Native's encounter, join-battle, total-victory, loot, prisoners and
camp menus then work exactly as in single player. The native screens they open
(loot, inventory, trade, party exchange) keep opening on the client through one
generic "screen session" protocol, which generalizes the loot-screen diff added
this week.

### C. Native battles

Make the battle mission a Native `lead_charge` with the network specifics
added, instead of a custom mission with Native pieces bolted on: keep Native's
triggers (reinforcements, morale, victory check, retreat, banners), replace
only the spawn source (human players' agents and armies) and result reporting.
After the battle, run Native's own `party_give_xp_and_gold`,
`party_calculate_loot` and total-victory menu in the winner's context. That
retires `module_retained_rewards.py`.

### D. Concurrency

The engine allows one mission per process. Recommendation: one live battle at a
time, with any other encounter queued and Native's auto-resolve (`simulate_battle`)
for AI-only fights. Move per-battle state from `$g_cycle_*` into a battle
record so a second battle process stays possible later, if the single-connection
requirement is ever relaxed.

## Migration order (each step testable on its own)

1. **Feasibility gate**: build-time rewrite plus context switch, then run
   Native's encounter menu for one player on the host, mirrored to the client.
2. Host-run menus for encounters and camp; delete the bespoke encounter menu,
   join menu and camp patches.
3. Generic screen sessions (loot, prisoners, trade, party exchange).
4. Battle mission on Native `lead_charge` triggers.
5. Post-battle on Native scripts; delete the retained reward code.
6. Remove dead legacy paths (dedicated battle workers, "fight locally"),
   shrinking `module_coop_scripts.py`.

## Risks

- Native code that mixes player and world state needs per-script review when
  building the global bank.
- Menus that change scene (town walks, tavern) already run as local visits and
  stay client-side.
- Some single-player-only engine behaviour (rest, main-party AI) may need hooks
  beyond `getMainParty`.
- The context switch must never interleave: menus run on the main thread, one
  player at a time.

## Implementation status (branch `vanilla-rework`)

Code: `runtime/NativeMissionProbe/Source/module_player_context.py` (new) and
`module_retained_campaign_battles.py`. Report of what the build rewrote:
`logs/player-context-report.txt`.

| Step | State |
| --- | --- |
| 1. Player context | Done at build time. `p_main_party`/`trp_player` become `$g_ctx_party`/`$g_ctx_troop` in 77 Native scripts and 8 menus. Player-scoped globals and casualty parties are banked per player. Contexts nest: a second player's context suspends the first and restores it on exit. The engine `getMainParty` hook was not needed. |
| 2. Host-run menus | Done for hostile encounters and post-battle: `simple_encounter`, retreat, `battle_debrief`, `total_victory`, `enemy_slipped_away`, `total_defeat`, `permanent_damage`. The host runs the menu, the client shows a mirror and sends the chosen option. Camp stays a client menu, because the mod's realm options are client menus. |
| 3. Screen sessions | Done: Native loot and party-exchange (prisoners, rescued troops) screens open on the client; the host validates the close-diff. |
| 4. Native battle triggers | Partly done. Label banners, Native courage, morale and routing (`apply_*_on_courage_scores`, `decide_run_away_or_not`) run on the host. A routed side counts as beaten. Not ported: reinforcement waves, AI battle tactics, and the Native victory messages. |
| 5. Native post-battle | Done: `party_give_xp_and_gold`, `party_calculate_loot` and the total-victory chain run in the winner's context. The custom rewards module is deleted. |
| 6. Legacy removal | Partly done. Removed: the custom rewards and debrief, the "Fight locally" option, the overlay banners, the B-key battle-server chooser and its reconnect. Kept as fallbacks: the old encounter menu (`$g_coop_legacy_encounter_menu=1`) and the dedicated-battle code in `module_coop_scripts.py`. |

### Not yet handled

- Lord capture conversations, captivity and Native's "join battle" menus are not mirrored.
- Relations with `fac_player_faction` are shared between players.
- A player who disconnects mid-battle loses that battle's results.
- Map animations: the user reported missing campaign-map animations; the cause is unknown.

### Rollback

`git checkout main`, then rebuild into the game module folder. Alternatively,
copy the `.txt` files from the newest `build/module-backups/NativeCoopProbe-*`
folder back into `runtime/NativeMissionProbe/Game/Modules/NativeCoopProbe`.
