"""Bijective symbolic analogy constraints and explicit checked case reuse."""
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Cases','url':'https://example.org/cases'}
def analogy():return {'source':SRC,'analogy_source_features':{'a':'red','b':'round'},'analogy_target_features':{'x':'red','y':'round'},'analogy_correspondences':[{'source_feature':'a','target_feature':'x'},{'source_feature':'b','target_feature':'y'}],'candidate_inferences':[{'inference_id':'i','source_feature':'a','value':'red','source':'fixture:i'}],'target_constraints':[{'feature_id':'x','allowed_values':['red'],'source':'fixture:constraint'}]}
def case():return {'source':SRC,'case_bank':[{'case_id':'z','features':{'color':'red','shape':'round'},'proposed_action':'action-z','source':'fixture:z'},{'case_id':'a','features':{'color':'red','shape':'square'},'proposed_action':'action-a','source':'fixture:a'}],'case_target':{'features':{'color':'red','shape':'round'},'source':'fixture:target'},'case_feature_weights':{'color':1,'shape':2},'case_target_checks':None}
def run(method,p):return execute(method,p)['result']['analogy_check'if method=='analogical_reasoning'else 'case_reuse']

def test_analogy_mapping_and_constraint_checked_inference():
 r=run('analogical_reasoning',analogy());assert r['status']=='mapped' and r['mapping_complete'] is True
 assert r['unmapped_source_features']==r['unmapped_target_features']==[] and r['many_to_one_targets']==[]
 assert r['inference_reports']==[{'inference_id':'i','source_feature':'a','target_feature':'x','value':'red','source_value_matches':True,'target_constraints_present':True,'constraint_sources':['fixture:constraint'],'supported':True,'source':'fixture:i'}]
 assert r['source_truth_verified'] is False and r['general_analogy'] is None

def test_unmapped_many_to_one_and_constraint_failures_preserved():
 p=analogy();p['analogy_correspondences']=p['analogy_correspondences'][:1];r=run('analogical_reasoning',p);assert r['mapping_complete'] is False and r['unmapped_source_features']==['b'] and r['unmapped_target_features']==['y']
 p=analogy();p['analogy_correspondences'][1]['target_feature']='x';r=run('analogical_reasoning',p);assert r['many_to_one_targets']==['x'] and r['inference_reports'][0]['supported'] is False
 p=analogy();p['target_constraints'][0]['allowed_values']=['blue'];assert run('analogical_reasoning',p)['inference_reports'][0]['supported'] is False
 p=analogy();p['target_constraints']=[];assert run('analogical_reasoning',p)['inference_reports'][0]['supported'] is False

def test_case_rank_and_checks_before_adaptation():
 p=case();r=run('case_based_reasoning',p);assert [c['case_id']for c in r['ranked_cases']]==['z','a'] and [c['similarity']for c in r['ranked_cases']]==[1,pytest.approx(1/3)]
 assert r['status']=='awaiting_target_checks' and r['adapted_action'] is None
 p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':'check','passed':True,'source':'fixture:check'}]};r=run('case_based_reasoning',p);assert r['status']=='checked_case_reuse' and r['adapted_action']=='action-z' and r['checks_passed'] is True and r['action_executed'] is False
 p['case_target_checks']['checks'][0]['passed']=False;r=run('case_based_reasoning',p);assert r['status']=='target_checks_failed' and r['adapted_action'] is None

def test_case_ties_and_nonbest_selection_explicit():
 p=case();p['case_bank'][0]['features']['shape']='square';assert [c['case_id']for c in run('case_based_reasoning',p)['ranked_cases']]==['a','z']
 p=case();p['case_target_checks']={'selected_case_id':'a','checks':[{'check_id':'c','passed':True,'source':'fixture'}]};assert run('case_based_reasoning',p)['adapted_action']=='action-a'

def test_invalid_map_reference_duplicate_source_and_inference():
 for value in [[{'source_feature':'unknown','target_feature':'x'}],analogy()['analogy_correspondences']*2]:
  p=analogy();p['analogy_correspondences']=value
  with pytest.raises(LearningReasoningError):run('analogical_reasoning',p)
 p=analogy();p['candidate_inferences'][0]['source_feature']='unknown'
 with pytest.raises(LearningReasoningError):run('analogical_reasoning',p)

def test_case_shape_refs_boolean_sources():
 for field,value in [('case_bank',[]),('case_feature_weights',{'color':0,'shape':1}),('case_target_checks',{'selected_case_id':'unknown','checks':[{'check_id':'c','passed':True,'source':'fixture'}]})]:
  p=case();p[field]=value
  with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)
 for key,value in [('passed',1),('source',''),('check_id','')]:
  p=case();p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':'c','passed':True,'source':'fixture'}]};p['case_target_checks']['checks'][0][key]=value
  with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)

def test_mounted_auth_minimal_refusal_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method,p in [('analogical_reasoning',analogy()),('case_based_reasoning',case())]:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':p}).status_code==401
  assert c.post(path,headers=h,json={'payload':p}).status_code==200
  assert c.post(path,headers=h,json={'payload':{'source':SRC}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**p,'resource_refs':[{'tenant_id':'b'}]}}).status_code==403

def test_inference_source_mismatch_and_mixed_checks():
 p=analogy();p['candidate_inferences'][0]['value']='blue';r=run('analogical_reasoning',p);assert r['inference_reports'][0]['source_value_matches'] is False and r['inference_reports'][0]['supported'] is False
 p=case();p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':'yes','passed':True,'source':'fixture'},{'check_id':'no','passed':False,'source':'fixture'}]};r=run('case_based_reasoning',p);assert r['checks_passed'] is False and r['adapted_action'] is None

def test_exact_case_cap_weights_and_sources():
 p=case();p['case_bank']=[{**p['case_bank'][0],'case_id':str(i)}for i in range(256)];assert len(run('case_based_reasoning',p)['ranked_cases'])==256
 p['case_bank'].append({**p['case_bank'][0],'case_id':'256'})
 with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)
 for weight in [True,float('nan'),1000.1]:
  p=case();p['case_feature_weights']['color']=weight
  with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)
 for key in ['case_id','source','proposed_action']:
  p=case();p['case_bank'][0][key]=''
  with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)

def test_full_boundaries_checks_echo_and_no_autoeffect():
 p=case();p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':'c','passed':True,'source':'fixture'}]};r=run('case_based_reasoning',p)
 assert r['checks']==p['case_target_checks']['checks'] and r['source_truth_verified'] is False and r['target_source']=='fixture:target'
 assert r['boundary']=='Declared weighted exact feature case retrieval and supplied action reuse only after caller-recorded target checks. No invented adaptation, execution, semantic similarity or general case learning.'
 assert run('analogical_reasoning',analogy())['boundary']=='Explicit supplied symbolic correspondences and target allowed-value constraints only. Mapping gaps/many-to-one preserved; no semantic analogy discovery or independently verified inferences.'
