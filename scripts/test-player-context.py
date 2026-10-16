"""Checks the host-run Native menu layer (module_player_context). Run with the bundled Python 2."""
import os,sys,unittest
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The project's compiled module source, imported before the shared harness
# pulls in the upstream copy of the same module names.
sys.path.insert(0,os.path.join(root,'runtime','NativeMissionProbe','Source'))
import module_player_context as ctx
import module_scripts
import module_game_menus
base=open(os.path.join(root,'scripts/test-campaign-realms.py')).read().split('class RealmTests')[0]
base=base.replace("else: raise AssertionError('Unexpected operation %r' % (op,))",'else: result=self.extra(masked,op,args)')
exec(base)
built=dict(module_scripts.scripts)
menus=dict((m[0],m) for m in module_game_menus.game_menus)

def mentions(ops,value):
    return any(isinstance(op,tuple) and value in op[1:] for op in ops)

class Translation(unittest.TestCase):
    def test_menu_operations_become_host_flags(self):
        self.assertEqual(ctx.translate((jump_to_menu,'mnu_total_victory')),[(assign,'$g_ctx_menu_next','mnu_total_victory')])
        self.assertEqual(ctx.translate((change_screen_return,)),[(assign,'$g_ctx_menu_close',1)])
        self.assertEqual(ctx.translate((change_screen_mission,)),[(assign,'$g_ctx_menu_battle',1)])
        self.assertEqual(ctx.translate((leave_encounter,)),[(call_script,'script_coop_retained_release_encounter','$g_ctx_party')])
    def test_bare_operations_are_translated(self):
        # Native writes argument-less operations as bare numbers: (change_screen_return).
        self.assertEqual(ctx.translate(change_screen_return),[(assign,'$g_ctx_menu_close',1)])
        self.assertEqual(ctx.translate(change_screen_mission),[(assign,'$g_ctx_menu_battle',1)])
        self.assertEqual(ctx.translate(leave_encounter),[(call_script,'script_coop_retained_release_encounter','$g_ctx_party')])
    def test_player_references_follow_the_context(self):
        self.assertEqual(ctx.translate((troop_is_wounded,'trp_player')),[(troop_is_wounded,'$g_ctx_troop')])
        self.assertEqual(ctx.translate((party_add_xp,'p_main_party',5)),[(party_add_xp,'$g_ctx_party',5)])
    def test_engine_encounter_queries_and_screens(self):
        self.assertEqual(ctx.translate((neg|encountered_party_is_attacker,)),[(call_script,'script_cf_coop_ctx_encountered_not_attacking')])
        self.assertEqual(ctx.translate((change_screen_loot,'trp_temp_troop')),[(call_script,'script_coop_ctx_open_loot','trp_temp_troop')])
        self.assertEqual(ctx.translate((change_screen_exchange_with_party,'p_temp_party')),[(call_script,'script_coop_ctx_open_exchange','p_temp_party')])
        self.assertEqual(ctx.translate((get_achievement_stat,':n',1,0)),[(assign,':n',0)])
    def test_single_player_scenes_are_dropped(self):
        self.assertEqual(ctx.translate((end_current_battle,)),[])
    def test_meetings_become_host_conversations(self):
        self.assertEqual(ctx.translate((call_script,'script_setup_party_meeting','$g_encountered_party')),
                         [(call_script,'script_coop_ctx_party_meeting','$g_encountered_party')])
        self.assertEqual(ctx.translate((call_script,'script_setup_troop_meeting',':t',':d')),
                         [(call_script,'script_coop_ctx_troop_meeting',':t',':d')])
    def test_conversation_operations_use_the_context(self):
        self.assertEqual(ctx.dialog_translate([store_conversation_troop,'$g_talk_troop']),[(assign,'$g_talk_troop','$g_ctx_talk_troop')])
        self.assertEqual(ctx.dialog_translate((store_repeat_object,':o')),[(assign,':o','$g_ctx_repeat_object')])
        self.assertEqual(ctx.dialog_translate((add_xp_as_reward,50)),[(add_xp_to_troop,50,'$g_ctx_troop')])
        self.assertEqual(ctx.dialog_translate((agent_play_sound,'$g_talk_agent',1)),[])
        self.assertEqual(ctx.translate((store_character_level,':lvl')),[(store_character_level,':lvl','$g_ctx_troop')])
    def test_dialog_text_follows_the_players_gender(self):
        self.assertEqual(ctx.dialog_text('{!}Hello {sir/madam}, {playername}.'),'@Hello {reg47?madam:sir}, {s47}.')
        self.assertEqual(ctx.dialog_text('{reg1?a:b}'),'@{reg1?a:b}')
        self.assertEqual(ctx.translate((call_script,'script_clear_party_group','$g_enemy_party')),
                         [(call_script,'script_coop_ctx_clear_party_group','$g_enemy_party')])

