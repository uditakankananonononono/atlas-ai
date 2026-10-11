"""Descriptive strategy scores and explicit learner-controlled evidence cycle."""
import pytest
from copy import deepcopy
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Synthetic learning','url':'https://example.org/learning'}
def attempts():return [{'id':'a','strategy':'recall','evidence_id':'e1','predicted_success':.8,'succeeded':True},{'id':'b','strategy':'recall','evidence_id':'e2','predicted_success':.4,'succeeded':False},{'id':'c','strategy':'example','evidence_id':'e3','predicted_success':.9,'succeeded':False}]
def base():return {'objective':'Improve supplied task results','source':SRC,'attempts':attempts()}
def cycle():return {**base(),'learning_goal':{'goal_id':'g','metric':'task_success_rate','target':.8,'source':'fixture:goal'},'strategy_catalog':[{'strategy':'recall','next_action':'Try closed-book task','source':'fixture:recall'},{'strategy':'example','next_action':'Study checked example','source':'fixture:example'}],'reflection':{'evidence_ids':['e1','e2','e3'],'observation':'Example attempt failed','source':'fixture:reflection'},'learner_choice':{'strategy':'example','reason':'I want another example','source':'fixture:choice'}}
def run(method='metacognition',p=None):return execute(method,base()if p is None else p)['result']

def test_823_hand_computed_scores_and_outcome_flip():
 r=run()['calibration'];assert r['brier_loss']==pytest.approx((.04+.16+.81)/3) and r['overconfidence']==pytest.approx((-.2+.4+.9)/3)
 assert r['strategies']==[{'strategy':'example','n':1,'brier_loss':pytest.approx(.81),'overconfidence':pytest.approx(.9),'observed_success_rate':0,'evidence_ids':['e3']},{'strategy':'recall','n':2,'brier_loss':pytest.approx(.1),'overconfidence':pytest.approx(.1),'observed_success_rate':.5,'evidence_ids':['e1','e2']}]
 assert r['best_observed_strategies']==['recall'] and r['recommended_strategy']=='recall'
 p=base();p['attempts'][2]['succeeded']=True;assert run(p=p)['calibration']['recommended_strategy']=='example'
 assert 'Descriptive calibration' in r['boundary'] and run()['scope']=='Measured strategy calibration, not full metacognition'

def test_ties_no_winner_duplicate_evidence_rejected():
 p=base();p['attempts']=[{'id':'a','strategy':'b','evidence_id':'a','predicted_success':.5,'succeeded':True},{'id':'b','strategy':'a','evidence_id':'b','predicted_success':.5,'succeeded':False}]
 r=run(p=p)['calibration'];assert r['best_observed_strategies']==['a','b'] and r['recommended_strategy'] is None
 p['attempts'][1]['evidence_id']='a'
 with pytest.raises(LearningReasoningError):run(p=p)

@pytest.mark.parametrize('change',[{'id':''},{'strategy':''},{'evidence_id':''},{'predicted_success':True},{'predicted_success':float('nan')},{'predicted_success':1.01},{'succeeded':1}])
def test_invalid_calibration_evidence(change):
 p=base();p['attempts'][0].update(change);before=deepcopy(p)
 with pytest.raises(LearningReasoningError):run(p=p)
 assert p==before

def test_824_recommendation_preserves_distinct_learner_choice():
 r=run('self_regulated_learning',cycle())['regulated_cycle']
 assert r['status']=='recommendation_ready' and r['recommended_strategy']=='recall' and r['recommended_action']=='Try closed-book task'
 assert r['learner_choice']=={'strategy':'example','reason':'I want another example','source':'fixture:choice'} and r['choice_matches_recommendation'] is False
 assert r['selected_next_action']=='Study checked example' and r['learner_approval_required'] is True and r['action_executed'] is False
 assert r['reflection_evidence_ids']==['e1','e2','e3'] and r['observed_goal_metric']==pytest.approx(1/3) and r['goal_met_on_observed_attempts'] is False
 assert r['source_truth_verified'] is False and r['learning_improvement'] is None

def test_cycle_missing_evidence_reflection_or_choice_abstains():
 p=cycle();p['attempts']=[];r=run('self_regulated_learning',p)['regulated_cycle'];assert r['status']=='abstained' and r['reason']=='missing_attempt_evidence' and r['recommended_strategy'] is None
 p=cycle();p['reflection']=None;r=run('self_regulated_learning',p)['regulated_cycle'];assert r['reason']=='missing_reflection' and r['selected_next_action'] is None
 p=cycle();p['learner_choice']=None;r=run('self_regulated_learning',p)['regulated_cycle'];assert r['status']=='awaiting_learner_choice' and r['recommended_strategy']=='recall' and r['selected_next_action'] is None

