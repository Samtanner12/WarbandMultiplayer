# -*- coding: ascii -*-
"""Run Native game menus on the host inside one player's context and mirror
them to that player's client (VANILLA_ARCHITECTURE.md).

Native code that names the single-player party/troop is rewritten at build
time to read $g_ctx_party/$g_ctx_troop. Both default to 0, the ids of
p_main_party and trp_player, so behaviour outside a context is unchanged.
Player-scoped globals and Native's temporary encounter parties are swapped
per player on context entry and exit."""
import os, re
from header_common import *
from header_operations import *
from header_game_menus import mnf_scale_picture
from module_constants import *

CTX_PLAYER, CTX_PARTY, CTX_TROOP = '$g_ctx_player', '$g_ctx_party', '$g_ctx_troop'
MIRRORED_MENUS = ['simple_encounter', 'encounter_retreat_confirm', 'encounter_retreat', 'battle_debrief',
                  'total_victory', 'enemy_slipped_away', 'total_defeat', 'permanent_damage']
BANK_PLAYER_BASE = 20000                                  # player slots: this player's globals
BANK_HOLDER, BANK_HOST_BASE = 'trp_temp_array_c', 20000   # host values while a context is open
# Native's per-encounter temporary parties, saved per player.
BANKED_PARTIES = ['p_main_party_backup', 'p_encountered_party_backup', 'p_collective_friends_backup',
                  'p_total_enemy_casualties', 'p_player_casualties', 'p_enemy_casualties', 'p_ally_casualties',
                  'p_collective_enemy']
PARTY_BANK_BASE, PARTY_STRIDE, PARTY_STACKS, PARTY_PRISONER_STACKS = 21000, 160, 32, 16
MENU_SLOT = 19398                 # player slot: Native menu the player is in
POST_BATTLE_SLOT = 19397          # player slot: 1 while Native post-battle menus are due
OPTION_MAP_BASE = 19300           # client player slots: mirror row -> Native option index
OFFER_BASE, COMPANION_OFFER_BASE, OFFER_STACKS = 19100, 19140, 16   # exchange-screen offers
SNAPSHOT_COUNT, SNAPSHOT_BASE, SNAPSHOT_MAX = 19199, 19200, 32       # client prisoner snapshot
COMPANION_SNAPSHOT_BASE = 19260   # client: companions of offered troops before the screen
ACCOUNT_SLOT, OFFER_COUNT_SLOT, COMPANION_COUNT_SLOT = 6029, 6023, 6031
LOOT_TROOP, LOOT_SLOTS = 'trp_household_possessions', 96
MAX_OPTIONS = 12
SERVER = multiplayer_event_multiplayer_campaign_server_events
CLIENT = multiplayer_event_multiplayer_campaign_client_events
# Network message types are 7 bits (0-127) and all are taken. Menu strings reuse
# the admin welcome-message type, which otherwise only travels client to server;
# the client treats it as mirror text only while a mirror event announced one.
EV_MENU_STRING = multiplayer_event_admin_set_welcome_message
# host -> client
EV_LOOT_SLOT, EV_PRISONER_OFFER = 84, 86
EV_MENU_BEGIN, EV_MENU_OPTION, EV_MENU_SHOW, EV_MENU_CLOSE, EV_MENU_MESSAGE = 95, 96, 97, 98, 99
EV_OPEN_LOOT, EV_COMPANION_OFFER, EV_OPEN_EXCHANGE = 100, 101, 102
# client -> host
EV_TAKE_PRISONERS, EV_RELEASE_PRISONERS, EV_SPOILS_DONE = 90, 91, 92
EV_MENU_CHOOSE, EV_SCREEN_CLOSED, EV_TAKE_COMPANIONS = 93, 94, 103
CLIENT_EVENT_IDS = [EV_MENU_BEGIN, EV_MENU_OPTION, EV_MENU_SHOW, EV_MENU_CLOSE, EV_MENU_MESSAGE,
                    EV_OPEN_LOOT, EV_COMPANION_OFFER, EV_OPEN_EXCHANGE, EV_LOOT_SLOT, EV_PRISONER_OFFER]
HOST_EVENT_IDS = [EV_TAKE_PRISONERS, EV_RELEASE_PRISONERS, EV_SPOILS_DONE, EV_MENU_CHOOSE,
                  EV_SCREEN_CLOSED, EV_TAKE_COMPANIONS]
# Native globals that describe "the player's" encounter, swapped per player.
PLAYER_SCOPED = re.compile(r'^\$(g_encounter|g_encountered|encountered_party|g_enemy|g_ally_party|'
    r'g_battle_result|g_engaged_enemy|new_encounter|cant_leave_encounter|g_leave_encounter|talk_context|'
    r'g_player_surrenders|g_enemy_surrenders|g_next_menu|num_routed|g_friend_fit|g_enemy_fit|'
    r'g_player_raiding_village|g_village_raid_evil|playerparty_|g_strength_contribution_of_player|'
    r'g_last_rest_center|loot_screen_shown|battle_renown_value|cant_talk_to_enemy|capture_screen_shown|'
    r'g_starting_strength|last_defeated_hero|last_freed_hero|routed_party_added|thanked_by_ally_leader|'
    r'npc_grievance|npc_praise|npc_with_grievance|disable_npc_complaints|g_move_heroes|any_allies|'
    r'g_relation_boost|g_private_battle|g_disable_condescending|g_joined_battle_to_help|g_player_luck|'
    r'g_prison_heroes|pin_number|players_kingdom|player_honor|player_right_to_rule|npc_with_personality|'
    r'npc_map_talk_context|g_talk_troop|supported_pretender)')
# Single-player conversation scenes and the engine's main-party battle.
DROPPED_SCRIPTS = ['script_setup_party_meeting', 'script_setup_troop_meeting',
                   'script_let_nearby_parties_join_current_battle']
REPLACED_SCRIPTS = {'script_clear_party_group': 'script_coop_ctx_clear_party_group'}
DROPPED_OPS = set(globals()[name] for name in ['set_jump_mission', 'jump_to_scene', 'set_party_battle_mode',
    'set_battle_advantage', 'unlock_achievement', 'set_achievement_stat',
    'party_quick_attach_to_current_battle', 'rest_for_hours', 'rest_for_hours_interactive', 'set_jump_entry',
    'modify_visitors_at_site', 'reset_visitors', 'set_visitor', 'set_visitors', 'end_current_battle',
    'play_track', 'start_map_conversation', 'party_ignore_player', 'simulate_battle'] if name in globals())
CLOSE_OPS = set([change_screen_return, change_screen_map, change_screen_quit])
FLAGS = neg | this_or_next

def rewrite_refs(op):
    if not isinstance(op, tuple): return op
    return (op[0],) + tuple(CTX_PARTY if a == 'p_main_party' else CTX_TROOP if a == 'trp_player' else a for a in op[1:])

