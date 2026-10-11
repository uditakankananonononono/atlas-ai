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
 p=system();p['system_flows'][0].update({'from':None,'rate_kind':'constant','driver':None,'rate':2});r=run('systems_thinking',p)
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

from app.modules.m20_general_cognitive_worker import qualitative_systems as core

def error(fn,p,msg):
 with pytest.raises(ValueError)as exc:fn(p)
 assert str(exc.value)==msg

@pytest.mark.parametrize('change,msg',[
 ('empty','qualitative_variables requires bounded object list'),('duplicate','unique variables, known initial and ordered landmark signs required'),('initial','unique variables, known initial and ordered landmark signs required'),('order','unique variables, known initial and ordered landmark signs required'),('marks_duplicate','unique landmark ids required'),('sign_bool','landmark sign requires integer[-1,1]'),('influence_unknown','unique influences, known variables and nonzero signs required'),('influence_duplicate','unique influences, known variables and nonzero signs required'),('influence_zero','unique influences, known variables and nonzero signs required'),('influence_source','influence source requires bounded nonempty string'),('steps_bool','qualitative_steps requires integer[0,8]')])
def test_qual_validators(change,msg):
 p=qualitative()
 if change=='empty':p['qualitative_variables']=[]
 elif change=='duplicate':p['qualitative_variables'].append(deepcopy(p['qualitative_variables'][0]))
 elif change=='initial':p['qualitative_variables'][0]['initial']='unknown'
 elif change=='order':p['qualitative_variables'][0]['landmarks'].reverse()
 elif change=='marks_duplicate':p['qualitative_variables'][0]['landmarks'][1]['id']='low'
 elif change=='sign_bool':p['qualitative_variables'][0]['landmarks'][0]['sign']=True
 elif change=='influence_unknown':p['qualitative_influences'][0]['to']='unknown'
 elif change=='influence_duplicate':p['qualitative_influences']*=2
 elif change=='influence_zero':p['qualitative_influences'][0]['sign']=0
 elif change=='influence_source':p['qualitative_influences'][0]['source']=''
 else:p['qualitative_steps']=True
 error(core.qualitative,p,msg)

def test_qual_bounds_and_exhaustion():
 p=qualitative();v=p['qualitative_variables'][0];p['qualitative_variables']=[{**deepcopy(v),'id':str(i)}for i in range(6)];p['qualitative_influences']=[];p['qualitative_steps']=8
 assert core.qualitative(p)['completed_steps']==8
 p['qualitative_variables'].append({**deepcopy(v),'id':'6'});error(core.qualitative,p,'qualitative_variables requires bounded object list')
 p=qualitative();p['qualitative_steps']=0;assert len(core.qualitative(p)['states_by_step'])==1
 p['qualitative_steps']=9;error(core.qualitative,p,'qualitative_steps requires integer[0,8]')
 p=qualitative();p['qualitative_influences']=[{**p['qualitative_influences'][0],'id':str(i)}for i in range(64)];core.qualitative(p)
 p['qualitative_influences'].append({**p['qualitative_influences'][0],'id':'64'});error(core.qualitative,p,'qualitative_influences requires bounded object list')
 p=qualitative();p['qualitative_variables']=[{**deepcopy(v),'id':str(i)}for i in range(6)]
 p['qualitative_influences']=[{'id':str(i)+str(s),'from':'0','to':str(i),'sign':s,'source':'fixture'}for i in range(6)for s in [-1,1]]
 r=core.qualitative(p);assert r['status']=='state_budget_exhausted' and r['completed_steps']==1 and len(r['states_by_step'])==2

@pytest.mark.parametrize('change,msg',[
 ('duplicate_stock','unique stock IDs and nonnegative initial required'),('negative','unique stock IDs and nonnegative initial required'),('source','stock source requires bounded nonempty string'),('duplicate_flow','unique flows with distinct known endpoints or one external endpoint required'),('unknown','unique flows with distinct known endpoints or one external endpoint required'),('self','unique flows with distinct known endpoints or one external endpoint required'),('external_both','unique flows with distinct known endpoints or one external endpoint required'),('unit','supported nonnegative rates and matching endpoint/time units required'),('time','supported nonnegative rates and matching endpoint/time units required'),('rate','supported nonnegative rates and matching endpoint/time units required'),('kind','supported nonnegative rates and matching endpoint/time units required'),('driver','constant has no driver/delay; proportional has matching known driver required'),('constant_driver','constant has no driver/delay; proportional has matching known driver required'),('delay','delay_steps requires integer[0,8]'),('steps','system_steps requires integer[0,64]'),('dt','system_dt in(0,1000] required')])
def test_stock_validators(change,msg):
 p=system();f=p['system_flows'][0]
 if change=='duplicate_stock':p['system_stocks'].append(deepcopy(p['system_stocks'][0]))
 elif change=='negative':p['system_stocks'][0]['initial']=-1
 elif change=='source':p['system_stocks'][0]['source']=''
 elif change=='duplicate_flow':p['system_flows']*=2
 elif change=='unknown':f['to']='unknown'
 elif change=='self':f['to']='a'
 elif change=='external_both':f['to']=f['from']=None
 elif change=='unit':f['stock_unit']='kg'
 elif change=='time':f['time_unit']='hour'
 elif change=='rate':f['rate']=-1
 elif change=='kind':f['rate_kind']='invented'
 elif change=='driver':f['driver']='unknown'
 elif change=='constant_driver':f['rate_kind']='constant'
 elif change=='delay':f['delay_steps']=9
 elif change=='steps':p['system_steps']=True
 else:p['system_dt']=0
 error(core.stock_flow,p,msg)