class Build(unittest.TestCase):
    def test_generated_scripts_exist(self):
        for name in ['coop_ctx_enter','coop_ctx_exit','coop_menu_present','coop_menu_choose','coop_ctx_start_encounter',
                     'coop_ctx_before_battle','coop_ctx_after_battle','coop_ctx_post_battle','coop_ctx_open_loot',
                     'coop_ctx_open_exchange','coop_ctx_take_offer','coop_ctx_screen_closed']:
            self.assertIn(name,built)
        for menu in ctx.MIRRORED_MENUS:
            self.assertIn('coop_menu_show_'+menu,built);self.assertIn('coop_menu_choose_'+menu,built)
            self.assertLessEqual(len(menus[menu][5]),ctx.MAX_OPTIONS,menu)
    def test_hostile_encounters_route_through_native_menu(self):
        self.assertTrue(mentions(built['game_event_party_encounter'],'script_coop_ctx_start_encounter'))
    def test_native_post_battle_scripts_use_the_context(self):
        for name in ['party_give_xp_and_gold','party_calculate_loot','encounter_init_variables','calculate_main_party_shares']:
            self.assertFalse(mentions(built[name],'p_main_party'),name)
            self.assertTrue(mentions(built[name],'$g_ctx_party'),name)
    def test_mirror_menus_exist(self):
        self.assertIn('coop_menu_mirror',menus);self.assertIn('coop_menu_mirror_close',menus)
    def test_menu_strings_fit_the_7_bit_message_type(self):
        # The engine writes message types in 7 bits; 129 arrived as type 1.
        self.assertLess(ctx.EV_MENU_STRING,128)
        sends=[op for name in built if name.startswith('coop_menu_show_') for op in built[name]
               if isinstance(op,tuple) and op[0] in (multiplayer_send_string_to_player,multiplayer_send_int_to_player,
                   multiplayer_send_2_int_to_player,multiplayer_send_3_int_to_player,multiplayer_send_4_int_to_player)]
        self.assertTrue(sends)
        for op in sends:self.assertLess(op[2],128,op)
        # Mirror text is consumed only when announced, so the real event still works.
        self.assertTrue(mentions(built['game_receive_network_message'],'$g_mirror_expect'))
    def test_loot_screen_settles_against_its_own_troop(self):
        ops=built['coop_trade_client_diff_and_send']
        self.assertTrue(mentions(ops,'$g_retained_loot_merchant'))
        self.assertFalse(any(isinstance(op,tuple) and op[0]==call_script and 'trp_find_item_cheat' in op for op in ops))
    def test_native_morale_runs_without_a_single_player(self):
        for name in ['coop_retained_courage_others','coop_retained_courage_death','coop_retained_run_away']:
            ops=built[name]
            self.assertFalse(any(isinstance(op,tuple) and op[0] in (agent_is_ally,get_player_agent_no) for op in ops),name)
            self.assertTrue(any(isinstance(op,tuple) and op[0]==agent_set_slot for op in ops),name)
        self.assertTrue(mentions(built['coop_retained_courage_death'],'script_cf_coop_retained_agent_side0'))
        self.assertFalse(mentions(built['coop_retained_run_away'],'script_cf_coop_retained_agent_side0'))

