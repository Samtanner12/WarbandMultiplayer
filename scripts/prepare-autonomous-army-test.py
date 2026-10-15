"""Finite native-engine regression fixtures for the two local test clients.
Creates normal map encounters, then uses engine damage and controller operations.
This never writes process memory or modifies production saves.
"""
from pathlib import Path
import os, subprocess, sys, re
root=Path(__file__).resolve().parents[1]
source=root/'runtime/NativeMissionProbe/Source'
p=source/'module_simple_triggers.py';s=p.read_text(encoding='cp1254')
marker='# FINITE_AUTONOMOUS_ARMY_REGRESSION'
if marker not in s:
    s+=r'''
# FINITE_AUTONOMOUS_ARMY_REGRESSION
simple_triggers += [(0, [
    (multiplayer_is_server), (multiplayer_is_campaign), (eq, "$g_full_host_probe_request", 3),
    (lt, "$g_autotest_round", 2), (eq, "$g_native_probe_started", 0),
    (try_begin), (eq, "$g_autotest_phase", 0),
        (assign, ":players", 0), (assign, ":a", -1), (assign, ":b", -1),
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (player_slot_eq, ":player", slot_player_coop_char_state, coop_char_state_ready),
            (try_begin), (lt, ":a", 0), (assign, ":a", ":player"),
            (else_try), (assign, ":b", ":player"), (try_end), (val_add, ":players", 1),
        (try_end), (eq, ":players", 2),
        (assign, "$g_autotest_a", ":a"), (assign, "$g_autotest_b", ":b"),
        (player_get_party_id, ":pa", ":a"), (player_get_party_id, ":pb", ":b"),
        (store_faction_of_party, ":fa", ":pa"), (store_faction_of_party, ":fb", ":pb"),
        (set_relation, ":fa", ":fb", -50),
        (set_fixed_point_multiplier, 100), (party_get_position, pos12, ":pa"),
        (position_move_x, pos12, 30), (party_set_position, ":pb", pos12),
        (party_set_ai_behavior, ":pa", ai_bhvr_attack_party), (party_set_ai_object, ":pa", ":pb"),
        (party_set_ai_behavior, ":pb", ai_bhvr_hold),
        (assign, "$g_autotest_phase", 1),
        (display_message, "@[AUTOTEST] native map encounter fixture armed"),
    (else_try), (eq, "$g_autotest_phase", 1),
        (player_get_party_id, ":pa", "$g_autotest_a"), (player_get_party_id, ":pb", "$g_autotest_b"),
        (party_get_battle_opponent, ":opponent", ":pa"), (eq, ":opponent", ":pb"),
        (call_script, "script_coop_ev_cli_start_battle", "$g_autotest_a"),
        (assign, "$g_autotest_phase", 2), (assign, "$g_autotest_step", 0),
        (display_message, "@[AUTOTEST] real party battle opponent accepted by encounter route"),
    (else_try), (eq, "$g_autotest_phase", 4), (eq, "$g_cycle_result_sent", 1), (ge, "$g_full_probe_resume_ready", 2),
        (val_add, "$g_autotest_round", 1),
        (assign, reg1, "$g_autotest_round"),
        (display_message, "@[AUTOTEST] completed retained-map round {reg1}"),
        (assign, "$g_autotest_phase", 0),
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (player_get_party_id, ":party", ":player"),
            (party_get_position, pos12, ":party"), (position_move_y, pos12, 50),
            (party_set_position, ":party", pos12),
            (party_set_ai_behavior, ":party", ai_bhvr_hold),
        (try_end),
    (try_end),
])]
'''
    p.write_text(s,encoding='cp1254')
