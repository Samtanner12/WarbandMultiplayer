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
    def test_player_references_follow_the_context(self):
        self.assertEqual(ctx.translate((troop_is_wounded,'trp_player')),[(troop_is_wounded,'$g_ctx_troop')])
        self.assertEqual(ctx.translate((party_add_xp,'p_main_party',5)),[(party_add_xp,'$g_ctx_party',5)])
    def test_engine_encounter_queries_and_screens(self):
        self.assertEqual(ctx.translate((neg|encountered_party_is_attacker,)),[(call_script,'script_cf_coop_ctx_encountered_not_attacking')])
        self.assertEqual(ctx.translate((change_screen_loot,'trp_temp_troop')),[(call_script,'script_coop_ctx_open_loot','trp_temp_troop')])
        self.assertEqual(ctx.translate((change_screen_exchange_with_party,'p_temp_party')),[(call_script,'script_coop_ctx_open_exchange','p_temp_party')])
        self.assertEqual(ctx.translate((get_achievement_stat,':n',1,0)),[(assign,':n',0)])
    def test_single_player_scenes_are_dropped(self):
        self.assertEqual(ctx.translate((call_script,'script_setup_troop_meeting',':t',':d')),[])
        self.assertEqual(ctx.translate((end_current_battle,)),[])
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
