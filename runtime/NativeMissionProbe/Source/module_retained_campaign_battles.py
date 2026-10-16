# -*- coding: ascii -*-
"""Isolated single-mission campaign coordinator. Host owns every admission/result."""
from header_common import *
from header_operations import *
from header_triggers import *
from header_mission_templates import *
from header_scenes import sf_generate, sf_auto_entry_points
from header_terrain_types import rt_water, rt_mountain, rt_steppe, rt_steppe_forest, rt_snow, rt_snow_forest, rt_desert, rt_desert_forest, rt_forest
from module_constants import *
import module_player_context as player_context

PARTICIPANT=6015
ROSTER_SPAWNED=6016
CONFIRMED=6017
COHORT_BASE=17000
COOLDOWN_SLOT=6040          # party slot: application time (ms) before which no new battle starts
BATTLE_COOLDOWN_MS=3000
FIELD_SPAN_M=200              # metres between the two armies on a generated battle map
FIELD_SPAN_CM=FIELD_SPAN_M*100
JOIN_TIME_SLOT=6042           # party slot: application time (ms) it was registered for the battle
JOIN_LOAD_TIMEOUT_MS=30000   # a human army not loaded in by then no longer holds the battle open
DEFEAT_CLEAR_HOURS=12        # game hours a beaten army waits for its victor's Native menus
SAVE_MIN_SIMPLE_TRIGGERS=151 # existing test saves hold this many; a save will not load with fewer

EV_TERRAIN_SEEDS=104        # host -> client: terrain, river and flora seeds for the battle map

def apply_terrain_seeds(scene):   # unused: the engine re-rolls these from the shared seed
    # sf_randomize would roll new seeds on each machine; the seeds make the terrain identical.
    return [(scene_set_flags,scene,sf_generate|sf_auto_entry_points),
        (scene_set_terrain_seed,scene,'$g_retained_terrain_seed'),(scene_set_river_seed,scene,'$g_retained_river_seed'),
        (scene_set_flora_seed,scene,'$g_retained_flora_seed')]

def terrain_seed_ops():
    # Host: the seed for a generated field map (-1 for fixed scenes). As in Native, the
    # battlefield comes from where the armies meet: the same spot gives the same field.
    # The plugin writes it where mbMission::start reads a randomized scene's terrain.
    return [(assign,'$g_retained_terrain_seed',-1),(assign,'$g_retained_river_seed',-1),(assign,'$g_retained_flora_seed',-1),
        (try_begin),(eq,'$g_retained_siege',0),
            (ge,'$g_retained_scene','scn_random_multi_plain_medium'),(le,'$g_retained_scene','scn_random_multi_desert_forest_large'),
            (set_fixed_point_multiplier,10),(party_get_position,pos22,'$g_cycle_attacker_party'),
            (position_get_x,':seed_x',pos22),(position_get_y,':seed_y',pos22),
            (val_add,':seed_x',5000),(val_add,':seed_y',5000),
            (store_mul,'$g_retained_terrain_seed',':seed_x',7919),(store_mul,':seed_part',':seed_y',104729),
            (val_add,'$g_retained_terrain_seed',':seed_part'),(val_mod,'$g_retained_terrain_seed',999983),(val_add,'$g_retained_terrain_seed',1),
            (store_mul,'$g_retained_river_seed',':seed_y',7927),(store_mul,':seed_part',':seed_x',104723),
            (val_add,'$g_retained_river_seed',':seed_part'),(val_mod,'$g_retained_river_seed',999979),(val_add,'$g_retained_river_seed',1),
            (store_mul,'$g_retained_flora_seed',':seed_x',7933),(store_mul,':seed_part',':seed_y',104717),
            (val_add,'$g_retained_flora_seed',':seed_part'),(val_mod,'$g_retained_flora_seed',999961),(val_add,'$g_retained_flora_seed',1),
        (try_end)]

# Native multiplayer maps by the terrain they show (fixed terrain, identical everywhere).
TERRAIN_MAPS=[((rt_steppe,rt_steppe_forest),['scn_multi_scene_2']),
    ((rt_snow,rt_snow_forest),['scn_multi_scene_9','scn_multi_scene_21','scn_multi_scene_14']),
    ((rt_forest,),['scn_multi_scene_18']),
    ((rt_desert,rt_desert_forest),['scn_multi_scene_20'])]
PLAIN_MAPS=['scn_multi_scene_7','scn_multi_scene_4','scn_multi_scene_19','scn_multi_scene_1']

def pick_map(maps):
    ops=[(store_random_in_range,':map_pick',0,len(maps))]
    for i,scene in enumerate(maps): ops+=[(try_begin),(eq,':map_pick',i),(assign,'$g_retained_scene',scene),(try_end)]
    return ops

def map_by_terrain(terrain,table,default):
    ops=[(try_begin)]
    for i,(kinds,maps) in enumerate(table):
        if i: ops.append((else_try))
        for kind in kinds[:-1]: ops.append((this_or_next|eq,terrain,kind))
        ops.append((eq,terrain,kinds[-1]))
        ops+=pick_map(maps)
    return ops+[(else_try)]+pick_map(default)+[(try_end)]

# Native's setup_random_scene picks a generated map for the terrain; these are its
# multiplayer variants. Their terrain is made identical on every machine by the
# host's seeds (terrain_seed_ops).
GENERATED_MAPS=[((rt_steppe,rt_steppe_forest),['scn_random_multi_steppe_large']),
    ((rt_snow,),['scn_random_multi_snow_large']),((rt_snow_forest,),['scn_random_multi_snow_forest_large']),
    ((rt_desert,),['scn_random_multi_desert_large']),((rt_desert_forest,),['scn_random_multi_desert_forest_large'])]
GENERATED_PLAIN=['scn_random_multi_plain_large']

def terrain_map_ops(terrain):
    # $g_coop_fixed_battle_maps = 1 falls back to Native's fixed multiplayer maps.
    return [(try_begin),(eq,'$g_coop_fixed_battle_maps',1)]+map_by_terrain(terrain,TERRAIN_MAPS,PLAIN_MAPS)+[
        (else_try)]+map_by_terrain(terrain,GENERATED_MAPS,GENERATED_PLAIN)+[(try_end)]

def participant_loops(ops):
    out=[]
    for raw in ops:
        out.append(raw)
        if isinstance(raw,tuple) and raw[0]==try_for_players:
            out.append((player_slot_eq,raw[1],PARTICIPANT,1))
    return out

def replace_script(scripts,name,ops):
    # A failing script fails its caller too; these are never conditions.
    ops=[(try_begin)]+ops+[(try_end)]
    for i,(key,_) in enumerate(scripts):
        if key==name:scripts[i]=(key,ops);return
    scripts.append((name,ops))

