# -*- coding: ascii -*-
"""Host-owned battle spoils, offered through Native's loot and prisoner screens.
The host decides what exists; client screens only report what moved."""
from header_common import *
from header_operations import *
from header_parties import player_loot_share, hero_loot_share
from module_constants import *

LOOT_TROOP = 'trp_household_possessions'
LOOT_SLOTS = 96            # the trade diff covers merchant slots 0-95
OFFER_BASE = 19100         # player slots: (troop, offered) pairs, 16 stacks
SNAPSHOT_COUNT = 19199     # client: entries in the prisoner snapshot
SNAPSHOT_BASE = 19200      # client: (troop, count before screen) pairs
SNAPSHOT_MAX = 32
SERVER = multiplayer_event_multiplayer_campaign_server_events
CLIENT = multiplayer_event_multiplayer_campaign_client_events
EV_LOOT_SLOT, EV_PRISONER_OFFER, EV_XP_GOLD = 84, 86, 89
EV_TAKE_PRISONERS, EV_RELEASE_PRISONERS, EV_SPOILS_DONE = 90, 91, 92

def enemy_cohorts(winner, body):
    return [(try_for_range, ':cohort_index', 0, '$g_retained_party_count'),
        (store_add, ':cohort_slot', 17000, ':cohort_index'),
        (party_get_slot, ':enemy', '$g_cycle_attacker_party', ':cohort_slot'),
        (party_get_slot, ':enemy_team', ':enemy', 6015), (neq, ':enemy_team', winner)] + body + [(try_end)]

def stack_losses(party):
    return [(store_mul, ':loss_slot', ':troop', 2), (val_add, ':loss_slot', 6200),
        (store_add, ':wound_slot', ':loss_slot', 1),
        (party_get_slot, ':killed', party, ':loss_slot'), (party_get_slot, ':wounded', party, ':wound_slot'),
        (store_add, ':losses', ':killed', ':wounded')]

def loot_shares(party):
    # script_calculate_main_party_shares for an arbitrary army.
    return [(assign, ':shares', player_loot_share),
        (party_get_num_companion_stacks, ':share_stacks', party),
        (try_for_range, ':share_stack', 1, ':share_stacks'),
            (party_stack_get_troop_id, ':share_troop', party, ':share_stack'),
            (try_begin), (neg|troop_is_hero, ':share_troop'),
                (party_stack_get_size, ':share_size', party, ':share_stack'), (val_add, ':shares', ':share_size'),
            (else_try), (val_add, ':shares', hero_loot_share), (try_end),
        (try_end)]