def translate(op):
    """Menu-only operations become host-side flags; context references are rewritten."""
    if not isinstance(op, tuple): return [op]
    code = op[0] & ~FLAGS
    if code == call_script and op[1] in DROPPED_SCRIPTS: return []
    if code == call_script and op[1] in REPLACED_SCRIPTS: return [rewrite_refs((op[0], REPLACED_SCRIPTS[op[1]]) + op[2:])]
    if code in DROPPED_OPS: return []
    if code == get_achievement_stat: return [(assign, op[1], 0)]
    if code == jump_to_menu: return [(assign, '$g_ctx_menu_next', op[1])]
    if code in CLOSE_OPS: return [(assign, '$g_ctx_menu_close', 1)]
    if code == change_screen_mission: return [(assign, '$g_ctx_menu_battle', 1)]
    if code == set_background_mesh: return [(assign, '$g_ctx_menu_mesh', op[1])]
    if code == leave_encounter: return [(call_script, 'script_coop_retained_release_encounter', CTX_PARTY)]
    if code == change_screen_loot: return [(call_script, 'script_coop_ctx_open_loot', rewrite_refs(op)[1])]
    if code == change_screen_exchange_with_party:
        return [(call_script, 'script_coop_ctx_open_exchange', rewrite_refs(op)[1])]
    if code == encountered_party_is_attacker:
        return [(call_script, 'script_cf_coop_ctx_encountered_not_attacking' if op[0] & neg
                 else 'script_cf_coop_ctx_encountered_attacks')]
    if code in (display_message, display_log_message):
        return [(str_store_string, s49, op[1]), (call_script, 'script_coop_ctx_send_message')]
    return [rewrite_refs(op)]

def translated(ops):
    out = []
    for op in ops: out.extend(translate(op))
    return out

def called_scripts(ops):
    return [op[1][len('script_'):] for op in ops if isinstance(op, tuple) and op[0] & ~FLAGS == call_script
            and isinstance(op[1], str) and op[1].startswith('script_') and op[1] not in DROPPED_SCRIPTS]

def globals_in(ops):
    return set(a for op in ops if isinstance(op, tuple) for a in op[1:] if isinstance(a, str) and a.startswith('$'))

def menu_ops(menu):
    ops = list(menu[4])
    for option in menu[5]: ops += list(option[1]) + list(option[3])
    return ops

CTX_STACK_BASE = BANK_HOST_BASE + 900   # holder slots: players whose context is suspended

def party_save(party, base):
    ops = [(party_get_num_companion_stacks, ':bank_n', party), (val_min, ':bank_n', PARTY_STACKS),
           (player_set_slot, ':player', base, ':bank_n'),
           (try_for_range, ':bank_i', 0, ':bank_n'),
               (party_stack_get_troop_id, ':bank_t', party, ':bank_i'), (party_stack_get_size, ':bank_s', party, ':bank_i'),
               (party_stack_get_num_wounded, ':bank_w', party, ':bank_i'),
               (store_mul, ':bank_slot', ':bank_i', 3), (val_add, ':bank_slot', base + 1),
               (player_set_slot, ':player', ':bank_slot', ':bank_t'), (val_add, ':bank_slot', 1),
               (player_set_slot, ':player', ':bank_slot', ':bank_s'), (val_add, ':bank_slot', 1),
               (player_set_slot, ':player', ':bank_slot', ':bank_w'),
           (try_end)]
    prisoners = base + 1 + 3 * PARTY_STACKS
    return ops + [(party_get_num_prisoner_stacks, ':bank_n', party), (val_min, ':bank_n', PARTY_PRISONER_STACKS),
        (player_set_slot, ':player', prisoners, ':bank_n'),
        (try_for_range, ':bank_i', 0, ':bank_n'),
            (party_prisoner_stack_get_troop_id, ':bank_t', party, ':bank_i'),
            (party_prisoner_stack_get_size, ':bank_s', party, ':bank_i'),
            (store_mul, ':bank_slot', ':bank_i', 2), (val_add, ':bank_slot', prisoners + 1),
            (player_set_slot, ':player', ':bank_slot', ':bank_t'), (val_add, ':bank_slot', 1),
            (player_set_slot, ':player', ':bank_slot', ':bank_s'),
        (try_end)]

def party_load(party, base):
    prisoners = base + 1 + 3 * PARTY_STACKS
    return [(party_clear, party), (player_get_slot, ':bank_n', ':player', base),
        (try_for_range, ':bank_i', 0, ':bank_n'),
            (store_mul, ':bank_slot', ':bank_i', 3), (val_add, ':bank_slot', base + 1),
            (player_get_slot, ':bank_t', ':player', ':bank_slot'), (val_add, ':bank_slot', 1),
            (player_get_slot, ':bank_s', ':player', ':bank_slot'), (val_add, ':bank_slot', 1),
            (player_get_slot, ':bank_w', ':player', ':bank_slot'),
            (gt, ':bank_s', 0), (party_add_members, party, ':bank_t', ':bank_s'),
            (party_wound_members, party, ':bank_t', ':bank_w'),
        (try_end),
        (player_get_slot, ':bank_n', ':player', prisoners),
        (try_for_range, ':bank_i', 0, ':bank_n'),
            (store_mul, ':bank_slot', ':bank_i', 2), (val_add, ':bank_slot', prisoners + 1),
            (player_get_slot, ':bank_t', ':player', ':bank_slot'), (val_add, ':bank_slot', 1),
            (player_get_slot, ':bank_s', ':player', ':bank_slot'),
            (gt, ':bank_s', 0), (party_add_prisoners, party, ':bank_t', ':bank_s'),
        (try_end)]