def install_scripts(scripts):
    replace_script(scripts,'coop_retained_confirm_retreat',[
        (try_begin),(eq,'$g_retained_retreat_question',0),
            (assign,'$g_retained_retreat_question',1),
            (question_box,'str_do_you_want_to_retreat'),
        (try_end),
    ])
    replace_script(scripts,'coop_retained_send_map_party',[
        (store_script_param,':recipient',1),(store_script_param,':party',2),(store_script_param,':fighting',3),
        (set_fixed_point_multiplier,1000),(party_get_position,pos12,':party'),
        (position_get_x,':x',pos12),(position_get_y,':y',pos12),
        (multiplayer_send_4_int_to_player,':recipient',multiplayer_event_multiplayer_campaign_server_events,73,':party',':x',':y'),
        (multiplayer_send_3_int_to_player,':recipient',multiplayer_event_multiplayer_campaign_server_events,74,':party',':fighting'),
    ])
    replace_script(scripts,'coop_retained_register_party',[
        (store_script_param,':party',1),(store_script_param,':team',2),(store_script_param,':owner',3),
        (store_add,':slot',COHORT_BASE,'$g_retained_party_count'),
        (party_set_slot,'$g_cycle_attacker_party',':slot',':party'),(val_add,'$g_retained_party_count',1),
        (party_set_slot,':party',slot_party_coop_battle_slot,1),
        (party_set_slot,':party',6015,':team'),(party_set_slot,':party',6016,':owner'),
        (party_set_slot,':party',6017,0),
        (store_application_time,':joined_at'),(party_set_slot,':party',JOIN_TIME_SLOT,':joined_at'),
        (try_begin),(neg|is_between,':party',centers_begin,centers_end),(disable_party,':party'),(try_end),
        (try_for_players,':recipient',1),(player_is_active,':recipient'),
            (player_slot_eq,':recipient',slot_player_coop_char_state,coop_char_state_ready),
            (call_script,'script_coop_retained_send_map_party',':recipient',':party',1),
        (try_end),
    ])
    replace_script(scripts,'coop_retained_invite',[
        (store_script_param,':player',1),(store_script_param,':team',2),
        (player_set_slot,':player',PARTICIPANT,1),(player_set_slot,':player',6002,':team'),
        (player_set_team_no,':player',':team'),
        (player_set_slot,':player',6000,0),(player_set_slot,':player',6001,0),
        (player_set_slot,':player',6004,0),(player_set_slot,':player',6006,0),
        (player_set_slot,':player',ROSTER_SPAWNED,0),(player_set_slot,':player',CONFIRMED,0),
        (player_set_slot,':player',player_context.POST_BATTLE_SLOT,0),
        (multiplayer_send_4_int_to_player,':player',multiplayer_event_multiplayer_campaign_server_events,
            EV_TERRAIN_SEEDS,'$g_retained_terrain_seed','$g_retained_river_seed','$g_retained_flora_seed'),
        (multiplayer_send_3_int_to_player,':player',multiplayer_event_multiplayer_campaign_server_events,
            67,'$g_retained_scene','mt_native_session_probe'),
        (call_script,'script_coop_ctx_before_battle',':player',':team'),
    ])
    replace_script(scripts,'coop_retained_start',[
        (store_script_param,':requester',1),(store_script_param,':target',2),(store_script_param,':siege',3),
        (assign,reg0,0),(assign,'$g_retained_reject_reason',1),
        (player_is_active,':requester'),
        (player_slot_eq,':requester',slot_player_coop_char_state,coop_char_state_ready),
        (assign,'$g_retained_reject_reason',2),
        # A finished battle whose flag outlived the scene cleanup.
        (try_begin),(eq,'$g_native_probe_started',1),(eq,'$g_cycle_result_sent',1),(eq,'$g_full_host_probe_request',3),
            (assign,'$g_native_probe_started',0),(try_end),
        (eq,'$g_native_probe_started',0),(eq,'$g_full_host_probe_request',3),
        (assign,'$g_retained_reject_reason',3),
        (player_get_party_id,':party',':requester'),(party_is_active,':party'),
        (gt,':target',0),(party_is_active,':target'),(neq,':party',':target'),
        # No battle runs now, so a reservation left on either army is stale.
        (party_set_slot,':party',slot_party_coop_battle_slot,0),
        (party_set_slot,':target',slot_party_coop_battle_slot,0),
        (assign,'$g_retained_reject_reason',4),
        (assign,':defender',-1),
        (try_for_players,':candidate',1),(player_is_active,':candidate'),
            (player_slot_eq,':candidate',slot_player_coop_char_state,coop_char_state_ready),
            (player_get_party_id,':candidate_party',':candidate'),(eq,':candidate_party',':target'),
            (assign,':defender',':candidate'),
        (try_end),
        (assign,'$g_retained_scene','scn_multi_scene_1'),(assign,'$g_retained_siege',':siege'),
        (try_begin),(eq,':siege',1),
            (is_between,':target',walled_centers_begin,walled_centers_end),
            (store_distance_to_party_from_party,':range',':party',':target'),(lt,':range',coop_tavern_transaction_range),
            (store_faction_of_party,':realm',':party'),(store_faction_of_party,':enemy',':target'),
            (store_relation,':relation',':realm',':enemy'),(lt,':relation',0),
            (party_get_slot,':kind',':target',slot_party_type),
            (try_begin),(eq,':kind',spt_town),(party_get_slot,'$g_retained_scene',':target',slot_town_walls),
            (else_try),(party_get_slot,'$g_retained_scene',':target',slot_castle_exterior),(try_end),
        (else_try),(eq,':siege',0),
            # A Native multiplayer field map for the terrain the armies meet on. Generated
            # (random_multi) maps came out with different terrain on the host and clients.
            (party_get_current_terrain,':terrain',':party'),
            ]+terrain_map_ops(':terrain')+[
        (else_try),(assign,'$g_retained_siege',-1),(try_end),
        (ge,'$g_retained_siege',0),
        (assign,'$g_cycle_attacker',':requester'),(assign,'$g_cycle_defender',':defender'),
        (assign,'$g_cycle_attacker_party',':party'),(assign,'$g_cycle_defender_party',':target'),
        # The map seed goes out with every invite, so it is set before the first one.
        ]+terrain_seed_ops()+[
        (assign,'$g_retained_party_count',0),(assign,'$g_retained_ai_spawned',0),
        (assign,'$g_cycle_result_sent',0),(assign,'$g_cycle_armies_spawned',0),
        (assign,'$g_cycle_retreat_requested',0),(assign,'$g_full_probe_peer_ready',0),
        (assign,'$g_full_probe_map_ready',0),(assign,'$g_full_probe_resume_ready',0),
        (assign,'$g_cycle_resume_sent',0),(assign,'$g_native_probe_started',1),
        (try_for_players,':p',1),(player_set_slot,':p',PARTICIPANT,0),(try_end),
        (val_add,'$g_retained_battle_serial',1),
        (call_script,'script_coop_retained_register_party',':party',0,':requester'),
        (call_script,'script_coop_retained_register_party',':target',1,':defender'),
        (call_script,'script_coop_retained_invite',':requester',0),
        (try_begin),(ge,':defender',1),(call_script,'script_coop_retained_invite',':defender',1),(try_end),
        (start_multiplayer_mission,'mt_native_session_probe','$g_retained_scene',1),
        (assign,reg0,1),
    ])
    replace_script(scripts,'coop_ev_cli_start_battle',[
        (store_script_param,':player',1),(player_get_party_id,':party',':player'),
        (party_get_battle_opponent,':opponent',':party'),
        (call_script,'script_coop_retained_start',':player',':opponent',0),
        (try_begin),(eq,reg0,0),(store_add,':reason','$g_retained_reject_reason',10),
            (multiplayer_send_2_int_to_player,':player',multiplayer_event_multiplayer_campaign_server_events,
            multiplayer_event_multiplayer_campaign_server_event_battle_rejected,':reason'),
            (call_script,'script_coop_retained_release_encounter',':party'),
        (try_end),
    ])
    for name in ['coop_ev_cli_request_siege','coop_ev_cli_request_siege_local']:
        replace_script(scripts,name,[
            (store_script_param,':player',1),(store_script_param,':center',2),
            (call_script,'script_coop_retained_start',':player',':center',1),
            (try_begin),(eq,reg0,0),(store_add,':reason','$g_retained_reject_reason',10),
                (multiplayer_send_2_int_to_player,':player',multiplayer_event_multiplayer_campaign_server_events,
                multiplayer_event_multiplayer_campaign_server_event_battle_rejected,':reason'),(try_end),
        ])
    replace_script(scripts,'coop_retained_reject_message',[
        (store_script_param,':reason',1),
        (try_begin),(eq,':reason',11),
            (display_message,'@Your character is still loading. Try again in a moment.',0xFFFF4444),
        (else_try),(eq,':reason',12),
            (display_message,'@The previous battle is still finishing on the server. Try again in a moment.',0xFFFF4444),
        (else_try),(eq,':reason',13),
            (display_message,'@There is no enemy engaged with your army to fight.',0xFFFF4444),
        (else_try),(eq,':reason',14),
            (display_message,'@You can only assault a hostile walled settlement you are standing next to.',0xFFFF4444),
        (else_try),
            (display_message,'@The battle could not be started.',0xFFFF4444),
        (try_end),
    ])
    for name,ops in scripts:
        if name!='multiplayer_campaign_server_events':continue
        for i,op in enumerate(ops):
            if isinstance(op,tuple) and op[0]==display_message and op[1]=='@All battle servers are busy -- try again shortly.':
                ops[i]=(call_script,'script_coop_retained_reject_message',':reject_reason')
    replace_script(scripts,'coop_retained_reinforce',[
        (store_script_param,':player',1),(store_script_param,':team',2),(assign,reg0,0),
        (player_is_active,':player'),(player_slot_eq,':player',slot_player_coop_char_state,coop_char_state_ready),
        (player_slot_eq,':player',PARTICIPANT,0),
        (eq,'$g_native_probe_started',1),(eq,'$g_cycle_armies_spawned',1),
        (eq,'$g_cycle_result_sent',0),(eq,'$g_full_host_probe_request',3),
        (is_between,':team',0,2),
        (player_get_party_id,':party',':player'),(party_is_active,':party'),
        (party_slot_eq,':party',slot_party_coop_battle_slot,0),
        (store_distance_to_party_from_party,':distance',':party','$g_cycle_attacker_party'),(le,':distance',2),
        (store_faction_of_party,':realm',':party'),
        (assign,':ally','$g_cycle_attacker_party'),(assign,':enemy','$g_cycle_defender_party'),
        (try_begin),(eq,':team',1),(assign,':ally','$g_cycle_defender_party'),(assign,':enemy','$g_cycle_attacker_party'),(try_end),
        (store_faction_of_party,':ally_realm',':ally'),(store_faction_of_party,':enemy_realm',':enemy'),
        (neq,':ally_realm','fac_outlaws'),
        (store_relation,':relation',':realm',':ally_realm'),(ge,':relation',0),
        (call_script,'script_coop_retained_register_party',':party',':team',':player'),
        (call_script,'script_coop_retained_invite',':player',':team'),(assign,reg0,1),
    ])
    # Native releases every army touching a finished battle. Armies that
    # walked into the engine battle while it was reserved are not cohort
    # members and would otherwise stay attached to it.
    replace_script(scripts,'coop_retained_release_bystanders',[
        (try_for_parties,':other'),(party_is_active,':other'),
            (neg|is_between,':other',centers_begin,centers_end),
            (party_slot_eq,':other',slot_party_coop_battle_slot,0),
            (party_get_battle_opponent,':opponent',':other'),(ge,':opponent',0),
            (party_slot_eq,':opponent',slot_party_coop_battle_slot,1),
            (party_leave_cur_battle,':other'),
            (call_script,'script_coop_retained_resume_ai',':other'),
        (try_end),
    ])
    # Disabling a party for the battle drops its path; re-issue its standing orders.
    replace_script(scripts,'coop_retained_resume_ai',[
        (store_script_param,':party',1),
        (party_is_active,':party'),(neg|is_between,':party',centers_begin,centers_end),
        (neg|party_slot_ge,':party',6016,1),(party_is_non_player,':party'),
        (get_party_ai_behavior,':behavior',':party'),(get_party_ai_object,':object',':party'),
        (party_get_ai_target_position,pos13,':party'),
        (party_set_ai_behavior,':party',':behavior'),
        (try_begin),(ge,':object',0),(party_is_active,':object'),(party_set_ai_object,':party',':object'),
        (else_try),(party_set_ai_target_position,':party',pos13),(try_end),
    ])
    # Native: a decisively beaten AI army leaves the map, routed survivors
    # included, and its lords escape to be respawned by the normal lord AI.
    replace_script(scripts,'coop_retained_defeated_ai',[
        (store_script_param,':party',1),
        (party_is_active,':party'),(neg|is_between,':party',centers_begin,centers_end),
        (neg|party_slot_ge,':party',6016,1),(party_is_non_player,':party'),
        (party_get_num_companion_stacks,':stacks',':party'),
        (try_for_range,':stack',0,':stacks'),
            (party_stack_get_troop_id,':troop',':party',':stack'),(troop_is_hero,':troop'),
            (troop_set_slot,':troop',slot_troop_leaded_party,-1),
            (str_store_troop_name_link,s1,':troop'),(store_troop_faction,':faction',':troop'),
            (str_store_faction_name_link,s3,':faction'),
            (display_log_message,'@{s1} of {s3} was defeated in battle but managed to escape.'),
        (try_end),
        (call_script,'script_clear_party_group',':party'),
        (try_for_players,':recipient',1),(player_is_active,':recipient'),
            (player_slot_eq,':recipient',slot_player_coop_char_state,coop_char_state_ready),
            (multiplayer_send_2_int_to_player,':recipient',multiplayer_event_multiplayer_campaign_server_events,79,':party'),
        (try_end),
        (try_begin),(gt,':party','p_spawn_points_end'),(remove_party,':party'),
        (else_try),(disable_party,':party'),(try_end),
    ])
    # Armies just out of an encounter or battle cannot start another for 3 s.
    replace_script(scripts,'coop_retained_set_cooldown',[
        (store_script_param,':party',1),(gt,':party',0),(party_is_active,':party'),
        (store_application_time,':until'),(val_add,':until',BATTLE_COOLDOWN_MS),
        (party_set_slot,':party',COOLDOWN_SLOT,':until'),
    ])
    # Ending an encounter without a battle (leave, ransom, refused start)
    # frees both armies, not only the player's, as Native's leave_encounter.
    replace_script(scripts,'coop_retained_release_encounter',[
        (store_script_param,':party',1),(gt,':party',0),(party_is_active,':party'),
        (party_get_battle_opponent,':opponent',':party'),
        (assign,reg56,':party'),(assign,reg57,':opponent'),
        ]+player_context.debug('encounter released: army {reg56}, opponent {reg57}')+[
        (party_leave_cur_battle,':party'),
        (call_script,'script_coop_retained_set_cooldown',':party'),
        (try_for_players,':recipient',1),(player_is_active,':recipient'),
            (player_slot_eq,':recipient',slot_player_coop_char_state,coop_char_state_ready),
            (call_script,'script_coop_retained_send_map_party',':recipient',':party',0),
        (try_end),
        (gt,':opponent',0),(party_is_active,':opponent'),
        (party_slot_eq,':opponent',slot_party_coop_battle_slot,0),
        (party_leave_cur_battle,':opponent'),
        (call_script,'script_coop_retained_set_cooldown',':opponent'),
        (call_script,'script_coop_retained_resume_ai',':opponent'),
        (try_for_players,':recipient',1),(player_is_active,':recipient'),
            (player_slot_eq,':recipient',slot_player_coop_char_state,coop_char_state_ready),
            (call_script,'script_coop_retained_send_map_party',':recipient',':opponent',0),
        (try_end),
    ])
    # A player's army keeps no battle state outside a running battle. Clears
    # leftovers from interrupted battles (crash, disconnect, failed launch).
    replace_script(scripts,'coop_retained_unstick_party',[
        # No party_is_active: a stuck army is often a disabled one.
        (store_script_param,':party',1),(gt,':party',0),
        (assign,':held',0),
        (try_begin),(eq,'$g_native_probe_started',1),(eq,'$g_cycle_result_sent',0),
            (try_for_range,':i',0,'$g_retained_party_count'),
                (store_add,':slot',COHORT_BASE,':i'),(party_slot_eq,'$g_cycle_attacker_party',':slot',':party'),
                (assign,':held',1),
            (try_end),
        (try_end),
        (eq,':held',0),
        (party_leave_cur_battle,':party'),(enable_party,':party'),
        (party_set_slot,':party',slot_party_coop_battle_slot,0),
        (try_for_players,':recipient',1),(player_is_active,':recipient'),
            (player_slot_eq,':recipient',slot_player_coop_char_state,coop_char_state_ready),
            (call_script,'script_coop_retained_send_map_party',':recipient',':party',0),
        (try_end),
    ])
    # A player army off the walkable map (sea, mountains, or a pocket only F8
    # can name) is moved beside the nearest town, castle or village.
    replace_script(scripts,'coop_retained_relocate_party',[
        (store_script_param,':party',1),(store_script_param,':force',2),
        (gt,':party',0),(party_is_active,':party'),
        (party_get_current_terrain,':terrain',':party'),
        (this_or_next|eq,':force',1),(this_or_next|eq,':terrain',rt_water),(eq,':terrain',rt_mountain),
        (assign,':nearest',-1),(assign,':best',1000000),
        (try_for_range,':center',centers_begin,centers_end),(party_is_active,':center'),
            (store_distance_to_party_from_party,':distance',':party',':center'),(lt,':distance',':best'),
            (assign,':best',':distance'),(assign,':nearest',':center'),
        (try_end),
        (ge,':nearest',0),
        (party_relocate_near_party,':party',':nearest',2),
        (try_for_players,':recipient',1),(player_is_active,':recipient'),
            (player_slot_eq,':recipient',slot_player_coop_char_state,coop_char_state_ready),
            (call_script,'script_coop_retained_send_map_party',':recipient',':party',0),
        (try_end),
    ])
    for name,ops in scripts:
        if name=='coop_center_lock_acquire':
            ops.extend([(store_script_param,':trace_player',1),(store_script_param,':trace_center',2),
                (assign,reg56,':trace_player'),(assign,reg57,':trace_center')]+player_context.debug('town: player {reg56} entered center {reg57}'))
        if name=='coop_center_lock_release':
            ops.extend([(store_script_param,':trace_player',1),(assign,reg56,':trace_player'),
                (store_add,':trace_party',multiplayer_campaign_player_parties_begin,':trace_player'),
                (party_get_attached_to,reg57,':trace_party')]+player_context.debug('town: player {reg56} left; party now attached to {reg57}'))
        if name=='coop_recover_player_encounter':
            # F8 also frees a player held in a town.
            ops[0:0]=[(store_script_param,':unstick_player',1),
                (call_script,'script_coop_center_lock_release',':unstick_player'),
                (player_get_party_id,':unstick_party',':unstick_player'),
                (call_script,'script_coop_retained_unstick_party',':unstick_party'),
                (call_script,'script_coop_retained_relocate_party',':unstick_party',1)]
        if name=='coop_player_hydrate':
            ops.extend([(store_script_param,':unstick_player',1),(player_get_party_id,':unstick_party',':unstick_player'),
                (call_script,'script_coop_retained_unstick_party',':unstick_party'),
                (call_script,'script_coop_retained_relocate_party',':unstick_party',0)])
    # Native kill experience for human-led armies (Native SP awards it per kill).
    replace_script(scripts,'coop_retained_kill_xp',[
        (store_script_param,':dead',1),(store_script_param,':killer',2),
        (ge,':killer',0),(agent_is_human,':dead'),(agent_is_human,':killer'),
        (agent_get_team,':dead_team',':dead'),(agent_get_team,':killer_team',':killer'),(neq,':dead_team',':killer_team'),
        (agent_get_slot,':party',':killer',6100),(gt,':party',0),
        (party_slot_ge,':party',6016,1),
        (agent_get_slot,':killer_troop',':killer',6101),(ge,':killer_troop',0),
        (agent_get_troop_id,':dead_troop',':dead'),(store_character_level,':level',':dead_troop'),
        (store_mul,':xp',':level',':level'),(val_div,':xp',10),(val_add,':xp',':level'),(val_add,':xp',':level'),
        (val_add,':xp',10),(val_mul,':xp',2),
        (try_begin),(troop_is_hero,':killer_troop'),(add_xp_to_troop,':xp',':killer_troop'),
        (else_try),
            (party_get_num_companion_stacks,':stacks',':party'),(assign,':done',0),
            (try_for_range,':stack',0,':stacks'),(eq,':done',0),
                (party_stack_get_troop_id,':troop',':party',':stack'),(eq,':troop',':killer_troop'),
                (party_add_xp_to_stack,':party',':stack',':xp'),(assign,':done',1),
            (try_end),
        (try_end),
    ])
    # Existing scene ACK/order/return handlers are participant-only.
    for name,ops in scripts:
        if name=='multiplayer_campaign_client_events':
            out=[]
            for op in ops:
                if isinstance(op,tuple) and op[:2]==(assign,'$g_cycle_retreat_requested') and op[2]==1:
                    out.extend([(store_add,':retreat_side',':team',1),(assign,'$g_cycle_retreat_requested',':retreat_side')])
                    continue
                out.append(op)
                if isinstance(op,tuple) and op[:2]==(eq,':event_type') and op[2] in [44,46,47,48,49]:
                    out.append((player_slot_eq,':player_no',PARTICIPANT,1))
            # Keep the existing dispatch try nesting intact: prefix a separate
            # handler, then prevent event 50 from entering legacy dispatch.
            out=[(store_script_param,':player_no',1),(store_script_param,':event_type',2),
                ]+player_context.host_client_events()+[
                (try_begin),(eq,':event_type',50),(store_script_param,':join_side',3),
                (call_script,'script_coop_retained_reinforce',':player_no',':join_side'),
                (eq,reg0,0),(multiplayer_send_int_to_player,':player_no',multiplayer_event_multiplayer_campaign_server_events,88),
                (try_end),
                # Leaving (or ransoming) an encounter releases both armies;
                # the legacy handler below still runs and only frees the player.
                (try_begin),(eq,':event_type',multiplayer_event_multiplayer_campaign_leave_encounter),
                    (player_get_party_id,':leaving_party',':player_no'),
                    (call_script,'script_coop_retained_release_encounter',':leaving_party'),
                (try_end),
                (neq,':event_type',50)]+out
            ops[:]=out
        if name=='coop_probe_push_return_rosters':
            # Roster refresh includes AI garrisons and all admitted human armies.
            ops[:]=[(store_script_param,':recipient',1),
                (try_for_range,':index',0,'$g_retained_party_count'),
                (store_add,':slot',COHORT_BASE,':index'),(party_get_slot,':party','$g_cycle_attacker_party',':slot'),
                (party_is_active,':party'),
                (multiplayer_send_2_int_to_player,':recipient',multiplayer_event_multiplayer_campaign_server_events,71,':party'),
                (party_get_num_companion_stacks,':stacks',':party'),
                (try_for_range,':stack',0,':stacks'),(party_stack_get_troop_id,':troop',':party',':stack'),
                (party_stack_get_size,':size',':party',':stack'),(party_stack_get_num_wounded,':wounds',':party',':stack'),
                (multiplayer_send_4_int_to_player,':recipient',multiplayer_event_multiplayer_campaign_server_events,72,':troop',':size',':wounds'),
                (try_end),(try_end),
                (call_script,'script_coop_send_char_sync_to_client',':recipient'),
                (call_script,'script_coop_send_party_upgradeable_to_client',':recipient'),
                # Back on the map: Native's debrief, then victory, defeat or retreat.
                (call_script,'script_coop_ctx_post_battle',':recipient')]
        if name=='multiplayer_campaign_server_events':
            ops[:]=[op for op in ops if not(isinstance(op,tuple) and op[0]==ge and op[1]=='$g_cycle_roster_party')]
            ops[:]=[(store_script_param,':retained_event',1),
                # Generated battle maps: the host's seed, written into the engine by the plugin
                # (g_multiplayerData+0x160) before the scene starts.
                (try_begin),(eq,':retained_event',EV_TERRAIN_SEEDS),
                    (store_script_param,'$g_retained_terrain_seed',2),(store_script_param,'$g_retained_river_seed',3),
                    (store_script_param,'$g_retained_flora_seed',4),
                (else_try),(eq,':retained_event',83),
                    (store_script_param,':agent',2),(store_script_param,':team',3),(store_script_param,':group',4),
                    (ge,':agent',0),(is_between,':team',0,2),(agent_is_active,':agent'),
                    (agent_set_team,':agent',':team'),(agent_set_group,':agent',':group'),
                    (agent_set_slot,':agent',6199,1),
                (else_try),(eq,':retained_event',79),
                    (store_script_param,':gone',2),(gt,':gone',0),(party_is_active,':gone'),(disable_party,':gone'),
                (else_try),(eq,':retained_event',85),
                    (store_script_param,':menu',2),(call_script,'script_coop_client_request_menu',':menu'),
                (else_try),(eq,':retained_event',87),
                    (store_script_param,'$g_retained_join_attacker',2),(store_script_param,'$g_retained_join_defender',3),
                    (call_script,'script_coop_client_request_menu','mnu_coop_retained_join'),
                (else_try),(eq,':retained_event',88),
                    (display_message,'@You cannot join that side of the battle: you are hostile to it, too far away, or the fight has ended.',0xFFFF4444),
                ]+player_context.client_server_events()+[
                (try_end)]+[(neq,':retained_event',event) for event in player_context.CLIENT_EVENT_IDS]+[
                (neq,':retained_event',79),(neq,':retained_event',83),(neq,':retained_event',85),
                (neq,':retained_event',87),(neq,':retained_event',88),(neq,':retained_event',EV_TERRAIN_SEEDS),
                (try_begin),(eq,':retained_event',73),
                    (store_script_param,':map_party',2),(store_script_param,':x',3),(store_script_param,':y',4),
                    (gt,':map_party',0),(set_fixed_point_multiplier,1000),
                    (party_get_position,pos12,':map_party'),(position_set_x,pos12,':x'),(position_set_y,pos12,':y'),
                    (party_set_position,':map_party',pos12),(enable_party,':map_party'),
                (else_try),(eq,':retained_event',74),
                    (store_script_param,':map_party',2),(store_script_param,':fighting',3),(gt,':map_party',0),
                    (enable_party,':map_party'),(party_set_slot,':map_party',slot_party_coop_battle_slot,':fighting'),
                    (try_begin),(eq,':fighting',0),(party_leave_cur_battle,':map_party'),(try_end),
                (try_end),(neq,':retained_event',73),(neq,':retained_event',74)]+ops

