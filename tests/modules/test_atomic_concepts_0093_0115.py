import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.atomic_concepts_0093_0115 import META,run
C={93:{'input':[1,0,0,0],'response':[0,0,1,0],'max_lag':3},94:{'individual_predictions':[1,1,1],'observed_system':[1,3,1],'threshold':1},95:{'stages':['a','b','c'],'capacities':[10,5,8],'demand_rate':7},96:{'stages':['a','b','c'],'capacities':[10,5,8],'proposed_uplift':4},97:{'x':[0,1,2,3],'y':[2,4,8,16]},98:{'x':[1,2.718281828,7.389056],'y':[1,3,5]},99:{'x':[1,2,4,8],'y':[3,12,48,192]},100:{'stages':[{'name':'design','cost':10,'customer_value':50,'revenue':20},{'name':'sell','cost':5,'customer_value':20,'revenue':40}]},101:{'stages':[{'name':'design','cost':10,'customer_value':50,'revenue':20},{'name':'sell','cost':5,'customer_value':20,'revenue':40}]},102:{'arrivals':[1,2,3,4],'departures':[{'entered_at':0,'exited_at':2},{'entered_at':1,'exited_at':3}],'window':2,'ending_wip':2},103:{'arrivals':[1,2,3,4],'departures':[{'entered_at':0,'exited_at':2},{'entered_at':1,'exited_at':3}],'window':2,'ending_wip':2},104:{'arrivals':[1,2,3,4],'departures':[{'entered_at':0,'exited_at':2},{'entered_at':1,'exited_at':3}],'window':2,'ending_wip':2},105:{'arrivals':[1,2,3,4],'departures':[{'entered_at':0,'exited_at':2},{'entered_at':1,'exited_at':3}],'window':2,'ending_wip':2},106:{'private_value':100,'bidder_count':5,'auction_type':'first_price'},107:{'buyer_values':[10,20,30,40]},108:{'claims':[{'claim':'licensed','issuer':'board','evidence_uri':'u','checked_at':'today'},{'claim':'expert'}]},109:{'claims':[{'claim':'licensed','issuer':'board','evidence_uri':'u','checked_at':'today'},{'claim':'expert'}]},110:{'my_facts':['artist','student'],'their_verified_facts':['artist','runner'],'open_questions':['What are you making?']},111:{'my_facts':['artist'],'their_verified_facts':['artist','doctor']},112:{'my_groups':['team-a','school'],'their_verified_groups':['team-a','club']},113:{'my_goals':['safer streets','growth'],'their_verified_goals':['safer streets']},114:{'papers':[{'id':'a','year':2020},{'id':'b','year':2021},{'id':'c','year':2022}],'citations':[{'citing':'b','cited':'a'},{'citing':'c','cited':'a'}]},115:{'papers':[{'id':'a','year':2020},{'id':'b','year':2021}],'citations':[{'citing':'b','cited':'a'}]}}
@pytest.mark.parametrize('row',range(93,116))
def test_each_atomic_concept_has_distinctive_output(row):
 m=META[row][1];r=run(m,C[row]);assert r['atomic_row']==row and r['atomic_row_id']==META[row][0] and r['output']['method_limits']
def test_models_recover_known_parameters():
 assert run('system_delay',C[93])['output']['estimated_delay_periods']==2
 assert run('exponential_model',C[97])['output']['growth_rate']==pytest.approx(__import__('math').log(2))
 assert run('power_law_model',C[99])['output']['exponent']==pytest.approx(2)
def test_toc_little_and_auction_invariants():
 assert run('constraint_identification',C[95])['output']['constraint']=='b'
 x=run('constraint_improvement',C[96])['output'];assert x['before_capacity']==5 and x['after_capacity']==8 and x['next_constraint']=='c'
 l=run('littles_law_check',C[105])['output'];assert l['wip']==2 and l['throughput_per_time']==1 and l['little_predicted_cycle_time']==2 and l['consistent']
 assert run('bidding_optimization',C[106])['output']['recommended_bid']==80
 assert run('selling_optimization',C[107])['output']['recommended_reserve']==20  # revenue ties at 20 and 30 (60); lowest reserve wins; old 40 yielded only 40
def test_no_fabricated_credibility_similarity_or_unity():
 a=run('expertise_positioning',C[108])['output'];assert len(a['verified_claims'])==1 and a['unsupported_claims'][0]['claim']=='expert'
 assert run('similarity_grounding',C[111])['output']['genuine_commonalities']==['artist']
 assert not run('shared_identity',{'my_groups':['a'],'their_verified_groups':['b']})['output']['frame_allowed']
def test_citation_direction_and_chronology():
 assert run('citation_influence',C[114])['output']['in_degree']['a']==2
 assert run('academic_idea_flow',C[115])['output']['idea_flow_edges']==[{'from':'a','to':'b'}]
