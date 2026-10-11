"""Finite signed-landmark successors and exact declared stock-flow simulation."""
import pytest
from copy import deepcopy
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Fixture','url':'https://example.org/system'}
def qualitative():return {'source':SRC,'qualitative_variables':[{'id':'a','landmarks':[{'id':'low','sign':-1},{'id':'zero','sign':0},{'id':'high','sign':1}],'initial':'high'},{'id':'b','landmarks':[{'id':'low','sign':-1},{'id':'zero','sign':0},{'id':'high','sign':1}],'initial':'zero'}],'qualitative_influences':[{'id':'i','from':'a','to':'b','sign':1,'source':'fixture:i'}],'qualitative_steps':2}
def system():return {'source':SRC,'problem':'Reservoir','system_stocks':[{'id':'a','unit':'litre','initial':10,'source':'fixture:a'},{'id':'b','unit':'litre','initial':0,'source':'fixture:b'}],'system_flows':[{'id':'move','from':'a','to':'b','rate_kind':'proportional','driver':'a','rate':'1/2','delay_steps':0,'stock_unit':'litre','time_unit':'day','source':'fixture:move'}],'system_time_unit':'day','system_dt':1,'system_steps':2}
def run(method,p):return execute(method,p)['result']['qualitative_graph' if method=='qualitative_reasoning' else 'stock_flow_simulation']
def test_qualitative_computes_adjacent_states_and_preserves_opposed_effects():
 p=qualitative();r=run('qualitative_reasoning',p);assert r['states_by_step']==[[{'a':'high','b':'zero'}],[{'a':'high','b':'high'}],[{'a':'high','b':'high'}]]
 p['qualitative_influences'].append({'id':'j','from':'a','to':'b','sign':-1,'source':'fixture:j'});p['qualitative_steps']=1;r=run('qualitative_reasoning',p)
 assert r['states_by_step'][1]==[{'a':'high','b':'low'},{'a':'high','b':'zero'},{'a':'high','b':'high'}]
 assert r['ambiguous_successors_preserved'] is True and r['source_truth_verified'] is False

def test_stock_flow_simultaneous_exact_conservation_feedback():
 r=run('systems_thinking',system())
 assert r['trajectory']==[{'step':0,'stocks':{'a':'10','b':'0'},'totals_by_unit':{'litre':'10'}},{'step':1,'stocks':{'a':'5','b':'5'},'totals_by_unit':{'litre':'10'}},{'step':2,'stocks':{'a':'5/2','b':'15/2'},'totals_by_unit':{'litre':'10'}}]
 assert r['closed_system'] is True and r['conservation_verified'] is True and r['feedback_cycles']==[{'stock_ids':['a'],'sign':-1}]
 assert r['source_truth_verified'] is False and r['real_world_prediction'] is None

def test_delay_uses_predeclared_constant_prehistory():
 p=system();p['system_flows'][0]['delay_steps']=1;r=run('systems_thinking',p)
 assert r['trajectory'][-1]['stocks']=={'a':'0','b':'10'} and r['flow_records'][1]['amount']=='5' and r['flow_records'][1]['driver_step']==0

def test_negative_stock_blocks_atomic_step():
 p=system();p['system_flows'][0]['rate']=2;r=run('systems_thinking',p)
 assert r['status']=='negative_stock_blocked' and len(r['trajectory'])==1 and r['blocked_step']==1 and r['blocked_stocks']==['a']

def test_external_flow_balance_and_unit_isolation():
 p=system();p['system_flows'][0].update({'from':None,'rate_kind':'constant','rate':2});r=run('systems_thinking',p)
 assert r['closed_system'] is False and r['trajectory'][-1]['totals_by_unit']=={'litre':'14'} and r['external_net_by_unit']=={'litre':'4'} and r['conservation_verified'] is True

@pytest.mark.parametrize('method',['qualitative_reasoning','systems_thinking'])
def test_minimal_refusal(method):
 with pytest.raises(LearningReasoningError):run(method,{'source':SRC,'problem':'x'})

def test_mounted_auth_and_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method,p in [('qualitative_reasoning',qualitative()),('systems_thinking',system())]:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':p}).status_code==401
  assert c.post(path,headers=h,json={'payload':p}).status_code==200
  assert c.post(path,headers=h,json={'payload':{'source':SRC,'problem':'x'}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**p,'resource_refs':[{'tenant_id':'b'}]}}).status_code==403
