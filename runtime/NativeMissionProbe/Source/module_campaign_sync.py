# -*- coding: ascii -*-
# Campaign authority. Append records to preserve existing module IDs.
from header_common import *
from header_operations import *
from header_triggers import *
from header_parties import *
from module_constants import *
from module_parties import parties

campaign_scripts = [
    ("coop_recover_player_encounter", [
        (store_script_param, ":player", 1),
        (player_slot_eq, ":player", slot_player_coop_char_state, coop_char_state_ready),
        (player_get_party_id, ":party", ":player"),
        (party_get_battle_opponent, ":opponent", ":party"),
        (call_script, "script_coop_release_failed_encounter", ":party", ":opponent"),
    ]),
    ("coop_release_failed_encounter", [
        (store_script_param, ":first", 1), (store_script_param, ":second", 2),
        (assign, ":allowed", 1),
        (try_for_range, ":side", 0, 2),
            (assign, ":party", ":first"),
            (try_begin), (eq, ":side", 1), (assign, ":party", ":second"), (try_end),
            (ge, ":party", 0), (party_is_active, ":party"),
            (party_slot_ge, ":party", slot_party_coop_battle_slot, 1),
            (assign, ":allowed", 0),
        (try_end),
        (try_for_players, ":player", 1),
            (player_is_active, ":player"), (player_get_party_id, ":party", ":player"),
            (this_or_next|eq, ":party", ":first"), (eq, ":party", ":second"),
            (neg|player_slot_eq, ":player", slot_player_coop_in_local_encounter, 0),
            (assign, ":allowed", 0),
        (try_end),
        (eq, ":allowed", 1),
        # No result is applied: this encounter never acquired a battle slot.
        (try_for_range, ":side", 0, 2),
            (assign, ":party", ":first"),
            (try_begin), (eq, ":side", 1), (assign, ":party", ":second"), (try_end),
            (ge, ":party", 0), (party_is_active, ":party"),
            (party_leave_cur_battle, ":party"),
        (try_end),
        (try_for_players, ":player", 1),
            (player_is_active, ":player"), (player_get_party_id, ":party", ":player"),
            (this_or_next|eq, ":party", ":first"), (eq, ":party", ":second"),
            (enable_party, ":party"),
            (party_set_ai_behavior, ":party", ai_bhvr_hold),
            (multiplayer_send_2_int_to_player, ":player", multiplayer_event_multiplayer_campaign_server_events,
                multiplayer_event_multiplayer_campaign_server_event_encounter_resolved, 0),
        (try_end),
        (display_message, "@[ENCOUNTER] Failed launch released both armies; no result applied."),
    ]),
    ("coop_realm_disconnect", [
        (store_script_param, ":player", 1),
        (player_get_slot, ":realm", ":player", slot_player_coop_faction),
        (is_between, ":realm", coop_player_factions_begin, coop_player_factions_end),
        (player_get_slot, ":account", ":player", slot_player_coop_steam_acctid),
        (player_get_troop_id, ":ruler", ":player"),
        (assign, ":regent", -1),
        (try_for_range, ":companion", companions_begin, companions_end),
            (troop_slot_eq, ":companion", slot_troop_occupation, slto_kingdom_hero),
            (store_faction_of_troop, ":holder", ":companion"), (eq, ":holder", ":realm"),
            (assign, ":regent", ":companion"),
        (try_end),
        (faction_set_slot, ":realm", slot_faction_leader, ":regent"),
        (try_for_range, ":center", centers_begin, centers_end),
            (party_slot_eq, ":center", slot_center_coop_owner_acctid, ":account"),
            (party_slot_eq, ":center", slot_town_lord, ":ruler"),
            (party_set_slot, ":center", slot_town_lord, -1),
        (try_end),
        (assign, "$g_coop_world_save_pending", 1),
    ]),
    ("coop_realm_assign", [
        (store_script_param, ":player", 1),
        (player_get_slot, ":account", ":player", slot_player_coop_steam_acctid),
        (assign, ":realm", -1),
        # Zero is the unallocated sentinel, never a shared anonymous realm.
        (neq, ":account", 0),
        (try_for_range, ":candidate", coop_player_factions_begin, coop_player_factions_end),
            (faction_slot_eq, ":candidate", slot_faction_coop_owner_acctid, ":account"),
            (assign, ":realm", ":candidate"),
        (try_end),
        (try_begin),
            (lt, ":realm", 0),
            (try_for_range, ":candidate", coop_player_factions_begin, coop_player_factions_end),
                (lt, ":realm", 0),
                (faction_slot_eq, ":candidate", slot_faction_coop_owner_acctid, 0),
                (assign, ":realm", ":candidate"),
                (faction_set_slot, ":realm", slot_faction_coop_owner_acctid, ":account"),
                (faction_set_slot, ":realm", slot_faction_state, sfs_active),
                (faction_set_slot, ":realm", slot_faction_marshall, -1),
                # Native recruitment and kingdom-hero routines need a culture.
                (try_for_range, ":slot", slot_faction_culture, slot_faction_culture + 1),
                    (faction_get_slot, ":value", "fac_kingdom_2", ":slot"),
                    (faction_set_slot, ":realm", ":slot", ":value"),
                (try_end),
                (try_for_range, ":slot", slot_faction_reinforcements_a, slot_faction_reinforcements_c + 1),
                    (faction_get_slot, ":value", "fac_kingdom_2", ":slot"),
                    (faction_set_slot, ":realm", ":slot", ":value"),
                (try_end),
                (assign, "$g_coop_world_save_pending", 1),
            (try_end),
        (try_end),
        (is_between, ":realm", coop_player_factions_begin, coop_player_factions_end),
        (player_set_slot, ":player", slot_player_coop_faction, ":realm"),
        (player_get_party_id, ":party", ":player"),
        (player_get_troop_id, ":hero", ":player"),
        (party_set_faction, ":party", ":realm"),
        (troop_set_faction, ":hero", ":realm"),
        (faction_set_slot, ":realm", slot_faction_leader, ":hero"),
        (str_store_player_username, s0, ":player"),
        (faction_set_name, ":realm", "@{s0}'s Realm"),
        (try_for_range, ":center", centers_begin, centers_end),
            (party_slot_eq, ":center", slot_center_coop_owner_acctid, ":account"),
            (store_faction_of_party, ":holder", ":center"),
            (eq, ":holder", ":realm"),
            (party_get_slot, ":lord", ":center", slot_town_lord),
            # Companion lords have stable troop IDs; only reconnecting rulers change.
            (neg|is_between, ":lord", companions_begin, companions_end),
            (party_set_slot, ":center", slot_town_lord, ":hero"),
        (try_end),
        (try_for_players, ":recipient", 1),
            (player_is_active, ":recipient"),
            (multiplayer_send_4_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events,
                multiplayer_event_multiplayer_campaign_server_event_player_faction, ":player", ":realm", ":account"),
        (try_end),
        (call_script, "script_coop_realm_snapshot", ":player"),
    ]),
    ("coop_realm_snapshot", [
        (store_script_param, ":recipient", 1),
        (try_for_players, ":player", 1),
            (player_is_active, ":player"),
            (player_get_slot, ":realm", ":player", slot_player_coop_faction),
            (is_between, ":realm", coop_player_factions_begin, coop_player_factions_end),
            (player_get_slot, ":account", ":player", slot_player_coop_steam_acctid),
            (multiplayer_send_4_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events,
                multiplayer_event_multiplayer_campaign_server_event_player_faction, ":player", ":realm", ":account"),
        (try_end),
        # Include offline owners and their saved wars, not just connected players.
        (try_for_range, ":realm", coop_player_factions_begin, coop_player_factions_end),
            (neg|faction_slot_eq, ":realm", slot_faction_coop_owner_acctid, 0),
            (assign, ":online", 0),
            (try_for_players, ":owner_player", 1),
                (player_is_active, ":owner_player"),
                (player_slot_eq, ":owner_player", slot_player_coop_faction, ":realm"),
                (assign, ":online", 1),
            (try_end),
            (try_begin),
                (eq, ":online", 0),
                (faction_get_slot, ":account", ":realm", slot_faction_coop_owner_acctid),
                (multiplayer_send_4_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events,
                    multiplayer_event_multiplayer_campaign_server_event_player_faction, -1, ":realm", ":account"),
            (try_end),
            (try_for_range, ":target", kingdoms_begin, coop_player_factions_end),
                (this_or_next|is_between, ":target", kingdoms_begin, kingdoms_end),
                (is_between, ":target", coop_player_factions_begin, coop_player_factions_end),
                (store_relation, ":relation", ":realm", ":target"),
                (multiplayer_send_4_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events,
                    multiplayer_event_multiplayer_campaign_server_event_realm_relation, ":realm", ":target", ":relation"),
            (try_end),
        (try_end),
        (call_script, "script_coop_clock_send", ":recipient"),
    ]),
    ("coop_realm_diplomacy", [
        (store_script_param, ":player", 1),
        (store_script_param, ":target", 2),
        (store_script_param, ":war", 3),
        (player_slot_eq, ":player", slot_player_coop_char_state, coop_char_state_ready),
        (player_get_slot, ":realm", ":player", slot_player_coop_faction),
        (is_between, ":realm", coop_player_factions_begin, coop_player_factions_end),
        (player_get_slot, ":account", ":player", slot_player_coop_steam_acctid),
        (neq, ":account", 0),
        (faction_slot_eq, ":realm", slot_faction_coop_owner_acctid, ":account"),
        (neq, ":realm", ":target"),
        (this_or_next|is_between, ":target", kingdoms_begin, kingdoms_end),
        (is_between, ":target", coop_player_factions_begin, coop_player_factions_end),
        (faction_slot_eq, ":target", slot_faction_state, sfs_active),
        (assign, ":valid_target", 0),
        (try_begin),
            (is_between, ":target", coop_player_factions_begin, coop_player_factions_end),
            (neg|faction_slot_eq, ":target", slot_faction_coop_owner_acctid, 0),
            (assign, ":valid_target", 1),
        (else_try),
            (is_between, ":target", kingdoms_begin, kingdoms_end),
            (assign, ":valid_target", 1),
        (try_end),
        (eq, ":valid_target", 1),
        (assign, ":relation", 101),
        (assign, "$g_coop_world_save_pending", 1),
        (try_begin),
            (eq, ":war", 1),
            (assign, ":relation", -50),
        (else_try),
            (eq, ":war", 0),
            # Peace needs matching consent; offers survive restarts in faction slots.
            (store_add, ":offer_slot", slot_faction_coop_peace_offers_begin, ":target"),
            (faction_set_slot, ":realm", ":offer_slot", 1),
            (store_add, ":reverse_slot", slot_faction_coop_peace_offers_begin, ":realm"),
            (faction_slot_eq, ":target", ":reverse_slot", 1),
            (assign, ":relation", 0),
        (try_end),
        # An unanswered offer saves its consent but cannot change hostility.
        (le, ":relation", 0),
        (set_relation, ":realm", ":target", ":relation"),
        (store_add, ":offer_slot", slot_faction_coop_peace_offers_begin, ":target"),
        (store_add, ":reverse_slot", slot_faction_coop_peace_offers_begin, ":realm"),
        (faction_set_slot, ":realm", ":offer_slot", 0),
        (faction_set_slot, ":target", ":reverse_slot", 0),
        (try_for_players, ":recipient", 1),
            (player_is_active, ":recipient"),
            (multiplayer_send_4_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events,
                multiplayer_event_multiplayer_campaign_server_event_realm_relation, ":realm", ":target", ":relation"),
        (try_end),
        (assign, "$g_recalculate_ais", 1),
        (assign, "$g_coop_world_save_pending", 1),
    ]),
    ("coop_realm_grant", [
        (store_script_param, ":player", 1),
        (store_script_param, ":center", 2),
        (store_script_param, ":companion", 3),
        (player_slot_eq, ":player", slot_player_coop_char_state, coop_char_state_ready),
        (is_between, ":center", centers_begin, centers_end),
        (is_between, ":companion", companions_begin, companions_end),
        (player_get_slot, ":realm", ":player", slot_player_coop_faction),
        (is_between, ":realm", coop_player_factions_begin, coop_player_factions_end),
        (player_get_slot, ":account", ":player", slot_player_coop_steam_acctid),
        (neq, ":account", 0),
        (faction_slot_eq, ":realm", slot_faction_coop_owner_acctid, ":account"),
        (party_slot_eq, ":center", slot_center_coop_owner_acctid, ":account"),
        (store_faction_of_party, ":holder", ":center"),
        (eq, ":holder", ":realm"),
        (player_get_party_id, ":party", ":player"),
        (party_count_members_of_type, ":count", ":party", ":companion"),
        (eq, ":count", 1),
        (assign, ":unique", 1),
        (try_for_players, ":other", 1),
            (player_is_active, ":other"), (neq, ":other", ":player"),
            (player_get_party_id, ":other_party", ":other"),
            (party_count_members_of_type, ":other_count", ":other_party", ":companion"),
            (gt, ":other_count", 0), (assign, ":unique", 0),
        (try_end),
        (eq, ":unique", 1),
        (neg|troop_slot_eq, ":companion", slot_troop_occupation, slto_kingdom_hero),
        (party_remove_members, ":party", ":companion", 1),
        (troop_set_slot, ":companion", slot_troop_occupation, slto_kingdom_hero),
        (troop_set_slot, ":companion", slot_troop_prisoner_of_party, -1),
        (call_script, "script_change_troop_faction", ":companion", ":realm"),
        (call_script, "script_give_center_to_lord", ":center", ":companion", 0),
        (call_script, "script_create_kingdom_hero_party", ":companion", ":center"),
        (assign, "$g_recalculate_ais", 1),
        (assign, "$g_coop_world_save_pending", 1),
        (call_script, "script_coop_save_character", ":player"),
    ]),
    ("coop_clock_send", [
        (store_script_param, ":recipient", 1),
        (ge, "$g_coop_clock_sequence", 1),
        (multiplayer_send_4_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events,
            multiplayer_event_multiplayer_campaign_server_event_clock, "$g_coop_clock_sequence", "$g_coop_clock_hours", "$g_coop_clock_fraction"),
    ]),
]

