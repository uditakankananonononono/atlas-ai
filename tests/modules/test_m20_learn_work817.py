"""Exact rational register tasks, verifier and bounded BFS, no general reasoning."""
from copy import deepcopy
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Arithmetic task','url':'https://example.org/task'}
def task():return {'initial':'1','goal':'6','operations':[{'id':'add','kind':'add','operand':'2','source':'fixture:add'},{'id':'mul','kind':'multiply','operand':'2','source':'fixture:mul'}],'max_depth':3,'state_bound':'100'}
def trace():return [{'pre':'1','operation_id':'add','post':'3','rationale':'apply:add','source':'fixture:step1'},{'pre':'3','operation_id':'mul','post':'6','rationale':'apply:multiply','source':'fixture:step2'}]
def payload():return {'objective':'Solve arithmetic register task','source':SRC,'arithmetic_task':task(),'worked_trace':trace(),'completion_task':{**task(),'initial':'2','goal':'8'}}
def run(method='worked_examples',**change):return execute(method,{**payload(),**change})['result']['arithmetic_work']

def test_valid_worked_trace_exact_feedback_and_completion():
 r=run();assert r['status']=='verified_worked_example' and r['trace_valid'] is True and r['goal_reached'] is True
 assert r['step_reports']==[{'step_index':0,'pre':'1','operation_id':'add','expected_post':'3','submitted_post':'3','pre_matches':True,'post_matches':True,'rationale_matches':True,'accepted':True,'operation_source':'fixture:add','step_source':'fixture:step1'},{'step_index':1,'pre':'3','operation_id':'mul','expected_post':'6','submitted_post':'6','pre_matches':True,'post_matches':True,'rationale_matches':True,'accepted':True,'operation_source':'fixture:mul','step_source':'fixture:step2'}]
 assert r['completion_problem']=={'initial':'2','goal':'8','operations':task()['operations'],'max_depth':3,'state_bound':'100','source_truth_verified':False}
 assert r['source_truth_verified'] is False and r['learner_understanding'] is None
 assert execute('worked_examples',payload())['evaluation']['capability_executed'] is True

@pytest.mark.parametrize('change',[{'pre':'2'},{'post':'4'},{'rationale':'because it works'},{'operation_id':'unknown'}])
def test_invalid_worked_trace_never_emits_completion(change):
 steps=trace();steps[0].update(change);r=run(worked_trace=steps)
 assert r['trace_valid'] is False and r['step_reports'][0]['accepted'] is False and r['completion_problem'] is None
 assert r['status']=='invalid_worked_trace'

def test_goal_wrong_or_incomplete_and_completion_reachability():
 r=run(worked_trace=trace()[:1]);assert r['trace_valid'] is True and r['goal_reached'] is False and r['completion_problem'] is None
 r=run(completion_task={**task(),'initial':'1','goal':'7','max_depth':1});assert r['completion_problem'] is None and r['completion_status']=='no_solution_within_bounds'
 r=run(completion_task=None);assert r['completion_problem'] is None and r['completion_status']=='not_supplied'

def test_problem_solver_shortest_trace_and_exact_rational_math():
 r=run('problem_solving');assert r['status']=='solved' and r['solution']==trace() and r['final_value']=='6' and r['solution_depth']==2
 t={'initial':'1/3','goal':'1','operations':[{'id':'add','kind':'add','operand':'1/3','source':'fixture:add'}],'max_depth':2,'state_bound':'10'}
 r=run('problem_solving',arithmetic_task=t);assert r['solution_depth']==2 and r['final_value']=='1'
 assert r['solution'][0]['post']=='2/3'

def test_solver_no_solution_and_explicit_bounds():
 r=run('problem_solving',arithmetic_task={**task(),'max_depth':1});assert r['status']=='no_solution_within_bounds' and r['solution'] is None
 r=run('problem_solving',arithmetic_task={**task(),'state_bound':'2'});assert r['status']=='no_solution_within_bounds'
 t={**task(),'goal':'1'};r=run('problem_solving',arithmetic_task=t);assert r['solution']==[] and r['solution_depth']==0

@pytest.mark.parametrize('change',[{'initial':True},{'initial':'nan'},{'goal':'1/0'},{'max_depth':True},{'max_depth':9},{'state_bound':'0'},{'operations':[]},{'operations':[{'id':'x','kind':'divide','operand':'0','source':'fixture'}]},{'operations':[{'id':'x','kind':'eval','operand':'2','source':'fixture'}]}])
def test_invalid_task_grammar_and_nonmutation(change):
 p=payload();p['arithmetic_task'].update(change);before=deepcopy(p)
 with pytest.raises(LearningReasoningError):execute('problem_solving',p)
 assert p==before

def test_sources_shapes_duplicate_operations_and_trace_cap():
 for field in ['source','id']:
  p=payload();p['arithmetic_task']['operations'][0][field]=''
  with pytest.raises(LearningReasoningError):execute('problem_solving',p)
 p=payload();p['arithmetic_task']['operations']*=2
 with pytest.raises(LearningReasoningError):execute('problem_solving',p)
 for value in [None,[[]],[{**trace()[0],'source':''}],trace()*5]:
  with pytest.raises(LearningReasoningError):run(worked_trace=value)

@pytest.mark.parametrize('kind,operand,goal',[('subtract','2','-1'),('divide','2','1/2'),('multiply','3','3'),('add','-1','0')])
def test_all_operation_semantics(kind,operand,goal):
 t={**task(),'goal':goal,'operations':[{'id':'op','kind':kind,'operand':operand,'source':'fixture'}]}
 r=run('problem_solving',arithmetic_task=t);assert r['final_value']==goal and r['solution_depth']==1

def test_mounted_auth_and_declared_break(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method in ['worked_examples','problem_solving']:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':payload()}).status_code==401
  r=c.post(path,headers=h,json={'payload':payload()});assert r.status_code==200 and r.json()['tenant_id']=='a'
  assert c.post(path,headers=h,json={'payload':{'objective':'x','source':SRC}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**payload(),'resource_refs':[{'tenant_id':'b'}]}}).status_code==403
