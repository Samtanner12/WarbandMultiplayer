"""Stage the full-engine host experiment into the existing isolated probe.

Never touches either LocalTest character or the installed Steam game.
Run only while NativeMissionProbe processes are stopped.
"""
from pathlib import Path
import os
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
source = root / 'runtime/NativeMissionProbe/Source'
game = root / 'runtime/NativeMissionProbe/Game'
menus = source / 'module_game_menus.py'
text = menus.read_text(encoding='cp1254')
marker = '# FULL_ENGINE_HOST_PROBE'
if marker not in text:
    with menus.open('a', encoding='cp1254') as output:
        output.write('''
# FULL_ENGINE_HOST_PROBE
# A fresh diagnostic world needs no playable local host character.
for probe_index, probe_menu in enumerate(game_menus):
    if probe_menu[0] == "start_game_0":
        game_menus[probe_index] = ("start_game_0", 0, "Initializing isolated engine host...", "none", [
            (assign, "$g_full_host_probe_request", 1),
            (change_screen_map),
        ], [])
        break
''')
triggers = source / 'module_simple_triggers.py'
text = triggers.read_text(encoding='cp1254')
peer_condition = '(player_is_active, ":probe_player"), (val_add, ":probe_peers", 1),'
ready_condition = '(player_is_active, ":probe_player"), (player_slot_eq, ":probe_player", slot_player_coop_char_state, coop_char_state_ready), (val_add, ":probe_peers", 1),'
if peer_condition in text:
    text = text.replace(peer_condition, ready_condition)
    triggers.write_text(text, encoding='cp1254')
admission_marker = '# INVITE_BEFORE_NATIVE_MISSION'
if admission_marker not in text:
    request = '        (start_multiplayer_mission, "mt_native_session_probe", "scn_town_1_arena", 1),'
    invite = '''
        # INVITE_BEFORE_NATIVE_MISSION
        (try_for_players, ":probe_player", 1), (player_is_active, ":probe_player"),
            (player_slot_eq, ":probe_player", slot_player_coop_char_state, coop_char_state_ready),
            (multiplayer_send_3_int_to_player, ":probe_player", multiplayer_event_multiplayer_campaign_server_events,
                67, "scn_town_1_arena", "mt_native_session_probe"),
        (try_end),
'''
    if request not in text: raise RuntimeError('Missing native mission request')
    text = text.replace(request, invite + request)
    triggers.write_text(text, encoding='cp1254')
