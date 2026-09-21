import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m14_project_builder.semantic_engines_575_584 import run as eng
from app.modules.m14_project_builder.semantic_architecture_635_684 import run as arch
from app.modules.m14_project_builder.routes import router

def ed(r):return {575:{'initial_state':{'x':1},'steps':2,'transition':{'x':{'multiplier':2}}},576:{'initial_state':{'score':0},'inputs':['hit'],'rules':{'hit':{'state_delta':{'score':1}}}},577:{'bodies':[{'position':0,'velocity':0,'acceleration':2}],'dt_seconds':.5,'steps':2},578:{'scene':{'objects':[{'id':'a','z':2},{'id':'b','z':1}]},'camera':{},'viewport':[1,1]},579:{'sample_rate_hz':48000,'tracks':[{'duration_seconds':1,'peak':.6,'gain':1},{'duration_seconds':2,'peak':.6,'gain':1}]},580:{'layers':['transport'],'links':[{'from':'a','to':'b'}],'packets':[{'id':'p','route':['a','b']}]},581:{'states':['idle','open'],'initial_state':'idle','transitions':[{'from':'idle','to':'open','message':'start'}]},582:{'text':'a'*100},583:{'bits':'1011'},584:{'roles':['a','b'],'messages':[{'from':'a','to':'b'}],'security_goals':['auth'],'threats':['replay']}}[r]
@pytest.mark.parametrize('row',range(575,585))
def test_engine_rows_distinctive(row):assert eng(row,ed(row))['result']
@pytest.mark.parametrize('row',range(575,585))
def test_engine_rows_invalid(row):
 with pytest.raises((ValueError,KeyError,TypeError)):eng(row,{})
def test_575_state_transition():assert eng(575,ed(575))['result']['state_trace'][-1]['x']==4
def test_576_interactive_input():assert eng(576,ed(576))['result']['final_state']['score']==1
def test_577_physics_integrator():assert eng(577,ed(577))['result']['bodies'][0]['position']==1.5
def test_578_render_order():assert eng(578,ed(578))['result']['ordered_object_ids']==['b','a']
def test_579_clipping():assert eng(579,ed(579))['result']['clipping_risk']
def test_580_packet_route():assert eng(580,ed(580))['result']['packet_routes'][0]['deliverable']
def test_581_protocol_determinism():assert eng(581,ed(581))['result']['deterministic']
def test_582_compression_round_trip():assert eng(582,ed(582))['result']['round_trip_verified']
def test_583_error_detection():
 x=ed(583);x['received_bits']='00111';assert eng(583,x)['result']['error_detected']
def test_584_no_fake_crypto_proof():assert not eng(584,ed(584))['result']['formal_security_proof']

def ad(r):
 if r==635:return {'indicators':[{'name':'a','good_events':9,'valid_events':10,'target':.9,'window':'1d'}]}
 if r==636:return {'target':.99,'total_events':1000,'bad_events':5}
 if r==637:return {'severity':'sev1','roles':['incident_commander'],'timeline':['t']}
 if r==638:return {'facts':['f'],'contributing_factors':['c'],'actions':[{'owner':'o','due':'d'}]}
 if r==639:return {'trigger':'x','steps':['s'],'verification':['v'],'rollback':['r']}
 if r==640:return {'people':['a'],'shifts':[{'primary':'a'}]}
 if r==641:return {'current_capacity':100,'growth_rate':.1,'periods':2}
 if r==642:return {'options':[{'savings':10,'migration_cost':3}]}
 if r==643:return {'resources':{'cpu':2},'jobs':[{'requests':{'cpu':1}}]}
 if r==644:return {'jobs':[{'id':'a','priority':1,'enqueued_at':'t'}]}
 if r in {645,646}:return {'nodes':['a','b'],'edges':[{'from':'a','to':'b'}]}
 if r==647:return {'expression':'0 * * * *','timezone':'UTC'}
 if r==648:return {'events':[{'sequence':1,'version':1}]}
 if r==649:return {'commands':['write'],'queries':['read']}
 if r==650:return {'steps':[{'id':'a','compensation':'undo'}]}
 if r==651:return {'participants':['a','b']}
 if r==652:return {'requests':[{'key':'k'},{'key':'k'}]}
 if r in {653,654}:return {'messages':[{'id':'m'}]}
 if r==655:return {'messages':[{'id':'m','attempts':3}],'max_attempts':3}
 if r==656:return {'error':{'transient':True},'attempt':1,'max_attempts':3}
 if r==657:return {'attempt':3,'base_seconds':2,'cap_seconds':10}
 if r==658:return {'pools':[{'resource':'a'},{'resource':'b'}]}
 if 659<=r<=670:return {'components':['a']}
 return {'model':{'name':'x'}}
@pytest.mark.parametrize('row',range(635,685))
def test_architecture_rows_distinctive(row):
 o=arch(row,ad(row));assert o['row']==row and o['result']
@pytest.mark.parametrize('row',range(635,685))
def test_architecture_rows_invalid(row):
 with pytest.raises((ValueError,KeyError,TypeError)):arch(row,{})
def test_636_error_budget():assert arch(636,ad(636))['result']['remaining']==pytest.approx(5)
def test_638_blame_forbidden():assert arch(638,ad(638))['result']['root_cause_person_forbidden']
def test_641_compound_capacity():assert arch(641,ad(641))['result']['forecast'][-1]==pytest.approx(121)
def test_647_cron_shape():assert arch(647,ad(647))['result']['valid_shape']
def test_652_idempotency_duplicate():assert arch(652,ad(652))['result']['requests'][1]['duplicate']
def test_653_exactly_once_caveat():assert arch(653,ad(653))['result']['end_to_end_guarantee_not_inferred']
def test_654_at_least_once_duplicates():assert arch(654,ad(654))['result']['duplicates_possible']
def test_657_capped_backoff():assert arch(657,ad(657))['result']['delay_seconds']==8
def test_patterns_have_distinct_invariants():assert len({arch(r,ad(r))['result']['pattern_invariant'] for r in range(659,671)})==12
def test_domain_rows_have_distinct_invariants():assert len({arch(r,ad(r))['result']['distinctive_invariant'] for r in range(671,685)})==14
def test_mounted_http_evidence():
 a=FastAPI();a.include_router(router);c=TestClient(a)
 assert c.post('/project-builder/semantic-engines-575-584/582',json=ed(582)).status_code==200
 assert c.post('/project-builder/semantic-architecture-635-684/652',json=ad(652)).status_code==200
 assert c.post('/project-builder/semantic-engines-575-584/575',json={}).status_code==422
