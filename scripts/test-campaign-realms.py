"""Execute the actual diplomacy operation list with a small authority model.

This tests RPC validation and consent transitions, not native combat behavior.
Run with the bundled Python 2 used by the module compiler.
"""
import os
import sys
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'WarbandTogether', 'wse2work', 'Native-Coop-master'))
import module_campaign_sync as sync
import module_scripts as module
from header_operations import *
from module_constants import *

class Authority(object):
    def __init__(self):
        self.vars = {}
        self.players = {1: {slot_player_coop_char_state: coop_char_state_ready,
                            slot_player_coop_faction: 100, slot_player_coop_steam_acctid: 111},
                        2: {slot_player_coop_char_state: coop_char_state_ready,
                            slot_player_coop_faction: 101, slot_player_coop_steam_acctid: 222}}
        self.factions = {100: {slot_faction_coop_owner_acctid: 111, slot_faction_state: sfs_active},
                         101: {slot_faction_coop_owner_acctid: 222, slot_faction_state: sfs_active}}
        self.relations = {}
        self.sent = []
        self.params = []
        self.parties = {500: {slot_party_coop_battle_slot: 0, 'opponent': 501, 'troops': 132},
                        501: {slot_party_coop_battle_slot: 0, 'opponent': 500, 'troops': 132}}

    def value(self, value):
        if value == coop_player_factions_begin: return 100
        if value == coop_player_factions_end: return 350
        if value == kingdoms_begin: return 10
        if value == kingdoms_end: return 17
        return self.vars.get(value, 0) if isinstance(value, basestring) and value[0] in ':$' else value

    def execute(self, operations):
        i = 0
        or_passed = False
        while i < len(operations):
            raw = operations[i]
            op = (raw,) if isinstance(raw, int) else raw
            code = op[0]
            if code in (try_begin, try_for_players, try_for_range):
                depth, j, branches, begin = 1, i + 1, [], i + 1
                while depth:
                    scan = operations[j]
                    token = scan if isinstance(scan, int) else scan[0]
                    if token in (try_begin, try_for_players, try_for_range): depth += 1
                    elif token == try_end: depth -= 1
                    elif token == else_try and depth == 1:
                        branches.append(operations[begin:j]); begin = j + 1
                    j += 1
                branches.append(operations[begin:j-1])
                if code in (try_for_players, try_for_range):
                    items = self.players if code == try_for_players else range(self.value(op[2]), self.value(op[3]))
                    for item in items:
                        self.vars[op[1]] = item
                        self.execute(branches[0])
                else:
                    for branch in branches:
                        if self.execute(branch): break
                i = j
                continue
            masked = code & ~(this_or_next | neg)
            args = [self.value(arg) for arg in op[1:]]
            result = True
            if masked == store_script_param: self.vars[op[1]] = self.params[args[1]-1]
            elif masked == player_get_slot: self.vars[op[1]] = self.players[args[1]].get(args[2], 0)
            elif masked == player_slot_eq: result = self.players[args[0]].get(args[1], 0) == args[2]
            elif masked == faction_slot_eq: result = self.factions.get(args[0], {}).get(args[1], 0) == args[2]
            elif masked == faction_set_slot: self.factions.setdefault(args[0], {})[args[1]] = args[2]
            elif masked == assign: self.vars[op[1]] = args[1]
            elif masked == store_add: self.vars[op[1]] = args[1] + args[2]
            elif masked == eq: result = args[0] == args[1]
            elif masked == neq: result = args[0] != args[1]
            elif masked == le: result = args[0] <= args[1]
            elif masked == gt: result = args[0] > args[1]
            elif masked == ge: result = args[0] >= args[1]
            elif masked == is_between: result = args[1] <= args[0] < args[2]
            elif masked == player_is_active: result = args[0] in self.players
            elif masked == player_get_party_id: self.vars[op[1]] = 499 + args[1]
            elif masked == party_is_active: result = args[0] in self.parties
            elif masked == party_slot_ge: result = self.parties[args[0]].get(args[1], 0) >= args[2]
            elif masked == party_leave_cur_battle: self.parties[args[0]]['opponent'] = -1
            elif masked == enable_party: self.parties[args[0]]['enabled'] = True
            elif masked == party_set_ai_behavior: self.parties[args[0]]['behavior'] = args[1]
            elif masked == multiplayer_send_2_int_to_player: self.sent.append(args)
            elif masked == display_message: pass
            elif masked == set_relation: self.relations[tuple(sorted(args[:2]))] = args[2]
            elif masked == multiplayer_send_4_int_to_player: self.sent.append(args)
            else: raise AssertionError('Unexpected operation %r' % (op,))
            if code & neg: result = not result
            if code & this_or_next:
                or_passed = or_passed or result
            else:
                result = result or or_passed
                or_passed = False
                if not result: return False
            i += 1
        return True

    def diplomacy(self, player, target, war):
        self.params = [player, target, war]
        return self.execute(dict(sync.campaign_scripts)['coop_realm_diplomacy'])

