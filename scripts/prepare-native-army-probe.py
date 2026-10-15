"""Extend the retained encounter test with real roster spawning and host casualty accounting.
Run only with all isolated probe processes stopped. NativeCoopTest is untouched.
"""
from pathlib import Path
import os
import subprocess
root=Path(__file__).resolve().parents[1]
source=root/'runtime/NativeMissionProbe/Source'
triggers=source/'module_simple_triggers.py'
s=triggers.read_text(encoding='cp1254')
s=s.replace('"scn_town_1_arena", "mt_native_session_probe"','"scn_multi_scene_1", "mt_native_session_probe"')
s=s.replace('"mt_native_session_probe", "scn_town_1_arena"','"mt_native_session_probe", "scn_multi_scene_1"')
triggers.write_text(s,encoding='cp1254')
missions=source/'module_mission_templates.py'
s=missions.read_text(encoding='cp1254')
# mtf_team_fight aliases the arena flag and makes ordinary casualties
# nonlethal. Friendly labels must use multiplayer ownership instead.
s=s.replace('("native_session_probe", mtf_battle_mode | mtf_team_fight,', '("native_session_probe", mtf_battle_mode,')
s=s.replace('(entry_point_get_position, pos3, ":team"), (agent_set_position, ":agent", pos3),',
    '(store_mul, ":entry", ":team", 32), (entry_point_get_position, pos3, ":entry"), (agent_set_position, ":agent", pos3),')
s=s.replace('(agent_equip_item, ":agent", "itm_practice_sword", 0),',
    '(agent_equip_item, ":agent", "itm_practice_sword", 0),\n            (player_get_party_id, ":party", ":player"),\n            (player_get_troop_id, ":hero", ":player"),\n            (agent_set_slot, ":agent", 6100, ":party"), (agent_set_slot, ":agent", 6101, ":hero"),\n            (agent_set_slot, ":agent", 6103, 1),\n            (team_set_leader, ":team", ":agent"),')
