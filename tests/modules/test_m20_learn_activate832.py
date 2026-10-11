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

def test_known_target_fact_zero_premise_and_full_boundaries():
 p=transfer();p['transfer_rule']['if']=[];p['feature_correspondences']=p['feature_correspondences'][-1:];p['target_task']['facts']=[]
 assert run('transfer',p)['expected_target_entailment'] is True
 p=transfer();p['target_task']['facts']=['target_done'];assert run('transfer',p)['expected_target_entailment'] is True
 assert run('transfer',p)['boundary']=='One explicit supplied positive Horn rule mapped bijectively to a symbolic target task; independent response is caller-declared, exact boolean entailment scoring only, not general cross-domain learning or verified truth.'
 assert run('prior_knowledge_activation',activation())['boundary']=='Exact supplied concept-key comparisons of prior responses, separate from new evidence; mismatches are misconception candidates, not grades or verified beliefs/understanding.'

def test_concept_and_record_caps():
 p=activation();p['activation_concepts']=[{**p['activation_concepts'][0],'concept_id':str(i)}for i in range(64)];p['prior_responses']=[];p['new_evidence']=[];assert len(run('prior_knowledge_activation',p)['concept_reports'])==64
 p['activation_concepts'].append({**p['activation_concepts'][0],'concept_id':'64'})
 with pytest.raises(LearningReasoningError):run('prior_knowledge_activation',p)
 p=activation();p['prior_responses']=[{**p['prior_responses'][0],'response_id':str(i)}for i in range(1000)];assert len(run('prior_knowledge_activation',p)['prior_reports'])==1000
 p['prior_responses'].append({**p['prior_responses'][0],'response_id':'1000'})
 with pytest.raises(LearningReasoningError):run('prior_knowledge_activation',p)

def test_rule_task_shapes_text_and_no_negation():
 for field in ['transfer_rule','target_task','target_response']:
  p=transfer();p[field]=[]
  with pytest.raises(LearningReasoningError):run('transfer',p)
 for field,key in [('transfer_rule','rule_id'),('transfer_rule','source'),('transfer_rule','then'),('target_task','task_id'),('target_task','source'),('target_task','query')]:
  p=transfer();p[field][key]=''
  with pytest.raises(LearningReasoningError):run('transfer',p)
 p=transfer();p['transfer_rule']['unless']=['x']
 with pytest.raises(LearningReasoningError):run('transfer',p)

def test_optional_activation_records_and_empty_concepts():
 from app.modules.m20_general_cognitive_worker.activation_transfer import activate
 p=activation();p.pop('prior_responses');p.pop('new_evidence');r=activate(p)
 assert r['prior_reports']==r['new_evidence']==[] and r['concept_reports'][0]['unactivated'] is True
 p['activation_concepts']=[]
 with pytest.raises(ValueError,match='activation_concepts requires bounded object list'):activate(p)

def test_activation_text_ids_values_and_unknown_new_core():
 from app.modules.m20_general_cognitive_worker.activation_transfer import activate
 for field,key in [('activation_concepts','concept_id'),('prior_responses','response_id'),('new_evidence','evidence_id'),('prior_responses','concept_id'),('new_evidence','concept_id'),('prior_responses','value'),('new_evidence','value')]:
  p=activation();p[field][0][key]=[]
  with pytest.raises(ValueError,match=key+' requires bounded nonempty string'):activate(p)
 p=activation();p['new_evidence'][0]['concept_id']='unknown'
 with pytest.raises(ValueError,match='unique records and known concepts required'):activate(p)

def test_activation_reversed_output_and_fixed_seed_values():
 import os,sys,subprocess
 from app.modules.m20_general_cognitive_worker.activation_transfer import activate
 p=activation();p['activation_concepts']=[{'concept_id':key,'accepted_values':['zebra','middle','alpha'],'source':'fixture'}for key in ['z','a']]
 p['prior_responses']=[{'response_id':key,'concept_id':key,'value':'alpha','source':'fixture'}for key in ['z','a']]
 p['new_evidence']=[{'evidence_id':key,'concept_id':key,'value':'alpha','source':'fixture'}for key in ['z','a']]
 r=activate(p)
 assert [x['concept_id']for x in r['concepts']]==[x['concept_id']for x in r['concept_reports']]==['a','z']
 assert [x['response_id']for x in r['prior_reports']]==[x['evidence_id']for x in r['new_evidence']]==['a','z']
 code="from app.modules.m20_general_cognitive_worker.activation_transfer import activate; p="+repr(p)+"; assert activate(p)['concepts'][0]['accepted_values']==['alpha','middle','zebra']"
 result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'PYTHONHASHSEED':'6'},capture_output=True,text=True);assert result.returncode==0,result.stderr

