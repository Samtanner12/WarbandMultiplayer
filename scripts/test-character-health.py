"""Run the actual optional health save/load operations with old and new saves."""
import os, unittest
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base=open(os.path.join(root,'scripts','test-campaign-realms.py')).read().split('class RealmTests')[0]
base=base.replace("else: raise AssertionError('Unexpected operation %r' % (op,))", 'else: result = self.extra(masked, op, args)')
exec(base)
import module_coop_scripts as source
import module_campaign_sync as campaign
from header_common import reg0
scripts=dict(source.coop_scripts)
save=scripts['coop_save_character'];load=scripts['coop_load_character']
def index(ops,code,key):
    return next(i for i,o in enumerate(ops) if isinstance(o,tuple) and o[0]==code and key in o)
def optional_load(key):
    i=index(load,dict_has_key,key)
    j=next(j for j in range(i,len(load)) if load[j]==try_end)
    start=max(k for k in range(i) if load[k]==try_begin)
    return load[start:j+1]
class HealthAuthority(Authority):
    def __init__(self):
        Authority.__init__(self);self.health={900:0,200:0};self.dictionary={}
        self.calls=[]
        self.vars.update({':troop_no':900,':stack_troop':200,'$coop_char_dict':1,reg0:0})
    def extra(self,code,op,a):
        if code==store_troop_health:self.vars[op[1]]=self.health[a[1]]
        elif code==troop_set_health:self.health[a[0]]=a[1]
        elif code==dict_set_int:self.dictionary[a[1]]=a[2]
        elif code==dict_get_int:self.vars[op[1]]=self.dictionary[a[2]]
        elif code==dict_has_key:return a[1] in self.dictionary
        elif code==troop_is_hero:return a[0] in self.health
        elif code==val_min:self.vars[op[1]]=min(a[0],a[1])
        elif code==val_max:self.vars[op[1]]=max(a[0],a[1])
        elif code==party_slot_eq:return self.parties[a[0]].get(a[1],0)==a[2]
        elif code==party_get_num_companion_stacks:self.vars[op[1]]=2
        elif code==party_stack_get_troop_id:self.vars[op[1]]=[900,200][a[2]]
        elif code==val_mul:self.vars[op[1]]=a[0]*a[1]
        elif code==val_add:self.vars[op[1]]=a[0]+a[1]
        elif code==player_set_slot:self.players[a[0]][a[1]]=a[2]
        elif code==call_script:self.calls.append(a)
        elif code==multiplayer_send_3_int_to_player:self.sent.append(a)
        else:raise AssertionError('Unsupported health operation %r'%(op,))
        return True
class HealthTests(unittest.TestCase):
    def test_healing_publishes_each_hero_to_both_ready_clients(self):
        h=HealthAuthority();h.params=[1];h.health={900:22,200:13}
        h.execute(dict(campaign.campaign_scripts)['coop_refresh_party_health'])
        self.assertEqual([(s[0],s[3],s[4]) for s in h.sent],[(1,900,22),(2,900,22),(1,200,13),(2,200,13)])
        h.sent=[];h.execute(dict(campaign.campaign_scripts)['coop_refresh_party_health'])
        self.assertEqual(h.sent,[])
    def test_unhydrated_client_does_not_receive_shared_health(self):
        h=HealthAuthority();h.params=[1];h.players[2][slot_player_coop_char_state]=0
        h.execute(dict(campaign.campaign_scripts)['coop_refresh_party_health'])
        self.assertEqual([s[0] for s in h.sent],[1,1])
    def test_native_healing_refreshes_only_after_percent_changes(self):
        h=HealthAuthority();h.params=[1];ops=dict(campaign.campaign_scripts)['coop_refresh_party_health']
        h.execute(ops);self.assertEqual(len(h.calls),3)
        h.execute(ops);self.assertEqual(len(h.calls),3)
        h.health[900]=11;h.execute(ops);self.assertEqual(len(h.calls),6)
        h.health[200]=9;h.execute(ops);self.assertEqual(len(h.calls),9)
    def test_health_refresh_skips_armies_in_battle(self):
        h=HealthAuthority();h.params=[1];h.parties[500][slot_party_coop_battle_slot]=1
        h.execute(dict(campaign.campaign_scripts)['coop_refresh_party_health']);self.assertEqual(h.calls,[])
    def roundtrip(self,key,troop):
        h=HealthAuthority();i=index(save,dict_set_int,key)
        h.execute(save[i-1:i+1]);h.health[troop]=100
        h.execute(optional_load(key));self.assertEqual(h.health[troop],0)
    def test_wounded_player_roundtrip(self):self.roundtrip('@char_health',900)
    def test_wounded_companion_roundtrip(self):self.roundtrip('@char_party_health_{reg0}',200)
    def test_older_dictionary_preserves_existing_health(self):
        h=HealthAuthority();h.health={900:61,200:42}
        h.execute(optional_load('@char_health'));h.execute(optional_load('@char_party_health_{reg0}'))
        self.assertEqual(h.health,{900:61,200:42})
    def test_corrupt_health_is_clamped(self):
        for value,expected in [(-1,0),(300,100)]:
            h=HealthAuthority();h.dictionary['@char_health']=value
            h.execute(optional_load('@char_health'));self.assertEqual(h.health[900],expected)
    def test_companion_health_applied_before_add_members_changes_reg0(self):
        health_index=index(load,dict_get_int,'@char_party_health_{reg0}')
        add=next(i for i in range(health_index,len(load)) if isinstance(load[i],tuple) and load[i][0]==party_add_members)
        self.assertLess(health_index,add)
if __name__=='__main__':unittest.main()