class Conversations(unittest.TestCase):
    def test_every_state_dispatches_and_encounters_open_one(self):
        self.assertIn('coop_dlg_state',built);self.assertIn('coop_dlg_advance',built);self.assertIn('coop_dlg_choose',built)
        states=[op[1+1] for op in built['coop_dlg_state'] if isinstance(op,tuple) and op[0]==eq and op[1]==':state']
        self.assertGreater(len(states),1000)
        for sid in states:self.assertIn('coop_dlg_%d'%sid,built)
        self.assertTrue(mentions(built['coop_menu_show_simple_encounter'],'script_coop_ctx_party_meeting'))
        self.assertTrue(mentions(built['coop_menu_present'],'script_coop_dlg_advance'))
    def test_client_leaves_the_mirror_after_answering(self):
        # Menus open only from the map, so a menu left open would show stale answers.
        for option in menus['coop_menu_mirror'][5]:
            self.assertTrue(any(op==change_screen_return or (isinstance(op,tuple) and op[0]==change_screen_return) for op in option[3]))
    def test_partner_can_speak_again_without_answers(self):
        self.assertTrue(mentions(built['coop_dlg_choose'],ctx.DLG_CONTINUE))
        self.assertTrue(mentions(built['coop_dlg_advance'],ctx.DLG_CONTINUE))
    def test_unsupported_options_are_hidden(self):
        self.assertFalse(any('encounter order attack' in repr(op) for op in built['coop_menu_choose_simple_encounter']))
    def test_answers_go_to_the_conversation_first(self):
        self.assertTrue(mentions(built['coop_menu_choose'],'script_coop_dlg_choose'))
    def test_looters_line_uses_the_encountered_template(self):
        start=built['coop_dlg_%d'%ctx.DLG_START]
        self.assertTrue(any(isinstance(op,tuple) and op[0]==party_get_template_id for op in start))
        self.assertFalse(any(isinstance(op,tuple) and op[0] in (store_conversation_troop,agent_play_sound,encounter_attack) for op in start))

class AfterBattle(unittest.TestCase):
    def test_context_exit_survives_a_failing_native_script(self):
        ops=[(call_script,'script_coop_ctx_enter',':p'),(eq,1,0),(call_script,'script_coop_ctx_exit',':p')]
        self.assertEqual(ctx.guard_contexts(ops),[ops[0],(try_begin),(eq,1,0),(try_end),ops[2]])
        for name in ['coop_menu_choose','coop_ctx_after_battle','coop_ctx_post_battle','coop_ctx_start_encounter']:
            ops=built[name];i=[n for n,o in enumerate(ops) if isinstance(o,tuple) and o[:2]==(call_script,'script_coop_ctx_enter')][0]
            self.assertEqual(ops[i+1],try_begin,name)
    def test_casualties_read_from_armies_disabled_for_the_battle(self):
        # The host disables both armies for the whole battle; party_is_active fails for them.
        self.assertFalse(any(isinstance(o,tuple) and o[0]==party_is_active for o in built['coop_ctx_after_battle']))
        self.assertFalse(any(isinstance(o,tuple) and o[0]==party_is_active for o in built['coop_retained_kill_xp']))
    def test_native_screens_open_from_a_menu(self):
        # change_screen_loot is ignored on the bare map; screens open from a menu and return to it.
        load=menus['coop_screen_host'][4]
        self.assertIn((change_screen_loot,ctx.LOOT_TROOP),load)
        self.assertTrue(mentions(load,'script_coop_ctx_client_screen_settle'))
    def test_field_battles_use_native_terrain_maps(self):
        start=built['coop_retained_start']
        # Generated maps by terrain, Native's fixed multiplayer maps as the fallback.
        self.assertTrue(mentions(start,'scn_random_multi_plain_large'))
        self.assertTrue(mentions(start,'scn_multi_scene_7'))
    def test_battle_map_seed_comes_from_the_location_and_is_shared(self):
        import module_retained_campaign_battles as retained
        start=built['coop_retained_start']
        self.assertTrue(any(isinstance(o,tuple) and o[0]==party_get_position for o in start))
        self.assertTrue(mentions(built['coop_retained_invite'],retained.EV_TERRAIN_SEEDS))
        # The engine derives the terrain from the shared seed; the scene keeps sf_randomize.
        self.assertFalse(any(isinstance(o,tuple) and o[0] in (scene_set_flags,scene_set_terrain_seed) for o in start))
    def test_unloaded_joiners_stop_holding_the_battle(self):
        import module_retained_campaign_battles as retained
        self.assertTrue(mentions(built['coop_retained_register_party'],retained.JOIN_TIME_SLOT))
    def test_screen_close_needs_a_shown_screen(self):
        self.assertTrue(mentions(built['wse_window_opened'],'$g_ctx_screen_shown'))
        self.assertTrue(mentions(menus['coop_screen_host'][4],'$g_ctx_screen_shown'))
    def test_victory_experience_is_reported(self):
        self.assertTrue(mentions(built['party_give_xp_and_gold'],'script_coop_ctx_party_add_xp'))
    def test_beaten_army_is_reenabled_before_clearing(self):
        ops=built['coop_ctx_clear_party_group']
        self.assertTrue(any(isinstance(o,tuple) and o[0]==enable_party for o in ops))
        self.assertTrue(mentions(ops,ctx.DEFEATED_SLOT))