def install_triggers(triggers):
    # Remove the old global invite: admission belongs to coop_retained_start.
    triggers[:]=[t for t in triggers if not any(isinstance(op,tuple) and op[:2]==(eq,'$g_encounter_cycle_requested') for op in t[1])]
    # Battles run inside the campaign host on the same connection; the old
    # dedicated battle-server chooser (B) and its reconnect are dead paths.
    # Saves store one record per simple trigger and refuse to load when the
    # module has fewer, so retired triggers stay as inert placeholders.
    legacy=[(eq,'$g_coop_battle_available',1),(eq,'$g_coop_battle_connect_pending',1)]
    triggers[:]=[(t[0],[(eq,1,0)]) if any(isinstance(op,tuple) and op in legacy for op in t[1]) else t for t in triggers]
    for i,(delay,ops) in enumerate(triggers):
        if any(isinstance(op,tuple) and op[:2]==(eq,'$g_cycle_map_restore') for op in ops):
            ops[:]=[(gt,op[1],0) if isinstance(op,tuple) and op[0]==ge and op[1] in ['$g_cycle_return_party_a','$g_cycle_return_party_b'] else op for op in ops]
        if any(isinstance(op,tuple) and op[:2]==(eq,'$g_cycle_resume_sent') for op in ops):
            triggers[i]=(delay,participant_loops(ops))
    triggers.append((0,[(neg|multiplayer_is_server),(multiplayer_is_campaign),
        (key_clicked,key_f10),
        (call_script,'script_coop_client_request_menu','mnu_coop_retained_join')]))
    # Native disables engaged armies on the authority. Replay their visible
    # map state for clients, including NPC armies and late joiners.
    triggers.append((0.25,[(multiplayer_is_server),(multiplayer_is_campaign),
        (eq,'$g_native_probe_started',1),(eq,'$g_cycle_result_sent',0),
        (try_for_players,':recipient',1),(player_is_active,':recipient'),
            (player_slot_eq,':recipient',slot_player_coop_char_state,coop_char_state_ready),
            (player_slot_eq,':recipient',PARTICIPANT,0),
            (try_for_range,':index',0,'$g_retained_party_count'),
                (store_add,':slot',COHORT_BASE,':index'),(party_get_slot,':party','$g_cycle_attacker_party',':slot'),
                (call_script,'script_coop_retained_send_map_party',':recipient',':party',1),
            (try_end),
        (try_end),
    ]))
    # Native encounter on arrival: a player who reaches an active battle is
    # offered the join menu once per battle, whoever is already fighting.
    triggers.append((0.5,[(multiplayer_is_server),(multiplayer_is_campaign),
        (eq,'$g_native_probe_started',1),(eq,'$g_cycle_result_sent',0),(eq,'$g_cycle_armies_spawned',1),
        (try_for_players,':visitor',1),(player_is_active,':visitor'),
            (player_slot_eq,':visitor',slot_player_coop_char_state,coop_char_state_ready),
            (player_slot_eq,':visitor',PARTICIPANT,0),
            (neg|player_slot_eq,':visitor',6030,'$g_retained_battle_serial'),
            (player_get_party_id,':visitor_party',':visitor'),(party_is_active,':visitor_party'),
            (party_slot_eq,':visitor_party',slot_party_coop_battle_slot,0),
            (store_distance_to_party_from_party,':distance',':visitor_party','$g_cycle_attacker_party'),(le,':distance',1),
            (player_set_slot,':visitor',6030,'$g_retained_battle_serial'),
            (multiplayer_send_3_int_to_player,':visitor',multiplayer_event_multiplayer_campaign_server_events,87,
                '$g_cycle_attacker_party','$g_cycle_defender_party'),
        (try_end),
    ]))
    triggers += player_context.client_triggers()+player_context.host_triggers()
    # A beaten army whose victor never reached Native's victory menu (left, disconnected).
    triggers.append((1,[(multiplayer_is_server),(multiplayer_is_campaign),(store_current_hours,':now'),
        (try_for_parties,':party'),(party_slot_ge,':party',player_context.DEFEATED_SLOT,1),
            (party_get_slot,':deadline',':party',player_context.DEFEATED_SLOT),(lt,':deadline',':now'),
            (call_script,'script_coop_ctx_clear_party_group',':party'),
        (try_end)]))
    while len(triggers)<SAVE_MIN_SIMPLE_TRIGGERS:triggers.append((24,[(eq,1,0)]))