if marker not in text:
    with triggers.open('a', encoding='cp1254') as output:
        output.write('''
# FULL_ENGINE_HOST_PROBE
simple_triggers += [(0, [
    (multiplayer_is_server), (multiplayer_is_campaign),
    (eq, "$g_full_host_probe_request", 3),
    (disable_party, "p_main_party"),
])]
''')
module = game / 'Modules/NativeCoopProbe'
gateway_marker = '# FULL_NATIVE_COMBAT_GATEWAY'
coop_scripts = source/'module_coop_scripts.py'
if gateway_marker not in coop_scripts.read_text(encoding='cp1254'):
    with coop_scripts.open('a', encoding='cp1254') as output:
        output.write('''
# FULL_NATIVE_COMBAT_GATEWAY
for probe_name, probe_operations in coop_scripts:
    if probe_name == "multiplayer_campaign_server_events":
        for probe_index, probe_operation in enumerate(probe_operations):
            if isinstance(probe_operation, tuple) and probe_operation[:2] == (eq, ":event_type"):
                probe_operations[probe_index:probe_index] = [
                    (eq, ":event_type", 67),
                    (store_script_param, "$g_full_probe_remote_scene", 2),
                    (store_script_param, "$g_full_probe_remote_template", 3),
                    (assign, "$g_full_probe_remote_request", 1),
                    (else_try),
                ]
                break
    if probe_name == "multiplayer_campaign_client_events":
        for probe_index, probe_operation in enumerate(probe_operations):
            if isinstance(probe_operation, tuple) and probe_operation[:2] == (eq, ":event_type"):
                probe_operations[probe_index:probe_index] = [
                    (eq, ":event_type", 44),
                    (multiplayer_is_server), (player_is_active, ":player_no"),
                    (player_slot_eq, ":player_no", slot_player_coop_char_state, coop_char_state_ready),
                    (assign, "$g_full_probe_peer_ready", 1),
                    (display_message, "@[PROBE] native combat peer acknowledged scene"),
                    (else_try),
                ]
                break
''')
missions = source/'module_mission_templates.py'
text = missions.read_text(encoding='cp1254')
if gateway_marker not in text:
    # Replace only the previously appended diagnostic mission.
    prefix, separator, _ = text.partition('mission_templates += [("native_session_probe"')
    if not separator: raise RuntimeError('Missing isolated mission probe')
    missions.write_text(prefix + '''
# FULL_NATIVE_COMBAT_GATEWAY
mission_templates += [("native_session_probe", mtf_battle_mode, -1, "Native connection probe", [], [
    (ti_after_mission_start, 0, 0, [(multiplayer_is_server)], [
        (team_set_relation, 0, 1, -1),
        (entry_point_get_position, pos1, 0), (set_spawn_position, pos1),
        (spawn_agent, "trp_looter"), (assign, "$g_probe_agent_a", reg0), (agent_set_team, reg0, 0),
        (entry_point_get_position, pos2, 1), (set_spawn_position, pos2),
        (spawn_agent, "trp_looter"), (assign, "$g_probe_agent_b", reg0), (agent_set_team, reg0, 1),
        (agent_set_scripted_destination, "$g_probe_agent_a", pos2),
        (agent_set_scripted_destination, "$g_probe_agent_b", pos1),
        (store_current_scene, ":probe_scene"),
        (try_for_players, ":probe_player", 1), (player_is_active, ":probe_player"),
            (multiplayer_send_3_int_to_player, ":probe_player", multiplayer_event_multiplayer_campaign_server_events,
                67, ":probe_scene", "mt_native_session_probe"),
        (try_end),
        (display_message, "@[PROBE] authoritative AI mission initialized"),
    ]),
    (0, 0, 0, [(neg|multiplayer_is_server), (eq, "$g_full_probe_client_ack_sent", 0)], [
        (assign, "$g_full_probe_client_ack_sent", 1),
        (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 44),
        (display_message, "@[PROBE] entered combat on campaign connection; F8 ends the client probe"),
    ]),
    (0, 0, 0, [(multiplayer_is_server), (eq, "$g_full_probe_peer_ready", 1)], [
        (try_for_players, ":probe_player", 1), (player_is_active, ":probe_player"),
            (player_get_agent_id, ":probe_agent", ":probe_player"),
            (lt, ":probe_agent", 0),
            (player_get_troop_id, ":probe_troop", ":probe_player"), (ge, ":probe_troop", 0),
            (player_set_team_no, ":probe_player", 0),
            (player_spawn_new_agent, ":probe_player", 0),
            (player_get_agent_id, ":probe_agent", ":probe_player"), (ge, ":probe_agent", 0),
            (call_script, "script_coop_equip_player_agent", ":probe_agent"),
            (assign, "$g_probe_human_agent", ":probe_agent"),
        (try_end),
    ]),
    (0, 0, 0, [(neg|multiplayer_is_server), (key_clicked, key_f8)], [(finish_mission, 0)]),
    (1, 0, 0, [], [
        (store_current_hours, "$g_probe_campaign_hour"),
        (store_mission_timer_a, "$g_probe_mission_seconds"),
        (assign, "$g_probe_alive", 0),
        (try_for_agents, ":probe_agent"), (agent_is_alive, ":probe_agent"),
            (val_add, "$g_probe_alive", 1),
        (try_end),
    ]),
])]
''', encoding='cp1254')
# Send after the native initializer has completed and campaign slot snapshots
# have been restored; ti_after_mission_start runs inside that initializer.
text = missions.read_text(encoding='cp1254')
notify_marker = '# DEFER_NATIVE_PROBE_NOTIFICATION'
if notify_marker not in text:
    begin = text.index('        (store_current_scene, ":probe_scene"),', text.index(gateway_marker))
    end = text.index('        (display_message, "@[PROBE] authoritative AI mission initialized"),', begin)
    text = text[:begin] + '        (assign, "$g_full_probe_notified", 0),\n' + text[end:]
    insertion = text.index('    (0, 0, 0, [(neg|multiplayer_is_server)', text.index(gateway_marker))
    text = text[:insertion] + '''
    # DEFER_NATIVE_PROBE_NOTIFICATION
    (0, 0, 0, [(multiplayer_is_server), (eq, "$g_full_probe_notified", 0)], [
        (store_current_scene, ":probe_scene"), (assign, ":probe_recipients", 0),
        (try_for_players, ":probe_player", 1), (player_is_active, ":probe_player"),
            (multiplayer_send_3_int_to_player, ":probe_player", multiplayer_event_multiplayer_campaign_server_events,
                67, ":probe_scene", "mt_native_session_probe"),
            (val_add, ":probe_recipients", 1),
        (try_end),
        (gt, ":probe_recipients", 0), (assign, "$g_full_probe_notified", 1),
    ]),
''' + text[insertion:]
    missions.write_text(text, encoding='cp1254')
