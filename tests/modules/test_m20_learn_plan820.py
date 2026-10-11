"""Structured objective decomposition, not autonomous goal choice/scheduling."""
from copy import deepcopy
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Supplied goal','url':'https://example.org/goal'}
def payload():return {'objective':'Complete task practice','source':SRC,'plan_goal':{'goal_id':'g','description':'Practice two skills','metric':'completed_tasks','target':10,'deadline':'2026-10-15T18:00:00+05:30','source':'fixture:goal'},'required_elements':['addition','division'],'plan_chunks':[{'chunk_id':'z','elements':['division'],'observable_subgoal':'Complete division tasks','metric':'completed_tasks','target':4,'deadline':'2026-10-15T16:00:00+05:30','prerequisites':['a'],'if_then':{'if':'After addition tasks','then':'Do division tasks'},'source':'fixture:z'},{'chunk_id':'a','elements':['addition'],'observable_subgoal':'Complete addition tasks','metric':'completed_tasks','target':6,'deadline':'2026-10-14T16:00:00+05:30','prerequisites':[],'if_then':{'if':'After breakfast','then':'Do addition tasks'},'source':'fixture:a'}]}
def run(method='chunking',**change):return execute(method,{**payload(),**change})['result']['objective_plan']

@pytest.mark.parametrize('method',['chunking','goal_setting'])
def test_ordered_chunks_computed_coverage_and_goal_aggregation(method):
 r=run(method);assert r['status']=='validated' and r['valid'] is True and r['ordered_chunk_ids']==['a','z']
 assert r['coverage']=={'required_elements':['addition','division'],'covered_elements':['addition','division'],'missing_elements':[],'unexpected_elements':[],'multiply_assigned_elements':[]}
 assert r['goal_aggregation']=={'metric':'completed_tasks','target':10,'chunk_target_total':10,'target_matches':True}
 assert r['chunks'][0]['chunk_id']=='a' and r['chunks'][1]['prerequisites']==['a']
 assert r['source_truth_verified'] is False and r['scheduled'] is False and r['goal_chosen_autonomously'] is False
 assert execute(method,payload())['evaluation']['capability_executed'] is True

def test_missing_duplicate_unexpected_coverage_and_target_mismatch():
 p=payload();p['plan_chunks'][1]['elements']=[];r=execute('chunking',p)['result']['objective_plan'];assert r['coverage']['missing_elements']==['addition'] and r['valid'] is False
 p=payload();p['plan_chunks'][0]['elements']+=['addition','extra'];r=execute('chunking',p)['result']['objective_plan'];assert r['coverage']['multiply_assigned_elements']==['addition'] and r['coverage']['unexpected_elements']==['extra'] and r['valid'] is False
 p=payload();p['plan_chunks'][0]['target']=5;r=execute('goal_setting',p)['result']['objective_plan'];assert r['goal_aggregation']['chunk_target_total']==11 and r['goal_aggregation']['target_matches'] is False and r['valid'] is False

def test_cycle_unknown_prerequisite_and_deadline_order():
 p=payload();p['plan_chunks'][1]['prerequisites']=['z']
 with pytest.raises(LearningReasoningError,match='acyclic'):execute('chunking',p)
 p=payload();p['plan_chunks'][0]['prerequisites']=['unknown']
 with pytest.raises(LearningReasoningError):execute('chunking',p)
 p=payload();p['plan_chunks'][0]['deadline']='2026-10-13T16:00:00+05:30'
 r=execute('chunking',p)['result']['objective_plan'];assert r['deadline_conflicts']==[{'chunk_id':'z','prerequisite_id':'a','reason':'prerequisite_deadline_after_chunk'}] and r['valid'] is False
 p=payload();p['plan_chunks'][0]['deadline']='2026-10-16T16:00:00+05:30';r=execute('goal_setting',p)['result']['objective_plan'];assert r['deadline_conflicts'][0]['reason']=='chunk_deadline_after_goal' and r['valid'] is False

@pytest.mark.parametrize('change',[{'plan_goal':None},{'required_elements':[]},{'required_elements':['addition','addition']},{'plan_chunks':[]},{'plan_chunks':[[]]}])
def test_shape_minimum_guards(change):
 with pytest.raises(LearningReasoningError):run(**change)

def test_text_metric_numeric_timezone_and_identity_guards():
 for field,value in [('target',True),('target',float('nan')),('target',-1),('source',''),('deadline','2026-10-15')]:
  p=payload();p['plan_goal'][field]=value
  with pytest.raises(LearningReasoningError):execute('goal_setting',p)
 for field,value in [('metric','different'),('observable_subgoal',''),('prerequisites','a'),('if_then',{'if':'','then':'x'}),('target',0)]:
  p=payload();p['plan_chunks'][0][field]=value
  with pytest.raises(LearningReasoningError):execute('chunking',p)
 p=payload();p['plan_chunks'].append(deepcopy(p['plan_chunks'][0]))
 with pytest.raises(LearningReasoningError):execute('chunking',p)

def test_deterministic_ties_and_input_nonmutation():
 p=payload();p['plan_chunks'][0]['prerequisites']=[];before=deepcopy(p)
 r=execute('chunking',p)['result']['objective_plan'];assert r['ordered_chunk_ids']==['a','z'] and p==before

def test_mounted_auth_declared_break_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method in ['chunking','goal_setting']:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':payload()}).status_code==401
  r=c.post(path,headers=h,json={'payload':payload()});assert r.status_code==200 and r.json()['tenant_id']=='a'
  assert c.post(path,headers=h,json={'payload':{'source':SRC,'objective':'x'}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**payload(),'resource_refs':[{'tenant_id':'b'}]}}).status_code==403

def test_exact_caps_target_bounds_and_equal_deadlines():
 p=payload();p['required_elements']=[str(i)for i in range(64)];p['plan_chunks']=[{'chunk_id':str(i),'elements':[str(i)],'observable_subgoal':'subgoal','metric':'completed_tasks','target':1,'deadline':p['plan_goal']['deadline'],'prerequisites':[],'if_then':{'if':'condition','then':'action'},'source':'fixture'}for i in range(64)];p['plan_goal']['target']=64
 assert execute('chunking',p)['result']['objective_plan']['valid'] is True
 p['required_elements'].append('64')
 with pytest.raises(LearningReasoningError):execute('chunking',p)
 p=payload();p['plan_goal']['target']=1000000;p['plan_chunks'][0]['target']=999994
 assert execute('goal_setting',p)['result']['objective_plan']['valid'] is True
 for value in [0,1000001,1.5]:
  p=payload();p['plan_goal']['target']=value
  with pytest.raises(LearningReasoningError):execute('goal_setting',p)

def test_full_goal_chunks_ifthen_and_boundary_echo():
 p=payload();r=execute('chunking',p)['result']['objective_plan']
 assert r['goal']==p['plan_goal'] and r['chunks']==[p['plan_chunks'][1],p['plan_chunks'][0]] and r['deadline_conflicts']==[]
 assert r['boundary']=='Supplied additive count-goal DAG decomposition and coverage/deadline/if-then validation only. No autonomous goal choice, feasibility prediction, scheduling or verified achievement.'

def test_duplicate_coverage_without_other_gap_invalidates():
 p=payload();p['plan_chunks'][0]['elements'].append('addition')
 r=execute('chunking',p)['result']['objective_plan']
 assert r['coverage']['missing_elements']==r['coverage']['unexpected_elements']==[] and r['coverage']['multiply_assigned_elements']==['addition'] and r['valid'] is False
