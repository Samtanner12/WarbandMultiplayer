# -*- coding: ascii -*-
"""Run Native game menus on the host inside one player's context and mirror
them to that player's client (VANILLA_ARCHITECTURE.md, step 1).

Native code that names the single-player party/troop is rewritten at build
time to read $g_ctx_party/$g_ctx_troop. Both default to 0, the ids of
p_main_party and trp_player, so behaviour outside a context is unchanged."""
import os, re
from header_common import *
from header_operations import *
from header_game_menus import mnf_scale_picture
from module_constants import *

CTX_PLAYER, CTX_PARTY, CTX_TROOP = '$g_ctx_player', '$g_ctx_party', '$g_ctx_troop'
MIRRORED_MENUS = ['simple_encounter']
BANK_PLAYER_BASE = 20000          # player slots: this player's bank
BANK_HOLDER, BANK_HOST_BASE = 'trp_temp_array_c', 20000   # host values while a context is open
MENU_SLOT = 19398                 # player slot: Native menu the player is in
OPTION_MAP_BASE = 19300           # client player slots: mirror row -> Native option index
MAX_OPTIONS = 12
SERVER = multiplayer_event_multiplayer_campaign_server_events
CLIENT = multiplayer_event_multiplayer_campaign_client_events
EV_MENU_STRING = 129              # string event, read in game_receive_network_message
EV_MENU_BEGIN, EV_MENU_OPTION, EV_MENU_SHOW, EV_MENU_CLOSE, EV_MENU_MESSAGE = 95, 96, 97, 98, 99
EV_MENU_CHOOSE = 93               # client -> host
# Native globals that describe "the player's" encounter, swapped per player.
PLAYER_SCOPED = re.compile(r'^\$(g_encounter|g_encountered|encountered_party|g_enemy|g_ally_party|'
    r'g_battle_result|g_engaged_enemy|new_encounter|cant_leave_encounter|g_leave_encounter|talk_context|'
    r'g_player_surrenders|g_enemy_surrenders|g_next_menu|num_routed|g_friend_fit|g_enemy_fit|'
    r'g_player_raiding_village|g_village_raid_evil|playerparty_prebattle|g_strength_contribution_of_player|'
    r'g_last_rest_center|loot_screen_shown|battle_renown_value|cant_talk_to_enemy|capture_screen_shown|'
    r'g_starting_strength|last_defeated_hero|last_freed_hero|routed_party_added|thanked_by_ally_leader|'
    r'npc_grievance|npc_praise|npc_with_grievance|disable_npc_complaints|g_move_heroes)')
# Single-player scene setup and engine main-party battle attachment.
DROPPED_SCRIPTS = ['script_setup_party_meeting', 'script_let_nearby_parties_join_current_battle']
DROPPED_OPS = set(globals()[name] for name in ['set_jump_mission', 'jump_to_scene', 'set_party_battle_mode',
    'set_battle_advantage', 'unlock_achievement', 'party_quick_attach_to_current_battle', 'rest_for_hours',
    'rest_for_hours_interactive', 'set_jump_entry', 'modify_visitors_at_site', 'reset_visitors', 'set_visitor',
    'set_visitors'] if name in globals())
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
    if code in DROPPED_OPS: return []
    if code == jump_to_menu: return [(assign, '$g_ctx_menu_next', op[1])]
    if code in CLOSE_OPS: return [(assign, '$g_ctx_menu_close', 1)]
    if code == change_screen_mission: return [(assign, '$g_ctx_menu_battle', 1)]
    if code == set_background_mesh: return [(assign, '$g_ctx_menu_mesh', op[1])]
    if code == leave_encounter: return [(call_script, 'script_coop_retained_release_encounter', CTX_PARTY)]
    if code == encountered_party_is_attacker:
        return [(call_script, 'script_cf_coop_ctx_encountered_not_attacking' if op[0] & neg
                 else 'script_cf_coop_ctx_encountered_attacks')]
    if code == display_message:
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