campaign_scripts += [
    ("coop_refresh_party_health", [
        (store_script_param, ":player", 1),
        (player_is_active, ":player"),
        (player_slot_eq, ":player", slot_player_coop_char_state, coop_char_state_ready),
        (player_get_party_id, ":party", ":player"), (party_is_active, ":party"),
        (party_slot_eq, ":party", slot_party_coop_battle_slot, 0),
        (party_get_num_companion_stacks, ":stacks", ":party"),
        (assign, ":signature", ":stacks"),
        (try_for_range, ":stack", 0, ":stacks"),
            (party_stack_get_troop_id, ":troop", ":party", ":stack"),
            (troop_is_hero, ":troop"), (store_troop_health, ":health", ":troop"),
            (store_add, ":weight", ":troop", 1), (val_mul, ":health", ":weight"),
            (val_add, ":signature", ":health"),
        (try_end),
        (neg|player_slot_eq, ":player", slot_player_coop_health_signature, ":signature"),
        (player_set_slot, ":player", slot_player_coop_health_signature, ":signature"),
        # Shared health of rival armies also needs a host refresh. Character
        # packets only update their owner; do not transfer another hero's XP.
        (try_for_range, ":stack", 0, ":stacks"),
            (party_stack_get_troop_id, ":troop", ":party", ":stack"),
            (troop_is_hero, ":troop"), (store_troop_health, ":percent", ":troop"),
            (try_for_players, ":recipient", 1), (player_is_active, ":recipient"),
                (player_slot_eq, ":recipient", slot_player_coop_char_state, coop_char_state_ready),
                (multiplayer_send_3_int_to_player, ":recipient", multiplayer_event_multiplayer_campaign_server_events,
                    multiplayer_event_multiplayer_campaign_server_event_hero_health, ":troop", ":percent"),
            (try_end),
        (try_end),
        # Native hourly healing writes health directly, bypassing setter hooks.
        # Refresh percentages from the host without changing Native heal rates.
        (call_script, "script_coop_char_pack_send_misc", ":player"),
        (call_script, "script_coop_char_send_hero_xp", ":player"),
        (call_script, "script_coop_save_character", ":player"),
    ]),
]