class Nesting(unittest.TestCase):
    def test_context_suspends_and_resumes_the_outer_player(self):
        enter=built['coop_ctx_enter'];leave=built['coop_ctx_exit']
        self.assertTrue(mentions(enter,'script_coop_ctx_bank_save'));self.assertTrue(mentions(enter,'script_coop_ctx_activate'))
        self.assertTrue(mentions(leave,'script_coop_ctx_bank_save'));self.assertTrue(mentions(leave,'script_coop_ctx_activate'))
        self.assertTrue(mentions(enter,'$g_ctx_depth'));self.assertTrue(mentions(leave,'$g_ctx_depth'))

offer=built['coop_ctx_take_offer']
class Host(Authority):
    def __init__(self):
        Authority.__init__(self);self.added=[];self.prisoners=[];self.skill=2;self.room=4;self.params=[1,100,3,0]
        self.players[1].update({ctx.ACCOUNT_SLOT:111,ctx.OFFER_COUNT_SLOT:1,ctx.OFFER_BASE:100,ctx.OFFER_BASE+1:3,
                                ctx.COMPANION_COUNT_SLOT:1,ctx.COMPANION_OFFER_BASE:200,ctx.COMPANION_OFFER_BASE+1:5})
    def extra(self,code,op,a):
        if code==troop_is_hero:return a[0]==900
        elif code==party_get_skill_level:self.vars[op[1]]=self.skill
        elif code==party_get_free_companions_capacity:self.vars[op[1]]=self.room
        elif code==party_get_num_prisoners:self.vars[op[1]]=0
        elif code in (store_mul,):self.vars[op[1]]=a[1]*a[2]
        elif code==val_sub:self.vars[op[1]]=a[0]-a[1]
        elif code==val_min:self.vars[op[1]]=min(a[0],a[1])
        elif code==val_add:self.vars[op[1]]=a[0]+a[1]
        elif code==player_set_slot:self.players[a[0]][a[1]]=a[2]
        elif code==party_add_prisoners:self.prisoners.append(a)
        elif code==party_add_members:self.added.append(a)
        else:raise AssertionError('Unsupported operation '+repr(op))
        return True
class Offers(unittest.TestCase):
    def test_prisoners_capped_by_offer_and_taken_once(self):
        h=Host();h.params=[1,100,9,0];h.execute(offer);h.execute(offer)
        self.assertEqual(h.prisoners,[[500,100,3]])
    def test_rescued_troops_capped_by_party_room(self):
        h=Host();h.params=[1,200,9,1];h.execute(offer);self.assertEqual(h.added,[[500,200,4]])
    def test_unoffered_hero_or_other_account_denied(self):
        for params in [[1,900,1,0],[1,101,1,0]]:
            h=Host();h.params=params;h.execute(offer);self.assertEqual(h.prisoners,[])
        h=Host();h.players[1][ctx.ACCOUNT_SLOT]=222;h.execute(offer);self.assertEqual(h.prisoners,[])

if __name__=='__main__':unittest.main()
