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
 r=run('problem_solving');assert r['status']=='solved' and [(s['pre'],s['operation_id'],s['post'])for s in r['solution']]==[('1','add','3'),('3','mul','6')] and r['final_value']=='6' and r['solution_depth']==2
 t={'initial':'1/3','goal':'1','operations':[{'id':'add','kind':'add','operand':'1/3','source':'fixture:add'}],'max_depth':2,'state_bound':'10'}
 r=run('problem_solving',arithmetic_task=t);assert r['solution_depth']==2 and r['final_value']=='1'
 assert r['solution'][0]['post']=='2/3'

def test_solver_no_solution_and_explicit_bounds():
 r=run('problem_solving',arithmetic_task={**task(),'max_depth':1});assert r['status']=='no_solution_within_bounds' and r['solution'] is None
 with pytest.raises(LearningReasoningError):run('problem_solving',arithmetic_task={**task(),'state_bound':'2'})
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

def test_shortest_deterministic_operation_ties_and_allsteps_conjunction():
 t={**task(),'goal':'3','operations':[{'id':'z','kind':'add','operand':'2','source':'fixture:z'},{'id':'a','kind':'add','operand':'2','source':'fixture:a'}]}
 r=run('problem_solving',arithmetic_task=t);assert r['solution_depth']==1 and r['solution'][0]['operation_id']=='a' and r['solution'][0]['operation_source']=='fixture:a'
 rows=trace()+[{'pre':'6','operation_id':'unknown','post':'6','rationale':'apply:add','source':'fixture:invalid'}]
 r=run(worked_trace=rows);assert r['goal_reached'] is True and r['trace_valid'] is False and r['completion_problem'] is None

def test_exact_depth_operations_rational_limits():
 for depth in [0,8]:
  t={**task(),'max_depth':depth,'goal':'1'};assert run('problem_solving',arithmetic_task=t)['status']=='solved'
 for depth in [-1,9,1.5]:
  with pytest.raises(LearningReasoningError):run('problem_solving',arithmetic_task={**task(),'max_depth':depth})
 rows=[{'id':str(i),'kind':'add','operand':'0','source':'fixture'}for i in range(8)]
 assert run('problem_solving',arithmetic_task={**task(),'operations':rows})['status']=='no_solution_within_bounds'
 with pytest.raises(LearningReasoningError):run('problem_solving',arithmetic_task={**task(),'operations':rows+[{'id':'8','kind':'add','operand':'0','source':'fixture'}]})
 for value in [1.5,'1'*65,str(10**12+1),'1/'+str(10**12+1)]:
  with pytest.raises(LearningReasoningError):run('problem_solving',arithmetic_task={**task(),'initial':value})

def test_invalid_step_never_advances_current_register():
 rows=trace();rows[0]['post']='4';r=run(worked_trace=rows)
 assert r['final_value']=='1' and r['step_reports'][1]['expected_post']=='2' and r['step_reports'][1]['pre_matches'] is False

@pytest.mark.parametrize('value',['1e99999999999999999999','1e-999999','1_0',' 3 '])
def test_forbidden_string_grammar_rejects_before_fraction_allocation(value):
 import time
 start=time.monotonic()
 with pytest.raises(LearningReasoningError):run('problem_solving',arithmetic_task={**task(),'initial':value})
 assert time.monotonic()-start<1

def test_rational_length_components_and_zero_initial_bounds():
 assert run('problem_solving',arithmetic_task={**task(),'initial':'0'*63+'1'})['status']=='solved'
 for value in ['0'*64+'1','1000000000001']:
  p=payload();p['arithmetic_task']['operations'][0]['operand']=value
  with pytest.raises(LearningReasoningError):execute('problem_solving',p)
 for t in [{**task(),'initial':'0','goal':'0','state_bound':'0'},{**task(),'initial':'101','goal':'1'}]:
  with pytest.raises(LearningReasoningError):run('problem_solving',arithmetic_task=t)