def install_native(scripts):
    from module_game_menus import game_menus
    menus = dict((m[0], m) for m in game_menus)
    by_name = dict(scripts)
    # Native scripts reachable from the mirrored menus run in context too.
    closure, pending = set(), []
    for name in MIRRORED_MENUS: pending += called_scripts(menu_ops(menus[name]))
    pending += ['encounter_init_variables', 'encounter_calculate_fit']
    while pending:
        name = pending.pop()
        if name in closure or name not in by_name or name.startswith('coop_'): continue
        closure.add(name); pending += called_scripts(by_name[name])
    for index, (name, ops) in enumerate(scripts):
        if name in closure: scripts[index] = (name, [rewrite_refs(op) for op in ops])
    referenced = set()
    for name in MIRRORED_MENUS: referenced |= globals_in(menu_ops(menus[name]))
    for name in closure: referenced |= globals_in(by_name[name])
    bank = sorted(g for g in referenced if PLAYER_SCOPED.match(g))
    write_report(closure, bank, sorted(referenced - set(bank)))

    # Bank load/save for one player: globals into player slots, parties serialized.
    load = [(store_script_param, ':player', 1)]
    save = [(store_script_param, ':player', 1)]
    for i, name in enumerate(bank):
        load += [(player_get_slot, name, ':player', BANK_PLAYER_BASE + i)]
        save += [(player_set_slot, ':player', BANK_PLAYER_BASE + i, name)]
    for i, party in enumerate(BANKED_PARTIES):
        load += party_load(party, PARTY_BANK_BASE + i * PARTY_STRIDE)
        save += party_save(party, PARTY_BANK_BASE + i * PARTY_STRIDE)
    activate = [(store_script_param, ':player', 1), (store_add, CTX_PLAYER, ':player', 1),
                (player_get_party_id, CTX_PARTY, ':player'), (player_get_troop_id, CTX_TROOP, ':player'),
                (call_script, 'script_coop_ctx_bank_load', ':player'),
                (call_script, 'script_coop_player_ctx_begin', ':player')]
    if '$players_kingdom' in bank:
        # The player's realm, not Native's single-player kingdom.
        activate += [(store_faction_of_party, '$players_kingdom', CTX_PARTY)]
    host_save = [(troop_set_slot, BANK_HOLDER, BANK_HOST_BASE + i, name) for i, name in enumerate(bank)]
    host_restore = [(troop_get_slot, name, BANK_HOLDER, BANK_HOST_BASE + i) for i, name in enumerate(bank)]
    # Contexts nest (a battle started from one player's menu admits others):
    # the open context is suspended onto a stack and resumed on exit.
    enter = [(store_script_param, ':player', 1),
        (try_begin), (eq, '$g_ctx_depth', 0)] + host_save + [
        (else_try),
            (store_sub, ':outer', CTX_PLAYER, 1),
            (call_script, 'script_coop_player_ctx_end', 0), (call_script, 'script_coop_ctx_bank_save', ':outer'),
            (store_add, ':stack_slot', CTX_STACK_BASE, '$g_ctx_depth'), (troop_set_slot, BANK_HOLDER, ':stack_slot', ':outer'),
        (try_end),
        (val_add, '$g_ctx_depth', 1),
        (call_script, 'script_coop_ctx_activate', ':player')]
    leave = [(store_script_param, ':player', 1),
        (call_script, 'script_coop_player_ctx_end', 1), (call_script, 'script_coop_ctx_bank_save', ':player'),
        (val_sub, '$g_ctx_depth', 1), (val_max, '$g_ctx_depth', 0),
        (try_begin), (eq, '$g_ctx_depth', 0)] + host_restore + [
            (assign, CTX_PLAYER, 0), (assign, CTX_PARTY, 0), (assign, CTX_TROOP, 0),
        (else_try),
            (store_add, ':stack_slot', CTX_STACK_BASE, '$g_ctx_depth'), (troop_get_slot, ':outer', BANK_HOLDER, ':stack_slot'),
            (call_script, 'script_coop_ctx_activate', ':outer'),
        (try_end)]

    generated = [('coop_ctx_bank_load', load), ('coop_ctx_bank_save', save), ('coop_ctx_activate', activate),
        ('coop_ctx_enter', enter), ('coop_ctx_exit', leave),
        ('cf_coop_ctx_encountered_attacks', [(get_party_ai_current_object, ':target', '$g_encountered_party'), (eq, ':target', CTX_PARTY)]),
        ('cf_coop_ctx_encountered_not_attacking', [(get_party_ai_current_object, ':target', '$g_encountered_party'), (neq, ':target', CTX_PARTY)]),
        ('coop_ctx_send_message', [(try_begin), (gt, CTX_PLAYER, 0), (store_sub, ':player', CTX_PLAYER, 1),
            (multiplayer_send_int_to_player, ':player', SERVER, EV_MENU_MESSAGE),
            (multiplayer_send_string_to_player, ':player', EV_MENU_STRING, s49), (try_end)])]
    for name in MIRRORED_MENUS:
        generated += [('coop_menu_show_' + name, show_script(menus[name])),
                      ('coop_menu_choose_' + name, choose_script(menus[name]))]
    generated += [('coop_menu_present', present_script()), ('coop_menu_choose', choose_dispatch()),
                  ('coop_ctx_start_encounter', start_encounter_script())] + session_scripts() + battle_scripts()
    scripts += generated

    for name, ops in scripts:
        if name == 'game_event_party_encounter':
            for i, op in enumerate(ops):
                if (isinstance(op, tuple) and op[0] == multiplayer_send_4_int_to_player and
                        op[3] == multiplayer_event_multiplayer_campaign_server_event_player_start_encounter):
                    ops[i] = (call_script, 'script_coop_ctx_start_encounter', op[1], op[4], op[5], op[6])
        if name == 'game_receive_network_message':
            ops[0:0] = [(store_script_param, ':mirror_event', 2),
                (assign, ':mirror_handled', 0),
                (try_begin), (eq, ':mirror_event', EV_MENU_STRING), (neg|multiplayer_is_server), (gt, '$g_mirror_expect', 0),
                    (call_script, 'script_coop_menu_mirror_string'),
                (assign, ':mirror_handled', 1),
                (try_end), (eq, ':mirror_handled', 0)]
        if name == 'coop_trade_client_diff_and_send':
            # The loot screen reuses the trade close-diff against its own troop.
            for i, op in enumerate(ops):
                if isinstance(op, tuple) and 'trp_find_item_cheat' in op:
                    ops[i] = tuple(':trade_merchant' if arg == 'trp_find_item_cheat' else arg for arg in op)
            ops[0:0] = [(assign, ':trade_merchant', 'trp_find_item_cheat'),
                (try_begin), (gt, '$g_retained_loot_merchant', 0),
                    (assign, ':trade_merchant', '$g_retained_loot_merchant'), (assign, '$g_retained_loot_merchant', 0),
                (try_end)]
    scripts += client_scripts()

def send_string(text):
    return [(str_store_string, s49, '@' + text), (multiplayer_send_string_to_player, ':player', EV_MENU_STRING, s49)]

def show_script(menu):
    ops = [(store_script_param, ':player', 1),
           (assign, '$g_ctx_menu_close', 0), (assign, '$g_ctx_menu_battle', 0), (assign, '$g_ctx_menu_mesh', 0),
           (assign, '$g_ctx_menu_screen', 0),
           (try_begin)] + translated(menu[4]) + [(try_end),
           (try_begin), (lt, '$g_ctx_menu_next', 0), (eq, '$g_ctx_menu_close', 0), (eq, '$g_ctx_menu_battle', 0),
           (eq, '$g_ctx_menu_screen', 0),
           (multiplayer_send_3_int_to_player, ':player', SERVER, EV_MENU_BEGIN, '$g_ctx_menu_mesh', 0)] + send_string(menu[2])
    for index, option in enumerate(menu[5][:MAX_OPTIONS]):
        ops += [(try_begin)] + translated(option[1]) + [
            (multiplayer_send_3_int_to_player, ':player', SERVER, EV_MENU_OPTION, index, 0)] + send_string(option[2]) + [(try_end)]
    return ops + [(multiplayer_send_2_int_to_player, ':player', SERVER, EV_MENU_SHOW, 'mnu_' + menu[0]), (try_end)]

def choose_script(menu):
    # Re-checks the option's condition on the host before its consequence.
    ops = [(store_script_param, ':player', 1), (store_script_param, ':option', 2),
           (assign, '$g_ctx_menu_close', 0), (assign, '$g_ctx_menu_battle', 0), (assign, '$g_ctx_menu_screen', 0)]
    for index, option in enumerate(menu[5][:MAX_OPTIONS]):
        ops += [(try_begin), (eq, ':option', index)] + translated(option[1]) + [
            (try_begin)] + translated(option[3]) + [(try_end), (try_end)]
    return ops + [(try_begin), (lt, '$g_ctx_menu_next', 0), (eq, '$g_ctx_menu_close', 0), (eq, '$g_ctx_menu_battle', 0),
                  (eq, '$g_ctx_menu_screen', 0), (assign, '$g_ctx_menu_next', 'mnu_' + menu[0]), (try_end)]

