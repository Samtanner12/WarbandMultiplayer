"""Stage the two-human native-connection combat test, with all probe processes stopped."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
from datetime import datetime

root = Path(__file__).resolve().parents[1]
source = root/'runtime/NativeMissionProbe/Source'
game = root/'runtime/NativeMissionProbe/Game'
marker = '# TWO_HUMAN_NATIVE_PVP_PROBE'
menus = source/'module_game_menus.py'
text = menus.read_text(encoding='cp1254')
if marker not in text:
    text = text.replace('(assign, "$g_full_host_probe_request", 1),',
        marker+'\n            (assign, "$g_native_pvp_probe", 1),\n            (assign, "$g_full_host_probe_request", 1),', 1)
    menus.write_text(text, encoding='cp1254')
triggers = source/'module_simple_triggers.py'
text = triggers.read_text(encoding='cp1254')
text = text.replace('(gt, ":probe_peers", 0), (assign, "$g_native_probe_started", 1)',
    '(ge, ":probe_peers", 2), (assign, "$g_native_probe_started", 1)')
if marker not in text:
    text += '''
# TWO_HUMAN_NATIVE_PVP_PROBE
simple_triggers += [(0, [
    (multiplayer_is_server), (multiplayer_is_campaign),
    (eq, "$g_full_host_probe_request", 3), (eq, "$g_pvp_host_named", 0),
    (server_set_name, "@CoopNativePvPTest"),
    (str_store_string, s58, "@ProbeHost"), (player_set_username, 0, s58),
    (assign, "$g_pvp_host_named", 1),
])]
'''
text = text.replace('(player_set_username, 0, "@ProbeHost"),',
    '(str_store_string, s58, "@ProbeHost"), (player_set_username, 0, s58),')
if '# PRIVATE_LAN_PVP_HOST' not in text:
    text = text.replace('(server_set_name, "@CoopNativePvPTest"),',
        '# PRIVATE_LAN_PVP_HOST\n    (server_set_add_to_game_servers_list, 0),\n    (server_set_name, "@CoopNativePvPTest"),', 1)
triggers.write_text(text, encoding='cp1254')

scripts = source/'module_coop_scripts.py'
text = scripts.read_text(encoding='cp1254')
# Remove the old respawn protection from already staged source as well.
text = text.replace('(store_add, "$g_probe_safe_until", ":probe_seconds", 20),', '')
text = text.replace('(team_set_relation, 0, 1, 0),', '(team_set_relation, 0, 1, -1),')
text = text.replace('@[PROBE] respawned; twenty seconds to draw the practice sword', '@[PROBE] respawned; combat active immediately')
scripts.write_text(text, encoding='cp1254')
if marker not in text:
    text = text.replace('(assign, "$g_full_probe_peer_ready", 1),', '''
                    # TWO_HUMAN_NATIVE_PVP_PROBE
                    (try_begin), (player_slot_eq, ":player_no", 6000, 0),
                        (player_set_slot, ":player_no", 6000, 1),
                        (val_add, "$g_full_probe_peer_ready", 1),
                    (try_end),''', 1)
    text = text.replace('(eq, "$g_full_probe_peer_ready", 1)', '(ge, "$g_full_probe_peer_ready", 2)')
    # Respawn restores that peer's assigned team, rather than the AI-test team.
    text = text.replace('(player_set_team_no, ":player_no", 1),', '''
                    (player_get_slot, ":probe_team", ":player_no", 6002),
                    (player_set_team_no, ":player_no", ":probe_team"),''', 1)
    text = text.replace('(player_spawn_new_agent, ":player_no", 0),', '''
                    (player_spawn_new_agent, ":player_no", ":probe_team"),
                    (player_set_slot, ":player_no", 6001, 0),''', 1)
    scripts.write_text(text, encoding='cp1254')

missions = source/'module_mission_templates.py'
text = missions.read_text(encoding='cp1254')
prefix, sep, _ = text.partition('# FULL_NATIVE_COMBAT_GATEWAY')
if not sep: raise RuntimeError('Initialize the full engine probe before staging PvP.')
missions.write_text(prefix+'''# FULL_NATIVE_COMBAT_GATEWAY
# TWO_HUMAN_NATIVE_PVP_PROBE
mission_templates += [("native_session_probe", mtf_battle_mode, -1, "Native human duel",
    [(entry, mtef_visitor_source|mtef_team_0, 0, aif_start_alarmed, 1, []) for entry in range(128)], [
    (ti_after_mission_start, 0, 0, [(neg|multiplayer_is_server)], [
        (assign, "$g_full_probe_client_ack_sent", 1),
        (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 44),
    ]),
    (ti_after_mission_start, 0, 0, [(multiplayer_is_server)], [
        (team_set_relation, 0, 1, -1),
        (assign, "$g_full_probe_notified", 0),
        (display_message, "@[PVP TEST] two human scene initialized on campaign peers"),
    ]),
    (0, 0, 0, [(multiplayer_is_server), (eq, "$g_full_probe_notified", 0)], [
        (store_current_scene, ":scene"), (assign, ":recipients", 0),
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (multiplayer_send_3_int_to_player, ":player", multiplayer_event_multiplayer_campaign_server_events,
                67, ":scene", "mt_native_session_probe"),
            (val_add, ":recipients", 1),
        (try_end), (ge, ":recipients", 2), (assign, "$g_full_probe_notified", 1),
    ]),
    (0, 0, 0, [(multiplayer_is_server), (ge, "$g_full_probe_peer_ready", 2)], [
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (player_slot_eq, ":player", 6001, 0),
            (player_get_slot, ":identity", ":player", slot_player_coop_steam_acctid),
            (assign, ":team", 1),
            (try_begin), (eq, ":identity", 2113929217), (assign, ":team", 0), (try_end),
            (player_set_slot, ":player", 6002, ":team"),
            (player_set_team_no, ":player", ":team"),
            (player_get_agent_id, ":agent", ":player"),
            (try_begin), (lt, ":agent", 0),
                (player_add_spawn_item, ":player", 0, "itm_practice_sword"),
                (player_spawn_new_agent, ":player", ":team"),
                (player_get_agent_id, ":agent", ":player"),
            (try_end),
            (ge, ":agent", 0), (agent_is_alive, ":agent"),
            (agent_set_team, ":agent", ":team"),
            (entry_point_get_position, pos3, ":team"), (agent_set_position, ":agent", pos3),
            (call_script, "script_coop_equip_player_agent", ":agent"),
            (agent_equip_item, ":agent", "itm_practice_sword", 0),
            (player_set_slot, ":player", 6001, 1),
            (assign, "$g_probe_human_agent", ":agent"),
        (try_end),
        (team_set_relation, 0, 1, -1),
    ]),
    (0, 0, 0, [(neg|multiplayer_is_server), (key_is_down, key_f9)], [
        (store_mission_timer_a, ":seconds"), (ge, ":seconds", "$g_probe_respawn_next_key"),
        (store_add, "$g_probe_respawn_next_key", ":seconds", 2),
        (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 45),
    ]),
    (1, 0, 0, [], [
        (store_current_hours, "$g_probe_campaign_hour"),
        (store_mission_timer_a, "$g_probe_mission_seconds"), (assign, "$g_probe_alive", 0),
        (try_for_agents, ":agent"), (agent_is_alive, ":agent"), (val_add, "$g_probe_alive", 1), (try_end),
    ]),
])]
''', encoding='cp1254')

# Optional encounter mode uses the real campaign battle request rather than
# starting a duel immediately when the second character joins.
if '--campaign-encounter' in sys.argv:
    trigger_text = triggers.read_text(encoding='cp1254')
    trigger_text = trigger_text.replace('(eq, "$g_native_probe_started", 0),',
        '(eq, "$g_native_probe_started", 0), (eq, "$g_encounter_cycle_requested", 1),', 1)
    triggers.write_text(trigger_text, encoding='cp1254')
    cycle_marker = '# RETAINED_ENCOUNTER_CYCLE_TEST'
    script_text = scripts.read_text(encoding='cp1254')
    if cycle_marker not in script_text:
        script_text += r'''
# RETAINED_ENCOUNTER_CYCLE_TEST
for cycle_index, cycle_script in enumerate(coop_scripts):
    if cycle_script[0] == "coop_ev_cli_start_battle":
        coop_scripts[cycle_index] = (cycle_script[0], [
            (store_script_param, ":requester", 1),
            (player_is_active, ":requester"),
            (eq, "$g_native_probe_started", 0),
            (player_get_party_id, ":party", ":requester"),
            (party_get_battle_opponent, ":opponent", ":party"),
            (assign, ":defender", -1),
            (try_for_players, ":candidate", 1), (player_is_active, ":candidate"),
                (player_get_party_id, ":candidate_party", ":candidate"),
                (eq, ":candidate_party", ":opponent"), (assign, ":defender", ":candidate"),
            (try_end),
            (try_begin), (ge, ":defender", 0),
                (assign, "$g_encounter_cycle_requested", 1),
                (assign, "$g_cycle_attacker", ":requester"),
                (assign, "$g_cycle_defender", ":defender"),
                (disable_party, ":party"), (disable_party, ":opponent"),
                (display_message, "@[CYCLE TEST] real human encounter admitted on retained peers"),
            (else_try),
                (multiplayer_send_2_int_to_player, ":requester", multiplayer_event_multiplayer_campaign_server_events,
                    multiplayer_event_multiplayer_campaign_server_event_battle_rejected, 2),
            (try_end),
        ])
    if cycle_script[0] == "multiplayer_campaign_server_events":
        for cycle_event_index, cycle_operation in enumerate(cycle_script[1]):
            if isinstance(cycle_operation, tuple) and cycle_operation[:2] == (eq, ":event_type"):
                cycle_script[1][cycle_event_index:cycle_event_index] = [
                    (eq, ":event_type", 68),
                    (assign, "$g_full_probe_remote_request", 5),
                    (assign, "$g_coop_encounter_done", 1),
                    (assign, "$g_coop_battle_requested", 0),
                    (assign, "$g_coop_pending_menu_armed", 0),
                    (else_try),
                ]
                break
'''
        scripts.write_text(script_text, encoding='cp1254')
    mission_text = missions.read_text(encoding='cp1254')
    # Diagnostic respawn stays available only in the standalone duel.
    mission_text = mission_text.replace('(neg|multiplayer_is_server), (key_is_down, key_f9)',
        '(neg|multiplayer_is_server), (eq, "$g_full_probe_remote_request", -1), (key_is_down, key_f9)')
    mission_text = mission_text.replace('    (1, 0, 0, [], [', r'''
    (0, 0, 0, [(neg|multiplayer_is_server), (eq, "$g_full_probe_remote_request", 5)], [
        (assign, "$g_full_probe_remote_request", 6), (finish_mission, 0),
    ]),
    (0.25, 0, 0, [(multiplayer_is_server), (eq, "$g_cycle_result_sent", 0),
        (ge, "$g_probe_mission_seconds", 3)], [
        (assign, ":living", 0), (assign, ":participants", 0),
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (val_add, ":participants", 1), (player_get_agent_id, ":agent", ":player"),
            (ge, ":agent", 0), (agent_is_alive, ":agent"), (val_add, ":living", 1),
        (try_end),
        (eq, ":participants", 2), (lt, ":living", 2),
        (assign, "$g_cycle_result_sent", 1),
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (player_get_party_id, ":party", ":player"),
            (party_leave_cur_battle, ":party"), (enable_party, ":party"),
            (call_script, "script_coop_save_character", ":player"),
            (multiplayer_send_int_to_player, ":player", multiplayer_event_multiplayer_campaign_server_events, 68),
        (try_end),
        (assign, "$g_full_host_probe_request", 4),
        (display_message, "@[CYCLE TEST] duel ended; release armies and return both peers to campaign"),
    ]),
    (1, 0, 0, [], [''', 1)
    missions.write_text(mission_text, encoding='cp1254')

module = game/'Modules/NativeCoopProbe'
env = dict(os.environ, WARBAND_EXPORT_DIR=str(module))
with (root/'logs/full-native-pvp-module-build.log').open('w') as output:
    subprocess.run([str(root/'tools/python27-extract/SourceDir/python.exe'), '-B', str(source/'run_module_build.py')],
        cwd=source, env=env, stdout=output, stderr=subprocess.STDOUT, check=True)

# Existing saved characters are copied into the diagnostic namespace only.
dictionary_source = root/'runtime/LocalTest/Host/WSE/NativeCoopTest'
dictionary_destination = game/'WSE/NativeCoopProbe'
dictionary_destination.mkdir(parents=True, exist_ok=True)
for identity in [2113929217, 2113929218]:
    name = 'coop char sid %d.wsedict' % identity
    target = dictionary_destination/name
    if target.exists():
        backup = root/'build/save-backups/pvp-dictionaries'/datetime.now().strftime('%Y%m%d-%H%M%S')
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup/name)
    shutil.copy2(dictionary_source/name, target)

for folder, slot in [('Game', 0), ('Client', 1), ('Client2', 2)]:
    directory = root/'runtime/NativeMissionProbe'/folder
    if not directory.exists(): raise RuntimeError('Stage both probe clients before PvP preparation')
    shutil.copy2(root/'build/bin/warband_coop.asi', directory/'warband_coop.asi')
    config = '[Coop]\nHostIP=127.0.0.1\nPort=7440\nModule=NativeCoopProbe\n[Steam]\nSteamHost=0\n[Development]\nExpectedPeers=2\n'
    config += 'FullHostProbe=1\n' if not slot else 'FullClientProbe=1\nCharacterSlot=%d\n' % slot
    (directory/'coop.ini').write_text(config, encoding='ascii')
print('Two-human PvP probe staged; NativeCoopTest saves are unchanged.')