# Native player spawning indexes the template's entry table directly.
# Supply its full 128-entry table before attempting an avatar spawn.
text = missions.read_text(encoding='cp1254')
empty_entries = '"Native connection probe", [], ['
if empty_entries in text:
    text = text.replace(empty_entries,
        '"Native connection probe", [(entry, mtef_visitor_source|mtef_team_0, 0, aif_start_alarmed, 1, []) for entry in range(128)], [', 1)
    missions.write_text(text, encoding='cp1254')
text = missions.read_text(encoding='cp1254')
equip_marker = '# EQUIP_NATIVE_AVATAR_SPAWN'
if equip_marker not in text:
    insertion = text.index('    (ti_after_mission_start', text.index(gateway_marker))
    text = text[:insertion] + '''
    # EQUIP_NATIVE_AVATAR_SPAWN
    (ti_on_agent_spawn, 0, 0, [(multiplayer_is_server)], [
        (store_trigger_param_1, ":probe_agent"),
        (agent_get_player_id, ":probe_player", ":probe_agent"), (gt, ":probe_player", 0),
        (call_script, "script_coop_equip_player_agent", ":probe_agent"),
        (assign, "$g_probe_human_agent", ":probe_agent"),
    ]),
''' + text[insertion:]
    missions.write_text(text, encoding='cp1254')
# Keep both diagnostic looters hostile to the human, and allow their normal
# combat AI to choose its target instead of fighting one another on arrival.
text = missions.read_text(encoding='cp1254')
hostile_marker = '# HOSTILE_HUMAN_COMBAT_PROBE'
if hostile_marker not in text:
    prefix, separator, probe = text.partition(gateway_marker)
    if not separator: raise RuntimeError('Missing isolated combat template')
    probe = probe.replace('(agent_set_team, reg0, 1)', '(agent_set_team, reg0, 0)', 1)
    probe = probe.replace('(agent_set_scripted_destination, "$g_probe_agent_a", pos2)',
        '(agent_clear_scripted_mode, "$g_probe_agent_a")', 1)
    probe = probe.replace('(agent_set_scripted_destination, "$g_probe_agent_b", pos1)',
        '(agent_clear_scripted_mode, "$g_probe_agent_b")', 1)
    probe = probe.replace('(player_set_team_no, ":probe_player", 0)',
        '(player_set_team_no, ":probe_player", 1)', 1)
    spawn = '        (call_script, "script_coop_equip_player_agent", ":probe_agent"),'
    probe = probe.replace(spawn, '''        # HOSTILE_HUMAN_COMBAT_PROBE
        (player_set_team_no, ":probe_player", 1),
        (agent_set_team, ":probe_agent", 1),
''' + spawn + '''
        # Diagnostic-only weapon, equipped on the battle agent. The saved
        # character inventory is not modified by this capability test.
        (agent_equip_item, ":probe_agent", "itm_practice_sword", 0),''', 1)
    missions.write_text(prefix+separator+probe, encoding='cp1254')
# Admission ACK must run during initialization; an unassigned avatar may
# prevent the tactical window from ticking regular mission triggers yet.
text = missions.read_text(encoding='cp1254')
ack_marker = '# ACK_DURING_SCENE_INITIALIZATION'
if ack_marker not in text:
    insertion = text.index('    (ti_after_mission_start', text.index(gateway_marker))
    text = text[:insertion] + '''
    # ACK_DURING_SCENE_INITIALIZATION
    (ti_after_mission_start, 0, 0, [(neg|multiplayer_is_server)], [
        (assign, "$g_full_probe_client_ack_sent", 1),
        (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 44),
    ]),
''' + text[insertion:]
    missions.write_text(text, encoding='cp1254')
# The second invitation is the host's scene-ready confirmation. It cannot
# cause a second initializer or reconnect on an already admitted client.
text = coop_scripts.read_text(encoding='cp1254')
confirm_marker = '# CONFIRM_HOST_SCENE_READY'
if confirm_marker not in text:
    old = '                    (assign, "$g_full_probe_remote_request", 1),'
    if old not in text: raise RuntimeError('Missing initial invitation handler')
    text = text.replace(old, '''                    # CONFIRM_HOST_SCENE_READY
                    (try_begin), (eq, "$g_full_probe_remote_request", 2),
                        (assign, "$g_full_probe_remote_request", 3),
                    (else_try), (eq, "$g_full_probe_remote_request", 0),
                        (assign, "$g_full_probe_remote_request", 1),
                    (try_end),''', 1)
    coop_scripts.write_text(text, encoding='cp1254')