def present_script():
    ops = [(store_script_param, ':player', 1),
        (try_for_range, ':step', 0, 8), (ge, '$g_ctx_menu_next', 0), (eq, '$g_ctx_menu_battle', 0),
            (eq, '$g_ctx_menu_screen', 0),
            (assign, ':menu', '$g_ctx_menu_next'), (assign, '$g_ctx_menu_next', -1),
            (player_set_slot, ':player', MENU_SLOT, ':menu'), (assign, ':handled', 0)]
    for name in MIRRORED_MENUS:
        ops += [(try_begin), (eq, ':menu', 'mnu_' + name),
                (call_script, 'script_coop_menu_show_' + name, ':player'), (assign, ':handled', 1), (try_end)]
    ops += [(try_begin), (eq, ':handled', 0), (assign, '$g_ctx_menu_close', 1),
                (str_store_string, s49, '@That part of the Native campaign is not available in multiplayer yet.'),
                (call_script, 'script_coop_ctx_send_message'),
                (call_script, 'script_coop_retained_release_encounter', CTX_PARTY),
            (try_end),
        (try_end),
        (try_begin), (eq, '$g_ctx_menu_screen', 1),
        (else_try), (eq, '$g_ctx_menu_battle', 1),
            (multiplayer_send_int_to_player, ':player', SERVER, EV_MENU_CLOSE),
            (call_script, 'script_coop_retained_start', ':player', '$g_encountered_party', 0),
            (try_begin), (eq, reg0, 0), (store_add, ':reason', '$g_retained_reject_reason', 10),
                (multiplayer_send_2_int_to_player, ':player', SERVER,
                    multiplayer_event_multiplayer_campaign_server_event_battle_rejected, ':reason'),
                (call_script, 'script_coop_retained_release_encounter', CTX_PARTY),
            (try_end),
        (else_try), (eq, '$g_ctx_menu_close', 1),
            (player_set_slot, ':player', MENU_SLOT, 0),
            (multiplayer_send_int_to_player, ':player', SERVER, EV_MENU_CLOSE),
        (try_end)]
    return ops

def commit_ops():
    # Native menus change the player's troop and party on the host; persist and resync.
    return [(call_script, 'script_coop_save_character', ':player'),
            (call_script, 'script_coop_send_char_sync_to_client', ':player'),
            (call_script, 'script_coop_push_player_inventory', ':player'),
            (call_script, 'script_coop_ctx_push_own_roster', ':player')]

def choose_dispatch():
    ops = [(store_script_param, ':player', 1), (store_script_param, ':option', 2), (try_begin),
           (player_is_active, ':player'), (player_slot_eq, ':player', slot_player_coop_char_state, coop_char_state_ready),
           (player_get_slot, ':menu', ':player', MENU_SLOT), (gt, ':menu', 0),
           (call_script, 'script_coop_ctx_enter', ':player'), (assign, '$g_ctx_menu_next', -1)]
    for name in MIRRORED_MENUS:
        ops += [(try_begin), (eq, ':menu', 'mnu_' + name),
                (call_script, 'script_coop_menu_choose_' + name, ':player', ':option'), (try_end)]
    return ops + [(call_script, 'script_coop_menu_present', ':player'),
                  (call_script, 'script_coop_ctx_exit', ':player')] + commit_ops() + [(try_end)]

def start_encounter_script():
    # Native game_event_party_encounter (single-player branch) for a plain
    # hostile encounter, then Native's mnu_simple_encounter. Anything else, or
    # $g_coop_legacy_encounter_menu = 1, keeps the multiplayer encounter menu.
    return [(store_script_param, ':player', 1), (store_script_param, ':party', 2),
        (store_script_param, ':party2', 3), (store_script_param, ':terrain', 4),
        (try_begin), (eq, '$g_coop_legacy_encounter_menu', 0), (lt, ':party2', 0),
            (gt, ':party', 0), (party_is_active, ':party'),
            (neg|is_between, ':party', multiplayer_campaign_player_parties_begin, multiplayer_campaign_player_parties_end),
            (call_script, 'script_coop_ctx_enter', ':player'),
            (assign, '$g_encountered_party', ':party'), (assign, '$g_encountered_party_2', -1),
            (store_faction_of_party, '$g_encountered_party_faction', ':party'),
            (store_faction_of_party, ':own_faction', CTX_PARTY),
            (store_relation, '$g_encountered_party_relation', '$g_encountered_party_faction', ':own_faction'),
            (party_get_slot, '$g_encountered_party_type', ':party', slot_party_type),
            (party_get_template_id, '$g_encountered_party_template', ':party'),
            (call_script, 'script_party_count_fit_regulars', CTX_PARTY), (assign, '$playerparty_prebattle_regulars', reg0),
            (assign, '$g_last_rest_center', -1), (assign, '$talk_context', 0),
            (assign, '$g_player_surrenders', 0), (assign, '$g_enemy_surrenders', 0),
            (assign, '$g_leave_encounter', 0), (assign, '$g_engaged_enemy', 0), (assign, '$new_encounter', 1),
            (assign, '$g_ctx_menu_next', 'mnu_simple_encounter'), (assign, '$g_ctx_menu_battle', 0),
            (assign, '$g_ctx_menu_screen', 0),
            (call_script, 'script_coop_menu_present', ':player'),
            (call_script, 'script_coop_ctx_exit', ':player'),
        (else_try),
            (multiplayer_send_4_int_to_player, ':player', SERVER,
                multiplayer_event_multiplayer_campaign_server_event_player_start_encounter, ':party', ':party2', ':terrain'),
        (try_end)]