campaign_triggers = [
    (1, [
        (multiplayer_is_server), (multiplayer_is_campaign),
        (try_for_players, ":player", 1), (player_is_active, ":player"),
            (call_script, "script_coop_refresh_party_health", ":player"),
        (try_end),
    ]),
    (0, [
        (neg|multiplayer_is_server), (multiplayer_is_campaign),
        (key_clicked, key_f8),
        (multiplayer_send_int_to_server, multiplayer_event_multiplayer_campaign_client_events,
            multiplayer_event_multiplayer_campaign_recover_encounter),
    ]),
    (0, [
        (neg|multiplayer_is_server), (multiplayer_is_campaign),
        (key_clicked, key_f6),
        (call_script, "script_coop_client_request_menu", "mnu_coop_realms"),
    ]),
    (0, [
        (neg|multiplayer_is_server), (multiplayer_is_campaign),
        (key_clicked, key_f7),
        (call_script, "script_coop_client_request_menu", "mnu_coop_realm_grants"),
    ]),
    (0.25, [
        (multiplayer_is_server), (multiplayer_is_campaign),
        (ge, "$g_coop_clock_hours", 0),
        (val_add, "$g_coop_clock_sequence", 1),
        (try_for_players, ":recipient", 1), (player_is_active, ":recipient"),
            (call_script, "script_coop_clock_send", ":recipient"),
        (try_end),
    ]),
    (6, [
        (multiplayer_is_server), (multiplayer_is_campaign),
        (try_for_range, ":realm", coop_player_factions_begin, coop_player_factions_end),
            (neg|faction_slot_eq, ":realm", slot_faction_coop_owner_acctid, 0),
            (call_script, "script_faction_recalculate_strength", ":realm"),
        (try_end),
    ]),
]

