"""Execute the host's spoils validation operations. Run with the bundled Python 2."""
import os,sys,unittest
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base=open(os.path.join(root,'scripts/test-campaign-realms.py')).read().split('class RealmTests')[0]
base=base.replace("else: raise AssertionError('Unexpected operation %r' % (op,))",'else: result=self.extra(masked,op,args)')
exec(base)
sys.path.insert(0,os.path.join(root,'scripts'))
import module_retained_rewards as rewards
records=[('coop_trade_client_diff_and_send',[(call_script,'script_coop_trade_client_diff','trp_find_item_cheat',':my_troop',coop_emit_send)]),
         ('multiplayer_campaign_client_events',[])]
rewards.install(records);scripts=dict(records)
take=scripts['coop_retained_take_prisoners'];release=scripts['coop_retained_release_prisoners']
LOOT=1078
class Host(Authority):
    def __init__(self):
        Authority.__init__(self)
        self.added=[];self.removed=[];self.calls=[];self.skill=2;self.held=0;self.prisoners={100:4}
        self.players[1].update({6029:111,6023:1,19100:100,19101:3})
        self.params=[1,100,3]
    def extra(self,code,op,a):
        if code==player_set_slot:self.players[a[0]][a[1]]=a[2]
        elif code==troop_is_hero:return a[0]==900
        elif code==party_get_skill_level:self.vars[op[1]]=self.skill
        elif code==store_mul:self.vars[op[1]]=a[1]*a[2]
        elif code==party_get_num_prisoners:self.vars[op[1]]=self.held
        elif code==val_sub:self.vars[op[1]]=a[0]-a[1]
        elif code==val_min:self.vars[op[1]]=min(a[0],a[1])
        elif code==val_add:self.vars[op[1]]=a[0]+a[1]
        elif code==party_add_prisoners:self.added.append(a)
        elif code==party_count_prisoners_of_type:self.vars[op[1]]=self.prisoners.get(a[2],0)
        elif code==party_remove_prisoners:self.removed.append(a)
        elif code==call_script:self.calls.append(a)
        else:raise AssertionError('Unsupported operation '+repr(op))
        return True
class Tests(unittest.TestCase):
    def test_takes_offered_prisoners_once(self):
        h=Host();h.execute(take);h.execute(take)
        self.assertEqual(h.added,[[500,100,3]]);self.assertEqual(h.players[1][19101],0)
    def test_cannot_take_more_than_offered(self):
        h=Host();h.params=[1,100,50];h.execute(take);self.assertEqual(h.added,[[500,100,3]])
    def test_prisoner_limit_caps_taking(self):
        h=Host();h.skill=1;h.held=4;h.execute(take);self.assertEqual(h.added,[[500,100,1]])
        h=Host();h.skill=0;h.execute(take);self.assertEqual(h.added,[])
    def test_unoffered_troop_and_heroes_denied(self):
        for troop in [101,900]:
            h=Host();h.params=[1,troop,1];h.execute(take);self.assertEqual(h.added,[])
    def test_reused_connection_identity_denied(self):
        h=Host();h.players[1][6029]=222;h.execute(take);self.assertEqual(h.added,[])
    def test_release_is_bounded_by_held_prisoners(self):
        h=Host();h.params=[1,100,10];h.execute(release);self.assertEqual(h.removed,[[500,100,4]])
        h=Host();h.params=[1,900,1];h.execute(release);self.assertEqual(h.removed,[])
    def test_loot_screen_routes_trade_diff_once(self):
        diff=scripts['coop_trade_client_diff_and_send']
        h=Host();h.vars['$g_retained_loot_merchant']=LOOT;h.execute(diff)
        self.assertEqual(h.calls[0][1],LOOT);self.assertEqual(h.vars['$g_retained_loot_merchant'],0)
        h.execute(diff);self.assertEqual(h.calls[1][1],'trp_find_item_cheat')
    def test_retained_scripts_cannot_fail_their_caller(self):
        for name,ops in records:
            if name.startswith('coop_retained_'):self.assertEqual(ops[0],try_begin,name)
if __name__=='__main__':unittest.main()