def install(scripts):
    scripts += [
    # Native party_give_xp_and_gold, split between every victorious army by size.
    ('coop_retained_battle_xp', [
        (store_script_param, ':winner', 1), (is_between, ':winner', 0, 2),
        (assign, ':gain', 0), (assign, ':side_size', 0),
        (try_for_range, ':i', 0, '$g_retained_party_count'),
            (store_add, ':cohort', 17000, ':i'), (party_get_slot, ':party', '$g_cycle_attacker_party', ':cohort'),
            (party_slot_eq, ':party', 6015, ':winner'), (neg|is_between, ':party', centers_begin, centers_end),
            (party_get_num_companions, ':size', ':party'), (val_add, ':side_size', ':size'),
        (try_end),
        ] + enemy_cohorts(':winner', [
            (party_get_num_companion_stacks, ':stacks', ':enemy'),
            (try_for_range, ':stack', 0, ':stacks'),
                (party_stack_get_troop_id, ':troop', ':enemy', ':stack'), (neg|troop_is_hero, ':troop'),
                ] + stack_losses(':enemy') + [(gt, ':losses', 0),
                (store_character_level, ':level', ':troop'), (store_add, ':each', ':level', 10),
                (val_mul, ':each', ':each'), (val_div, ':each', 10), (val_mul, ':each', ':losses'),
                (val_add, ':gain', ':each'),
            (try_end),
        ]) + [
        (gt, ':gain', 0), (val_max, ':side_size', 1),
        (try_for_range, ':i', 0, '$g_retained_party_count'),
            (store_add, ':cohort', 17000, ':i'), (party_get_slot, ':party', '$g_cycle_attacker_party', ':cohort'),
            (party_slot_eq, ':party', 6015, ':winner'), (neg|is_between, ':party', centers_begin, centers_end),
            (party_get_num_companions, ':size', ':party'),
            (store_mul, ':share', ':gain', ':size'), (val_div, ':share', ':side_size'), (val_min, ':share', 40000),
            (store_random_in_range, ':r', 50, 100), (store_mul, ':xp', ':share', ':r'), (val_div, ':xp', 100),
            (party_add_xp, ':party', ':xp'),
            (party_get_slot, ':owner', ':party', 6016), (ge, ':owner', 1), (player_is_active, ':owner'),
            ] + loot_shares(':party') + [
            (store_mul, ':gold', ':share', player_loot_share), (val_min, ':gold', 60000),
            (store_random_in_range, ':r', 50, 100), (val_mul, ':gold', ':r'), (val_div, ':gold', 100),
            (val_div, ':gold', ':shares'),
            (party_get_num_companion_stacks, ':stacks', ':party'),
            (try_for_range, ':stack', 0, ':stacks'),
                (party_stack_get_troop_id, ':hero', ':party', ':stack'), (troop_is_hero, ':hero'),
                (troop_add_gold, ':hero', ':gold'),
            (try_end),
            (player_get_slot, ':dirty', ':owner', slot_player_coop_char_dirty),
            (val_or, ':dirty', coop_char_dirty_gold), (player_set_slot, ':owner', slot_player_coop_char_dirty, ':dirty'),
            (player_get_troop_id, ':player_troop', ':owner'), (store_troop_gold, ':purse', ':player_troop'),
            (multiplayer_send_2_int_to_player, ':owner', SERVER,
                multiplayer_event_multiplayer_campaign_server_event_trade_gold_sync, ':purse'),
            (multiplayer_send_3_int_to_player, ':owner', SERVER, EV_XP_GOLD, ':xp', ':gold'),
        (try_end),
    ]),
    ('coop_retained_prepare_rewards', [
        (store_script_param, ':winner', 1), (assign, ':recipient', -1),
        (try_for_players, ':p', 1), (player_is_active, ':p'), (player_slot_eq, ':p', 6015, 1),
            (player_set_slot, ':p', 6020, 0), (player_set_slot, ':p', 6021, 0), (player_set_slot, ':p', 6022, 0),
            (player_set_slot, ':p', 6023, 0),
            (player_get_slot, ':account', ':p', slot_player_coop_steam_acctid), (player_set_slot, ':p', 6029, ':account'),
            (player_get_team_no, ':team', ':p'), (eq, ':team', ':winner'), (lt, ':recipient', 0), (assign, ':recipient', ':p'),
        (try_end),
        (troop_clear_inventory, LOOT_TROOP),
        (store_troop_gold, ':old_gold', LOOT_TROOP), (troop_remove_gold, LOOT_TROOP, ':old_gold'),
        (ge, ':recipient', 1), (eq, '$g_cycle_retreat_requested', 0),
        (player_get_party_id, ':army', ':recipient'),
        # Native party_calculate_loot: every enemy casualty is looted once.
        ] + loot_shares(':army') + [
        (party_get_num_companions, ':own_size', ':army'), (assign, ':side_size', 0),
        (try_for_range, ':i', 0, '$g_retained_party_count'),
            (store_add, ':cohort', 17000, ':i'), (party_get_slot, ':ally', '$g_cycle_attacker_party', ':cohort'),
            (party_slot_eq, ':ally', 6015, ':winner'),
            (party_get_num_companions, ':size', ':ally'), (val_add, ':side_size', ':size'),
        (try_end),
        (val_max, ':side_size', 1),
        (store_mul, ':contribution', ':own_size', 100), (val_div, ':contribution', ':side_size'),
        (val_max, ':contribution', 1), (val_min, ':contribution', 100),
        (store_mul, ':probability', player_loot_share, 3), (val_mul, ':probability', ':contribution'),
        (party_get_skill_level, ':looting', ':army', 'skl_looting'), (val_add, ':looting', 10),
        (val_mul, ':probability', ':looting'), (val_div, ':probability', 10), (val_div, ':probability', ':shares'),
        ] + enemy_cohorts(':winner', [
            (party_get_num_companion_stacks, ':stacks', ':enemy'),
            (try_for_range, ':stack', 0, ':stacks'),
                (party_stack_get_troop_id, ':troop', ':enemy', ':stack'), (neg|troop_is_hero, ':troop'),
                ] + stack_losses(':enemy') + [
                (try_for_range, ':unused', 0, ':losses'),
                    (troop_loot_troop, LOOT_TROOP, ':troop', ':probability'),
                (try_end),
            (try_end),
        ]) + [
        (troop_get_inventory_capacity, ':capacity', LOOT_TROOP),
        (try_for_range, ':slot', LOOT_SLOTS, ':capacity'), (troop_set_inventory_slot, LOOT_TROOP, ':slot', -1), (try_end),
        (assign, ':loot_count', 0),
        (try_for_range, ':slot', 0, LOOT_SLOTS),
            (troop_get_inventory_slot, ':item', LOOT_TROOP, ':slot'), (ge, ':item', 0), (val_add, ':loot_count', 1),
        (try_end),
        (player_set_slot, ':recipient', slot_player_coop_merchant_troop, LOOT_TROOP),
        # Wounded regulars become prisoners within the army's prisoner limit.
        (party_get_skill_level, ':skill', ':army', 'skl_prisoner_management'), (store_mul, ':room', ':skill', 5),
        (party_get_num_prisoners, ':held', ':army'), (val_sub, ':room', ':held'), (val_max, ':room', 0),
        (assign, ':prisoner_count', 0), (assign, ':prisoner_stacks', 0),
        ] + enemy_cohorts(':winner', [
            (party_get_num_companion_stacks, ':stacks', ':enemy'),
            (try_for_range_backwards, ':stack', 0, ':stacks'),
                (party_stack_get_troop_id, ':troop', ':enemy', ':stack'), (neg|troop_is_hero, ':troop'),
                ] + stack_losses(':enemy') + [
                (gt, ':wounded', 0), (gt, ':room', 0), (lt, ':prisoner_stacks', 16),
                (assign, ':captured', ':wounded'), (val_min, ':captured', ':room'), (val_sub, ':room', ':captured'),
                (store_mul, ':slot', ':prisoner_stacks', 2), (val_add, ':slot', OFFER_BASE),
                (player_set_slot, ':recipient', ':slot', ':troop'), (val_add, ':slot', 1),
                (player_set_slot, ':recipient', ':slot', ':captured'),
                (party_remove_members, ':enemy', ':troop', ':captured'),
                (val_sub, ':wounded', ':captured'), (party_set_slot, ':enemy', ':wound_slot', ':wounded'),
                (val_add, ':prisoner_count', ':captured'), (val_add, ':prisoner_stacks', 1),
            (try_end),
        ]) + [
        (player_set_slot, ':recipient', 6021, ':loot_count'), (player_set_slot, ':recipient', 6022, ':prisoner_count'),
        (player_set_slot, ':recipient', 6023, ':prisoner_stacks'),
    ]),
    # Mirrors the offered loot and prisoners into the client's screen troops.
    ('coop_retained_send_spoils', [
        (store_script_param, ':player', 1),
        (multiplayer_send_4_int_to_player, ':player', SERVER, EV_LOOT_SLOT, -1, 0, 0),
        (try_begin), (player_slot_ge, ':player', 6021, 1),
            (try_for_range, ':slot', 0, LOOT_SLOTS),
                (troop_get_inventory_slot, ':item', LOOT_TROOP, ':slot'), (ge, ':item', 0),
                (troop_get_inventory_slot_modifier, ':imod', LOOT_TROOP, ':slot'),
                (multiplayer_send_4_int_to_player, ':player', SERVER, EV_LOOT_SLOT, ':slot', ':item', ':imod'),
            (try_end),
        (try_end),
        (multiplayer_send_4_int_to_player, ':player', SERVER, EV_PRISONER_OFFER, -1, 0, 0),
        (player_get_slot, ':stacks', ':player', 6023),
        (try_for_range, ':i', 0, ':stacks'),
            (store_mul, ':slot', ':i', 2), (val_add, ':slot', OFFER_BASE),
            (player_get_slot, ':troop', ':player', ':slot'), (val_add, ':slot', 1),
            (player_get_slot, ':count', ':player', ':slot'),
            (multiplayer_send_4_int_to_player, ':player', SERVER, EV_PRISONER_OFFER, ':i', ':troop', ':count'),
        (try_end),
    ]),
    ('coop_retained_take_prisoners', [
        (store_script_param, ':player', 1), (store_script_param, ':troop', 2), (store_script_param, ':count', 3),
        (player_is_active, ':player'), (player_slot_eq, ':player', slot_player_coop_char_state, coop_char_state_ready),
        (player_get_slot, ':account', ':player', slot_player_coop_steam_acctid), (player_slot_eq, ':player', 6029, ':account'),
        (gt, ':count', 0), (neg|troop_is_hero, ':troop'),
        (player_get_party_id, ':army', ':player'), (party_is_active, ':army'),
        (party_get_skill_level, ':skill', ':army', 'skl_prisoner_management'), (store_mul, ':room', ':skill', 5),
        (party_get_num_prisoners, ':held', ':army'), (val_sub, ':room', ':held'), (val_min, ':count', ':room'),
        (player_get_slot, ':stacks', ':player', 6023),
        (try_for_range, ':i', 0, ':stacks'), (gt, ':count', 0),
            (store_mul, ':slot', ':i', 2), (val_add, ':slot', OFFER_BASE),
            (player_slot_eq, ':player', ':slot', ':troop'), (val_add, ':slot', 1),
            (player_get_slot, ':offered', ':player', ':slot'),
            (assign, ':taken', ':count'), (val_min, ':taken', ':offered'), (gt, ':taken', 0),
            (party_add_prisoners, ':army', ':troop', ':taken'),
            (val_sub, ':offered', ':taken'), (player_set_slot, ':player', ':slot', ':offered'),
            (val_sub, ':count', ':taken'),
        (try_end),
    ]),
    ('coop_retained_release_prisoners', [
        (store_script_param, ':player', 1), (store_script_param, ':troop', 2), (store_script_param, ':count', 3),
        (player_is_active, ':player'), (player_slot_eq, ':player', slot_player_coop_char_state, coop_char_state_ready),
        (gt, ':count', 0), (neg|troop_is_hero, ':troop'),
        (player_get_party_id, ':army', ':player'), (party_is_active, ':army'),
        (party_count_prisoners_of_type, ':held', ':army', ':troop'), (val_min, ':count', ':held'), (gt, ':count', 0),
        (party_remove_prisoners, ':army', ':troop', ':count'),
    ]),
    # Client: Native "take prisoners" screen over the host's offer.
    ('coop_retained_open_prisoners', [
        (multiplayer_get_my_player, ':me'), (player_get_party_id, ':army', ':me'),
        (party_clear, 'p_temp_party'), (assign, ':n', 0),
        (party_get_num_prisoner_stacks, ':own', ':army'),
        (try_for_range, ':i', 0, ':own'), (lt, ':n', SNAPSHOT_MAX),
            (party_prisoner_stack_get_troop_id, ':troop', ':army', ':i'),
            (party_prisoner_stack_get_size, ':size', ':army', ':i'),
            (store_mul, ':s', ':n', 2), (val_add, ':s', SNAPSHOT_BASE),
            (player_set_slot, ':me', ':s', ':troop'), (val_add, ':s', 1), (player_set_slot, ':me', ':s', ':size'),
            (val_add, ':n', 1),
        (try_end),
        (player_get_slot, ':stacks', ':me', 6023),
        (try_for_range, ':i', 0, ':stacks'),
            (store_mul, ':slot', ':i', 2), (val_add, ':slot', OFFER_BASE),
            (player_get_slot, ':troop', ':me', ':slot'), (val_add, ':slot', 1),
            (player_get_slot, ':count', ':me', ':slot'), (gt, ':count', 0),
            (party_add_prisoners, 'p_temp_party', ':troop', ':count'),
            (assign, ':known', 0),
            (try_for_range, ':j', 0, ':n'),
                (store_mul, ':s', ':j', 2), (val_add, ':s', SNAPSHOT_BASE),
                (player_slot_eq, ':me', ':s', ':troop'), (assign, ':known', 1),
            (try_end),
            (eq, ':known', 0), (lt, ':n', SNAPSHOT_MAX),
            (store_mul, ':s', ':n', 2), (val_add, ':s', SNAPSHOT_BASE),
            (player_set_slot, ':me', ':s', ':troop'), (val_add, ':s', 1), (player_set_slot, ':me', ':s', 0),
            (val_add, ':n', 1),
        (try_end),
        (player_set_slot, ':me', SNAPSHOT_COUNT, ':n'),
        (assign, '$g_retained_prisoner_open', 1),
        (change_screen_exchange_with_party, 'p_temp_party'),
    ]),
    # Client: report what the prisoner screen moved; the host re-validates.
    ('coop_retained_prisoner_diff', [
        (multiplayer_get_my_player, ':me'), (player_get_party_id, ':army', ':me'),
        (player_get_slot, ':n', ':me', SNAPSHOT_COUNT),
        (try_for_range, ':j', 0, ':n'),
            (store_mul, ':s', ':j', 2), (val_add, ':s', SNAPSHOT_BASE),
            (player_get_slot, ':troop', ':me', ':s'), (val_add, ':s', 1), (player_get_slot, ':before', ':me', ':s'),
            (party_count_prisoners_of_type, ':now', ':army', ':troop'),
            (store_sub, ':delta', ':now', ':before'),
            (try_begin), (gt, ':delta', 0),
                (multiplayer_send_3_int_to_server, CLIENT, EV_TAKE_PRISONERS, ':troop', ':delta'),
            (else_try), (lt, ':delta', 0), (val_mul, ':delta', -1),
                (multiplayer_send_3_int_to_server, CLIENT, EV_RELEASE_PRISONERS, ':troop', ':delta'),
            (try_end),
        (try_end),
        (player_set_slot, ':me', SNAPSHOT_COUNT, 0),
        (player_get_slot, ':stacks', ':me', 6023), (assign, ':remaining', 0),
        (try_for_range, ':i', 0, ':stacks'),
            (store_mul, ':slot', ':i', 2), (val_add, ':slot', OFFER_BASE),
            (player_get_slot, ':troop', ':me', ':slot'), (val_add, ':slot', 1),
            (party_count_prisoners_of_type, ':left', 'p_temp_party', ':troop'),
            (player_set_slot, ':me', ':slot', ':left'), (val_add, ':remaining', ':left'),
        (try_end),
        (player_set_slot, ':me', 6022, ':remaining'),
        (multiplayer_send_int_to_server, CLIENT, EV_SPOILS_DONE),
    ]),
    ]
    # A failing script fails its caller too (the battle-end trigger included).
    for i in range(len(scripts)):
        if scripts[i][0].startswith('coop_retained_') and scripts[i][1][:1] != [(try_begin)]:
            scripts[i] = (scripts[i][0], [(try_begin)] + scripts[i][1] + [(try_end)])
    for name, ops in scripts:
        if name == 'multiplayer_campaign_client_events':
            ops[:] = [(store_script_param, ':reward_event', 2),
                (try_begin), (eq, ':reward_event', EV_TAKE_PRISONERS),
                    (store_script_param, ':recipient', 1), (store_script_param, ':reward_troop', 3),
                    (store_script_param, ':reward_count', 4),
                    (call_script, 'script_coop_retained_take_prisoners', ':recipient', ':reward_troop', ':reward_count'),
                (else_try), (eq, ':reward_event', EV_RELEASE_PRISONERS),
                    (store_script_param, ':recipient', 1), (store_script_param, ':reward_troop', 3),
                    (store_script_param, ':reward_count', 4),
                    (call_script, 'script_coop_retained_release_prisoners', ':recipient', ':reward_troop', ':reward_count'),
                (else_try), (eq, ':reward_event', EV_SPOILS_DONE),
                    (store_script_param, ':recipient', 1), (player_is_active, ':recipient'),
                    (player_slot_eq, ':recipient', slot_player_coop_char_state, coop_char_state_ready),
                    (call_script, 'script_coop_save_character', ':recipient'),
                    (call_script, 'script_coop_send_char_sync_to_client', ':recipient'),
                (try_end),
                (neq, ':reward_event', EV_TAKE_PRISONERS), (neq, ':reward_event', EV_RELEASE_PRISONERS),
                (neq, ':reward_event', EV_SPOILS_DONE)] + ops
        if name == 'coop_trade_client_diff_and_send':
            # The loot screen reuses the trade close-diff against its own troop.
            for i, op in enumerate(ops):
                if isinstance(op, tuple) and 'trp_find_item_cheat' in op:
                    ops[i] = tuple(':trade_merchant' if arg == 'trp_find_item_cheat' else arg for arg in op)
            ops[0:0] = [(assign, ':trade_merchant', 'trp_find_item_cheat'),
                (try_begin), (gt, '$g_retained_loot_merchant', 0),
                    (assign, ':trade_merchant', '$g_retained_loot_merchant'), (assign, '$g_retained_loot_merchant', 0),
                (try_end)]

