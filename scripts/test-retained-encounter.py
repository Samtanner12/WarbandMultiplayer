"""Execute the encounter release and battle cooldown operations. Run with the bundled Python 2."""
import os,sys,unittest
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base=open(os.path.join(root,'scripts/test-campaign-realms.py')).read().split('class RealmTests')[0]
base=base.replace("else: raise AssertionError('Unexpected operation %r' % (op,))",'else: result=self.extra(masked,op,args)')
exec(base)
sys.path.insert(0,os.path.join(root,'scripts'))
import module_retained_campaign_battles as service
records=[];service.install_scripts(records);scripts=dict(records)
release=scripts['coop_retained_release_encounter'];cooldown=scripts['coop_retained_set_cooldown']
class Host(Authority):
    def __init__(self):
        Authority.__init__(self);self.now=50000;self.calls=[];self.params=[500]
    def extra(self,code,op,a):
        if code==party_get_battle_opponent:self.vars[op[1]]=self.parties[a[1]]['opponent']
        elif code==store_application_time:self.vars[op[1]]=self.now
        elif code==val_add:self.vars[op[1]]=a[0]+a[1]
        elif code==party_set_slot:self.parties[a[0]][a[1]]=a[2]
        elif code==party_slot_eq:return self.parties[a[0]].get(a[1],0)==a[2]
        elif code==str_store_string:pass   # trace text
        elif code==call_script:
            if a[0]=='script_coop_menu_trace':return True
            self.calls.append(a)
            if a[0]=='script_coop_retained_set_cooldown':
                saved=self.params;self.params=a[1:];self.execute(cooldown);self.params=saved
        else:raise AssertionError('Unsupported operation '+repr(op))
        return True
class Tests(unittest.TestCase):
    def test_leave_frees_both_armies_with_cooldown(self):
        h=Host();h.execute(release)
        self.assertEqual([h.parties[p]['opponent'] for p in [500,501]],[-1,-1])
        for p in [500,501]:self.assertEqual(h.parties[p][service.COOLDOWN_SLOT],50000+service.BATTLE_COOLDOWN_MS)
        self.assertIn(['script_coop_retained_resume_ai',501],h.calls)
    def test_opponent_reserved_by_running_battle_is_untouched(self):
        h=Host();h.parties[501][slot_party_coop_battle_slot]=1;h.execute(release)
        self.assertEqual(h.parties[500]['opponent'],-1);self.assertEqual(h.parties[501]['opponent'],500)
        self.assertNotIn(service.COOLDOWN_SLOT,h.parties[501])
    def test_no_opponent_still_frees_player(self):
        h=Host();h.parties[500]['opponent']=-1;h.execute(release)
        self.assertEqual(h.parties[500][service.COOLDOWN_SLOT],50000+service.BATTLE_COOLDOWN_MS)
if __name__=='__main__':unittest.main()