start=s.index('    (0.25, 0, 0, [(multiplayer_is_server), (eq, "$g_cycle_result_sent", 0),')
end=s.index('    (1, 0, 0, [], [',start)
s=s[:start]+r'''    common_battle_init_banner,
    # Full roster spawn and authoritative per-agent accounting.
    (0.1, 0, 0, [(multiplayer_is_server), (eq, "$g_cycle_armies_spawned", 0)], [
        (assign, ":humans", 0),
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (player_slot_eq, ":player", 6001, 1), (val_add, ":humans", 1),
        (try_end), (eq, ":humans", 2),
        (assign, "$g_cycle_armies_spawned", 1), (assign, "$g_full_probe_map_ready", 0),
        (assign, "$g_full_probe_resume_ready", 0), (assign, "$g_cycle_resume_sent", 0),
        (try_for_players, ":ack_player", 1), (player_is_active, ":ack_player"),
            (player_set_slot, ":ack_player", 6004, 0), (player_set_slot, ":ack_player", 6006, 0),
        (try_end),
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (player_get_party_id, ":party", ":player"), (player_get_troop_id, ":hero", ":player"),
            (player_get_team_no, ":team", ":player"), (store_mul, ":entry", ":team", 32),
            (party_get_num_companion_stacks, ":stacks", ":party"),
            (assign, ":spawned", 0),
            (try_for_range, ":stack", 0, ":stacks"),
                (party_stack_get_troop_id, ":troop", ":party", ":stack"),
                (store_mul, ":loss_slot", ":troop", 2), (val_add, ":loss_slot", 6200),
                (store_add, ":wound_slot", ":loss_slot", 1),
                (party_set_slot, ":party", ":loss_slot", 0), (party_set_slot, ":party", ":wound_slot", 0),
                (party_stack_get_size, ":size", ":party", ":stack"),
                (party_stack_get_num_wounded, ":wounded", ":party", ":stack"),
                (store_sub, ":healthy", ":size", ":wounded"), (neq, ":troop", ":hero"),
                # Hero wound counts can lag their native recovering health.
                (try_begin), (troop_is_hero, ":troop"),
                    (store_troop_health, ":health", ":troop"), (assign, ":healthy", 0),
                    (try_begin), (gt, ":health", 15), (assign, ":healthy", ":size"), (try_end),
                (try_end),
                (try_for_range, ":soldier", 0, ":healthy"),
                    (entry_point_get_position, pos4, ":entry"),
                    (store_mod, ":column", ":spawned", 10), (store_div, ":row", ":spawned", 10),
                    (store_mul, ":x", ":column", 150), (val_sub, ":x", 750),
                    (store_mul, ":y", ":row", 150), (val_sub, ":y", 600),
                    (position_move_x, pos4, ":x"), (position_move_y, pos4, ":y"),
                    (set_spawn_position, pos4), (spawn_agent, ":troop"), (assign, ":agent", reg0),
                    (agent_set_team, ":agent", ":team"), (agent_set_group, ":agent", ":player"),
                    (agent_set_slot, ":agent", 6100, ":party"), (agent_set_slot, ":agent", 6101, ":troop"),
                    (val_add, ":spawned", 1),
                (try_end),
            (try_end),
            (assign, reg1, ":spawned"), (str_store_player_username, s1, ":player"),
            (display_message, "@[ARMY TEST] {s1}: {reg1} healthy roster troops spawned"),
            (team_give_order, ":player", grc_everyone, mordr_charge),
        (try_end),
    ]),
    (ti_on_agent_killed_or_wounded, 0, 0, [(multiplayer_is_server)], [
        (store_trigger_param_1, ":agent"), (store_trigger_param_3, ":wounded"),
        (agent_is_human, ":agent"), (agent_slot_eq, ":agent", 6102, 0),
        (agent_get_slot, ":party", ":agent", 6100), (gt, ":party", 0),
        (agent_get_slot, ":troop", ":agent", 6101), (ge, ":troop", 0),
        (agent_set_slot, ":agent", 6102, 1),
        # Heroes are always wounded even if the native animation is lethal.
        (try_begin), (this_or_next|troop_is_hero, ":troop"), (agent_slot_eq, ":agent", 6103, 1), (assign, ":wounded", 1), (try_end),
        (store_mul, ":loss_slot", ":troop", 2), (val_add, ":loss_slot", 6200),
        (try_begin), (eq, ":wounded", 1), (val_add, ":loss_slot", 1), (try_end),
        (party_get_slot, ":losses", ":party", ":loss_slot"), (val_add, ":losses", 1),
        (party_set_slot, ":party", ":loss_slot", ":losses"),
    ]),
    (0.25, 0, 0, [(multiplayer_is_server), (eq, "$g_cycle_result_sent", 0),
        (eq, "$g_cycle_armies_spawned", 1)], [
        (assign, ":side0", 0), (assign, ":side1", 0),
        (try_for_agents, ":agent"), (agent_is_human, ":agent"), (agent_is_alive, ":agent"),
            (agent_get_team, ":team", ":agent"),
            (try_begin), (eq, ":team", 0), (val_add, ":side0", 1),
            (else_try), (eq, ":team", 1), (val_add, ":side1", 1), (try_end),
        (try_end),
        (this_or_next|eq, ":side0", 0), (eq, ":side1", 0),
        (assign, "$g_cycle_result_sent", 1),
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (player_get_party_id, ":party", ":player"),
            (player_get_troop_id, ":hero", ":player"),
            (party_get_num_companion_stacks, ":stacks", ":party"),
            (assign, ":total_killed", 0), (assign, ":total_wounded", 0),
            (try_for_range_backwards, ":stack", 0, ":stacks"),
                (party_stack_get_troop_id, ":troop", ":party", ":stack"),
                (store_mul, ":loss_slot", ":troop", 2), (val_add, ":loss_slot", 6200),
                (store_add, ":wound_slot", ":loss_slot", 1),
                (party_get_slot, ":killed", ":party", ":loss_slot"),
                (party_get_slot, ":wounded", ":party", ":wound_slot"),
                (try_begin), (this_or_next|troop_is_hero, ":troop"), (eq, ":troop", ":hero"),
                    (val_add, ":wounded", ":killed"), (assign, ":killed", 0),
                    (try_begin), (gt, ":wounded", 0), (troop_set_health, ":troop", 0), (try_end),
                (try_end),
                (party_remove_members, ":party", ":troop", ":killed"),
                (party_wound_members, ":party", ":troop", ":wounded"),
                (val_add, ":total_killed", ":killed"), (val_add, ":total_wounded", ":wounded"),
            (try_end),
            (party_leave_cur_battle, ":party"), (enable_party, ":party"),
            (call_script, "script_coop_save_character", ":player"),
            (player_set_slot, ":player", 6010, ":total_killed"), (player_set_slot, ":player", 6011, ":total_wounded"),
            (multiplayer_send_3_int_to_player, ":player", multiplayer_event_multiplayer_campaign_server_events, 68,
                "$g_cycle_attacker_party", "$g_cycle_defender_party"),
        (try_end),
        (assign, "$g_full_host_probe_request", 4),
        (display_message, "@[ARMY TEST] losses committed once; returning armies to campaign"),
    ]),
'''+s[end:]
# Battle controls are validated by the host, not by a client win report.
s=s.replace('(team_set_relation, 0, 1, -1),\n        (assign, "$g_full_probe_client_ack_sent", 1),', '(team_set_relation, 0, 1, -1),\n        (assign, "$g_full_probe_client_ack_sent", 1),')
s=s.replace('(assign, "$g_full_probe_client_ack_sent", 1),', '(team_set_faction, 0, "fac_kingdom_1"), (team_set_faction, 1, "fac_kingdom_2"), (assign, "$g_full_probe_client_ack_sent", 1),',1)
s=s.replace('(team_set_relation, 0, 1, -1),\n        (assign, "$g_cycle_order_division", grc_everyone),', '(team_set_relation, 0, 1, -1),\n        (team_set_faction, 0, "fac_kingdom_1"), (team_set_faction, 1, "fac_kingdom_2"),\n        (assign, "$g_cycle_order_division", grc_everyone),',1)
s=s.replace('(team_set_leader, ":team", ":agent"),',
    '(store_faction_of_party, ":realm", ":party"), (team_set_faction, ":team", ":realm"),\n            (team_set_leader, ":player", ":agent"),')