def test_allowed_state_exact_bound_components_and_dedup_metrics():
 from app.modules.m20_general_cognitive_worker.arithmetic_work import allowed,task as parsed
 from fractions import Fraction
 t=parsed(task());assert allowed(Fraction(100),t) is True and allowed(Fraction(1000001,10000),t) is False
 # Repeated divide reaches a denominator above the component cap.
 t={**task(),'initial':'1','goal':'1/1000000000000','operations':[{'id':'d','kind':'divide','operand':'1000000','source':'fixture'}],'max_depth':3}
 r=run('problem_solving',arithmetic_task=t);assert r['states_seen']==3 and r['solution_depth']==2
 t['goal']='0';r=run('problem_solving',arithmetic_task=t);assert r['states_seen']==3 and r['states_expanded']==3 and r['status']=='no_solution_within_bounds'
 t={**task(),'initial':'1','goal':'2','operations':[{'id':'a','kind':'add','operand':'0','source':'fixture'},{'id':'b','kind':'multiply','operand':'1','source':'fixture'}]}
 r=run('problem_solving',arithmetic_task=t);assert r['states_seen']==1 and r['states_expanded']==1

def test_search_budget_path_and_full_solver_step():
 t={'initial':'0','goal':'-1','operations':[{'id':str(i),'kind':'add','operand':str(10**i),'source':'fixture'}for i in range(6)]+[{'id':'6','kind':'multiply','operand':'2','source':'fixture'},{'id':'7','kind':'multiply','operand':'3','source':'fixture'}],'max_depth':8,'state_bound':'1000000'}
 r=run('problem_solving',arithmetic_task=t);assert r['status']=='search_budget_exhausted' and r['states_seen']==10000 and r['solution'] is None
 r=run('problem_solving');assert r['solution'][0]=={'pre':'1','operation_id':'add','post':'3','rationale':'apply:add','operation_source':'fixture:add'}

def test_trace_depth_post_bound_status_and_unknown_expected():
 t={**task(),'max_depth':2}
 assert run(arithmetic_task=t,worked_trace=trace())['trace_valid'] is True
 with pytest.raises(LearningReasoningError):run(arithmetic_task=t,worked_trace=trace()+[trace()[0]])
 t={**task(),'initial':'1','goal':'1','state_bound':'1','operations':[{'id':'m','kind':'multiply','operand':'2','source':'fixture'}]}
 r=run(arithmetic_task=t,worked_trace=[{'pre':'1','operation_id':'m','post':'2','rationale':'apply:multiply','source':'fixture'}]);assert r['step_reports'][0]['accepted'] is False and r['step_reports'][0]['post_matches'] is False
 assert run(worked_trace=trace()[:1])['status']=='invalid_worked_trace'
 rows=trace();rows[0]['operation_id']='unknown';assert run(worked_trace=rows)['step_reports'][0]['expected_post'] is None

def test_dos_strings_refuse_all_numeric_positions_and_mounted_routes(monkeypatch,oidc_auth_headers):
 import time
 bad='1e99999999999999999999'
 for key in ['initial','goal','state_bound']:
  p=payload();p['arithmetic_task'][key]=bad
  start=time.monotonic()
  with pytest.raises(LearningReasoningError):execute('worked_examples',p)
  assert time.monotonic()-start<1
 p=payload();p['arithmetic_task']['operations'][0]['operand']=bad
 with pytest.raises(LearningReasoningError):execute('worked_examples',p)
 for key in ['pre','post']:
  rows=trace();rows[0][key]=bad
  with pytest.raises(LearningReasoningError):run(worked_trace=rows)
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method in ['worked_examples','problem_solving']:
  p=payload();p['arithmetic_task']['initial']=bad;start=time.monotonic()
  assert c.post('/api/v1/api/modules/20/learning-reasoning-810-859/'+method,headers=h,json={'payload':p}).status_code==422
  assert time.monotonic()-start<2

def test_signed_zero_padded_string_length_exact_boundary():
 assert run('problem_solving',arithmetic_task={**task(),'initial':'+'+'0'*62+'1'})['status']=='solved'
 with pytest.raises(LearningReasoningError):run('problem_solving',arithmetic_task={**task(),'initial':'+'+'0'*63+'1'})
