"""Execute the real client team handler against creation-order fixtures."""
import os,sys,unittest
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base=open(os.path.join(root,'scripts/test-campaign-realms.py')).read().split('class RealmTests')[0]
base=base.replace("else: raise AssertionError('Unexpected operation %r' % (op,))",'else: result=self.extra(masked,op,args)')
exec(base)
sys.path.insert(0,os.path.join(root,'scripts'))
import module_retained_campaign_battles as coordinator
records=[('multiplayer_campaign_server_events',[])];coordinator.install_scripts(records)
full=dict(records)['multiplayer_campaign_server_events']
begin=next(i for i,op in enumerate(full) if isinstance(op,tuple) and op[:3]==(eq,':retained_event',83))
def branch_end(ops,start):
    depth=0
    for i in range(start,len(ops)):
        token=ops[i][0] if isinstance(ops[i],tuple) else ops[i]
        if token==try_begin:depth+=1
        elif token==try_end and depth:depth-=1
        elif token in (else_try,try_end):return i
end=branch_end(full,begin)
handler=[(store_script_param,':retained_event',1)]+full[begin:end]
class Client(Authority):
    def __init__(self):
        Authority.__init__(self);self.actors={0:dict(team=0,group=0,slots={})};self.params=[83,0,1,0]
    def extra(self,code,op,a):
        if code==agent_is_active:return a[0] in self.actors
        elif code==agent_set_team:self.actors[a[0]]['team']=a[1]
        elif code==agent_set_group:self.actors[a[0]]['group']=a[1]
        elif code==agent_set_slot:self.actors[a[0]]['slots'][a[1]]=a[2]
        else:raise AssertionError('Unsupported operation '+repr(op))
        return True
class Tests(unittest.TestCase):
    def test_agent_zero_enemy_corrected_before_label_confirmation(self):
        h=Client();self.assertTrue(h.execute(handler));self.assertEqual(h.actors[0]['team'],1)
        self.assertEqual(h.actors[0]['slots'][6199],1)
    def test_packet_before_creation_can_be_replayed(self):
        h=Client();h.actors={};self.assertFalse(h.execute(handler))
        h.actors[0]=dict(team=0,group=0,slots={});self.assertTrue(h.execute(handler));self.assertEqual(h.actors[0]['team'],1)
    def test_invalid_team_does_not_confirm_label(self):
        h=Client();h.params=[83,0,2,0];self.assertFalse(h.execute(handler));self.assertEqual(h.actors[0]['slots'],{})
    def test_friendly_reinforcement_group_preserved(self):
        h=Client();h.params=[83,0,0,2];h.execute(handler);self.assertEqual(h.actors[0]['group'],2)
if __name__=='__main__':unittest.main()
