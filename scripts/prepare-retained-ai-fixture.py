"""Finite isolated engine fixture: one army fights NPCs, the other stays on map."""
from pathlib import Path
import os, subprocess, shutil, sys
root=Path(__file__).resolve().parents[1];source=root/'runtime/NativeMissionProbe/Source'
shutil.copy2(root/'scripts/module_retained_campaign_battles.py',source/'module_retained_campaign_battles.py')
path=source/'module_simple_triggers.py';text=path.read_text(encoding='cp1254').partition('# RETAINED_AI_ENGINE_FIXTURE')[0]
text+='''
# RETAINED_AI_ENGINE_FIXTURE
simple_triggers += [(0, [
    (multiplayer_is_server), (multiplayer_is_campaign), (eq,"$g_retained_fixture_phase",0),
    (eq,"$g_native_probe_started",0), (eq,"$g_full_host_probe_request",3),
    (assign,":ready",0), (assign,":attacker",-1),
    (try_for_players,":p",1),(player_is_active,":p"),
        (player_slot_eq,":p",slot_player_coop_char_state,coop_char_state_ready),
        (val_add,":ready",1),
        (try_begin),(player_slot_eq,":p",slot_player_coop_steam_acctid,2113929218),(assign,":attacker",":p"),(try_end),
    (try_end),(eq,":ready",2),(ge,":attacker",1),
    (player_get_party_id,":army",":attacker"),
    (spawn_around_party,":army","pt_looters"),(assign,"$g_retained_fixture_enemy",reg0),
    (party_clear,"$g_retained_fixture_enemy"),(party_add_members,"$g_retained_fixture_enemy","trp_looter",140),
    (party_get_position,pos12,":army"),(position_move_x,pos12,30),
    (party_set_position,"$g_retained_fixture_enemy",pos12),
    (store_faction_of_party,":realm",":army"),(store_faction_of_party,":enemy_realm","$g_retained_fixture_enemy"),
    (set_relation,":realm",":enemy_realm",-50),
    (try_for_players,":p",1),(player_is_active,":p"),(player_get_party_id,":other",":p"),
        (store_faction_of_party,":other_realm",":other"),(set_relation,":other_realm",":enemy_realm",-50),
        (set_relation,":realm",":other_realm",0),(try_end),
    (party_set_ai_behavior,"$g_retained_fixture_enemy",ai_bhvr_hold),
    (party_set_ai_behavior,":army",ai_bhvr_attack_party),(party_set_ai_object,":army","$g_retained_fixture_enemy"),
    (assign,"$g_retained_fixture_attacker",":attacker"),(assign,"$g_retained_fixture_phase",1),
]), (0, [
    (multiplayer_is_server),(multiplayer_is_campaign),(eq,"$g_retained_fixture_phase",1),
    (player_get_party_id,":army","$g_retained_fixture_attacker"),
    (party_get_position,pos12,":army"),(position_move_x,pos12,30),
    (party_set_position,"$g_retained_fixture_enemy",pos12),
    (call_script,"script_coop_retained_start","$g_retained_fixture_attacker","$g_retained_fixture_enemy",0),
    (eq,"$g_native_probe_started",1),(assign,"$g_retained_fixture_phase",2),
    (display_message,"@[AI ENGINE TEST] coordinator admission; other client remains on map"),
]), (0, [
    (multiplayer_is_server),(multiplayer_is_campaign),(eq,"$g_retained_fixture_phase",2),
    (eq,"$g_retained_fixture_joined",0),(eq,"$g_cycle_result_sent",0),
    (eq,"$g_cycle_armies_spawned",1),
    (ge,"$g_probe_mission_seconds",20),
    (try_for_players,":p",1),(player_is_active,":p"),
        (player_slot_eq,":p",slot_player_coop_char_state,coop_char_state_ready),(player_slot_eq,":p",6015,0),
        (player_get_party_id,":party",":p"),(store_faction_of_party,":realm",":party"),
        (store_faction_of_party,":ally","$g_cycle_attacker_party"),
        (set_relation,":realm",":ally",0),(set_relation,":realm","fac_outlaws",-50),
        (call_script,"script_multiplayer_campaign_client_events",":p",50,0),
        (player_slot_eq,":p",6015,1),(assign,"$g_retained_fixture_joined",1),
    (try_end),
])]
'''
if '--single-client' in sys.argv:
    text=text.replace('(eq,":ready",2)','(eq,":ready",1)')
path.write_text(text,encoding='cp1254')
mission_path=source/'module_mission_templates.py'
mission_text=mission_path.read_text(encoding='cp1254').partition('# RETAINED_AI_UI_FIXTURE')[0]
mission_text+='''
# RETAINED_AI_UI_FIXTURE
for fixture_mission in mission_templates:
    if fixture_mission[0]=='native_session_probe':
        fixture_mission[5].append((1,0,0,[(neg|multiplayer_is_server)], [
            (multiplayer_get_my_player,":me"),
            (player_slot_eq,":me",19200,0),(store_mission_timer_a,":seconds"),(ge,":seconds",5),
            (player_set_slot,":me",19200,1),(call_script,"script_coop_retained_confirm_retreat"),
        ]))
'''
mission_path.write_text(mission_text,encoding='cp1254')
env=dict(os.environ,WARBAND_EXPORT_DIR=str(root/'runtime/NativeMissionProbe/Game/Modules/NativeCoopProbe'))
with (root/'logs/retained-ai-fixture-build.log').open('w') as log:
    subprocess.run([str(root/'tools/python27-extract/SourceDir/python.exe'),'-B',str(source/'run_module_build.py')],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
print('Finite AI encounter fixture compiled; no forced combat damage.')