s=s.replace('(this_or_next|eq, ":side0", 0), (eq, ":side1", 0),',
    '(this_or_next|gt, "$g_cycle_retreat_requested", 0), (this_or_next|eq, ":side0", 0), (eq, ":side1", 0),')
s=s.replace('        (assign, "$g_cycle_result_sent", 1),',
    '        (assign, "$g_cycle_result_sent", 1), (assign, "$g_full_host_probe_request", 4),')
# Team hostility must be present locally for native friendly markers too.
s=s.replace('(assign, "$g_full_probe_client_ack_sent", 1),', '(assign, "$g_full_probe_client_ack_sent", 1), (assign, "$g_multiplayer_allow_player_banners", 1), (assign, "$g_cycle_order_division", grc_everyone),')
s=s.replace('    (1, 0, 0, [], [', r'''    (0.2, 0, 0, [(multiplayer_is_server), (eq, "$g_cycle_result_sent", 0)], [
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (player_get_agent_id, ":current", ":player"),
            (assign, ":fallen", 0),
            (try_begin), (lt, ":current", 0), (assign, ":fallen", 1),
            (else_try), (neg|agent_is_alive, ":current"), (assign, ":fallen", 1), (try_end),
            (eq, ":fallen", 1), (player_get_party_id, ":party", ":player"),
            (assign, ":replacement", -1),
            (try_for_agents, ":candidate"), (lt, ":replacement", 0),
                (agent_is_human, ":candidate"), (agent_is_alive, ":candidate"),
                (agent_slot_eq, ":candidate", 6100, ":party"),
                (agent_get_player_id, ":controller", ":candidate"), (lt, ":controller", 0),
                (assign, ":replacement", ":candidate"),
            (try_end), (ge, ":replacement", 0),
            (player_control_agent, ":player", ":replacement"),
            (player_get_team_no, ":team", ":player"), (team_set_leader, ":player", ":replacement"),
            (display_message, "@[ARMY TEST] surviving soldier assigned; commander ownership retained"),
        (try_end),
    ]),
    (0, 0, 0, [(neg|multiplayer_is_server), (key_clicked, key_tab)], [
        (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 46),
    ]),
    (ti_tab_pressed, 0, 0, [(neg|multiplayer_is_server)], [
        (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 46),
    ]),
    (0, 0, 0, [(neg|multiplayer_is_server)], [
        (team_set_relation, 0, 1, -1),
        (try_begin), (key_clicked, key_0), (assign, "$g_cycle_order_division", grc_everyone),
        (else_try), (key_clicked, key_1), (assign, "$g_cycle_order_division", grc_infantry),
        (else_try), (key_clicked, key_2), (assign, "$g_cycle_order_division", grc_archers),
        (else_try), (key_clicked, key_3), (assign, "$g_cycle_order_division", grc_cavalry), (try_end),
        (assign, ":order", -1), (store_mission_timer_a, ":seconds"),
        (try_begin), (eq, "$g_cycle_order_menu", 1),
            (try_begin), (key_clicked, key_f1), (assign, ":order", mordr_hold),
            (else_try), (key_clicked, key_f2), (assign, ":order", mordr_follow),
            (else_try), (key_clicked, key_f3), (assign, ":order", mordr_charge),
            (else_try), (key_clicked, key_f4), (assign, ":order", mordr_stand_ground),
            (else_try), (key_clicked, key_f5),
                (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 46),
                (assign, "$g_cycle_order_menu", 0),
            (try_end),
            (try_begin), (gt, ":seconds", "$g_cycle_order_until"), (assign, "$g_cycle_order_menu", 0), (try_end),
        (else_try), (key_clicked, key_f1),
            (assign, "$g_cycle_order_menu", 1), (store_add, "$g_cycle_order_until", ":seconds", 5),
        (try_end),
        (try_begin), (ge, ":order", 0),
            (multiplayer_send_3_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 47,
                "$g_cycle_order_division", ":order"), (assign, "$g_cycle_order_menu", 0),
        (try_end),
    ]),
    (1, 0, 0, [], [''', 1)