def install_native(scripts):
    from module_game_menus import game_menus
    menus = dict((m[0], m) for m in game_menus)
    by_name = dict(scripts)
    # Native scripts reachable from the mirrored menus run in context too.
    closure, pending = set(), []
    for name in MIRRORED_MENUS: pending += called_scripts(menu_ops(menus[name]))
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

    enter = [(store_script_param, ':player', 1), (store_add, CTX_PLAYER, ':player', 1),
             (player_get_party_id, CTX_PARTY, ':player'), (player_get_troop_id, CTX_TROOP, ':player')]
    leave = [(store_script_param, ':player', 1)]
    for i, name in enumerate(bank):
        enter += [(troop_set_slot, BANK_HOLDER, BANK_HOST_BASE + i, name), (player_get_slot, name, ':player', BANK_PLAYER_BASE + i)]
        leave += [(player_set_slot, ':player', BANK_PLAYER_BASE + i, name), (troop_get_slot, name, BANK_HOLDER, BANK_HOST_BASE + i)]
    leave += [(assign, CTX_PLAYER, 0), (assign, CTX_PARTY, 0), (assign, CTX_TROOP, 0)]

    generated = [('coop_ctx_enter', enter), ('coop_ctx_exit', leave),
        ('cf_coop_ctx_encountered_attacks', [(get_party_ai_current_object, ':target', '$g_encountered_party'), (eq, ':target', CTX_PARTY)]),
        ('cf_coop_ctx_encountered_not_attacking', [(get_party_ai_current_object, ':target', '$g_encountered_party'), (neq, ':target', CTX_PARTY)]),
        ('coop_ctx_send_message', [(try_begin), (gt, CTX_PLAYER, 0), (store_sub, ':player', CTX_PLAYER, 1),
            (multiplayer_send_int_to_player, ':player', SERVER, EV_MENU_MESSAGE),
            (multiplayer_send_string_to_player, ':player', EV_MENU_STRING, s49), (try_end)])]
    for name in MIRRORED_MENUS:
        generated += [('coop_menu_show_' + name, show_script(menus[name])),
                      ('coop_menu_choose_' + name, choose_script(menus[name]))]
    generated += [('coop_menu_present', present_script()), ('coop_menu_choose', choose_dispatch()),
                  ('coop_ctx_start_encounter', start_encounter_script())]
    scripts += generated

    for name, ops in scripts:
        if name == 'game_event_party_encounter':
            for i, op in enumerate(ops):
                if (isinstance(op, tuple) and op[0] == multiplayer_send_4_int_to_player and
                        op[3] == multiplayer_event_multiplayer_campaign_server_event_player_start_encounter):
                    ops[i] = (call_script, 'script_coop_ctx_start_encounter', op[1], op[4], op[5], op[6])
        if name == 'game_receive_network_message':
            ops[0:0] = [(store_script_param, ':mirror_event', 2),
                (try_begin), (eq, ':mirror_event', EV_MENU_STRING), (neg|multiplayer_is_server),
                    (call_script, 'script_coop_menu_mirror_string'),
                (try_end), (neq, ':mirror_event', EV_MENU_STRING)]
    scripts.append(('coop_menu_mirror_string', [
        (try_begin), (eq, '$g_mirror_dict_ready', 0), (dict_create, '$g_mirror_dict'), (assign, '$g_mirror_dict_ready', 1), (try_end),
        (try_begin), (eq, '$g_mirror_expect', 2), (display_message, '@{s0}'),
        (else_try), (eq, '$g_mirror_expect', 1), (assign, reg5, '$g_mirror_count'),
            (dict_set_str, '$g_mirror_dict', '@mo{reg5}', s0), (val_add, '$g_mirror_count', 1),
        (else_try), (dict_set_str, '$g_mirror_dict', '@mtext', s0),
        (try_end), (assign, '$g_mirror_expect', 0)]))

def send_string(text):
    return [(str_store_string, s49, '@' + text), (multiplayer_send_string_to_player, ':player', EV_MENU_STRING, s49)]

def show_script(menu):
    ops = [(store_script_param, ':player', 1),
           (assign, '$g_ctx_menu_close', 0), (assign, '$g_ctx_menu_battle', 0), (assign, '$g_ctx_menu_mesh', 0),
           (try_begin)] + translated(menu[4]) + [(try_end),
           (try_begin), (lt, '$g_ctx_menu_next', 0), (eq, '$g_ctx_menu_close', 0), (eq, '$g_ctx_menu_battle', 0),
           (multiplayer_send_3_int_to_player, ':player', SERVER, EV_MENU_BEGIN, '$g_ctx_menu_mesh', 0)] + send_string(menu[2])
    for index, option in enumerate(menu[5][:MAX_OPTIONS]):
        ops += [(try_begin)] + translated(option[1]) + [
            (multiplayer_send_3_int_to_player, ':player', SERVER, EV_MENU_OPTION, index, 0)] + send_string(option[2]) + [(try_end)]
    return ops + [(multiplayer_send_2_int_to_player, ':player', SERVER, EV_MENU_SHOW, 'mnu_' + menu[0]), (try_end)]

def choose_script(menu):
    # Re-checks the option's condition on the host before its consequence.
    ops = [(store_script_param, ':player', 1), (store_script_param, ':option', 2),
           (assign, '$g_ctx_menu_close', 0), (assign, '$g_ctx_menu_battle', 0)]
    for index, option in enumerate(menu[5][:MAX_OPTIONS]):
        ops += [(try_begin), (eq, ':option', index)] + translated(option[1]) + [
            (try_begin)] + translated(option[3]) + [(try_end), (try_end)]
    return ops + [(try_begin), (lt, '$g_ctx_menu_next', 0), (eq, '$g_ctx_menu_close', 0), (eq, '$g_ctx_menu_battle', 0),
                  (assign, '$g_ctx_menu_next', 'mnu_' + menu[0]), (try_end)]