def install_menus(menus):
    menus.append(('coop_retained_join',0,'{s10}','none',[
            (try_begin),(gt,'$g_retained_join_attacker',0),(gt,'$g_retained_join_defender',0),
                (str_store_party_name,s1,'$g_retained_join_attacker'),(str_store_party_name,s2,'$g_retained_join_defender'),
                (str_store_string,s10,'@You come across a battle between {s1} and {s2}. You may join a side you are not hostile to. Independent bandits cannot be supported.'),
            (else_try),
                (str_store_string,s1,'@the attackers'),(str_store_string,s2,'@the defenders'),
                (str_store_string,s10,'@You can join a battle being fought nearby. You may join a side you are not hostile to. Independent bandits cannot be supported.'),
            (try_end),
        ],[
            ('attackers',[],'Join the battle on the side of {s1}.',[
                (multiplayer_send_2_int_to_server,multiplayer_event_multiplayer_campaign_client_events,50,0),(change_screen_map)]),
            ('defenders',[],'Join the battle on the side of {s2}.',[
                (multiplayer_send_2_int_to_server,multiplayer_event_multiplayer_campaign_client_events,50,1),(change_screen_map)]),
            ('leave',[],"Don't get involved.",[(change_screen_map)]),
        ]))
    for menu in menus:
        if menu[0]=='camp':
            if player_context.TEST_TROOPS_KEY:
                menu[5].insert(0,('coop_test_troops',[(multiplayer_is_campaign)],'Test build: add 15 troops to my army.',[
                    (multiplayer_send_int_to_server,player_context.CLIENT,player_context.EV_TEST_TROOPS),
                    (display_message,'@Test build: asked the host for 15 troops.'),(change_screen_map)]))
            menu[5].insert(0,('retained_join',[(multiplayer_is_campaign)],'Join a nearby battle.',[
                (assign,'$g_retained_join_attacker',0),(assign,'$g_retained_join_defender',0),
                (jump_to_menu,'mnu_coop_retained_join')]))
        if menu[0]=='multiplayer_campaign_encounter':
            menu[5][:]=[option for option in menu[5] if option[0]!='encounter_fight_sp']