s=s.replace('(team_set_relation, 0, 1, -1),\n        (assign, "$g_full_probe_notified", 0),',
    '(team_set_relation, 0, 1, -1),\n        (assign, "$g_cycle_order_division", grc_everyone),\n        (assign, "$g_multiplayer_allow_player_banners", 1),\n        (assign, "$g_full_probe_notified", 0),')
missions.write_text(s,encoding='cp1254')
scripts=source/'module_coop_scripts.py'
s=scripts.read_text(encoding='cp1254')
s=s.replace('(assign, "$g_cycle_defender", ":defender"),',
    '(assign, "$g_cycle_defender", ":defender"),\n                (assign, "$g_cycle_attacker_party", ":party"), (assign, "$g_cycle_defender_party", ":opponent"),\n                (assign, "$g_cycle_result_sent", 0), (assign, "$g_cycle_armies_spawned", 0),')
s=s.replace('(assign, "$g_full_probe_remote_request", 5),',
    '(store_script_param, "$g_cycle_return_party_a", 2), (store_script_param, "$g_cycle_return_party_b", 3),\n                    (assign, "$g_cycle_map_restore", 1),\n                    (assign, "$g_full_probe_remote_request", 5),')
if '# ARMY_CONTROL_RPC' not in s:
    s+=r'''
# ARMY_CONTROL_RPC
for control_name, control_operations in coop_scripts:
    if control_name == "multiplayer_campaign_client_events":
        for control_index, control_operation in enumerate(control_operations):
            if isinstance(control_operation, tuple) and control_operation[:2] == (eq, ":event_type"):
                control_operations[control_index:control_index] = [
                    (eq, ":event_type", 48), (multiplayer_is_server), (player_is_active, ":player_no"),
                    (eq, "$g_full_host_probe_request", 4), (player_slot_eq, ":player_no", 6004, 0),
                    (player_set_slot, ":player_no", 6004, 1), (val_add, "$g_full_probe_map_ready", 1),
                    (else_try),
                    (eq, ":event_type", 46), (multiplayer_is_server), (player_is_active, ":player_no"),
                    (eq, "$g_cycle_result_sent", 0), (eq, "$g_cycle_armies_spawned", 1), (eq, "$g_cycle_retreat_requested", 0),
                    (player_get_agent_id, ":controlled", ":player_no"), (ge, ":controlled", 0),
                    (agent_is_alive, ":controlled"), (player_get_team_no, ":team", ":player_no"),
                    (player_get_party_id, ":party", ":player_no"),
                    (set_fixed_point_multiplier, 100), (agent_get_position, pos10, ":controlled"),
                    (assign, ":near_enemy", 0),
                    (try_for_agents, ":enemy"), (agent_is_human, ":enemy"), (agent_is_alive, ":enemy"),
                        (agent_get_team, ":enemy_team", ":enemy"), (teams_are_enemies, ":team", ":enemy_team"),
                        (agent_get_position, pos11, ":enemy"),
                        (get_distance_between_positions, ":distance", pos10, pos11),
                        (lt, ":distance", 1500), (assign, ":near_enemy", 1),
                    (try_end),
                    (try_begin), (eq, ":near_enemy", 0),
                        (store_random_in_range, ":cover_needed", 2, 6), (assign, ":cover_losses", 0),
                        (try_for_agents, ":cover"), (lt, ":cover_losses", ":cover_needed"),
                            (agent_is_human, ":cover"), (agent_is_alive, ":cover"),
                            (agent_slot_eq, ":cover", 6100, ":party"), (agent_slot_eq, ":cover", 6102, 0),
                            (neq, ":cover", ":controlled"),
                            (agent_get_slot, ":troop", ":cover", 6101), (neg|troop_is_hero, ":troop"),
                            (agent_slot_eq, ":cover", 6103, 0),
                            (store_mul, ":loss_slot", ":troop", 2), (val_add, ":loss_slot", 6200),
                            (party_get_slot, ":losses", ":party", ":loss_slot"), (val_add, ":losses", 1),
                            (party_set_slot, ":party", ":loss_slot", ":losses"),
                            (agent_set_slot, ":cover", 6102, 1), (val_add, ":cover_losses", 1),
                        (try_end),
                        (assign, "$g_cycle_retreat_requested", 1),
                        (player_set_slot, ":player_no", 6012, ":cover_losses"),
                        (multiplayer_send_2_int_to_player, ":player_no", multiplayer_event_multiplayer_campaign_server_events, 69, ":cover_losses"),
                    (else_try),
                        (multiplayer_send_2_int_to_player, ":player_no", multiplayer_event_multiplayer_campaign_server_events, 69, -1),
                    (try_end),
                    (else_try),
                    (eq, ":event_type", 47), (multiplayer_is_server), (player_is_active, ":player_no"),
                    (eq, "$g_cycle_result_sent", 0), (eq, "$g_cycle_armies_spawned", 1),
                    (store_script_param, ":division", 3), (store_script_param, ":order", 4),
                    (this_or_next|is_between, ":division", 0, 4), (eq, ":division", grc_everyone),
                    (this_or_next|is_between, ":order", mordr_hold, mordr_charge+1), (eq, ":order", mordr_stand_ground),
                    (player_get_agent_id, ":controlled", ":player_no"), (ge, ":controlled", 0), (agent_is_alive, ":controlled"),
                    (player_get_team_no, ":team", ":player_no"),
                    (agent_get_position, pos10, ":controlled"), (team_set_order_position, ":team", ":division", pos10),
                    (team_give_order, ":team", ":division", ":order"),
                    (else_try),
                ]
                break
    if control_name == "multiplayer_campaign_server_events":
        for control_index, control_operation in enumerate(control_operations):
            if isinstance(control_operation, tuple) and control_operation[:2] == (eq, ":event_type"):
                control_operations[control_index:control_index] = [
                    (eq, ":event_type", 69), (store_script_param, reg1, 2),
                    (try_begin), (lt, reg1, 0), (display_message, "@Cannot retreat: an enemy is within 15 metres."),
                    (else_try), (display_message, "@Retreating. {reg1} soldiers are lost covering the withdrawal."), (try_end),
                    (else_try),
                ]
                break
'''
s=s.replace('(eq, "$g_cycle_result_sent", 0), (eq, "$g_cycle_armies_spawned", 1),\n                    (player_get_agent_id, ":controlled",', '(eq, "$g_cycle_result_sent", 0), (eq, "$g_cycle_armies_spawned", 1), (eq, "$g_cycle_retreat_requested", 0),\n                    (player_get_agent_id, ":controlled",',1)
s=s.replace('(store_script_param, ":division", 2), (store_script_param, ":order", 3),', '(store_script_param, ":division", 3), (store_script_param, ":order", 4),')
if '(eq, ":event_type", 48)' not in s:
    s=s.replace('(eq, ":event_type", 46), (multiplayer_is_server), (player_is_active, ":player_no"),', '''(eq, ":event_type", 48), (multiplayer_is_server), (player_is_active, ":player_no"),
                    (eq, "$g_full_host_probe_request", 4), (player_slot_eq, ":player_no", 6004, 0),
                    (player_set_slot, ":player_no", 6004, 1), (val_add, "$g_full_probe_map_ready", 1),
                    (else_try),
                    (eq, ":event_type", 46), (multiplayer_is_server), (player_is_active, ":player_no"),''',1)