text = missions.read_text(encoding='cp1254')
respawn_marker = '# DIAGNOSTIC_LOADOUT_AND_RESPAWN'
if respawn_marker not in text:
    start = text.index('    (ti_after_mission_start, 0, 0, [(multiplayer_is_server)], [', text.index(gateway_marker))
    insertion = text.index('\n', start)+1
    text = text[:insertion] + '''
        # DIAGNOSTIC_LOADOUT_AND_RESPAWN
        # Native spawning applies player spawn equipment after its callback.
        (try_for_players, ":probe_player", 1), (player_is_active, ":probe_player"),
            (player_set_team_no, ":probe_player", 1),
            (player_add_spawn_item, ":probe_player", ek_item_0, "itm_practice_sword"),
        (try_end),

''' + text[insertion:]
    insertion = text.index('    (1, 0, 0, [], [', text.index(gateway_marker))
    text = text[:insertion] + '''
    (0, 0, 0, [(multiplayer_is_server)], [
        (team_set_relation, 0, 1, -1),
    ]),
    (0, 0, 0, [(neg|multiplayer_is_server), (key_is_down, key_f9)], [
        (store_mission_timer_a, ":probe_seconds"),
        (ge, ":probe_seconds", "$g_probe_respawn_next_key"),
        (store_add, "$g_probe_respawn_next_key", ":probe_seconds", 2),
        (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 45),
    ]),
''' + text[insertion:]
    missions.write_text(text, encoding='cp1254')
    text = coop_scripts.read_text(encoding='cp1254')
    text += '''
# DIAGNOSTIC_LOADOUT_AND_RESPAWN
for probe_name, probe_operations in coop_scripts:
    if probe_name == "multiplayer_campaign_client_events":
        for probe_index, probe_operation in enumerate(probe_operations):
            if isinstance(probe_operation, tuple) and probe_operation[:2] == (eq, ":event_type"):
                probe_operations[probe_index:probe_index] = [
                    (eq, ":event_type", 45), (multiplayer_is_server),
                    (eq, "$g_full_probe_peer_ready", 1), (player_is_active, ":player_no"),
                    (player_slot_eq, ":player_no", slot_player_coop_char_state, coop_char_state_ready),
                    (player_get_agent_id, ":probe_old_agent", ":player_no"),
                    (assign, ":probe_can_respawn", 0),
                    (try_begin), (lt, ":probe_old_agent", 0), (assign, ":probe_can_respawn", 1),
                    (else_try), (neg|agent_is_alive, ":probe_old_agent"), (assign, ":probe_can_respawn", 1),
                    (try_end), (eq, ":probe_can_respawn", 1),
                    (player_set_team_no, ":player_no", 1),
                    (player_add_spawn_item, ":player_no", ek_item_0, "itm_practice_sword"),
                    (player_spawn_new_agent, ":player_no", 0),
                    (store_mission_timer_a, ":probe_seconds"),

                    (team_set_relation, 0, 1, -1),
                    (display_message, "@[PROBE] respawned; combat active immediately"),
                    (else_try),
                ]
                break
'''
    coop_scripts.write_text(text, encoding='cp1254')
scripts_file = source/'module_scripts.py'
text = scripts_file.read_text(encoding='cp1254')
rpc_marker = '# ISOLATED_COMBAT_RPC_AUTHORITY'
if rpc_marker not in text:
    start = text.index('(eq, ":event_type", multiplayer_event_multiplayer_campaign_client_events),')
    guard = text.index('(multiplayer_is_campaign),', start)
    text = text[:guard] + text[guard:].replace('(multiplayer_is_campaign),',
        '# ISOLATED_COMBAT_RPC_AUTHORITY\n\t\t(this_or_next|multiplayer_is_campaign), (eq, "$g_full_host_probe_request", 3),', 1)
    scripts_file.write_text(text, encoding='cp1254')
env = dict(os.environ, WARBAND_EXPORT_DIR=str(module))
with (root / 'logs/full-host-probe-module-build.log').open('w') as output:
    subprocess.run([str(root/'tools/python27-extract/SourceDir/python.exe'), '-B', str(source/'run_module_build.py')],
                   cwd=source, env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
shutil.copy2(root/'build/bin/warband_coop.asi', game/'warband_coop.asi')
config = game/'coop.ini'
text = config.read_text(encoding='ascii')
if '[Development]' not in text:
    config.write_text(text+'\n[Development]\nFullHostProbe=1\n', encoding='ascii')
(game/'full_host_config.ini').write_text(
    '[General]\niMaxFrameRate=60\nbPauseWhenMinimized=false\nsStoragePath=%s\\\n'
    '[Network]\nbLoopbackServer=true\nbAutoSelectClientPort=true\niNumPlayersLimit=250\niServerPort=7440\n' % (game/'WSE'), encoding='ascii')
print('Full graphical engine host probe staged. Only the isolated probe was updated.')