class RealmTests(unittest.TestCase):
    def test_failed_launch_releases_both_armies_without_casualties(self):
        host = Authority(); host.params = [500, 501]
        self.assertTrue(host.execute(dict(sync.campaign_scripts)['coop_release_failed_encounter']))
        self.assertEqual([host.parties[p]['opponent'] for p in [500, 501]], [-1, -1])
        self.assertEqual([host.parties[p]['troops'] for p in [500, 501]], [132, 132])
        self.assertEqual(len(host.sent), 2)

    def test_recovery_cannot_abort_a_running_dedicated_or_local_battle(self):
        for kind in ('worker', 'local'):
            host = Authority(); host.params = [500, 501]
            if kind == 'worker': host.parties[501][slot_party_coop_battle_slot] = 1
            else: host.players[2][slot_player_coop_in_local_encounter] = 1
            self.assertFalse(host.execute(dict(sync.campaign_scripts)['coop_release_failed_encounter']))
            self.assertEqual(host.parties[500]['opponent'], 501)
            self.assertEqual(host.sent, [])

    def test_war_is_between_owned_factions_and_broadcast_to_both(self):
        host = Authority()
        self.assertTrue(host.diplomacy(1, 101, 1))
        self.assertEqual(host.relations[(100, 101)], -50)
        self.assertEqual(len(host.sent), 2)
        self.assertEqual(host.vars['$g_coop_world_save_pending'], 1)

    def test_one_player_cannot_force_peace(self):
        host = Authority(); host.diplomacy(1, 101, 1)
        self.assertFalse(host.diplomacy(1, 101, 0))
        self.assertEqual(host.relations[(100, 101)], -50)
        self.assertTrue(host.diplomacy(2, 100, 0))
        self.assertEqual(host.relations[(100, 101)], 0)

    def test_redeclaring_war_cancels_old_peace_consent(self):
        host = Authority(); host.diplomacy(1, 101, 0)
        host.diplomacy(2, 100, 1)
        self.assertFalse(host.diplomacy(2, 100, 0))
        self.assertEqual(host.relations[(100, 101)], -50)

    def test_owner_impersonation_unhydrated_and_invalid_targets_denied(self):
        for mutate in ('owner', 'loading', 'self', 'nonkingdom', 'unallocated', 'bad_action'):
            host = Authority(); target, action = 101, 1
            if mutate == 'owner': host.players[1][slot_player_coop_steam_acctid] = 222
            if mutate == 'loading': host.players[1][slot_player_coop_char_state] = 0
            if mutate == 'self': target = 100
            if mutate == 'nonkingdom': target = 50
            if mutate == 'unallocated': target = 102
            if mutate == 'bad_action': action = 8
            host.diplomacy(1, target, action)
            self.assertEqual(host.relations, {}, mutate)

    def test_uses_native_companion_lord_routines(self):
        grant = dict(sync.campaign_scripts)['coop_realm_grant']
        calls = [op[1] for op in grant if isinstance(op, tuple) and op[0] == call_script]
        self.assertEqual(calls[:3], ['script_change_troop_faction', 'script_give_center_to_lord', 'script_create_kingdom_hero_party'])
        self.assertFalse(any('companion_army' in str(op) for op in grant))

    def test_native_ai_ranges_include_personal_realms_and_filter_other_factions(self):
        scripts = dict(module.scripts)
        for name in ('recalculate_ais', 'npc_decision_checklist_party_ai', 'npc_decision_checklist_faction_ai_alt'):
            operations = scripts[name]
            count = 0
            for i, op in enumerate(operations):
                if isinstance(op, tuple) and op[0] == try_for_range and op[-1] == coop_player_factions_end:
                    self.assertEqual(operations[i+1][0], this_or_next|is_between)
                    self.assertEqual(operations[i+2][-2:], (coop_player_factions_begin, coop_player_factions_end))
                    count += 1
            self.assertGreater(count, 0, name)

unittest.main()