def test_unknown_strategy_and_reflection_evidence_reject():
 for change in ['attempt','choice','reflection']:
  p=cycle()
  if change=='attempt':p['attempts'][0]['strategy']='unknown'
  elif change=='choice':p['learner_choice']['strategy']='unknown'
  else:p['reflection']['evidence_ids']=['unknown']
  with pytest.raises(LearningReasoningError):run('self_regulated_learning',p)

def test_mounted_calibration_cycle_auth_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method,payload in [('metacognition',base()),('self_regulated_learning',cycle())]:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':payload}).status_code==401
  r=c.post(path,headers=h,json={'payload':payload});assert r.status_code==200 and r.json()['tenant_id']=='a'
  assert c.post(path,headers=h,json={'payload':{**payload,'resource_refs':[{'tenant_id':'b'}]}}).status_code==403
 assert c.post('/api/v1/api/modules/20/learning-reasoning-810-859/self_regulated_learning',headers=h,json={'payload':{'objective':'x','source':SRC}}).status_code==422

def test_cycle_ties_no_choice_and_goal_exact_threshold():
 p=cycle();p['attempts']=[{'id':'a','strategy':'recall','evidence_id':'e1','predicted_success':.5,'succeeded':True},{'id':'b','strategy':'example','evidence_id':'e2','predicted_success':.5,'succeeded':False}];p['reflection']['evidence_ids']=['e2','e1'];p['learning_goal']['target']=.5
 r=run('self_regulated_learning',p)['regulated_cycle'];assert r['recommended_strategy'] is None and r['recommended_action'] is None and r['choice_matches_recommendation'] is None
 assert r['selected_next_action']=='Study checked example' and r['goal_met_on_observed_attempts'] is True and r['reflection_evidence_ids']==['e1','e2']
 p['learner_choice']=None;assert run('self_regulated_learning',p)['regulated_cycle']['status']=='awaiting_learner_choice'

@pytest.mark.parametrize('change',[{'learning_goal':None},{'learning_goal':{'goal_id':'g','source':'fixture','metric':'score','target':.5}},{'learning_goal':{'goal_id':'g','source':'fixture','metric':'task_success_rate','target':True}},{'strategy_catalog':[]},{'strategy_catalog':[[]]},{'reflection':{'source':'fixture','observation':'x','evidence_ids':['e1']}},{'reflection':{'source':'fixture','observation':'x','evidence_ids':['e1','e1','e2','e3']}},{'learner_choice':{'strategy':'recall','reason':'','source':'fixture'}}])
def test_cycle_shapes_bounds_refs_invalid(change):
 p={**cycle(),**change};before=deepcopy(p)
 with pytest.raises(LearningReasoningError):run('self_regulated_learning',p)
 assert p==before

def test_catalog_and_attempt_caps():
 p=cycle();p['strategy_catalog']=[{'strategy':str(i),'next_action':'action','source':'fixture'}for i in range(32)];p['attempts']=[]
 assert run('self_regulated_learning',p)['regulated_cycle']['reason']=='missing_attempt_evidence'
 p['strategy_catalog'].append({'strategy':'32','next_action':'action','source':'fixture'})
 with pytest.raises(LearningReasoningError):run('self_regulated_learning',p)
 p=cycle();p['strategy_catalog']*=2
 with pytest.raises(LearningReasoningError):run('self_regulated_learning',p)
 p=cycle();p['attempts']=[{'id':str(i),'strategy':'recall','evidence_id':str(i),'predicted_success':.5,'succeeded':False}for i in range(1000)];p['reflection']['evidence_ids']=[str(i)for i in range(1000)]
 assert run('self_regulated_learning',p)['regulated_cycle']['status']=='recommendation_ready'
 p['attempts'].append({'id':'1000','strategy':'recall','evidence_id':'1000','predicted_success':.5,'succeeded':False})
 with pytest.raises(LearningReasoningError):run('self_regulated_learning',p)

def test_unknown_attempt_strategy_core_valueerror_not_keyerror():
 from app.modules.m20_general_cognitive_worker.regulated_learning import cycle as core_cycle
 p=cycle();p['attempts'][0]['strategy']='unknown'
 with pytest.raises(ValueError,match='unknown attempt strategy'):core_cycle(p)