s=s.replace('(assign, "$g_cycle_armies_spawned", 0),', '(assign, "$g_cycle_armies_spawned", 0), (assign, "$g_cycle_retreat_requested", 0),')
s=s.replace('(team_set_order_position, ":team", ":division", pos10)', '(team_set_order_position, ":player_no", ":division", pos10)')
s=s.replace('(team_give_order, ":team", ":division", ":order")', '(team_give_order, ":player_no", ":division", ":order")')
if '(eq, ":event_type", 49), (multiplayer_is_server)' not in s:
    s=s.replace('(eq, ":event_type", 48), (multiplayer_is_server)', '''(eq, ":event_type", 49), (multiplayer_is_server), (player_is_active, ":player_no"),
                    (eq, "$g_cycle_result_sent", 1), (player_slot_eq, ":player_no", 6006, 0),
                    (player_set_slot, ":player_no", 6006, 1), (val_add, "$g_full_probe_resume_ready", 1),
                    (else_try),
                    (eq, ":event_type", 48), (multiplayer_is_server)''',1)
    s=s.replace('(eq, ":event_type", 69), (store_script_param, reg1, 2),', '''(eq, ":event_type", 70), (assign, "$g_full_probe_remote_request", 7),
                    (assign, "$g_cycle_resume_ack_pending", 1),
                    (else_try),
                    (eq, ":event_type", 69), (store_script_param, reg1, 2),''',1)
