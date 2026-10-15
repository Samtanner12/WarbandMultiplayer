"""Execute staged module casualty and retreat operations against adversarial fixtures.
This is an authority/accounting test; it does not simulate native networking.
"""
import os, sys, math, unittest
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base=open(os.path.join(root,'scripts','test-campaign-realms.py')).read().split('class RealmTests')[0]
base=base.replace('(try_begin, try_for_players, try_for_range)', '(try_begin, try_for_players, try_for_range, try_for_agents)')
base=base.replace('(try_for_players, try_for_range):', '(try_for_players, try_for_range, try_for_agents):')
base=base.replace('items = self.players if code == try_for_players else range(self.value(op[2]), self.value(op[3]))', 'items = self.agents if code == try_for_agents else self.players if code == try_for_players else range(self.value(op[2]), self.value(op[3]))')
base=base.replace("else: raise AssertionError('Unexpected operation %r' % (op,))", 'else: result = self.extra(masked, op, args)')
base=base.replace('result = args[0] in self.parties', "result = args[0] in self.parties and self.parties[args[0]].get('enabled', True)")
exec(base)
sys.path.insert(0, os.path.join(root,'runtime','NativeMissionProbe','Source'))
from header_triggers import *
import module_mission_templates as missions
import module_simple_triggers as simple
sys.modules.pop('module_coop_scripts',None)
import module_coop_scripts as scripts
mission=[m for m in missions.mission_templates if m[0]=='native_session_probe'][0]
casualty=[t[4] for t in mission[5] if t[0]==ti_on_agent_killed_or_wounded][0]
rpc=dict(scripts.coop_scripts)['multiplayer_campaign_client_events']
start=next(i for i,o in enumerate(rpc) if isinstance(o,tuple) and o[:3]==(eq,':event_type',46))
# Include the nested retreat branches; locate the next top-level event branch.
finish=next(i for i in range(start+1,len(rpc)) if isinstance(rpc[i],tuple) and rpc[i][:3]==(eq,':event_type',47))-1
retreat=rpc[start:finish]
class BattleAuthority(Authority):
    def value(self, value):
        if value == multiplayer_campaign_player_parties_begin: return 3
        return Authority.value(self,value)
    def __init__(self):
        Authority.__init__(self)
        self.agents={10:dict(party=500,troop=900,hero=False,protected=True,pos=(0,0),alive=True),
                     11:dict(party=500,troop=100,hero=False,protected=False,pos=(0,0),alive=True),
                     12:dict(party=500,troop=100,hero=False,protected=False,pos=(0,0),alive=True),
                     13:dict(party=500,troop=200,hero=True,protected=False,pos=(0,0),alive=True),
                     20:dict(party=501,troop=100,hero=False,protected=False,pos=(5000,0),alive=True)}
        for a in self.agents.values(): a['slots']={6100:a['party'],6101:a['troop'],6103:int(a['protected'])}
        self.vars.update({':event_type':46,':player_no':1,'$g_cycle_result_sent':0,'$g_cycle_armies_spawned':1})
        self.players[1][6015]=1
        self.trigger=[11,20,0]; self.positions={}
    def extra(self, code, op, a):
        if code==store_trigger_param_1: self.vars[op[1]]=self.trigger[0]
        elif code==store_trigger_param_3: self.vars[op[1]]=self.trigger[2]
        elif code==agent_is_human: return a[0] in self.agents
        elif code==agent_is_alive: return self.agents[a[0]]['alive']
        elif code==agent_slot_eq: return self.agents[a[0]]['slots'].get(a[1],0)==a[2]
        elif code==agent_get_slot: self.vars[op[1]]=self.agents[a[1]]['slots'].get(a[2],0)
        elif code==agent_set_slot: self.agents[a[0]]['slots'][a[1]]=a[2]
        elif code==troop_is_hero: return any(x['troop']==a[0] and x['hero'] for x in self.agents.values())
        elif code==store_mul: self.vars[op[1]]=a[1]*a[2]
        elif code==val_add: self.vars[op[1]]=a[0]+a[1]
        elif code==party_get_slot: self.vars[op[1]]=self.parties[a[1]].get(a[2],0)
        elif code==player_set_slot: self.players[a[0]][a[1]]=a[2]
        elif code==party_set_slot: self.parties[a[0]][a[1]]=a[2]
        elif code==multiplayer_is_server: return True
        elif code==player_get_agent_id: self.vars[op[1]]=10 if a[1]==1 else 20
        elif code==player_get_team_no: self.vars[op[1]]=a[1]-1
        elif code==agent_get_team: self.vars[op[1]]=0 if self.agents[a[1]]['party']==500 else 1
        elif code==teams_are_enemies: return a[0]!=a[1]
        elif code==set_fixed_point_multiplier: pass
        elif code==agent_get_position: self.positions[a[0]]=self.agents[a[1]]['pos']
        elif code==get_distance_between_positions:
            p,q=self.positions[a[1]],self.positions[a[2]];self.vars[op[1]]=int(math.hypot(p[0]-q[0],p[1]-q[1]))
        elif code==lt: return a[0]<a[1]
        elif code==store_random_in_range: self.vars[op[1]]=a[1]
        else: raise AssertionError('Unsupported operation %r'%(op,))
        return True