def session_scripts():
    """Native loot and exchange screens opened by a host-run menu."""
    return [
    ('coop_ctx_open_loot', [(store_script_param, ':source', 1),
        (try_begin), (gt, CTX_PLAYER, 0), (store_sub, ':player', CTX_PLAYER, 1),
            (troop_clear_inventory, LOOT_TROOP),
            (store_troop_gold, ':old_gold', LOOT_TROOP), (troop_remove_gold, LOOT_TROOP, ':old_gold'),
            (multiplayer_send_4_int_to_player, ':player', SERVER, EV_LOOT_SLOT, -1, 0, 0),
            (troop_get_inventory_capacity, ':capacity', ':source'), (val_min, ':capacity', LOOT_SLOTS),
            (try_for_range, ':slot', 0, ':capacity'),
                (troop_get_inventory_slot, ':item', ':source', ':slot'), (ge, ':item', 0),
                (troop_get_inventory_slot_modifier, ':imod', ':source', ':slot'),
                (troop_set_inventory_slot, LOOT_TROOP, ':slot', ':item'),
                (troop_set_inventory_slot_modifier, LOOT_TROOP, ':slot', ':imod'),
                (multiplayer_send_4_int_to_player, ':player', SERVER, EV_LOOT_SLOT, ':slot', ':item', ':imod'),
            (try_end),
            (player_set_slot, ':player', slot_player_coop_merchant_troop, LOOT_TROOP),
            (multiplayer_send_int_to_player, ':player', SERVER, EV_OPEN_LOOT),
            (assign, '$g_ctx_menu_screen', 1),
        (try_end)]),
    ('coop_ctx_open_exchange', [(store_script_param, ':source', 1),
        (try_begin), (gt, CTX_PLAYER, 0), (store_sub, ':player', CTX_PLAYER, 1),
            (player_get_slot, ':account', ':player', slot_player_coop_steam_acctid),
            (player_set_slot, ':player', ACCOUNT_SLOT, ':account'),
            (multiplayer_send_4_int_to_player, ':player', SERVER, EV_PRISONER_OFFER, -1, 0, 0),
            (party_get_num_prisoner_stacks, ':stacks', ':source'), (val_min, ':stacks', OFFER_STACKS), (assign, ':n', 0),
            (try_for_range, ':i', 0, ':stacks'),
                (party_prisoner_stack_get_troop_id, ':troop', ':source', ':i'), (neg|troop_is_hero, ':troop'),
                (party_prisoner_stack_get_size, ':count', ':source', ':i'),
                (store_mul, ':slot', ':n', 2), (val_add, ':slot', OFFER_BASE),
                (player_set_slot, ':player', ':slot', ':troop'), (val_add, ':slot', 1), (player_set_slot, ':player', ':slot', ':count'),
                (multiplayer_send_4_int_to_player, ':player', SERVER, EV_PRISONER_OFFER, ':n', ':troop', ':count'),
                (val_add, ':n', 1),
            (try_end),
            (player_set_slot, ':player', OFFER_COUNT_SLOT, ':n'),
            (party_get_num_companion_stacks, ':stacks', ':source'), (val_min, ':stacks', OFFER_STACKS), (assign, ':n', 0),
            (try_for_range, ':i', 0, ':stacks'),
                (party_stack_get_troop_id, ':troop', ':source', ':i'), (neg|troop_is_hero, ':troop'),
                (party_stack_get_size, ':count', ':source', ':i'),
                (store_mul, ':slot', ':n', 2), (val_add, ':slot', COMPANION_OFFER_BASE),
                (player_set_slot, ':player', ':slot', ':troop'), (val_add, ':slot', 1), (player_set_slot, ':player', ':slot', ':count'),
                (multiplayer_send_4_int_to_player, ':player', SERVER, EV_COMPANION_OFFER, ':n', ':troop', ':count'),
                (val_add, ':n', 1),
            (try_end),
            (player_set_slot, ':player', COMPANION_COUNT_SLOT, ':n'),
            (multiplayer_send_int_to_player, ':player', SERVER, EV_OPEN_EXCHANGE),
            (assign, '$g_ctx_menu_screen', 1),
        (try_end)]),
    # Host: the player took offered prisoners / rescued troops, within limits.
    ('coop_ctx_take_offer', [(store_script_param, ':player', 1), (store_script_param, ':troop', 2),
        (store_script_param, ':count', 3), (store_script_param, ':companions', 4),
        (try_begin), (player_is_active, ':player'), (player_slot_eq, ':player', slot_player_coop_char_state, coop_char_state_ready),
            (player_get_slot, ':account', ':player', slot_player_coop_steam_acctid), (player_slot_eq, ':player', ACCOUNT_SLOT, ':account'),
            (gt, ':count', 0), (neg|troop_is_hero, ':troop'),
            (player_get_party_id, ':army', ':player'), (party_is_active, ':army'),
            (assign, ':base', OFFER_BASE), (player_get_slot, ':stacks', ':player', OFFER_COUNT_SLOT),
            (try_begin), (eq, ':companions', 1),
                (assign, ':base', COMPANION_OFFER_BASE), (player_get_slot, ':stacks', ':player', COMPANION_COUNT_SLOT),
                (party_get_free_companions_capacity, ':room', ':army'),
            (else_try),
                (party_get_skill_level, ':skill', ':army', 'skl_prisoner_management'), (store_mul, ':room', ':skill', 5),
                (party_get_num_prisoners, ':held', ':army'), (val_sub, ':room', ':held'),
            (try_end),
            (val_min, ':count', ':room'),
            (try_for_range, ':i', 0, ':stacks'), (gt, ':count', 0),
                (store_mul, ':slot', ':i', 2), (val_add, ':slot', ':base'),
                (player_slot_eq, ':player', ':slot', ':troop'), (val_add, ':slot', 1),
                (player_get_slot, ':offered', ':player', ':slot'),
                (assign, ':taken', ':count'), (val_min, ':taken', ':offered'), (gt, ':taken', 0),
                (try_begin), (eq, ':companions', 1), (party_add_members, ':army', ':troop', ':taken'),
                (else_try), (party_add_prisoners, ':army', ':troop', ':taken'), (try_end),
                (val_sub, ':offered', ':taken'), (player_set_slot, ':player', ':slot', ':offered'),
                (val_sub, ':count', ':taken'),
            (try_end),
        (try_end)]),
    ('coop_ctx_release_prisoners', [(store_script_param, ':player', 1), (store_script_param, ':troop', 2),
        (store_script_param, ':count', 3),
        (try_begin), (player_is_active, ':player'), (player_slot_eq, ':player', slot_player_coop_char_state, coop_char_state_ready),
            (gt, ':count', 0), (neg|troop_is_hero, ':troop'),
            (player_get_party_id, ':army', ':player'), (party_is_active, ':army'),
            (party_count_prisoners_of_type, ':held', ':army', ':troop'), (val_min, ':count', ':held'), (gt, ':count', 0),
            (party_remove_prisoners, ':army', ':troop', ':count'),
        (try_end)]),
    # Host: the client closed a Native screen; Native shows the menu again.
    ('coop_ctx_screen_closed', [(store_script_param, ':player', 1),
        (try_begin), (player_is_active, ':player'), (player_slot_eq, ':player', slot_player_coop_char_state, coop_char_state_ready),
            (player_get_slot, ':menu', ':player', MENU_SLOT), (gt, ':menu', 0),
            (call_script, 'script_coop_ctx_enter', ':player'),
            (assign, '$g_ctx_menu_next', ':menu'), (assign, '$g_ctx_menu_battle', 0), (assign, '$g_ctx_menu_screen', 0),
            (call_script, 'script_coop_menu_present', ':player'),
            (call_script, 'script_coop_ctx_exit', ':player'),
            ] + commit_ops() + [
        (try_end)]),
    ('coop_ctx_push_own_roster', [(store_script_param, ':player', 1),
        (try_begin), (player_get_party_id, ':army', ':player'), (party_is_active, ':army'),
            (multiplayer_send_2_int_to_player, ':player', SERVER, 71, ':army'),
            (party_get_num_companion_stacks, ':stacks', ':army'),
            (try_for_range, ':stack', 0, ':stacks'), (party_stack_get_troop_id, ':troop', ':army', ':stack'),
                (party_stack_get_size, ':size', ':army', ':stack'), (party_stack_get_num_wounded, ':wounds', ':army', ':stack'),
                (multiplayer_send_4_int_to_player, ':player', SERVER, 72, ':troop', ':size', ':wounds'),
            (try_end),
        (try_end)]),
    # Native's clear_party_group, but a human army is never emptied: its
    # owner goes through Native's total defeat instead.
    ('coop_ctx_clear_party_group', [(store_script_param, ':party', 1),
        (try_begin), (gt, ':party', 0), (party_is_active, ':party'),
            (neg|is_between, ':party', multiplayer_campaign_player_parties_begin, multiplayer_campaign_player_parties_end),
            (neg|is_between, ':party', centers_begin, centers_end),
            (call_script, 'script_clear_party_group', ':party'),
            (try_for_players, ':recipient', 1), (player_is_active, ':recipient'),
                (player_slot_eq, ':recipient', slot_player_coop_char_state, coop_char_state_ready),
                (multiplayer_send_2_int_to_player, ':recipient', SERVER, 79, ':party'),
            (try_end),
            (try_begin), (gt, ':party', 'p_spawn_points_end'), (remove_party, ':party'),
            (else_try), (disable_party, ':party'), (try_end),
        (try_end)]),
    ]