def menus(menus):
    for menu in menus:
        if menu[0] == 'coop_retained_debrief':
            menu[5][0][3][:] = [(jump_to_menu, 'mnu_coop_retained_loot')]
    spoils_text = [
        (multiplayer_get_my_player, ':me'),
        # Native screens return to this menu; settle whichever just closed.
        (try_begin), (eq, '$g_retained_loot_open', 1), (assign, '$g_retained_loot_open', 0),
            (eq, '$g_coop_trade_screen_open', 1), (assign, '$g_coop_trade_screen_open', 2),
            (assign, '$g_retained_loot_merchant', LOOT_TROOP),
            (call_script, 'script_coop_trade_client_diff_and_send'),
        (try_end),
        (try_begin), (eq, '$g_retained_prisoner_open', 1), (assign, '$g_retained_prisoner_open', 0),
            (call_script, 'script_coop_retained_prisoner_diff'),
        (try_end),
        (assign, ':items', 0),
        (try_for_range, ':slot', 0, LOOT_SLOTS),
            (troop_get_inventory_slot, ':item', LOOT_TROOP, ':slot'), (ge, ':item', 0), (val_add, ':items', 1),
        (try_end),
        (player_set_slot, ':me', 6021, ':items'),
        (assign, reg1, ':items'), (player_get_slot, reg2, ':me', 6022),
        (try_begin), (eq, reg1, 0), (eq, reg2, 0),
            (str_store_string, s10, '@There is nothing more to take from the battlefield.'),
        (else_try),
            (str_store_string, s10, '@{reg1} items of loot remain on the battlefield and {reg2} wounded enemies can be taken prisoner.'),
        (try_end),
    ]
    menus += [('coop_retained_loot', 0, 'The battle is over.^^{s10}', 'none', spoils_text, [
            ('loot', [(multiplayer_get_my_player, ':me'), (player_slot_ge, ':me', 6021, 1)], 'Take loot.', [
                (call_script, 'script_coop_trade_snapshot_merchant', LOOT_TROOP),
                (multiplayer_get_my_player, ':me'), (player_get_troop_id, ':hero', ':me'),
                (store_troop_gold, '$g_coop_trade_gold_before', ':hero'),
                (assign, '$g_retained_loot_merchant', LOOT_TROOP),
                (assign, '$g_retained_loot_open', 1), (assign, '$g_coop_trade_screen_open', 1),
                (change_screen_loot, LOOT_TROOP)]),
            ('prisoners', [(multiplayer_get_my_player, ':me'), (player_slot_ge, ':me', 6022, 1)], 'Take prisoners.', [
                (call_script, 'script_coop_retained_open_prisoners')]),
            ('continue', [], 'Continue...', [(change_screen_map)]),
        ]),
        ('coop_retained_prisoners', 0, '{s10}', 'none', spoils_text, [
            ('back', [], 'Continue...', [(jump_to_menu, 'mnu_coop_retained_loot')]),
        ])]