def present_script():
    ops = [(store_script_param, ':player', 1),
        (try_for_range, ':step', 0, 8), (ge, '$g_ctx_menu_next', 0), (eq, '$g_ctx_menu_battle', 0),
            (assign, ':menu', '$g_ctx_menu_next'), (assign, '$g_ctx_menu_next', -1),
            (player_set_slot, ':player', MENU_SLOT, ':menu'), (assign, ':handled', 0)]
    for name in MIRRORED_MENUS:
        ops += [(try_begin), (eq, ':menu', 'mnu_' + name),
                (call_script, 'script_coop_menu_show_' + name, ':player'), (assign, ':handled', 1), (try_end)]
    ops += [(try_begin), (eq, ':handled', 0), (assign, '$g_ctx_menu_close', 1),
                (str_store_string, s49, '@That part of the Native encounter is not mirrored yet.'),
                (call_script, 'script_coop_ctx_send_message'),
            (try_end),
        (try_end),
        (try_begin), (eq, '$g_ctx_menu_battle', 1),
            (multiplayer_send_int_to_player, ':player', SERVER, EV_MENU_CLOSE),
            (call_script, 'script_coop_retained_start', ':player', '$g_encountered_party', 0),
            (try_begin), (eq, reg0, 0), (store_add, ':reason', '$g_retained_reject_reason', 10),
                (multiplayer_send_2_int_to_player, ':player', SERVER,
                    multiplayer_event_multiplayer_campaign_server_event_battle_rejected, ':reason'),
                (call_script, 'script_coop_retained_release_encounter', CTX_PARTY),
            (try_end),
        (else_try), (eq, '$g_ctx_menu_close', 1),
            (multiplayer_send_int_to_player, ':player', SERVER, EV_MENU_CLOSE),
        (try_end)]
    return ops

def choose_dispatch():
    ops = [(store_script_param, ':player', 1), (store_script_param, ':option', 2), (try_begin),
           (player_is_active, ':player'), (player_slot_eq, ':player', slot_player_coop_char_state, coop_char_state_ready),
           (player_get_slot, ':menu', ':player', MENU_SLOT), (gt, ':menu', 0),
           (call_script, 'script_coop_ctx_enter', ':player'), (assign, '$g_ctx_menu_next', -1)]
    for name in MIRRORED_MENUS:
        ops += [(try_begin), (eq, ':menu', 'mnu_' + name),
                (call_script, 'script_coop_menu_choose_' + name, ':player', ':option'), (try_end)]
    return ops + [(call_script, 'script_coop_menu_present', ':player'),
                  (call_script, 'script_coop_ctx_exit', ':player'), (try_end)]

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
            (call_script, 'script_coop_menu_present', ':player'),
            (call_script, 'script_coop_ctx_exit', ':player'),
        (else_try),
            (multiplayer_send_4_int_to_player, ':player', SERVER,
                multiplayer_event_multiplayer_campaign_server_event_player_start_encounter, ':party', ':party2', ':terrain'),
        (try_end)]

def client_server_events():
    """Client handlers for the mirror protocol, placed in the server-event prefix."""
    return [(else_try), (eq, ':retained_event', EV_MENU_BEGIN),
            (store_script_param, '$g_mirror_mesh', 2), (assign, '$g_mirror_count', 0), (assign, '$g_mirror_expect', 0),
        (else_try), (eq, ':retained_event', EV_MENU_OPTION),
            (store_script_param, ':native_option', 2), (multiplayer_get_my_player, ':me'),
            (store_add, ':map_slot', OPTION_MAP_BASE, '$g_mirror_count'), (player_set_slot, ':me', ':map_slot', ':native_option'),
            (assign, '$g_mirror_expect', 1),
        (else_try), (eq, ':retained_event', EV_MENU_SHOW),
            (call_script, 'script_coop_client_request_menu', 'mnu_coop_menu_mirror'),
        (else_try), (eq, ':retained_event', EV_MENU_CLOSE),
            (assign, '$g_mirror_count', 0), (call_script, 'script_coop_client_request_menu', 'mnu_coop_menu_mirror_close'),
        (else_try), (eq, ':retained_event', EV_MENU_MESSAGE), (assign, '$g_mirror_expect', 2)]

CLIENT_EVENT_IDS = [EV_MENU_BEGIN, EV_MENU_OPTION, EV_MENU_SHOW, EV_MENU_CLOSE, EV_MENU_MESSAGE]

def install_menus(menus):
    load = [(try_begin), (eq, '$g_mirror_dict_ready', 1), (dict_get_str, s50, '$g_mirror_dict', '@mtext')]
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

def write_report(closure, bank, world):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'logs', 'player-context-report.txt')
    try:
        with open(path, 'w') as report:
            report.write('Mirrored menus: %s\n' % ', '.join(MIRRORED_MENUS))
            report.write('Native scripts rewritten to the player context (%d):\n  %s\n' % (len(closure), '\n  '.join(sorted(closure))))
            report.write('Per-player globals swapped (%d):\n  %s\n' % (len(bank), '\n  '.join(bank)))
            report.write('Other globals read in context, left shared (%d):\n  %s\n' % (len(world), '\n  '.join(world)))
            report.write('Dropped on the host: %s\n' % ', '.join(DROPPED_SCRIPTS))
    except IOError:
        pass
