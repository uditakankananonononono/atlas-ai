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
 assert run('selling_optimization',C[107])['output']['recommended_reserve']==40
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