s=s.replace('(eq, "$g_cycle_result_sent", 1), (player_slot_eq, ":player_no", 6006, 0),', '(eq, "$g_cycle_result_sent", 1), (eq, "$g_full_host_probe_request", 3), (player_slot_eq, ":player_no", 6004, 1), (player_slot_eq, ":player_no", 6006, 0),')
# Native campaign deltas omit stack changes made while the mission owns the
# replication tables. Push an absolute roster on the retained reliable stream
# after the client's campaign decoder acknowledgement. Preserve prisoners.
if '# ARMY_RETURN_ROSTER' not in s:
    s=s.replace('(val_add, "$g_full_probe_resume_ready", 1),', '(val_add, "$g_full_probe_resume_ready", 1),\n                    (call_script, "script_coop_probe_push_return_rosters", ":player_no"),',1)
    s=s.replace('(eq, ":event_type", 70),', '''(eq, ":event_type", 71), (store_script_param, "$g_cycle_roster_party", 2),
                    (ge, "$g_cycle_roster_party", multiplayer_campaign_player_parties_begin),
                    (party_get_num_companion_stacks, ":stacks", "$g_cycle_roster_party"),
                    (try_for_range_backwards, ":stack", 0, ":stacks"),
                        (party_stack_get_troop_id, ":troop", "$g_cycle_roster_party", ":stack"),
                        (party_stack_get_size, ":size", "$g_cycle_roster_party", ":stack"),
                        (party_remove_members, "$g_cycle_roster_party", ":troop", ":size"),
                    (try_end), (enable_party, "$g_cycle_roster_party"),
                    (else_try),
                    (eq, ":event_type", 72), (store_script_param, ":troop", 2),
                    (store_script_param, ":size", 3), (store_script_param, ":wounded", 4),
                    (ge, "$g_cycle_roster_party", multiplayer_campaign_player_parties_begin),
                    (party_add_members, "$g_cycle_roster_party", ":troop", ":size"),
                    (party_wound_members, "$g_cycle_roster_party", ":troop", ":wounded"),
                    (try_begin), (troop_is_hero, ":troop"), (gt, ":wounded", 0),
                        (troop_set_health, ":troop", 0),
                    (try_end),
                    (else_try),
                    (eq, ":event_type", 70),''',1)
    s+=r'''
# ARMY_RETURN_ROSTER
coop_scripts += [("coop_probe_push_return_rosters", [
    (store_script_param, ":recipient", 1),
    (try_for_range, ":side", 0, 2),
        (assign, ":party", "$g_cycle_attacker_party"),
        (try_begin), (eq, ":side", 1), (assign, ":party", "$g_cycle_defender_party"), (try_end),
        (multiplayer_send_2_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events, 71, ":party"),
        (party_get_num_companion_stacks, ":stacks", ":party"),
        (try_for_range, ":stack", 0, ":stacks"),
            (party_stack_get_troop_id, ":troop", ":party", ":stack"),
            (party_stack_get_size, ":size", ":party", ":stack"),
            (party_stack_get_num_wounded, ":wounded", ":party", ":stack"),
            (multiplayer_send_4_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events, 72, ":troop", ":size", ":wounded"),
        (try_end),
    (try_end),
    (call_script, "script_coop_send_char_sync_to_client", ":recipient"),
    (call_script, "script_coop_send_party_upgradeable_to_client", ":recipient"),
])]
'''
scripts.write_text(s,encoding='cp1254')
s=triggers.read_text(encoding='cp1254')
if '# ARMY_MAP_RESTORE' not in s:
    s+=r'''
# ARMY_MAP_RESTORE
simple_triggers += [(0, [
    (multiplayer_is_campaign), (neg|multiplayer_is_server),
    (eq, "$g_cycle_map_restore", 1), (eq, "$g_full_probe_remote_request", 8),
    (try_begin), (party_is_active, "$g_cycle_return_party_a"),
        (party_leave_cur_battle, "$g_cycle_return_party_a"), (enable_party, "$g_cycle_return_party_a"),
    (try_end),
    (try_begin), (party_is_active, "$g_cycle_return_party_b"),
        (party_leave_cur_battle, "$g_cycle_return_party_b"), (enable_party, "$g_cycle_return_party_b"),
    (try_end),
    (multiplayer_get_my_player, ":player"), (player_get_party_id, ":party", ":player"),
    (set_camera_follow_party, ":party", 1),
    (assign, "$g_cycle_map_restore", 0),
    (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 48),
    (display_message, "@[ARMY TEST] retained map restored"),
])]
'''
if '(multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 48)' not in s:
    s=s.replace('(assign, "$g_cycle_map_restore", 0),', '(assign, "$g_cycle_map_restore", 0),\n    (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 48),',1)