# Camp diplomacy only changes faction hostility, using native companion armies.
realm_options = []
for i in range(250):
    realm = "fac_coop_kingdom_%04d" % i
    realm_options.append(("realm_%d" % i, [
        (neg|faction_slot_eq, realm, slot_faction_coop_owner_acctid, 0),
        (multiplayer_get_my_player, ":player"),
        (neg|player_slot_eq, ":player", slot_player_coop_faction, realm),
        (str_store_faction_name, s1, realm),
    ], "Diplomacy with {s1}", [
        (assign, "$g_coop_diplomacy_target", realm), (jump_to_menu, "mnu_coop_realm_diplomacy"),
    ]))
realm_options.append(("back", [], "Return", [(jump_to_menu, "mnu_camp")]))
grant_options = []
for party in parties:
    if not party[0].startswith(("town_", "castle_", "village_")):
        continue
    center = "p_" + party[0]
    grant_options.append(("grant_" + party[0], [
        (multiplayer_get_my_player, ":player"),
        (player_get_slot, ":realm", ":player", slot_player_coop_faction),
        (store_faction_of_party, ":holder", center), (eq, ":holder", ":realm"),
        (str_store_party_name, s1, center),
    ], "Grant {s1} to a companion", [
        (assign, "$g_coop_grant_center", center), (jump_to_menu, "mnu_coop_realm_companion"),
    ]))