current= (source/'module_simple_triggers.py').read_text(encoding='cp1254')
current=current.replace('(eq, "$g_autotest_phase", 4), (eq, "$g_cycle_result_sent", 1),\n', '(eq, "$g_autotest_phase", 4), (eq, "$g_cycle_result_sent", 1), (ge, "$g_full_probe_resume_ready", 2),\n')
(source/'module_simple_triggers.py').write_text(current,encoding='cp1254')
p=source/'module_mission_templates.py';s=p.read_text(encoding='cp1254')
if marker not in s:
    s+=r'''
# FINITE_AUTONOMOUS_ARMY_REGRESSION
for auto_mission in mission_templates:
    if auto_mission[0] == "native_session_probe":
        auto_mission[5].append((0.25, 0, 0, [
            (multiplayer_is_server), (eq, "$g_cycle_armies_spawned", 1), (eq, "$g_cycle_result_sent", 0),
        ], [
            (store_mission_timer_a, ":seconds"),
            (try_begin), (eq, "$g_autotest_round", 0),
                (try_begin), (eq, "$g_autotest_step", 0), (ge, ":seconds", 4),
                    (player_get_agent_id, ":hero", "$g_autotest_a"), (ge, ":hero", 0),
                    (assign, "$g_autotest_original_agent", ":hero"),
                    (player_get_agent_id, ":enemy", "$g_autotest_b"), (ge, ":enemy", 0),
                    (agent_deliver_damage_to_agent, ":enemy", ":hero", 1000, "itm_sword_medieval_a"),
                    (assign, "$g_autotest_step", 1),
                (else_try), (eq, "$g_autotest_step", 1), (ge, ":seconds", 7),
                    (player_get_agent_id, ":replacement", "$g_autotest_a"), (ge, ":replacement", 0),
                    (neq, ":replacement", "$g_autotest_original_agent"), (agent_is_alive, ":replacement"),
                    (assign, "$g_autotest_takeover_agent", ":replacement"),
                    (call_script, "script_multiplayer_campaign_client_events", "$g_autotest_a", 47, grc_everyone, mordr_hold),
                    (player_get_team_no, ":team", "$g_autotest_a"),
                    (team_get_movement_order, "$g_autotest_order_observed", "$g_autotest_a", grc_infantry),
                    (display_message, "@[AUTOTEST] takeover succeeded; native command order sampled"),
                    (assign, "$g_autotest_step", 2),
                (else_try), (eq, "$g_autotest_step", 2), (ge, ":seconds", 10),
                    (player_get_agent_id, ":controlled", "$g_autotest_a"), (ge, ":controlled", 0),
                    (set_fixed_point_multiplier, 100),
                    (assign, ":best_distance", -1),
                    (player_get_team_no, ":team", "$g_autotest_a"),
                    (try_for_range, ":corner", 0, 4),
                        (init_position, pos12), (store_mod, ":x", ":corner", 2), (store_div, ":y", ":corner", 2),
                        (val_mul, ":x", 17000), (val_add, ":x", 1000), (val_mul, ":y", 17000), (val_add, ":y", 1000),
                        (position_set_x, pos12, ":x"), (position_set_y, pos12, ":y"),
                        (assign, ":nearest", 100000),
                        (try_for_agents, ":enemy"), (agent_is_human, ":enemy"), (agent_is_alive, ":enemy"),
                            (agent_get_team, ":enemy_team", ":enemy"), (teams_are_enemies, ":team", ":enemy_team"),
                            (agent_get_position, pos13, ":enemy"), (get_distance_between_positions, ":distance", pos12, pos13),
                            (val_min, ":nearest", ":distance"),
                        (try_end),
                        (try_begin), (gt, ":nearest", ":best_distance"),
                            (assign, ":best_distance", ":nearest"), (copy_position, pos14, pos12),
                        (try_end),
                    (try_end),
                    (agent_set_position, ":controlled", pos14),
                    (call_script, "script_multiplayer_campaign_client_events", "$g_autotest_a", 46),
                    (eq, "$g_cycle_retreat_requested", 1),
                    (assign, "$g_autotest_step", 3), (assign, "$g_autotest_phase", 4),
                    (display_message, "@[AUTOTEST] safe retreat accepted with host covering-loss accounting"),
                (try_end),
            (else_try), (eq, "$g_autotest_round", 1), (eq, "$g_autotest_step", 0), (ge, ":seconds", 8),
                (player_get_team_no, ":losing_team", "$g_autotest_a"),
                (player_get_agent_id, ":killer", "$g_autotest_b"), (ge, ":killer", 0),
                (try_for_agents, ":victim"), (agent_is_human, ":victim"), (agent_is_alive, ":victim"),
                    (agent_get_team, ":team", ":victim"), (eq, ":team", ":losing_team"),
                    (agent_deliver_damage_to_agent, ":killer", ":victim", 1000, "itm_sword_medieval_a"),
                (try_end),
                (assign, "$g_autotest_step", 1), (assign, "$g_autotest_phase", 4),
                (display_message, "@[AUTOTEST] full-side casualty burst generated through native damage"),
            (try_end),
        ]))
'''
    p.write_text(s,encoding='cp1254')
# A longer second round permits visual and disconnect checks without human
# input. Ordinary accounting regression remains the short finite fixture.
mission_text=p.read_text(encoding='cp1254')
hold_seconds=45 if '--hold-second' in sys.argv else 8
mission_text=re.sub(r'(\(eq, "\$g_autotest_round", 1\), \(eq, "\$g_autotest_step", 0\), \(ge, ":seconds", )\d+(\),)', lambda m:m.group(1)+str(hold_seconds)+m.group(2),mission_text)
p.write_text(mission_text,encoding='cp1254')
env=dict(os.environ,WARBAND_EXPORT_DIR=str(root/'runtime/NativeMissionProbe/Game/Modules/NativeCoopProbe'))
with (root/'logs/autonomous-army-fixture-build.log').open('w') as out:
    subprocess.run([str(root/'tools/python27-extract/SourceDir/python.exe'),'-B',str(source/'run_module_build.py')],cwd=source,env=env,stdout=out,stderr=subprocess.STDOUT,check=True)
print('Finite two-round native regression fixture compiled.')
