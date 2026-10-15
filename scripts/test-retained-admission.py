"""Execute actual admission operations; no simulated claim about native networking."""
import os, sys, unittest
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base=open(os.path.join(root,'scripts/test-campaign-realms.py')).read().split('class RealmTests')[0]
base=base.replace("else: raise AssertionError('Unexpected operation %r' % (op,))",'else: result=self.extra(masked,op,args)')
exec(base)
sys.path.insert(0,os.path.join(root,'scripts'))
import module_retained_campaign_battles as service
from header_common import reg0
records=[];service.install_scripts(records);ops=dict(records)['coop_retained_reinforce']
class Admission(Authority):
    def __init__(self):
        Authority.__init__(self)
        self.calls=[];self.distance=1;self.faction={500:100,700:100,701:101}
        self.relations={(100,100):0,(100,101):-50}
        self.players[1][service.PARTICIPANT]=0
        self.vars.update({'$g_native_probe_started':1,'$g_cycle_armies_spawned':1,
          '$g_cycle_result_sent':0,'$g_full_host_probe_request':3,
          '$g_cycle_attacker_party':700,'$g_cycle_defender_party':701})
        self.params=[1,0]
    def extra(self,code,op,args):
        if code==store_distance_to_party_from_party:self.vars[op[1]]=self.distance
        elif code==store_faction_of_party:self.vars[op[1]]=self.faction[args[1]]
        elif code==store_relation:self.vars[op[1]]=self.relations.get(tuple(sorted(args[1:])),0)
        elif code==call_script:self.calls.append(args)
        elif code==party_slot_eq:return self.parties[args[0]].get(args[1],0)==args[2]
        else:raise AssertionError('Unhandled operation '+repr(op))
        return True
class Tests(unittest.TestCase):
    def test_nearby_hostile_human_is_admitted(self):
        a=Admission();self.assertTrue(a.execute(ops));self.assertEqual(a.vars[reg0],1);self.assertEqual(len(a.calls),2)
    def test_ai_has_no_player_admission(self):
        a=Admission();a.params=[0,0];self.assertTrue(a.execute(ops));self.assertEqual(a.vars[reg0],0);self.assertEqual(a.calls,[])
    def test_distant_human_cannot_teleport_into_battle(self):
        a=Admission();a.distance=3;self.assertTrue(a.execute(ops));self.assertEqual(a.vars[reg0],0);self.assertEqual(a.calls,[])
    def test_participant_cannot_join_twice(self):
        a=Admission();a.players[1][service.PARTICIPANT]=1;self.assertTrue(a.execute(ops));self.assertEqual(a.vars[reg0],0)
    def test_warring_ally_side_rejected(self):
        a=Admission();a.relations[(100,100)]=-50;self.assertTrue(a.execute(ops));self.assertEqual(a.vars[reg0],0)
    def test_neutral_to_both_can_join_either_side(self):
        for side in [0,1]:
            a=Admission();a.params=[1,side];a.relations[(100,101)]=0
            self.assertTrue(a.execute(ops));self.assertEqual(a.vars[reg0],1)
    def test_hostile_to_selected_side_rejected(self):
        a=Admission();a.params=[1,1];self.assertTrue(a.execute(ops));self.assertEqual(a.vars[reg0],0);self.assertEqual(a.calls,[])
    def test_outlaw_side_rejected(self):
        a=Admission();a.faction[700]='fac_outlaws';self.assertTrue(a.execute(ops));self.assertEqual(a.vars[reg0],0)
    def test_finished_or_unspawned_battle_rejected(self):
        for key,value in [('$g_cycle_result_sent',1),('$g_cycle_armies_spawned',0),('$g_full_host_probe_request',4)]:
            a=Admission();a.vars[key]=value;self.assertTrue(a.execute(ops));self.assertEqual(a.vars[reg0],0)
if __name__=='__main__':unittest.main()