class BattleTests(unittest.TestCase):
    def test_return_enables_disabled_existing_armies(self):
        ops=next(t[1] for t in simple.simple_triggers if any(isinstance(o,tuple) and o[:3]==(eq,'$g_cycle_map_restore',1) for o in t[1]))
        start=next(i for i,o in enumerate(ops) if (o if isinstance(o,(int,long)) else o[0])==try_begin)
        end=next(i for i in range(start,len(ops)) if isinstance(ops[i],tuple) and ops[i][0]==multiplayer_get_my_player)
        h=BattleAuthority(); h.vars.update({'$g_cycle_return_party_a':500,'$g_cycle_return_party_b':501})
        for p in h.parties.values(): p['enabled']=False
        self.assertFalse(h.execute([(party_is_active,500)]))
        h.execute(ops[start:end])
        for p in h.parties.values():
            self.assertTrue(p['enabled']);self.assertEqual(p['opponent'],-1)
    def test_return_restores_ai_party_below_player_party_range(self):
        ops=next(t[1] for t in simple.simple_triggers if any(isinstance(o,tuple) and o[:3]==(eq,'$g_cycle_map_restore',1) for o in t[1]))
        start=next(i for i,o in enumerate(ops) if (o if isinstance(o,(int,long)) else o[0])==try_begin)
        end=next(i for i in range(start,len(ops)) if isinstance(ops[i],tuple) and ops[i][0]==multiplayer_get_my_player)
        h=BattleAuthority();h.parties[1]={'enabled':False,'opponent':500}
        h.vars.update({'$g_cycle_return_party_a':500,'$g_cycle_return_party_b':1})
        h.execute(ops[start:end]);self.assertTrue(h.parties[1]['enabled']);self.assertEqual(h.parties[1]['opponent'],-1)
    def test_regular_lethal_loss_is_recorded_once(self):
        h=BattleAuthority();self.assertTrue(h.execute(casualty));h.execute(casualty)
        self.assertEqual(h.parties[500][6400],1)
        self.assertEqual(h.parties[500].get(6401,0),0)
    def test_blunt_regular_loss_is_wounded(self):
        h=BattleAuthority();h.trigger[2]=1;h.execute(casualty)
        self.assertEqual(h.parties[500].get(6400,0),0);self.assertEqual(h.parties[500][6401],1)
    def test_companion_and_original_player_never_recorded_killed(self):
        for agent,troop in [(13,200),(10,900)]:
            h=BattleAuthority();h.trigger[0]=agent;h.execute(casualty)
            self.assertEqual(h.parties[500].get(6200+troop*2,0),0)
            self.assertEqual(h.parties[500][6201+troop*2],1)
    def test_near_enemy_denies_retreat_without_loss(self):
        h=BattleAuthority();h.agents[20]['pos']=(1499,0);h.execute(retreat)
        self.assertEqual(h.vars.get('$g_cycle_retreat_requested',0),0)
        self.assertEqual(h.parties[500].get(6400,0),0)
    def test_retreat_cover_excludes_heroes_controlled_soldier_and_enemy(self):
        h=BattleAuthority();h.execute(retreat)
        self.assertEqual(h.vars['$g_cycle_retreat_requested'],1)
        self.assertEqual(h.parties[500][6400],2)
        self.assertEqual(h.parties[500].get(6600,0),0)
        self.assertEqual(h.parties[501].get(6400,0),0)
        h.trigger[0]=11;h.execute(casualty);self.assertEqual(h.parties[500][6400],2)
    def test_defender_retreat_records_defending_side(self):
        h=BattleAuthority();h.players[2][6015]=1;h.vars[':player_no']=2;h.execute(retreat)
        self.assertEqual(h.vars['$g_cycle_retreat_requested'],2)
if __name__=='__main__': unittest.main()