def test_goal_echo_fields_and_inclusive_targets():
 from app.modules.m20_general_cognitive_worker.regulated_learning import cycle as core
 p=cycle();r=core(p);assert r['goal']=={'goal_id':'g','metric':'task_success_rate','source':'fixture:goal','target':.8}
 for target in [0,1]:
  p=cycle();p['learning_goal']['target']=target;assert core(p)['goal']['target']==target
 p=cycle();p['learning_goal']['target']=1.0001
 with pytest.raises(ValueError,match=r'task_success_rate metric and target\[0,1\] required'):core(p)
 for field in ['goal_id','metric','source']:
  p=cycle();p['learning_goal'][field]=[]
  with pytest.raises(ValueError,match=field+' requires bounded nonempty string'):core(p)

def test_catalog_empty_unmasked_text_and_source_echo():
 from app.modules.m20_general_cognitive_worker.regulated_learning import cycle as core
 p=cycle();p['strategy_catalog']=[]
 with pytest.raises(ValueError,match='strategy_catalog requires1..32 entries'):core(p)
 for field in ['strategy','next_action','source']:
  p=cycle();p['strategy_catalog'][0][field]=[]
  with pytest.raises(ValueError,match=field+' requires bounded nonempty string'):core(p)
 # Source is intentionally not echoed in cycle output, but must be required.
 p=cycle();p['strategy_catalog'][0].pop('source')
 with pytest.raises(ValueError,match='source requires bounded nonempty string'):core(p)

def test_attempts_list_guard_and_1001_refusal_before_calibration():
 from app.modules.m20_general_cognitive_worker.regulated_learning import cycle as core
 for value in [None,{},'x']:
  p=cycle();p['attempts']=value
  with pytest.raises(ValueError,match='attempts requires0..1000 records'):core(p)
 p=cycle();p['attempts']=[{'id':str(i),'strategy':'recall','evidence_id':str(i),'predicted_success':.5,'succeeded':False}for i in range(1001)]
 p['reflection']=None
 with pytest.raises(ValueError,match='attempts requires0..1000 records'):core(p)

def test_reflection_shape_text_ids_guard_and_error_order():
 from app.modules.m20_general_cognitive_worker.regulated_learning import cycle as core
 p=cycle();p['reflection']=[]
 with pytest.raises(ValueError,match='reflection object required'):core(p)
 for field in ['observation','source']:
  p=cycle();p['reflection'][field]=[]
  with pytest.raises(ValueError,match='reflection '+field+' requires bounded nonempty string'):core(p)
 for value in ['e1',[],list(range(1001))]:
  p=cycle();p['reflection']['evidence_ids']=value
  with pytest.raises(ValueError,match='reflection evidence IDs required'):core(p)
 p=cycle();p['reflection']['evidence_ids']=[[]]
 with pytest.raises(ValueError,match='reflection evidence ID requires bounded nonempty string'):core(p)

def test_full_cycle_calibration_reflection_tie_outputs_and_choice_errors():
 from app.modules.m20_general_cognitive_worker.regulated_learning import cycle as core
 p=cycle();r=core(p);assert r['calibration']==run()['calibration'] and r['reflection']=={'observation':'Example attempt failed','source':'fixture:reflection'} and r['reason'] is None
 p['learner_choice']=None;r=core(p);assert r['reason']=='no_learner_choice' and r['status']=='awaiting_learner_choice'
 p=cycle();p['learner_choice']=[]
 with pytest.raises(ValueError,match='learner_choice object required'):core(p)
 p=cycle();p['learner_choice']['strategy']='unknown'
 with pytest.raises(ValueError,match='unknown learner choice strategy'):core(p)
 p=cycle();p['attempts']=[{'id':'a','strategy':'recall','evidence_id':'e1','predicted_success':.5,'succeeded':True},{'id':'b','strategy':'example','evidence_id':'e2','predicted_success':.5,'succeeded':False}];p['reflection']['evidence_ids']=['e1','e2']
 r=core(p);assert r['best_observed_strategies']==['example','recall'] and r['calibration']['best_observed_strategies']==['example','recall']

def test_duplicate_attempt_id_distinct_evidence_refused():
 p=base();p['attempts'][1]['id']=p['attempts'][0]['id']
 with pytest.raises(LearningReasoningError,match='attempt ids and evidence ids must be unique'):run(p=p)

@pytest.mark.parametrize('ids',[{'e1':1,'e2':1,'e3':1},'e1'])
def test_reflection_ids_dictionary_and_string_refuse_before_iteration(ids):
 from app.modules.m20_general_cognitive_worker.regulated_learning import cycle as core
 p=cycle();p['reflection']['evidence_ids']=ids
 with pytest.raises(ValueError,match='^reflection evidence IDs required$'):core(p)