def install_presentations(presentations):
    # Troop banners come from Native's label banner (common_battle_init_banner),
    # not from a presentation overlay.
    pass

def install_native_scripts(scripts):
    # The map's Camp button starts an encounter with p_camp_bandits; Native
    # answers it with the camp menu. The multiplayer branch treated it as a
    # hostile encounter, so the menu never opened.
    for name,ops in scripts:
        if name!='game_event_party_encounter':continue
        ops[:]=[(store_script_param_1,':camp_encountered'),
            (try_begin),(multiplayer_is_campaign),(eq,':camp_encountered','p_camp_bandits'),
                (try_begin),(multiplayer_is_server),
                    (store_script_param,':camp_party',3),(gt,':camp_party',0),(party_is_active,':camp_party'),
                    (party_leave_cur_battle,':camp_party'),
                    (party_get_player_id,':camp_player',':camp_party'),(ge,':camp_player',1),
                    (multiplayer_send_2_int_to_player,':camp_player',multiplayer_event_multiplayer_campaign_server_events,85,'mnu_camp'),
                (else_try),(neg|multiplayer_is_server),
                    (call_script,'script_coop_client_request_menu','mnu_camp'),
                (try_end),
                (leave_encounter),
            (else_try),(multiplayer_is_campaign),(multiplayer_is_server),
                # Native pauses the world while the player is in a menu: a player answering a
                # host-run menu or conversation, or whose post-battle menus are still to come,
                # is not engaged (their window could not show a new encounter).
                (store_script_param,':busy_party',3),(assign,':busy',0),
                (try_for_range,':side',0,2),
                    (assign,':side_party',':busy_party'),(try_begin),(eq,':side',1),(assign,':side_party',':camp_encountered'),(try_end),
                    (gt,':side_party',0),(party_is_active,':side_party'),
                    (party_get_player_id,':busy_player',':side_party'),(ge,':busy_player',1),(player_is_active,':busy_player'),
                    (this_or_next|player_slot_eq,':busy_player',player_context.POST_BATTLE_SLOT,1),
                    (player_slot_ge,':busy_player',player_context.MENU_SLOT,1),
                    (assign,':busy',1),
                (try_end),
                (eq,':busy',1),
                # The AI side lets go of this encounter; the busy player keeps their own.
                (try_begin),(gt,':camp_encountered',0),(party_is_active,':camp_encountered'),(party_is_non_player,':camp_encountered'),
                    (party_slot_eq,':camp_encountered',slot_party_coop_battle_slot,0),
                    (party_leave_cur_battle,':camp_encountered'),(try_end),
                (leave_encounter),
            (else_try),(multiplayer_is_campaign),(multiplayer_is_server),
                # Battle cooldown: armies just out of a battle or encounter
                # cannot be engaged again until it expires. Settlements are exempt.
                (store_script_param,':cool_party',3),(gt,':cool_party',0),(party_is_active,':cool_party'),
                (neg|is_between,':camp_encountered',centers_begin,centers_end),
                # Stamps are application time, which restarts with the game while the stamps are
                # saved with the world: only a stamp at most one cooldown ahead is a live cooldown.
                (store_application_time,':cool_now'),(store_add,':cool_limit',':cool_now',BATTLE_COOLDOWN_MS),(assign,':cooling',0),
                (try_begin),(party_get_slot,':cool_until',':cool_party',COOLDOWN_SLOT),
                    (gt,':cool_until',':cool_now'),(le,':cool_until',':cool_limit'),(assign,':cooling',1),(try_end),
                (try_begin),(gt,':camp_encountered',0),(party_is_active,':camp_encountered'),
                    (party_get_slot,':cool_until',':camp_encountered',COOLDOWN_SLOT),
                    (gt,':cool_until',':cool_now'),(le,':cool_until',':cool_limit'),(assign,':cooling',1),(try_end),
                # Native: nothing attacks a party left alone after captivity (party_ignore_player).
                (try_begin),(gt,':camp_encountered',0),(party_is_active,':camp_encountered'),
                    (store_current_hours,':ignore_now'),(party_slot_ge,':cool_party',player_context.IGNORED_UNTIL_SLOT,':ignore_now'),
                    (get_party_ai_current_object,':ignore_target',':camp_encountered'),(eq,':ignore_target',':cool_party'),
                    (assign,':cooling',1),(try_end),
                (eq,':cooling',1),
                (party_leave_cur_battle,':cool_party'),
                (try_begin),(gt,':camp_encountered',0),(party_is_active,':camp_encountered'),
                    (party_slot_eq,':camp_encountered',slot_party_coop_battle_slot,0),
                    (party_leave_cur_battle,':camp_encountered'),(try_end),
                (leave_encounter),
            (else_try)]+ops+[(try_end)]
    # Campaign factions are not the fixed multiplayer culture IDs expected
    # by Native's shield and marker helper. Use the owning player's banner
    # while a retained mission is active and preserve Native elsewhere.
    for name,ops in scripts:
        if name!='agent_troop_get_banner_mesh':continue
        ops[:]=[(try_begin),(this_or_next|eq,'$g_native_probe_started',1),
            (is_between,'$g_full_probe_remote_request',1,5),
            (store_script_param,':retained_agent',1),(assign,reg0,'mesh_banners_default_b'),
            (try_begin),(ge,':retained_agent',0),(agent_is_active,':retained_agent'),
                (agent_get_group,':owner',':retained_agent'),(player_is_active,':owner'),
                (player_get_banner_id,':banner',':owner'),(ge,':banner',0),
                (store_add,':mesh',':banner',arms_meshes_begin),
                (is_between,':mesh',arms_meshes_begin,arms_meshes_end_minus_one),(assign,reg0,':mesh'),
            (else_try),
                # AI armies carry their faction's banner, as Native multiplayer does.
                (ge,':retained_agent',0),(agent_is_active,':retained_agent'),
                (agent_get_team,':team',':retained_agent'),(team_get_faction,':faction',':team'),
                (gt,':faction',0),(faction_get_slot,':mesh',':faction',slot_faction_banner),(gt,':mesh',0),
                (assign,reg0,':mesh'),
            (try_end),(else_try)]+ops+[(try_end)]
    install_courage_scripts(scripts)

