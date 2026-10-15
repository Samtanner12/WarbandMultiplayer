# Warband multiplayer campaign — private project

Status: the local build and one-PC test support two separately saved characters and independently moving campaign armies. Peaceful scene exit has retained the campaign session in the isolated test. Current source implements personal realms, faction war/peace authority, Native companion settlement grants, capture ownership stamps, and host clock sampling. Authority/math tests pass; these additions are not yet verified in gameplay. Synchronized combat, PvP sides, and player-only battle admission on the same connection remain unfinished. The existing battle-worker reconnect route does not satisfy the requested transport.

## Confirmed requirements

- Each player owns a separate persistent character and army.
- Players can cooperate, fight each other, and rule rival kingdoms.
- Campaign time runs continuously at one fixed normal campaign speed. No player pause, fast-forward, or literal 1:1 wall-clock requirement.
- Battles run while uninvolved players continue travelling and using campaign features.
- Campaign and battle use one persistent client-to-server connection. Disconnecting/reconnecting to a battle server, even automatically, does not satisfy this requirement (confirmed October 13, 2026).
- AI parties cannot join an already active battle against a player. Proposed uniform rule: no AI-led party may join either side after combat starts.
- Human-led parties may join active battles. Their own AI soldiers are allowed; the restriction concerns additional AI-led campaign parties.
- Private use. WarbandTogether is the authorized starting point.
- Target: a self-contained mod installation and one launcher, using WSE2 and an installed copy of Warband.

## Architecture revision: persistent connection

The existing WarbandTogether battle transfer is a baseline prototype only. Its dedicated battle allocation and automatic reconnect path cannot be the final client transport. Changing menu labels or hiding the browser does not solve this requirement.

The replacement must keep the campaign session and player identity alive during mission entry, combat, mission exit, and return to the map. Campaign messages and battle messages need separate routing within that same session. Battle messages carry a battle identity, participant identity, sequence, and message type; the server validates membership before routing inputs or snapshots. Campaign simulation continues for every other player.

WSE2's exposed module operations have not established a supported way to host simultaneous campaign and independent mission worlds through that session. Engine hooks or a new transport/mission integration are required; the feasibility gate is still open. Internal simulation workers may be useful, but they must not require a client disconnect or second server connection.

First engine gate: two local clients connect once; A enters a small synchronized mission while B remains on the map; A returns without a network reconnect or identity reset. Log the connection lifecycle and reject any implementation that silently substitutes a server hop. Only after that gate passes should full combat, admissions, PvP and kingdoms be built on this transport.

Single-PC testing also needs separate test character identities and an isolated test world, because the baseline keys characters by Steam account. The documented WSE2 mutex patch allows multiple windows, but simultaneous acceptance of the same licensed account by the server has not been verified. Authentication checks are not to be changed as part of the test setup.

## Proposed gameplay implementation rules

Campaign server owns world time, party identities, army rosters, character state, inventory, economy, quests, diplomacy, settlements, and saves. Clients request actions; the server validates and applies them.

At battle creation, assign a unique battle ID, snapshot starting armies, reserve those parties, and allocate a battle server. Reserved parties cannot move, trade troops, or enter a second encounter. Mark the battle at its map location while the rest of the campaign continues.

Admission must be checked on the campaign server AND battle server. An arriving human-led party must physically reach the battle, have a valid side under current diplomacy, and receive a server-issued admission record tied to account ID, party ID, battle ID, and side. Connecting directly to a battle port does not grant participation. Joining transfers and locks that player's army; it does not teleport troops from elsewhere on the map.

AI-led arrivals are refused and cannot alter the reserved armies. AI armies already included at battle creation continue fighting normally. Reinforcement waves drawn from those initial armies remain valid.

Battle servers report casualties and results for every participating army on both sides. Apply each result exactly once, release army reservations, then return players to the campaign. Wins, losses, retreats, disconnects, and server crashes need explicit outcomes. Never trust client-reported victories in a PvP world.

Persist player kingdoms independently: ruler account, faction ID, relations, vassals, settlements, treasury, and diplomacy. Audit Native's shared player globals before allowing simultaneous political actions.

Proposed siege rule: freeze participating garrison and settlement combat ownership during an assault; unrelated settlement activity continues. No arriving AI relief army may enter the active assault. Human-led relief follows the same admission checks.

## Initial audit

Source checkout: WarbandTogether/ (upstream main).
Inspected commit: e1c62a7d027f0a283584452f1b65976c03de92e0.

- Upstream already separates campaign and battle servers and supports a battle server pool.
- Battle mission entry assigns joining players to team 1 in module_coop_mission_templates.py. This needs server-authorized per-party team assignment for PvP.
- Upstream permits local battle paths with client-reported results. Those need removal or replacement for competitive campaign play.
- Campaign tick documentation describes continuous dedicated campaign time, but normal-speed equivalence must be measured in-game, not inferred from server frame rate. Documented engine time multiplier and game-hour trigger units require careful validation.
- Build guide pins WSE2 revision 1145 / 1.1.4.5. Engine hook addresses and binary patches are version-specific; do not automatically upgrade WSE2.
- Build requires Python 2.7 and MSVC x86. C:\Python27\python.exe was not found; the standard Visual Studio installer locator was not found. Other locations have not been exhaustively checked.
- No Warband installation or runnable WSE2 baseline has been verified yet.

## Milestones and acceptance gates

1. Baseline: locate Warband, obtain the pinned WSE2 runtime, configure isolated build outputs, compile upstream, run two clients. Existing build scripts automatically deploy to the game directory; revise this before running them.
2. Time and independence: verify two armies moving simultaneously, menus do not pause the server, a battle does not pause uninvolved players, speed cannot be changed by a client.
3. Battle isolation: start player-versus-AI combat; nearby AI cannot join, but an arriving human-led army can join with its own roster. Reject remote joins and duplicate admissions.
4. PvP: two players fight on opposite teams with independent troop commands; casualties, defeat, prisoners, loot, and rewards resolve correctly for both parties.
5. Kingdoms: independent rulers, diplomacy, fiefs, sieges, and vassals without shared-player-global corruption.
6. Full campaign: quests, companions, trading, progression, town visits, persistent saves, reconnection, interrupted-battle recovery.
7. Packaging: a private installer/launcher, pinned runtime checks, configuration, saves and logs, with no manual battle-server switching.

First playable acceptance test: player A fights while B keeps travelling; an AI arrival cannot reinforce the encounter; B reaches the battle and joins with their army; results apply once; both players reconnect with correct persistent state. Then repeat with B joining the opposing side under valid diplomacy.

## References

- https://github.com/Night1099/WarbandTogether
- https://github.com/Night1099/WarbandTogether/blob/main/docs/BUILD.md
- https://github.com/Night1099/WarbandTogether/blob/main/docs/flows/campaign-server-tick.md
- https://github.com/Ruslan-700/WSE2-Releases

WSE2's distribution is publicly downloadable. An explicit engine-binary redistribution grant was not verified during this audit. This is recorded for packaging, not a prerequisite to inspecting and developing the private project.