def test_system_caps_empty_flows_and_unit_totals():
 p=system();stock=p['system_stocks'][0];p['system_stocks']=[{**stock,'id':str(i)}for i in range(16)];p['system_flows']=[];p['system_steps']=64
 r=core.stock_flow(p);assert len(r['trajectory'])==65 and r['trajectory'][-1]['totals_by_unit']=={'litre':'160'} and r['feedback_cycles']==[]
 p['system_stocks'].append({**stock,'id':'overflow'});error(core.stock_flow,p,'system_stocks requires bounded object list')
 p=system();p['system_flows']=[{**p['system_flows'][0],'id':str(i),'rate':0}for i in range(32)];assert len(core.stock_flow(p)['flow_records'])==64
 p['system_flows'].append({**p['system_flows'][0],'id':'overflow'});error(core.stock_flow,p,'system_flows requires bounded object list')
 p=system();p['system_flows']=[];p['system_stocks'][1]['unit']='kg';p['system_stocks'][1]['initial']=3
 assert core.stock_flow(p)['trajectory'][-1]['totals_by_unit']=={'kg':'3','litre':'10'}
 p['system_steps']=65;error(core.stock_flow,p,'system_steps requires integer[0,64]')

def test_simultaneous_flows_order_and_two_stock_feedback():
 p=system();p['system_flows'].append({**p['system_flows'][0],'id':'back','from':'b','to':'a','driver':'b','rate':'1/4'})
 r=core.stock_flow(p);assert r['trajectory'][-1]['stocks']=={'a':'15/4','b':'25/4'}
 assert r['feedback_cycles']==[{'stock_ids':['a'],'sign':-1},{'stock_ids':['a','b'],'sign':1},{'stock_ids':['b'],'sign':-1}]
 p['system_flows'].reverse();assert core.stock_flow(p)==r

def test_delay_max_prehistory_and_rational_overflow():
 p=system();p['system_flows'][0]['delay_steps']=8;p['system_steps']=1;r=core.stock_flow(p)
 assert r['flow_records'][0]['driver_step']==0
 p=system();p['system_stocks'][0]['initial']=10**12;p['system_flows'][0]['rate']=1000
 error(core.stock_flow,p,'simulation rational components exceed10**12')

def test_landmark_bounds_and_zero_negative_sign_edges():
 p=qualitative();p['qualitative_variables'][0]['landmarks']=[{'id':str(i),'sign':-1 if i<2 else 0 if i==2 else 1}for i in range(5)];p['qualitative_variables'][0]['initial']='4'
 assert core.qualitative(p)['states_by_step'][1][0]['b']=='high'
 p['qualitative_variables'][0]['landmarks'].append({'id':'5','sign':1});error(core.qualitative,p,'landmarks requires bounded object list')
 p=qualitative();p['qualitative_variables'][0]['landmarks']=[{'id':'zero','sign':0}];p['qualitative_variables'][0]['initial']='zero';error(core.qualitative,p,'landmarks requires bounded object list')
 p=qualitative();p['qualitative_variables'][0]['initial']='zero';assert core.qualitative(p)['states_by_step'][1][0]['b']=='zero'
 p['qualitative_variables'][0]['initial']='low';assert core.qualitative(p)['states_by_step'][1][0]['b']=='low'
 p['qualitative_influences'][0]['sign']=-1;assert core.qualitative(p)['states_by_step'][1][0]['b']=='high'

def test_stock_dt_scaling_empty_initial_and_canonical_sorted_output():
 p=system();p['system_dt']='1/2';p['system_steps']=1;r=core.stock_flow(p)
 assert r['trajectory'][-1]['stocks']=={'a':'15/2','b':'5/2'} and r['flow_records'][0]['amount']=='5/2'
 p=system();p['system_steps']=0;r=core.stock_flow(p);assert len(r['trajectory'])==1 and r['flow_records']==[]
 p=system();p['system_stocks'].reverse();assert core.stock_flow(p)==core.stock_flow(system())
 p['system_stocks']=[];error(core.stock_flow,p,'system_stocks requires bounded object list')
 p=system();p['system_flows'][0]['rate_kind']='constant';p['system_flows'][0]['driver']=None;p['system_flows'][0]['delay_steps']=1
 error(core.stock_flow,p,'constant has no driver/delay; proportional has matching known driver required')


def test_boundary_echo_execution_kind_and_no_prediction():
 from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import capabilities
 catalog={c['row_id']:c['execution_kind']for c in capabilities()}
 assert catalog[840]==catalog[856]=='restricted_computation'
 for method,p in [('qualitative_reasoning',qualitative()),('systems_thinking',system())]:
  r=execute(method,p);assert r['evaluation']['capability_executed'] is True and r['evaluation']['independent_verification_required'] is True
  result=r['result']['qualitative_graph' if method=='qualitative_reasoning'else'stock_flow_simulation']
  assert result['source_truth_verified'] is False and result['boundary']