def battle_scripts():
    """Feed Native's encounter state from the retained battle."""
    cohort = [(try_for_range, ':index', 0, '$g_retained_party_count'),
        (store_add, ':cohort_slot', 17000, ':index'),
        (party_get_slot, ':cohort', '$g_cycle_attacker_party', ':cohort_slot'),
        (party_is_active, ':cohort'), (party_get_slot, ':cohort_team', ':cohort', 6015)]
    return [
    # At admission: Native's encounter setup (backups, starting strengths).
    ('coop_ctx_before_battle', [(store_script_param, ':player', 1), (store_script_param, ':team', 2),
        (try_begin), (player_is_active, ':player'),
            (call_script, 'script_coop_ctx_enter', ':player'),
            (assign, ':enemy', '$g_cycle_defender_party'),
            (try_begin), (eq, ':team', 1), (assign, ':enemy', '$g_cycle_attacker_party'), (try_end),
            (try_begin), (neq, '$g_encountered_party', ':enemy'),
                # Joined or player-versus-player battle: no Native encounter yet.
                (assign, '$g_encountered_party', ':enemy'), (assign, '$g_encountered_party_2', -1),
                (store_faction_of_party, '$g_encountered_party_faction', ':enemy'),
                (party_get_template_id, '$g_encountered_party_template', ':enemy'),
                (call_script, 'script_encounter_init_variables'),
            (try_end),
            (assign, '$g_enemy_party', ':enemy'),
            (party_clear, 'p_total_enemy_casualties'),
            (call_script, 'script_party_count_fit_regulars', CTX_PARTY), (assign, '$playerparty_prebattle_regulars', reg0),
            (call_script, 'script_coop_ctx_exit', ':player'),
        (try_end)]),
    # At the result: Native's casualty parties and battle result, for menus later.
    ('coop_ctx_after_battle', [(store_script_param, ':player', 1), (store_script_param, ':winner', 2),
        (try_begin), (player_is_active, ':player'),
            (player_get_team_no, ':team', ':player'),
            (call_script, 'script_coop_ctx_enter', ':player'),
            (assign, '$g_battle_result', -1),
            (try_begin), (eq, ':winner', ':team'), (assign, '$g_battle_result', 1),
            (else_try), (store_add, ':own_retreat', ':team', 1), (eq, '$g_cycle_retreat_requested', ':own_retreat'),
                (assign, '$g_battle_result', 0),
            (try_end),
            (assign, '$g_engaged_enemy', 1), (assign, '$g_next_menu', 'mnu_simple_encounter'),
            (assign, '$any_allies_at_the_last_battle', 0), (assign, '$g_ally_party', -1),
            (party_clear, 'p_player_casualties'), (party_clear, 'p_enemy_casualties'), (party_clear, 'p_ally_casualties'),
            ] + cohort + [
                (assign, ':casualties', 'p_enemy_casualties'),
                (try_begin), (eq, ':cohort', CTX_PARTY), (assign, ':casualties', 'p_player_casualties'),
                (else_try), (eq, ':cohort_team', ':team'), (assign, ':casualties', 'p_ally_casualties'),
                    (assign, '$any_allies_at_the_last_battle', 1),
                    (try_begin), (lt, '$g_ally_party', 0), (neg|is_between, ':cohort', centers_begin, centers_end),
                        (assign, '$g_ally_party', ':cohort'), (try_end),
                (try_end),
                (party_get_num_companion_stacks, ':stacks', ':cohort'),
                (try_for_range, ':stack', 0, ':stacks'),
                    (party_stack_get_troop_id, ':troop', ':cohort', ':stack'),
                    (store_mul, ':loss_slot', ':troop', 2), (val_add, ':loss_slot', 6200), (store_add, ':wound_slot', ':loss_slot', 1),
                    (party_get_slot, ':killed', ':cohort', ':loss_slot'), (party_get_slot, ':wounded', ':cohort', ':wound_slot'),
                    (store_add, ':lost', ':killed', ':wounded'), (gt, ':lost', 0),
                    (party_add_members, ':casualties', ':troop', ':lost'), (party_wound_members, ':casualties', ':troop', ':wounded'),
                    (try_begin), (eq, ':casualties', 'p_enemy_casualties'),
                        (party_add_members, 'p_total_enemy_casualties', ':troop', ':lost'),
                        (party_wound_members, 'p_total_enemy_casualties', ':troop', ':wounded'),
                    (try_end),
                (try_end),
            (try_end),
            (player_set_slot, ':player', POST_BATTLE_SLOT, 1),
            (call_script, 'script_coop_ctx_exit', ':player'),
        (try_end)]),
    # Back on the map: Native's debrief, then victory, defeat or retreat.
    ('coop_ctx_post_battle', [(store_script_param, ':player', 1),
        (try_begin), (player_is_active, ':player'), (player_slot_eq, ':player', POST_BATTLE_SLOT, 1),
            (player_set_slot, ':player', POST_BATTLE_SLOT, 0),
            (call_script, 'script_coop_ctx_enter', ':player'),
            (assign, '$g_ctx_menu_next', 'mnu_battle_debrief'), (assign, '$g_ctx_menu_battle', 0),
            (assign, '$g_ctx_menu_screen', 0),
            (call_script, 'script_coop_menu_present', ':player'),
            (call_script, 'script_coop_ctx_exit', ':player'),
            ] + commit_ops() + [
        (try_end)]),
    ]