grant_options.append(("back", [], "Return", [(jump_to_menu, "mnu_camp")]))
companion_options = []
for i in range(1, 17):
    companion = "trp_npc%d" % i
    companion_options.append(("promote_%d" % i, [
        (multiplayer_get_my_player, ":player"),
        (player_get_party_id, ":party", ":player"),
        (party_count_members_of_type, ":count", ":party", companion), (eq, ":count", 1),
        (neg|troop_slot_eq, companion, slot_troop_occupation, slto_kingdom_hero),
        (str_store_troop_name, s2, companion),
    ], "Make {s2} a lord of this settlement", [
        (multiplayer_send_3_int_to_server, multiplayer_event_multiplayer_campaign_client_events,
            multiplayer_event_multiplayer_campaign_realm_grant, "$g_coop_grant_center", companion),
        (jump_to_menu, "mnu_coop_realm_grants"),
    ]))
companion_options.append(("back", [], "Return", [(jump_to_menu, "mnu_coop_realm_grants")]))
campaign_menus = [
    ("coop_realm_grants", 0, "Grant an owned settlement to a companion. They become a native lord and raise their own army.", "none", [], grant_options),
    ("coop_realm_companion", 0, "Choose a companion for {s1}.", "none", [
        (str_store_party_name, s1, "$g_coop_grant_center"),
    ], companion_options),
    ("coop_realms", 0, "Select a player's realm.", "none", [], realm_options),
    ("coop_realm_diplomacy", 0, "Relations with {s1}: {reg0}. Peace requires both rulers to agree.", "none", [
        (str_store_faction_name, s1, "$g_coop_diplomacy_target"),
        (multiplayer_get_my_player, ":player"),
        (player_get_slot, ":realm", ":player", slot_player_coop_faction),
        (store_relation, reg0, ":realm", "$g_coop_diplomacy_target"),
    ], [
        ("war", [], "Declare war", [
            (multiplayer_send_3_int_to_server, multiplayer_event_multiplayer_campaign_client_events,
                multiplayer_event_multiplayer_campaign_realm_diplomacy, "$g_coop_diplomacy_target", 1),
            (jump_to_menu, "mnu_coop_realms"),
        ]),
        ("peace", [], "Offer or accept peace", [
            (multiplayer_send_3_int_to_server, multiplayer_event_multiplayer_campaign_client_events,
                multiplayer_event_multiplayer_campaign_realm_diplomacy, "$g_coop_diplomacy_target", 0),
            (jump_to_menu, "mnu_coop_realms"),
        ]),
        ("back", [], "Return", [(jump_to_menu, "mnu_coop_realms")]),
    ]),
]

def extend_native_realm_ai(scripts):
    # Only broaden AI searches: changing all kingdom ranges would corrupt
    # Native's compact diplomacy-slot arrays and include non-kingdom factions.
    names = set(["recalculate_ais", "npc_decision_checklist_party_ai",
                 "npc_decision_checklist_faction_ai_alt"])
    for name, operations in scripts:
        if name not in names:
            continue
        rewritten = []
        for operation in operations:
            if (isinstance(operation, tuple) and len(operation) == 4 and operation[0] == try_for_range
                    and operation[3] == kingdoms_end):
                variable, begin = operation[1:3]
                rewritten += [(try_for_range, variable, begin, coop_player_factions_end),
                              (this_or_next|is_between, variable, begin, kingdoms_end),
                              (is_between, variable, coop_player_factions_begin, coop_player_factions_end),
                              (this_or_next|is_between, variable, begin, kingdoms_end),
                              (neg|faction_slot_eq, variable, slot_faction_coop_owner_acctid, 0)]
                if name == "recalculate_ais":
                    rewritten.append((faction_slot_ge, variable, slot_faction_leader, 0))
            else:
                rewritten.append(operation)
        operations[:] = rewritten