s=s.replace('(eq, "$g_cycle_map_restore", 1), (eq, "$g_full_probe_remote_request", 0),', '(eq, "$g_cycle_map_restore", 1), (eq, "$g_full_probe_remote_request", 8),')
if '# RETURN_REPLICATION_RESUME' not in s:
    s+=r'''
# RETURN_REPLICATION_RESUME
simple_triggers += [(0, [
    (multiplayer_is_server), (multiplayer_is_campaign), (eq, "$g_full_host_probe_request", 3),
    (eq, "$g_cycle_result_sent", 1), (eq, "$g_cycle_resume_sent", 0),
    (try_for_players, ":player", 1), (player_is_active, ":player"),
        (multiplayer_send_int_to_player, ":player", multiplayer_event_multiplayer_campaign_server_events, 70),
    (try_end), (assign, "$g_cycle_resume_sent", 1),
]), (0, [
    (neg|multiplayer_is_server), (multiplayer_is_campaign), (eq, "$g_full_probe_remote_request", 0),
    (eq, "$g_cycle_resume_ack_pending", 1), (assign, "$g_cycle_resume_ack_pending", 0),
    (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events, 49),
])]
'''
# Disabled parties deliberately fail party_is_active. The validated return
# IDs are persistent player parties, so enable them before asking activity.
s=s.replace('(party_is_active, "$g_cycle_return_party_a")', '(ge, "$g_cycle_return_party_a", multiplayer_campaign_player_parties_begin)')
s=s.replace('(party_is_active, "$g_cycle_return_party_b")', '(ge, "$g_cycle_return_party_b", multiplayer_campaign_player_parties_begin)')
triggers.write_text(s,encoding='cp1254')
rpc_source=source/'module_scripts.py'
rpc_text=rpc_source.read_text(encoding='cp1254').replace('(this_or_next|multiplayer_is_campaign), (eq, "$g_full_host_probe_request", 3),','(this_or_next|multiplayer_is_campaign), (is_between, "$g_full_host_probe_request", 3, 5),')
if '# COOP_NATIVE_SAVED_WORLD_BOOTSTRAP' not in rpc_text:
    rpc_text+=r'''
# COOP_NATIVE_SAVED_WORLD_BOOTSTRAP
# A saved module latch cannot represent a socket in a new process. Rearm the
# isolated graphical host when WSE finishes loading a local campaign file.
for load_name, load_operations in scripts:
    if load_name == "wse_savegame_loaded":
        load_operations += [
            (try_begin), (neg|game_in_multiplayer_mode),
                (call_script, "script_coop_server_session_reset"),
                (assign, "$g_native_probe_started", 0), (assign, "$g_full_probe_peer_ready", 0),
                (assign, "$g_encounter_cycle_requested", 0), (assign, "$g_cycle_result_sent", 0),
                (assign, "$g_cycle_resume_sent", 0), (assign, "$g_pvp_host_named", 0),
                (assign, "$g_full_host_probe_request", 1),
            (try_end),
        ]
'''
rpc_source.write_text(rpc_text,encoding='cp1254')
presentations=source/'module_presentations.py'
presentation_text=presentations.read_text(encoding='cp1254')
if '# COOP_FRIENDLY_OVERHEAD_BANNERS' not in presentation_text:
    presentation_text+=r'''
# COOP_FRIENDLY_OVERHEAD_BANNERS
# Client-local overlays follow the current controller's team, including after
# takeover. A bounded pool avoids one allocation per soldier per frame.
presentations += [("coop_friendly_overhead", prsntf_read_only, 0, [
    (ti_on_presentation_load, [
        (set_fixed_point_multiplier, 1000),
        (multiplayer_get_my_player, ":player"),
        (profile_get_banner_id, ":banner"),
        (store_add, ":mesh", ":banner", arms_meshes_begin),
        (try_begin), (neg|is_between, ":mesh", arms_meshes_begin, arms_meshes_end_minus_one),
            (assign, ":mesh", "mesh_arms_a01"), (try_end),
        (init_position, pos20), (position_set_x, pos20, 120), (position_set_y, pos20, 120),
        (try_for_range, ":slot", 16000, 16128),
            (create_mesh_overlay, ":overlay", ":mesh"),
            (overlay_set_size, ":overlay", pos20), (overlay_set_alpha, ":overlay", 0),
            (player_set_slot, ":player", ":slot", ":overlay"),
        (try_end), (presentation_set_duration, 999999),
    ]),
    (ti_on_presentation_run, [
        (set_fixed_point_multiplier, 1000),
        (try_begin), (ge, "$g_full_probe_remote_request", 5),
            (presentation_set_duration, 0),
        (else_try),
            (multiplayer_get_my_player, ":player"), (player_get_team_no, ":team", ":player"),
            (player_get_agent_id, ":controlled", ":player"),
            (mission_cam_get_position, pos20), (assign, ":next_slot", 16000),
            (try_for_range, ":slot", 16000, 16128),
                (player_get_slot, ":overlay", ":player", ":slot"), (overlay_set_alpha, ":overlay", 0),
            (try_end),
            (try_for_agents, ":agent"), (lt, ":next_slot", 16128),
                (agent_is_human, ":agent"), (agent_is_alive, ":agent"), (neq, ":agent", ":controlled"),
                (agent_get_team, ":agent_team", ":agent"), (eq, ":agent_team", ":team"),
                (agent_get_position, pos21, ":agent"),
                (get_distance_between_positions, ":distance", pos20, pos21), (le, ":distance", 100000),
                (position_move_z, pos21, 2300), (neg|position_is_behind_position, pos20, pos21),
                (position_get_screen_projection, pos22, pos21),
                (position_get_x, ":x", pos22), (position_get_y, ":y", pos22),
                (is_between, ":x", 10, 990), (is_between, ":y", 10, 740),
                (player_get_slot, ":overlay", ":player", ":next_slot"),
                (overlay_set_position, ":overlay", pos22), (overlay_set_alpha, ":overlay", 220),
                (val_add, ":next_slot", 1),
            (try_end),
        (try_end),
    ]),
])]
'''
    presentations.write_text(presentation_text,encoding='cp1254')