def client_scripts():
    return [
    ('coop_menu_mirror_string', [
        (try_begin), (eq, '$g_mirror_dict_ready', 0), (dict_create, '$g_mirror_dict'), (assign, '$g_mirror_dict_ready', 1), (try_end),
        (try_begin), (eq, '$g_mirror_expect', 2), (display_message, '@{s0}'),
        (else_try), (eq, '$g_mirror_expect', 1), (assign, reg5, '$g_mirror_count'),
            (dict_set_str, '$g_mirror_dict', '@mo{reg5}', s0), (val_add, '$g_mirror_count', 1),
        (else_try), (eq, '$g_mirror_expect', 3), (dict_set_str, '$g_mirror_dict', '@mtext', s0),
        (try_end), (assign, '$g_mirror_expect', 0)]),
    # Client: a Native screen opened by the host closed; report it.
    ('coop_ctx_client_screen_settle', [
        # Options shown before the screen belong to the menu that opened it.
        (try_begin), (gt, '$g_ctx_screen_open', 0), (assign, '$g_mirror_count', 0), (try_end),
        (try_begin), (eq, '$g_ctx_screen_open', 1), (assign, '$g_ctx_screen_open', 0),
            (try_begin), (eq, '$g_coop_trade_screen_open', 1), (assign, '$g_coop_trade_screen_open', 2),
                (assign, '$g_retained_loot_merchant', LOOT_TROOP),
                (call_script, 'script_coop_trade_client_diff_and_send'),
            (try_end),
            (multiplayer_send_int_to_server, CLIENT, EV_SCREEN_CLOSED),
        (else_try), (eq, '$g_ctx_screen_open', 2), (assign, '$g_ctx_screen_open', 0),
            (call_script, 'script_coop_ctx_client_exchange_diff'),
            (multiplayer_send_int_to_server, CLIENT, EV_SCREEN_CLOSED),
        (try_end)]),
    ('coop_ctx_client_open_exchange', [
        (multiplayer_get_my_player, ':me'), (player_get_party_id, ':army', ':me'),
        (party_clear, 'p_temp_party'), (assign, ':n', 0),
        (party_get_num_prisoner_stacks, ':own', ':army'),
        (try_for_range, ':i', 0, ':own'), (lt, ':n', SNAPSHOT_MAX),
            (party_prisoner_stack_get_troop_id, ':troop', ':army', ':i'), (party_prisoner_stack_get_size, ':size', ':army', ':i'),
            (store_mul, ':s', ':n', 2), (val_add, ':s', SNAPSHOT_BASE),
            (player_set_slot, ':me', ':s', ':troop'), (val_add, ':s', 1), (player_set_slot, ':me', ':s', ':size'), (val_add, ':n', 1),
        (try_end),
        (player_get_slot, ':stacks', ':me', OFFER_COUNT_SLOT),
        (try_for_range, ':i', 0, ':stacks'),
            (store_mul, ':slot', ':i', 2), (val_add, ':slot', OFFER_BASE),
            (player_get_slot, ':troop', ':me', ':slot'), (val_add, ':slot', 1), (player_get_slot, ':count', ':me', ':slot'),
            (gt, ':count', 0), (party_add_prisoners, 'p_temp_party', ':troop', ':count'),
            (assign, ':known', 0),
            (try_for_range, ':j', 0, ':n'), (store_mul, ':s', ':j', 2), (val_add, ':s', SNAPSHOT_BASE),
                (player_slot_eq, ':me', ':s', ':troop'), (assign, ':known', 1), (try_end),
            (eq, ':known', 0), (lt, ':n', SNAPSHOT_MAX),
            (store_mul, ':s', ':n', 2), (val_add, ':s', SNAPSHOT_BASE),
            (player_set_slot, ':me', ':s', ':troop'), (val_add, ':s', 1), (player_set_slot, ':me', ':s', 0), (val_add, ':n', 1),
        (try_end),
        (player_set_slot, ':me', SNAPSHOT_COUNT, ':n'),
        (player_get_slot, ':stacks', ':me', COMPANION_COUNT_SLOT),
        (try_for_range, ':i', 0, ':stacks'),
            (store_mul, ':slot', ':i', 2), (val_add, ':slot', COMPANION_OFFER_BASE),
            (player_get_slot, ':troop', ':me', ':slot'), (val_add, ':slot', 1), (player_get_slot, ':count', ':me', ':slot'),
            (party_count_members_of_type, ':before', ':army', ':troop'),
            (store_add, ':s', COMPANION_SNAPSHOT_BASE, ':i'), (player_set_slot, ':me', ':s', ':before'),
            (gt, ':count', 0), (party_add_members, 'p_temp_party', ':troop', ':count'),
        (try_end),
        (assign, '$g_ctx_screen_open', 2),
        (change_screen_exchange_with_party, 'p_temp_party')]),
    ('coop_ctx_client_exchange_diff', [
        (multiplayer_get_my_player, ':me'), (player_get_party_id, ':army', ':me'),
        (player_get_slot, ':n', ':me', SNAPSHOT_COUNT),
        (try_for_range, ':j', 0, ':n'),
            (store_mul, ':s', ':j', 2), (val_add, ':s', SNAPSHOT_BASE),
            (player_get_slot, ':troop', ':me', ':s'), (val_add, ':s', 1), (player_get_slot, ':before', ':me', ':s'),
            (party_count_prisoners_of_type, ':now', ':army', ':troop'), (store_sub, ':delta', ':now', ':before'),
            (try_begin), (gt, ':delta', 0),
                (multiplayer_send_3_int_to_server, CLIENT, EV_TAKE_PRISONERS, ':troop', ':delta'),
            (else_try), (lt, ':delta', 0), (val_mul, ':delta', -1),
                (multiplayer_send_3_int_to_server, CLIENT, EV_RELEASE_PRISONERS, ':troop', ':delta'),
            (try_end),
        (try_end),
        (player_set_slot, ':me', SNAPSHOT_COUNT, 0),
        (player_get_slot, ':stacks', ':me', COMPANION_COUNT_SLOT),
        (try_for_range, ':i', 0, ':stacks'),
            (store_mul, ':slot', ':i', 2), (val_add, ':slot', COMPANION_OFFER_BASE),
            (player_get_slot, ':troop', ':me', ':slot'),
            (store_add, ':s', COMPANION_SNAPSHOT_BASE, ':i'), (player_get_slot, ':before', ':me', ':s'),
            (party_count_members_of_type, ':now', ':army', ':troop'), (store_sub, ':delta', ':now', ':before'),
            (gt, ':delta', 0),
            (multiplayer_send_3_int_to_server, CLIENT, EV_TAKE_COMPANIONS, ':troop', ':delta'),
        (try_end),
        (multiplayer_send_int_to_server, CLIENT, EV_SPOILS_DONE)]),
    ]