# Native's morale and rout model (lead_charge), copied for the multiplayer
# battle. Native measures sides against the single player's team
# (agent_is_ally, get_player_agent_no); here a side is the agent's team and
# every human-controlled agent counts as Native's player agent.
COURAGE_SCRIPTS={'apply_effect_of_other_people_on_courage_scores':'coop_retained_courage_others',
                 'apply_death_effect_on_courage_scores':'coop_retained_courage_death',
                 'decide_run_away_or_not':'coop_retained_run_away'}

def courage_ops(name,ops):
    out=[]
    for i,op in enumerate(ops):
        if isinstance(op,tuple) and op[0]==agent_is_ally:
            nxt=ops[i+1] if i+1<len(ops) else None
            # Native's handicaps for the player's own side have no single side
            # here; drop them rather than penalize one team.
            handicap=name=='decide_run_away_or_not' or (isinstance(nxt,tuple) and nxt[0]==val_sub)
            out.append((eq,1,0) if handicap else (call_script,'script_cf_coop_retained_agent_side0',op[1]))
        elif op==(neq,':centered_agent_no',':player_agent'):out.append((agent_is_non_player,':centered_agent_no'))
        elif op==(eq,':agent_no',':player_agent'):out.append((neg|agent_is_non_player,':agent_no'))
        elif isinstance(op,tuple) and op[0]==get_player_agent_no:out.append((assign,op[1],-1))
        elif isinstance(op,tuple) and op[0]==team_get_movement_order:
            # Multiplayer orders belong to the commanding player (the agent's group), not
            # the team; soldiers no player commands take no retreat order.
            out+=[(agent_get_group,':order_group',':cur_agent'),(ge,':order_group',1),(player_is_active,':order_group'),
                  (team_get_movement_order,op[1],':order_group',op[3])]
        else:out.append(op)
    return out

def install_courage_scripts(scripts):
    native=dict(scripts)
    for source,target in sorted(COURAGE_SCRIPTS.items()):
        replace_script(scripts,target,courage_ops(source,list(native[source])))
    scripts.append(('cf_coop_retained_agent_side0',[
        (store_script_param,':agent',1),(agent_get_team,':team',':agent'),(store_mod,':side',':team',2),(eq,':side',0)]))