def test_negative_paths_and_http_mount():
 with pytest.raises(ValueError):run('exponential_model',{'x':[1,2,3],'y':[1,0,3]})
 with pytest.raises(ValueError):run('littles_law_check',{'arrivals':[],'departures':[],'window':0})
 with pytest.raises(ValueError):run('bidding_optimization',{'private_value':10,'bidder_count':1})
 c=TestClient(app);h={'X-Tenant-ID':'atomic','X-Actor-ID':'tester'}
 assert len(c.get('/api/v1/api/modules/20/atomic-concepts-93-115/methods',headers=h).json())==23
 r=c.post('/api/v1/api/modules/20/atomic-concepts-93-115/analyze',headers=h,json={'method':'power_law_model','data':C[99]});assert r.status_code==200 and r.json()['output']['exponent']==pytest.approx(2)
 assert c.post('/api/v1/api/modules/20/atomic-concepts-93-115/analyze',headers=h,json={'method':'bad'}).status_code==422

import itertools,math,random
_URL='/api/v1/api/modules/20/atomic-concepts-93-115/analyze'
_H={'X-Tenant-ID':'atomic','X-Actor-ID':'tester'}
def _ref_reserve(vals):
 best=None
 for r0 in sorted(set(vals)):
  rev=sum(r0 for v in vals if v>=r0)
  if best is None or rev>best[1]:best=(r0,rev)
 return best
def test_reserve_issue_example():
 o=run('selling_optimization',{'buyer_values':[5,5,8]})['output'];assert o['recommended_reserve']==5 and o['empirical_revenue_bound']==15
def test_reserve_matches_bruteforce_random_and_ties():
 rnd=random.Random(7)
 for _ in range(300):
  vals=[rnd.choice([0,1,2,3,5,8,13]) if rnd.random()<.5 else rnd.uniform(0,50) for _ in range(rnd.randint(1,9))]
  if max(vals)==0:continue
  o=run('selling_optimization',{'buyer_values':vals})['output'];r,rev=_ref_reserve(vals)
  assert o['recommended_reserve']==r and o['empirical_revenue_bound']==pytest.approx(rev)
  # independent: no price on a fine grid of all pairs beats it
  assert all(c*sum(v>=c for v in vals)<=rev+1e-9 for c in vals)
def test_reserve_all_zero_and_validation():
 assert run('selling_optimization',{'buyer_values':[0,0]})['output']['empirical_revenue_bound']==0
 for bad in ([],[-1,2],[1,float('nan')],[1,float('inf')],[True,2],['a'],None):
  with pytest.raises(ValueError):run('selling_optimization',{'buyer_values':bad})
def _ref_scores(x,y,m):return [sum(a*b for a,b in zip(x[:len(x)-k],y[k:]))/(len(x)-k) for k in range(m+1)]
def test_lag_matches_bruteforce_random():
 rnd=random.Random(3)
 for _ in range(200):
  n=rnd.randint(1,8);x=[rnd.choice([0,1,-1,2.5,rnd.uniform(-5,5)]) for _ in range(n)];y=[rnd.choice([0,1,rnd.uniform(-5,5)]) for _ in range(n)];m=rnd.randint(0,n-1)
  o=run('system_delay',{'input':x,'response':y,'max_lag':m})['output'];ref=_ref_scores(x,y,m)
  assert o['lag_scores']==pytest.approx(ref);assert o['estimated_delay_periods']==max(range(m+1),key=lambda i:ref[i])
 o=run('system_delay',{'input':[1,2,3],'response':[1,2,3]})['output'];assert len(o['lag_scores'])==3
 o=run('system_delay',{'input':[1,1],'response':[1,1],'max_lag':1})['output'];assert o['lag_scores']==[1,1] and o['estimated_delay_periods']==0
@pytest.mark.parametrize('lag',[4,5,100,-1,1.5,True,'2',None])
def test_lag_rejected_at_run_and_route_422(lag):
 d={'input':[1,0,0,0],'response':[0,0,1,0],'max_lag':lag}
 with pytest.raises(ValueError):run('system_delay',d)
 c=TestClient(app,raise_server_exceptions=False);r=c.post(_URL,headers=_H,json={'method':'system_delay','data':d});assert r.status_code==422
@pytest.mark.parametrize('d',[{'input':[1,2],'response':[1],'max_lag':0},{'input':[],'response':[],'max_lag':0},{'input':[1,float('nan')],'response':[1,2],'max_lag':1}])
def test_lag_domain_guards(d):
 with pytest.raises(ValueError):run('system_delay',d)
def test_route_422_reserve():
 c=TestClient(app,raise_server_exceptions=False)
 for bad in ([],[-1]):assert c.post(_URL,headers=_H,json={'method':'selling_optimization','data':{'buyer_values':bad}}).status_code==422
 r=c.post(_URL,headers=_H,json={'method':'selling_optimization','data':{'buyer_values':[5,5,8]}});assert r.status_code==200 and r.json()['output']['recommended_reserve']==5