def client_server_events():
    """Client handlers for the mirror protocol, placed in the server-event prefix."""
    return [(else_try), (eq, ':retained_event', EV_MENU_BEGIN),
            (store_script_param, '$g_mirror_mesh', 2), (assign, '$g_mirror_count', 0), (assign, '$g_mirror_expect', 3),
        (else_try), (eq, ':retained_event', EV_MENU_OPTION),
            (store_script_param, ':native_option', 2), (multiplayer_get_my_player, ':me'),
            (store_add, ':map_slot', OPTION_MAP_BASE, '$g_mirror_count'), (player_set_slot, ':me', ':map_slot', ':native_option'),
            (assign, '$g_mirror_expect', 1),
        (else_try), (eq, ':retained_event', EV_MENU_SHOW),
            (call_script, 'script_coop_client_request_menu', 'mnu_coop_menu_mirror'),
        (else_try), (eq, ':retained_event', EV_MENU_CLOSE),
            (assign, '$g_mirror_count', 0), (call_script, 'script_coop_client_request_menu', 'mnu_coop_menu_mirror_close'),
        (else_try), (eq, ':retained_event', EV_MENU_MESSAGE), (assign, '$g_mirror_expect', 2),
        (else_try), (eq, ':retained_event', EV_LOOT_SLOT),
            (store_script_param, ':slot', 2), (store_script_param, ':item', 3), (store_script_param, ':imod', 4),
            (try_begin), (eq, ':slot', -1), (troop_clear_inventory, LOOT_TROOP),
            (else_try), (troop_set_inventory_slot, LOOT_TROOP, ':slot', ':item'),
                (troop_set_inventory_slot_modifier, LOOT_TROOP, ':slot', ':imod'), (try_end),
        (else_try), (eq, ':retained_event', EV_OPEN_LOOT),
            (call_script, 'script_coop_trade_snapshot_merchant', LOOT_TROOP),
            (multiplayer_get_my_player, ':me'), (player_get_troop_id, ':hero', ':me'),
            (store_troop_gold, '$g_coop_trade_gold_before', ':hero'),
            (assign, '$g_retained_loot_merchant', LOOT_TROOP),
            (assign, '$g_coop_trade_screen_open', 1), (assign, '$g_ctx_screen_open', 1),
            (change_screen_loot, LOOT_TROOP),
        (else_try), (eq, ':retained_event', EV_PRISONER_OFFER),
            (store_script_param, ':index', 2), (store_script_param, ':troop', 3), (store_script_param, ':count', 4),
            (multiplayer_get_my_player, ':me'),
            (try_begin), (eq, ':index', -1), (player_set_slot, ':me', OFFER_COUNT_SLOT, 0), (player_set_slot, ':me', COMPANION_COUNT_SLOT, 0),
            (else_try), (is_between, ':index', 0, OFFER_STACKS),
                (store_mul, ':slot', ':index', 2), (val_add, ':slot', OFFER_BASE),
                (player_set_slot, ':me', ':slot', ':troop'), (val_add, ':slot', 1), (player_set_slot, ':me', ':slot', ':count'),
                (store_add, ':stacks', ':index', 1), (player_set_slot, ':me', OFFER_COUNT_SLOT, ':stacks'),
            (try_end),
        (else_try), (eq, ':retained_event', EV_COMPANION_OFFER),
            (store_script_param, ':index', 2), (store_script_param, ':troop', 3), (store_script_param, ':count', 4),
            (multiplayer_get_my_player, ':me'), (is_between, ':index', 0, OFFER_STACKS),
            (store_mul, ':slot', ':index', 2), (val_add, ':slot', COMPANION_OFFER_BASE),
            (player_set_slot, ':me', ':slot', ':troop'), (val_add, ':slot', 1), (player_set_slot, ':me', ':slot', ':count'),
            (store_add, ':stacks', ':index', 1), (player_set_slot, ':me', COMPANION_COUNT_SLOT, ':stacks'),
        (else_try), (eq, ':retained_event', EV_OPEN_EXCHANGE),
            (call_script, 'script_coop_ctx_client_open_exchange')]

def host_client_events():
    """Host handlers for client events, placed in the client-event prefix."""
    return [(try_begin), (eq, ':event_type', EV_MENU_CHOOSE), (store_script_param, ':ctx_a', 3),
            (call_script, 'script_coop_menu_choose', ':player_no', ':ctx_a'),
        (else_try), (eq, ':event_type', EV_SCREEN_CLOSED),
            (call_script, 'script_coop_ctx_screen_closed', ':player_no'),
        (else_try), (eq, ':event_type', EV_TAKE_PRISONERS), (store_script_param, ':ctx_a', 3), (store_script_param, ':ctx_b', 4),
            (call_script, 'script_coop_ctx_take_offer', ':player_no', ':ctx_a', ':ctx_b', 0),
        (else_try), (eq, ':event_type', EV_TAKE_COMPANIONS), (store_script_param, ':ctx_a', 3), (store_script_param, ':ctx_b', 4),
            (call_script, 'script_coop_ctx_take_offer', ':player_no', ':ctx_a', ':ctx_b', 1),
        (else_try), (eq, ':event_type', EV_RELEASE_PRISONERS), (store_script_param, ':ctx_a', 3), (store_script_param, ':ctx_b', 4),
            (call_script, 'script_coop_ctx_release_prisoners', ':player_no', ':ctx_a', ':ctx_b'),
        (try_end)] + [(neq, ':event_type', event) for event in HOST_EVENT_IDS]

def install_menus(menus):
    load = [(try_begin), (eq, '$g_ctx_screen_open', 0), (else_try), (call_script, 'script_coop_ctx_client_screen_settle'), (try_end),
            (try_begin), (eq, '$g_mirror_dict_ready', 1), (dict_get_str, s50, '$g_mirror_dict', '@mtext')]
    for row in range(MAX_OPTIONS):
        load += [(assign, reg5, row), (dict_get_str, s51 + row, '$g_mirror_dict', '@mo{reg5}')]
    load += [(try_end), (try_begin), (gt, '$g_mirror_mesh', 0), (set_background_mesh, '$g_mirror_mesh'), (try_end)]
    options = []
    for row in range(MAX_OPTIONS):
        options.append(('mirror_%d' % row, [(gt, '$g_mirror_count', row)], '{s%d}' % (51 + row), [
            (multiplayer_get_my_player, ':me'), (player_get_slot, ':native_option', ':me', OPTION_MAP_BASE + row),
            (assign, '$g_mirror_count', 0),
            (multiplayer_send_2_int_to_server, CLIENT, EV_MENU_CHOOSE, ':native_option')]))
    menus += [('coop_menu_mirror', mnf_scale_picture, '{s50}', 'none', load, options),
              ('coop_menu_mirror_close', 0, ' ', 'none', [(change_screen_return)], [])]

def client_triggers():
    # A Native screen may return to the map instead of the mirror menu.
    return [(0, [(neg|multiplayer_is_server), (multiplayer_is_campaign), (gt, '$g_ctx_screen_open', 0),
                 (call_script, 'script_coop_ctx_client_screen_settle')])]

def write_report(closure, bank, world):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'logs', 'player-context-report.txt')
    try:
        with open(path, 'w') as report:
            report.write('Mirrored menus: %s\n' % ', '.join(MIRRORED_MENUS))
            report.write('Native scripts rewritten to the player context (%d):\n  %s\n' % (len(closure), '\n  '.join(sorted(closure))))
            report.write('Per-player globals swapped (%d):\n  %s\n' % (len(bank), '\n  '.join(bank)))
            report.write('Other globals read in context, left shared (%d):\n  %s\n' % (len(world), '\n  '.join(world)))
            report.write('Per-player parties swapped: %s\n' % ', '.join(BANKED_PARTIES))
            report.write('Dropped on the host: %s\n' % ', '.join(DROPPED_SCRIPTS))
    except IOError:
        pass