def test_transfer_premise_fact_shapes_and_cap_messages():
 from app.modules.m20_general_cognitive_worker.activation_transfer import transfer as core
 for field,key,label in [('transfer_rule','if','rule premises'),('target_task','facts','target facts')]:
  for value in ['s',[5],['s','s'],[str(i)for i in range(65)]]:
   p=transfer();p[field][key]=value
   with pytest.raises(ValueError,match=label+' requires'):core(p)
 p=transfer();p['target_task']['facts']=[str(i)for i in range(64)];assert core(p)['expected_target_entailment'] is False

def test_effective_63_premises_and_correspondence_cap():
 from app.modules.m20_general_cognitive_worker.activation_transfer import transfer as core
 for n in [63,64]:
  p=transfer();p['transfer_rule']['if']=[str(i)for i in range(n)];p['feature_correspondences']=[{'source_feature':str(i),'target_feature':'t'+str(i)}for i in range(n)]+[{'source_feature':'source_done','target_feature':'target_done'}];p['target_task']['facts']=[]
  if n==63:assert core(p)['expected_target_entailment'] is False
  else:
   with pytest.raises(ValueError,match='feature_correspondences requires bounded object list'):core(p)
 # Nominal64 premise grammar allowed when conclusion itself is a premise:64atoms.
 p=transfer();p['transfer_rule']['if']=[str(i)for i in range(63)]+['source_done'];p['feature_correspondences']=[{'source_feature':str(i),'target_feature':'t'+str(i)}for i in range(63)]+[{'source_feature':'source_done','target_feature':'target_done'}]
 assert core(p)['expected_target_entailment'] is False

def test_correspondence_nontext_duplicate_source_extra_and_exact_error():
 from app.modules.m20_general_cognitive_worker.activation_transfer import transfer as core
 p=transfer();p['feature_correspondences'][0]['target_feature']=[]
 with pytest.raises(ValueError,match='target_feature requires bounded nonempty string'):core(p)
 p=transfer();p['feature_correspondences'].append({'source_feature':'source_ready','target_feature':'different'})
 with pytest.raises(ValueError,match='one-to-one unique correspondences required'):core(p)
 p=transfer();p['feature_correspondences'].append({'source_feature':'extra','target_feature':'extra'})
 with pytest.raises(ValueError,match='correspondences must cover exactly rule atoms'):core(p)
 p=transfer();p['feature_correspondences'].pop()
 with pytest.raises(ValueError,match='correspondences must cover exactly rule atoms'):core(p)

def test_transfer_sort_fixed_seed_and_falsey_unless_ignored():
 import os,sys,subprocess
 from app.modules.m20_general_cognitive_worker.activation_transfer import transfer as core
 p=transfer();p['transfer_rule']['if']=['zebra','middle','alpha'];p['feature_correspondences']=[{'source_feature':key,'target_feature':key}for key in ['zebra','middle','alpha']]+[{'source_feature':'source_done','target_feature':'target_done'}];p['target_task']['facts']=['zebra','middle','alpha']
 r=core(p);assert [x['source_feature']for x in r['feature_correspondences']]==['alpha','middle','source_done','zebra']
 code="from app.modules.m20_general_cognitive_worker.activation_transfer import transfer; p="+repr(p)+"; r=transfer(p); assert r['adapted_rule']['if']==['alpha','middle','zebra']; assert r['target_task']['facts']==['alpha','middle','zebra']"
 result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'PYTHONHASHSEED':'6'},capture_output=True,text=True);assert result.returncode==0,result.stderr
 for value in [[], '',0,False]:
  p=transfer();p['transfer_rule']['unless']=value;assert core(p)['correct'] is True