mission_text=missions.read_text(encoding='cp1254')
if '"prsnt_coop_friendly_overhead"' not in mission_text:
    mission_text+=r'''
# COOP_FRIENDLY_OVERHEAD_BANNERS
for banner_mission in mission_templates:
    if banner_mission[0] == "native_session_probe":
        banner_mission[5].append((ti_after_mission_start, 0, 0, [(neg|multiplayer_is_server)], [
            (start_presentation, "prsnt_coop_friendly_overhead"),
        ]))
'''
    missions.write_text(mission_text,encoding='cp1254')
mission_text=missions.read_text(encoding='cp1254')
if '# COOP_FRIENDLY_OVERHEAD_DELAYED_START' not in mission_text:
    mission_text+=r'''
# COOP_FRIENDLY_OVERHEAD_DELAYED_START
# Native tactical-window initialization clears presentations created during
# MetaMission.start. Start again after the replicated player agent exists.
for banner_mission in mission_templates:
    if banner_mission[0] == "native_session_probe":
        banner_mission[5].append((0.25, 0, 0, [
            (neg|multiplayer_is_server), (lt, "$g_full_probe_remote_request", 5),
            (neg|is_presentation_active, "prsnt_coop_friendly_overhead"),
            (multiplayer_get_my_player, ":player"), (player_get_agent_id, ":agent", ":player"),
            (ge, ":agent", 0), (agent_is_alive, ":agent"),
        ], [(start_presentation, "prsnt_coop_friendly_overhead")]))
'''
    missions.write_text(mission_text,encoding='cp1254')
env=dict(os.environ,WARBAND_EXPORT_DIR=str(root/'runtime/NativeMissionProbe/Game/Modules/NativeCoopProbe'))
with (root/'logs/native-army-module-build.log').open('w') as output:
    subprocess.run([str(root/'tools/python27-extract/SourceDir/python.exe'),'-B',str(source/'run_module_build.py')],cwd=source,env=env,stdout=output,stderr=subprocess.STDOUT,check=True)
print('Retained encounter army test compiled; heroes are wound-only and losses are host-counted.')