def install_missions(missions):
    for mission in missions:
        if mission[0]!='native_session_probe':continue
        kept=[];banner_kept=False
        for trigger in mission[5]:
            # Native label banners: keep one common_battle_init_banner (listed twice).
            if any(isinstance(op,tuple) and op[0]==call_script and op[1]=='script_troop_agent_set_banner' for op in trigger[4]):
                if not banner_kept:kept.append(trigger);banner_kept=True
                continue
            if any(isinstance(op,tuple) and op[0]==start_presentation and op[1]=='prsnt_coop_friendly_overhead' for op in trigger[4]):continue
            if trigger[0] in [0,ti_tab_pressed] and any(isinstance(op,tuple) and op[0]==multiplayer_send_int_to_server and op[-1]==46 for op in trigger[4]):
                if trigger[0]==ti_tab_pressed:
                    kept.append((ti_tab_pressed,0,0,[(neg|multiplayer_is_server)],[(call_script,'script_coop_retained_confirm_retreat')]))
                    continue
                changed=[(call_script,'script_coop_retained_confirm_retreat') if isinstance(op,tuple) and op[0]==multiplayer_send_int_to_server and op[-1]==46 else op for op in trigger[4]]
                trigger=(trigger[0],trigger[1],trigger[2],trigger[3],changed)
            server=any(isinstance(op,tuple) and op[0]==multiplayer_is_server for op in trigger[3])
            if not server:kept.append(trigger);continue
            # Preserve authoritative casualty accounting and soldier takeover.
            if trigger[0]==ti_on_agent_killed_or_wounded or trigger[0]==0.2:
                kept.append((trigger[0],trigger[1],trigger[2],trigger[3],participant_loops(trigger[4])))
        mission[5][:]=kept
        mission[5].extend([
            (0.5,0,0,[(multiplayer_is_server),(eq,'$g_cycle_result_sent',0)],[
                (try_for_players,':recipient',1),(player_is_active,':recipient'),
                    (player_slot_eq,':recipient',PARTICIPANT,1),(player_slot_eq,':recipient',6000,1),
                    # Once per agent and recipient: resending every agent each
                    # tick floods the reliable queue and labels trickle in.
                    (store_add,':sent_slot',6300,':recipient'),
                    (try_for_agents,':agent'),(agent_is_human,':agent'),(agent_slot_eq,':agent',':sent_slot',0),
                        (agent_get_team,':team',':agent'),(is_between,':team',0,2),
                        (agent_get_group,':group',':agent'),
                        (multiplayer_send_4_int_to_player,':recipient',multiplayer_event_multiplayer_campaign_server_events,83,':agent',':team',':group'),
                        (agent_set_slot,':agent',':sent_slot',1),
                    (try_end),
                (try_end),
            ]),
            (ti_on_agent_killed_or_wounded,0,0,[(multiplayer_is_server),(eq,'$g_cycle_result_sent',0)],[
                (store_trigger_param_1,':dead'),(store_trigger_param_2,':killer'),
                (call_script,'script_coop_retained_kill_xp',':dead',':killer'),
                (try_begin),(ge,':dead',0),(call_script,'script_coop_retained_courage_death',':dead',':killer'),(try_end),
            ]),
            # Native morale: nearby friends and fleeing comrades move courage;
            # soldiers below their limit rout (never before 45 s, never heroes).
            (3,0,0,[(multiplayer_is_server),(eq,'$g_cycle_result_sent',0),(eq,'$g_cycle_armies_spawned',1)],[
                (call_script,'script_coop_retained_courage_others'),
                (store_mission_timer_a,':mission_time'),
                (try_for_agents,':agent'),(agent_is_human,':agent'),(agent_is_alive,':agent'),(agent_is_non_player,':agent'),
                    (call_script,'script_coop_retained_run_away',':agent',':mission_time'),
                (try_end),
            ]),
            (ti_after_mission_start,0,0,[(neg|multiplayer_is_server)],[(assign,'$g_retained_retreat_question',0),(assign,'$g_multiplayer_allow_player_banners',0),
                (assign,'$g_terrain_diag_count',0)]),
            # Terrain diagnostics: a client's own soldier should stand on the client's ground
            # (0 cm) when the host and client generated the same battle map.
            (2,0,0,[(neg|multiplayer_is_server),(lt,'$g_terrain_diag_count',6)],[
                (multiplayer_get_my_player,':me'),(ge,':me',0),(player_get_agent_id,':agent',':me'),(ge,':agent',0),
                (agent_is_alive,':agent'),(val_add,'$g_terrain_diag_count',1),
                (set_fixed_point_multiplier,100),(agent_get_position,pos21,':agent'),
                (position_get_distance_to_terrain,reg56,pos21),(position_get_z,reg57,pos21),(store_current_scene,reg58),
                (assign,reg59,'$g_retained_terrain_seed'),
                ]+player_context.debug('terrain (client): scene {reg58}, seed {reg59}: my soldier at {reg57} cm, {reg56} cm above my ground')+[
            ]),
            (ti_after_mission_start,0,0,[(multiplayer_is_server)],[(assign,'$g_terrain_diag_count',0),
                (store_current_scene,reg58),(assign,reg59,'$g_retained_terrain_seed'),(assign,reg56,'$g_retained_river_seed'),
                (assign,reg57,'$g_retained_flora_seed'),
                ]+player_context.debug('terrain (host): scene {reg58}, seeds {reg59}/{reg56}/{reg57}')+[]),
            (2,0,0,[(multiplayer_is_server),(eq,'$g_cycle_armies_spawned',1),(lt,'$g_terrain_diag_count',2)],[
                (val_add,'$g_terrain_diag_count',1),(set_fixed_point_multiplier,100),
                (try_for_agents,':agent'),(agent_is_human,':agent'),(agent_slot_eq,':agent',6103,1),
                    (agent_get_position,pos21,':agent'),(position_get_distance_to_terrain,reg56,pos21),(position_get_z,reg57,pos21),
                    (assign,reg58,':agent'),
                    ]+player_context.debug('terrain (host): player soldier {reg58} at {reg57} cm, {reg56} cm above the host ground')+[
                (try_end),
            ]),
            (ti_question_answered,0,0,[(neg|multiplayer_is_server)],[
                (store_trigger_param_1,':answer'),(eq,'$g_retained_retreat_question',1),
                (assign,'$g_retained_retreat_question',0),
                (try_begin),(eq,':answer',0),
                    (multiplayer_send_int_to_server,multiplayer_event_multiplayer_campaign_client_events,46),(try_end),
            ]),
            (ti_after_mission_start,0,0,[(multiplayer_is_server)],[
                (team_set_relation,0,1,-1),
                (store_faction_of_party,':a','$g_cycle_attacker_party'),(team_set_faction,0,':a'),
                (store_faction_of_party,':b','$g_cycle_defender_party'),(team_set_faction,1,':b'),
            ]),
            (0.1,0,0,[(multiplayer_is_server),(eq,'$g_cycle_result_sent',0)],[
                (store_current_scene,':scene'),
                (try_for_players,':player',1),(player_is_active,':player'),
                    (player_slot_eq,':player',PARTICIPANT,1),(player_slot_eq,':player',6000,1),
                    (try_begin),(player_slot_eq,':player',CONFIRMED,0),
                        (multiplayer_send_4_int_to_player,':player',multiplayer_event_multiplayer_campaign_server_events,
                            EV_TERRAIN_SEEDS,'$g_retained_terrain_seed','$g_retained_river_seed','$g_retained_flora_seed'),
                        (multiplayer_send_3_int_to_player,':player',multiplayer_event_multiplayer_campaign_server_events,67,':scene','mt_native_session_probe'),
                        (player_set_slot,':player',CONFIRMED,1),
                    (try_end),
                (try_end),
                (try_for_range,':index',0,'$g_retained_party_count'),
                    (store_add,':slot',COHORT_BASE,':index'),(party_get_slot,':party','$g_cycle_attacker_party',':slot'),
                    (party_slot_eq,':party',6017,0),
                    (party_get_slot,':team',':party',6015),(party_get_slot,':owner',':party',6016),
                    (assign,':can_spawn',1),(assign,':hero',-1),
                    (try_begin),(ge,':owner',1),
                        (assign,':can_spawn',0),(player_is_active,':owner'),(player_slot_eq,':owner',6000,1),
                        (player_get_troop_id,':hero',':owner'),(assign,':can_spawn',1),
                        (player_set_team_no,':owner',':team'),
                    (try_end),(eq,':can_spawn',1),
                    (party_set_slot,':party',6017,1),
                    (store_mul,':entry',':team',32),
                    (try_begin),(eq,'$g_retained_siege',1),(eq,':team',1),(assign,':entry',10),(try_end),
                    (set_fixed_point_multiplier,100),(entry_point_get_position,pos5,':entry'),
                    # Generated maps place their entry points far apart (over 400 m on the large
                    # ones): as in a Native field battle, the second army stands about FIELD_SPAN_M metres from
                    # the first, on the line towards its own entry point and facing the same way.
                    # A map without that entry point gets the first army's heading instead.
                    (try_begin),(neq,':entry',0),
                        (position_get_x,':entry_x',pos5),(position_get_y,':entry_y',pos5),
                        (entry_point_get_position,pos6,0),(position_get_x,':first_x',pos6),(position_get_y,':first_y',pos6),
                        (try_begin),(eq,':entry_x',0),(eq,':entry_y',0),
                            (copy_position,pos5,pos6),(position_move_y,pos5,FIELD_SPAN_CM),(position_rotate_z,pos5,180),
                        (else_try),(gt,'$g_retained_terrain_seed',0),
                            (get_distance_between_positions,':span',pos5,pos6),(gt,':span',FIELD_SPAN_CM),
                            (store_sub,':dx',':entry_x',':first_x'),(store_sub,':dy',':entry_y',':first_y'),
                            (val_mul,':dx',FIELD_SPAN_M),(val_div,':dx',':span'),(val_mul,':dx',100),
                            (val_mul,':dy',FIELD_SPAN_M),(val_div,':dy',':span'),(val_mul,':dy',100),
                            (val_add,':dx',':first_x'),(val_add,':dy',':first_y'),
                            (position_set_x,pos5,':dx'),(position_set_y,pos5,':dy'),
                        (try_end),
                    (try_end),
                    (position_get_x,reg57,pos5),(position_get_y,reg58,pos5),(position_get_z,reg59,pos5),(assign,reg56,':party'),(assign,reg60,':entry'),
                    ]+player_context.debug('spawn: army {reg56} at entry {reg60}: {reg57}, {reg58}, height {reg59} cm')+[
                    (party_get_num_companion_stacks,':stacks',':party'),(assign,':spawned',0),
                    (try_for_range,':stack',0,':stacks'),
                        (party_stack_get_troop_id,':troop',':party',':stack'),
                        (party_stack_get_size,':size',':party',':stack'),(party_stack_get_num_wounded,':wounds',':party',':stack'),
                        (store_sub,':healthy',':size',':wounds'),
                        (store_mul,':loss_slot',':troop',2),(val_add,':loss_slot',6200),
                        (store_add,':wound_slot',':loss_slot',1),
                        (party_set_slot,':party',':loss_slot',0),(party_set_slot,':party',':wound_slot',0),
                        (try_begin),(troop_is_hero,':troop'),(store_troop_health,':health',':troop'),
                            (assign,':healthy',0),(try_begin),(gt,':health',15),(assign,':healthy',1),(try_end),
                        (try_end),
                        (try_for_range,':soldier',0,':healthy'),
                            (copy_position,pos4,pos5),
                            (store_mod,':column',':spawned',10),(store_div,':row',':spawned',10),
                            (store_mul,':x',':column',150),(val_sub,':x',750),(store_mul,':y',':row',150),
                            (position_move_x,pos4,':x'),(position_move_y,pos4,':y'),
                            # Generated maps vary in height; their terrain now matches on every machine.
                            (try_begin),(gt,'$g_retained_terrain_seed',0),(position_set_z_to_ground_level,pos4),(try_end),
                            (set_spawn_position,pos4),
                            (spawn_agent,':troop'),(assign,':agent',reg0),
                            (agent_set_team,':agent',':team'),(assign,':group',0),
                            (try_begin),(ge,':owner',1),(assign,':group',':owner'),(try_end),
                            (agent_set_group,':agent',':group'),
                            (agent_set_slot,':agent',6100,':party'),(agent_set_slot,':agent',6101,':troop'),
                            (try_begin),(troop_is_hero,':troop'),(agent_set_hit_points,':agent',':health',0),(try_end),
                            # Native's starting courage: level, chance and party morale.
                            (store_character_level,':courage_level',':troop'),(val_mul,':courage_level',35),
                            (store_random_in_range,':courage',5000,8000),(val_add,':courage',':courage_level'),
                            (party_get_morale,':courage_morale',':party'),(val_sub,':courage_morale',70),
                            (val_mul,':courage_morale',30),(val_add,':courage',':courage_morale'),
                            (agent_set_slot,':agent',slot_agent_courage_score,':courage'),
                            (try_begin),(eq,':troop',':hero'),(agent_set_slot,':agent',6103,1),
                                (player_control_agent,':owner',':agent'),(team_set_leader,':owner',':agent'),(try_end),
                            (val_add,':spawned',1),
                        (try_end),
                    (try_end),
                    (assign,reg56,':party'),(assign,reg57,':spawned'),
                    ]+player_context.debug('spawn: army {reg56} put {reg57} soldiers on the field')+[
                    (try_begin),(ge,':owner',1),(player_is_active,':owner'),
                        (player_set_slot,':owner',6001,1),(team_give_order,':owner',grc_everyone,mordr_charge),
                    (try_end),
                (try_end),
                (assign,'$g_cycle_armies_spawned',1),
            ]),
            (0.25,0,0,[(multiplayer_is_server),(eq,'$g_cycle_result_sent',0),(eq,'$g_cycle_armies_spawned',1)],[
                (assign,':side0',0),(assign,':side1',0),(assign,':pending',0),
                (try_for_range,':index',0,'$g_retained_party_count'),
                    (store_add,':slot',COHORT_BASE,':index'),(party_get_slot,':party','$g_cycle_attacker_party',':slot'),
                    (party_slot_eq,':party',6017,0),(party_get_slot,':pending_owner',':party',6016),
                    (try_begin),(lt,':pending_owner',1),(assign,':pending',1),
                    # A joining player's army that never loads in stops holding the battle open.
                    (else_try),(player_is_active,':pending_owner'),
                        (party_get_slot,':joined_at',':party',JOIN_TIME_SLOT),(store_application_time,':now'),
                        (store_sub,':waited',':now',':joined_at'),(is_between,':waited',0,JOIN_LOAD_TIMEOUT_MS),(assign,':pending',1),(try_end),
                (try_end),
                (eq,':pending',0),
                # Routed soldiers no longer hold the field, as in Native.
                (try_for_agents,':agent'),(agent_is_human,':agent'),(agent_is_alive,':agent'),
                    (agent_slot_eq,':agent',slot_agent_is_running_away,0),
                    (agent_get_team,':team',':agent'),
                    (try_begin),(eq,':team',0),(val_add,':side0',1),
                    (else_try),(eq,':team',1),(val_add,':side1',1),(try_end),
                (try_end),
                (this_or_next|gt,'$g_cycle_retreat_requested',0),(this_or_next|eq,':side0',0),(eq,':side1',0),
                (assign,'$g_cycle_result_sent',1),(assign,'$g_full_host_probe_request',4),
                (assign,':winner',-1),(try_begin),(eq,':side1',0),(assign,':winner',0),
                (else_try),(eq,':side0',0),(assign,':winner',1),(try_end),
                (try_begin),(gt,'$g_cycle_retreat_requested',0),
                    (store_sub,':retreat_team','$g_cycle_retreat_requested',1),(store_sub,':winner',1,':retreat_team'),(try_end),
                (assign,reg56,':winner'),(assign,reg57,':side0'),(assign,reg58,':side1'),(assign,reg59,'$g_cycle_retreat_requested'),
                ]+player_context.debug('battle over: winning side {reg56}, attackers standing {reg57}, defenders standing {reg58}, retreat {reg59}')+[
                # Native's casualty parties per player, before losses leave the armies.
                (assign,':human_winner',0),
                (try_for_players,':recipient',1),(player_is_active,':recipient'),(player_slot_eq,':recipient',PARTICIPANT,1),
                    (call_script,'script_coop_ctx_after_battle',':recipient',':winner'),
                    (player_get_team_no,':recipient_team',':recipient'),(eq,':recipient_team',':winner'),
                    (eq,'$g_cycle_retreat_requested',0),(assign,':human_winner',1),
                (try_end),
                (assign,':losing_root',-1),
                (try_begin),(eq,':winner',0),(assign,':losing_root','$g_cycle_defender_party'),
                (else_try),(eq,':winner',1),(assign,':losing_root','$g_cycle_attacker_party'),(try_end),
                (call_script,'script_coop_retained_release_bystanders'),
                (try_for_agents,':agent'),(agent_is_human,':agent'),(agent_is_alive,':agent'),
                    (agent_get_slot,':troop',':agent',6101),(troop_is_hero,':troop'),
                    (store_agent_hit_points,':health',':agent',0),(troop_set_health,':troop',':health'),(try_end),
                (try_for_range,':index',0,'$g_retained_party_count'),
                    (store_add,':slot',COHORT_BASE,':index'),(party_get_slot,':party','$g_cycle_attacker_party',':slot'),
                    (party_get_num_companion_stacks,':stacks',':party'),(assign,':army_killed',0),(assign,':army_wounded',0),
                    (try_for_range_backwards,':stack',0,':stacks'),
                        (party_stack_get_troop_id,':troop',':party',':stack'),
                        (store_mul,':loss_slot',':troop',2),(val_add,':loss_slot',6200),(store_add,':wound_slot',':loss_slot',1),
                        (party_get_slot,':killed',':party',':loss_slot'),(party_get_slot,':wounds',':party',':wound_slot'),
                        (try_begin),(troop_is_hero,':troop'),(val_add,':wounds',':killed'),(assign,':killed',0),
                            (try_begin),(gt,':wounds',0),(troop_set_health,':troop',0),(try_end),(try_end),
                        (party_remove_members,':party',':troop',':killed'),(party_wound_members,':party',':troop',':wounds'),
                        (val_add,':army_killed',':killed'),(val_add,':army_wounded',':wounds'),
                    (try_end),
                    (assign,reg56,':party'),(party_get_num_companions,reg57,':party'),(assign,reg58,':army_killed'),(assign,reg59,':army_wounded'),
                    ]+player_context.debug('army {reg56}: {reg57} troops after the battle ({reg58} killed, {reg59} wounded)')+[
                    (party_leave_cur_battle,':party'),(enable_party,':party'),(party_set_slot,':party',slot_party_coop_battle_slot,0),
                    (call_script,'script_coop_retained_set_cooldown',':party'),
                    (try_for_players,':recipient',1),(player_is_active,':recipient'),
                        (player_slot_eq,':recipient',slot_player_coop_char_state,coop_char_state_ready),
                        (call_script,'script_coop_retained_send_map_party',':recipient',':party',0),
                    (try_end),
                (try_end),
                (try_for_range,':index',0,'$g_retained_party_count'),
                    (store_add,':slot',COHORT_BASE,':index'),(party_get_slot,':party','$g_cycle_attacker_party',':slot'),
                    (party_get_slot,':team',':party',6015),
                    (try_begin),(eq,':human_winner',1),(eq,':party',':losing_root'),
                        # Native total victory loots, takes prisoners, then clears it.
                        (party_is_non_player,':party'),(neg|is_between,':party',centers_begin,centers_end),
                        (disable_party,':party'),
                        # Cleared by Native's victory menu, or after a few hours if nobody gets there.
                        (store_current_hours,':defeat_deadline'),(val_add,':defeat_deadline',DEFEAT_CLEAR_HOURS),
                        (party_set_slot,':party',player_context.DEFEATED_SLOT,':defeat_deadline'),
                        (try_for_players,':recipient',1),(player_is_active,':recipient'),
                            (player_slot_eq,':recipient',slot_player_coop_char_state,coop_char_state_ready),
                            (multiplayer_send_2_int_to_player,':recipient',multiplayer_event_multiplayer_campaign_server_events,79,':party'),
                        (try_end),
                    (else_try),
                        (try_begin),(ge,':winner',0),(neq,':team',':winner'),(eq,'$g_cycle_retreat_requested',0),
                            (call_script,'script_coop_retained_defeated_ai',':party'),
                        (try_end),
                        (call_script,'script_coop_retained_resume_ai',':party'),
                    (try_end),
                (try_end),
                (try_begin),(eq,'$g_retained_siege',1),(eq,':side1',0),(eq,'$g_cycle_retreat_requested',0),
                    (call_script,'script_coop_siege_capture_consequences','$g_cycle_attacker','$g_cycle_defender_party'),(try_end),
                (try_for_players,':player',1),(player_is_active,':player'),(player_slot_eq,':player',PARTICIPANT,1),
                    (call_script,'script_coop_save_character',':player'),
                    (multiplayer_send_3_int_to_player,':player',multiplayer_event_multiplayer_campaign_server_events,68,
                        '$g_cycle_attacker_party','$g_cycle_defender_party'),(try_end),
                (try_for_players,':player',1),(player_is_active,':player'),(player_slot_eq,':player',PARTICIPANT,0),
                    (player_slot_eq,':player',slot_player_coop_char_state,coop_char_state_ready),
                    (call_script,'script_coop_probe_push_return_rosters',':player'),(try_end),
            ]),
        ])
