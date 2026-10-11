"""Supplied prior activation and symbolic transfer performance evidence."""
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Lesson','url':'https://example.org/lesson'}
def activation():return {'source':SRC,'objective':'Activate symbolic concepts','activation_concepts':[{'concept_id':'c','accepted_values':['correct'],'source':'fixture:concept'}],'prior_responses':[{'response_id':'r','concept_id':'c','value':'wrong','source':'fixture:prior'}],'new_evidence':[{'evidence_id':'e','concept_id':'c','value':'correct','source':'fixture:new'}]}
def transfer():return {'source':SRC,'source_case':{'features':['source']},'target_case':{'features':['target']},'transfer_rule':{'rule_id':'r','if':['source_ready','source_safe'],'then':'source_done','source':'fixture:rule'},'target_task':{'task_id':'t','facts':['target_ready','target_safe'],'query':'target_done','source':'fixture:task'},'feature_correspondences':[{'source_feature':'source_ready','target_feature':'target_ready'},{'source_feature':'source_safe','target_feature':'target_safe'},{'source_feature':'source_done','target_feature':'target_done'}],'target_response':{'response_id':'resp','entailed':True,'independent':True,'source':'fixture:response'}}
def run(method,p):return execute(method,p)['result']['activation'if method=='prior_knowledge_activation'else 'transfer_evidence']

def test_prior_activation_separates_misconception_and_new_evidence_not_grading():
 r=run('prior_knowledge_activation',activation());assert r['status']=='activated'
 assert r['prior_reports']==[{'response_id':'r','concept_id':'c','value':'wrong','source':'fixture:prior','matches_supplied_key':False,'misconception_candidate':True}]
 assert r['new_evidence']==activation()['new_evidence'] and r['prior_reports'][0]['value']=='wrong'
 assert r['concept_reports']==[{'concept_id':'c','prior_response_ids':['r'],'new_evidence_ids':['e'],'unactivated':False}]
 assert r['grade'] is None and r['source_truth_verified'] is False and r['learner_understanding'] is None

def test_unknown_prior_no_response_and_key_match():
 p=activation();p['prior_responses']=[];r=run('prior_knowledge_activation',p);assert r['concept_reports'][0]['unactivated'] is True and r['prior_reports']==[]
 p=activation();p['prior_responses'][0]['value']='correct';assert run('prior_knowledge_activation',p)['prior_reports'][0]['misconception_candidate'] is False
 p=activation();p['prior_responses'][0]['concept_id']='unknown'
 with pytest.raises(LearningReasoningError):run('prior_knowledge_activation',p)

def test_transfer_actual_mapping_target_check_and_response_evidence():
 r=run('transfer',transfer());assert r['status']=='scored_transfer_evidence' and r['correct'] is True and r['transfer_evidence_recorded'] is True
 assert r['adapted_rule']=={'rule_id':'r','if':['target_ready','target_safe'],'then':'target_done','source':'fixture:rule'}
 assert r['expected_target_entailment'] is True and r['target_response']==transfer()['target_response']
 assert r['source_truth_verified'] is False and r['general_transfer'] is None

def test_target_changed_outcome_wrong_response_and_missing_response():
 p=transfer();p['target_task']['facts']=['target_ready'];r=run('transfer',p);assert r['expected_target_entailment'] is False and r['correct'] is False and r['transfer_evidence_recorded'] is True
 p['target_response']['entailed']=False;assert run('transfer',p)['correct'] is True
 p=transfer();p['target_response']=None;r=run('transfer',p);assert r['status']=='awaiting_independent_target_response' and r['correct'] is None and r['transfer_evidence_recorded'] is False
 p=transfer();p['target_response']['independent']=False
 with pytest.raises(LearningReasoningError):run('transfer',p)

def test_invalid_feature_maps_query_and_response_types():
 for value in [[],transfer()['feature_correspondences'][:2],transfer()['feature_correspondences']+transfer()['feature_correspondences'][:1]]:
  p=transfer();p['feature_correspondences']=value
  with pytest.raises(LearningReasoningError):run('transfer',p)
 p=transfer();p['feature_correspondences'][1]['target_feature']='target_ready'
 with pytest.raises(LearningReasoningError):run('transfer',p)
 p=transfer();p['target_task']['query']='unrelated'
 with pytest.raises(LearningReasoningError):run('transfer',p)
 for key,value in [('entailed',1),('independent',1),('source','')]:
  p=transfer();p['target_response'][key]=value
  with pytest.raises(LearningReasoningError):run('transfer',p)

def test_activation_shapes_source_duplicates():
 for field in ['activation_concepts','prior_responses','new_evidence']:
  p=activation();p[field][0]['source']=''
  with pytest.raises(LearningReasoningError):run('prior_knowledge_activation',p)
  p=activation();p[field]*=2
  with pytest.raises(LearningReasoningError):run('prior_knowledge_activation',p)
 p=activation();p['activation_concepts'][0]['accepted_values']=[]
 with pytest.raises(LearningReasoningError):run('prior_knowledge_activation',p)

def test_mounted_auth_refusal_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method,p in [('prior_knowledge_activation',activation()),('transfer',transfer())]:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':p}).status_code==401
  assert c.post(path,headers=h,json={'payload':p}).status_code==200
  assert c.post(path,headers=h,json={'payload':{**p,'resource_refs':[{'tenant_id':'b'}]}}).status_code==403
  assert c.post(path,headers=h,json={'payload':{'source':SRC,'objective':'x','source_case':{},'target_case':{}}}).status_code==422
