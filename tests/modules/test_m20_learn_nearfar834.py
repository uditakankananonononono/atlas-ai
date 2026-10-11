"""Declared feature rubric similarity and separate target answer performance."""
import pytest
from copy import deepcopy
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Feature rubric','url':'https://example.org/rubric'}
def payload():return {'source':SRC,'source_case':{'features':['legacy']},'target_case':{'features':['legacy']},'transfer_schema':[{'feature_id':'operation','weight':2,'source':'fixture:operation'},{'feature_id':'context','weight':1,'source':'fixture:context'}],'source_features':{'operation':'add','context':'shop'},'target_features':{'operation':'add','context':'lab'},'similarity_threshold':.6,'independent_target_task':{'task_id':'t','accepted_answers':['4'],'source':'fixture:key'},'independent_target_response':{'response_id':'r','answer':'4','independent':True,'source':'fixture:response'}}
def run(method='near_transfer',p=None):return execute(method,payload()if p is None else p)['result']['near_far_transfer']

@pytest.mark.parametrize('method',['near_transfer','far_transfer'])
def test_rubric_classification_not_forced_by_method_name(method):
 r=run(method);assert r['classification']=='near' and r['similarity']==pytest.approx(2/3) and r['threshold']==.6
 assert r['feature_reports']==[{'feature_id':'context','source_value':'shop','target_value':'lab','weight':1,'matches':False,'source':'fixture:context'},{'feature_id':'operation','source_value':'add','target_value':'add','weight':2,'matches':True,'source':'fixture:operation'}]
 assert r['requested_mode']==method and r['target_performance']=={'task_id':'t','response_id':'r','correct':True,'response_source':'fixture:response','answer_key_source':'fixture:key','independence_verified':False}
 assert r['source_truth_verified'] is False and r['general_transfer'] is None

def test_far_exact_threshold_and_wrong_response_independent():
 p=payload();p['target_features']['operation']='multiply';r=run(p=p);assert r['classification']=='far' and r['similarity']==0 and r['target_performance']['correct'] is True
 p=payload();p['similarity_threshold']=2/3;p['independent_target_response']['answer']='wrong';r=run(p=p);assert r['classification']=='near' and r['target_performance']['correct'] is False
 p['similarity_threshold']=2/3+1e-6;assert run(p=p)['classification']=='far'

def test_missing_response_abstains_performance_without_losing_similarity():
 p=payload();p['independent_target_response']=None;r=run(p=p)
 assert r['status']=='awaiting_independent_target_response' and r['classification']=='near' and r['target_performance'] is None and r['transfer_evidence_recorded'] is False
 p['independent_target_response']=payload()['independent_target_response'];p['independent_target_response']['independent']=False
 with pytest.raises(LearningReasoningError):run(p=p)

@pytest.mark.parametrize('field,value',[('transfer_schema',[]),('source_features',{}),('target_features',{'unknown':'value'}),('similarity_threshold',True),('similarity_threshold',float('nan')),('similarity_threshold',1.01),('independent_target_task',[])])
def test_shapes_schema_threshold_refusals(field,value):
 p=payload();p[field]=value;before=deepcopy(p)
 with pytest.raises(LearningReasoningError):run(p=p)
 assert p==before

def test_schema_duplicate_weight_and_text_guards():
 for key,value in [('feature_id',[]),('source',''),('weight',0),('weight',True),('weight',float('inf'))]:
  p=payload();p['transfer_schema'][0][key]=value
  with pytest.raises(LearningReasoningError):run(p=p)
 p=payload();p['transfer_schema']*=2
 with pytest.raises(LearningReasoningError):run(p=p)
 p=payload();p['source_features']['operation']=[]
 with pytest.raises(LearningReasoningError):run(p=p)

def test_answer_key_and_response_guards():
 for value in [[],[''],['4','4']]:
  p=payload();p['independent_target_task']['accepted_answers']=value
  with pytest.raises(LearningReasoningError):run(p=p)
 for key,value in [('response_id',''),('source',''),('answer',''),('independent',1)]:
  p=payload();p['independent_target_response'][key]=value
  with pytest.raises(LearningReasoningError):run(p=p)

def test_mounted_auth_refusal_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method in ['near_transfer','far_transfer']:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':payload()}).status_code==401
  r=c.post(path,headers=h,json={'payload':payload()});assert r.status_code==200 and r.json()['tenant_id']=='a'
  assert c.post(path,headers=h,json={'payload':{'source':SRC,'source_case':{'features':['x']},'target_case':{'features':['x']}}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**payload(),'resource_refs':[{'tenant_id':'b'}]}}).status_code==403

def test_exact_weight_threshold_caps_and_output_boundary():
 p=payload();p['similarity_threshold']=0;assert run(p=p)['classification']=='near'
 p['similarity_threshold']=1;assert run(p=p)['classification']=='far'
 p=payload();p['transfer_schema']=[{'feature_id':str(i),'weight':1000,'source':'fixture'}for i in range(64)];p['source_features']={str(i):'same'for i in range(64)};p['target_features']=dict(p['source_features'])
 r=run(p=p);assert r['total_weight']==64000 and r['matching_weight']==64000 and r['similarity']==1
 p['transfer_schema'].append({'feature_id':'64','weight':1,'source':'fixture'})
 with pytest.raises(LearningReasoningError):run(p=p)
 p=payload();p['transfer_schema'][0]['weight']=1000.1
 with pytest.raises(LearningReasoningError):run(p=p)
 assert run()['boundary']=='Caller-declared weighted exact feature agreement rubric; near/far is threshold classification, not semantic distance. Independent target exact-key response scoring is separate, independence/truth not verified; no general transfer claim.'

def test_schema_empty_and_65_fully_matching_core_refusal():
 from app.modules.m20_general_cognitive_worker.near_far_transfer import compare
 p=payload();p.update(transfer_schema=[],source_features={},target_features={})
 with pytest.raises(ValueError,match='^transfer_schema requires bounded object list$'):compare('near_transfer',p)
 p=payload();p['transfer_schema']=[{'feature_id':str(i),'weight':1,'source':'fixture'}for i in range(65)];p['source_features']={str(i):'same'for i in range(65)};p['target_features']=dict(p['source_features'])
 with pytest.raises(ValueError,match='^transfer_schema requires bounded object list$'):compare('near_transfer',p)

@pytest.mark.parametrize('field',['source_features','target_features'])
def test_feature_dictionary_shapes_exact_cover_and_missing_core(field):
 from app.modules.m20_general_cognitive_worker.near_far_transfer import compare
 for value in [['operation','context'],{'operation':'add'},{'operation':'add','context':'shop','extra':'value'}]:
  p=payload();p[field]=value
  with pytest.raises(ValueError,match='^'+field+' must cover exactly declared feature schema$'):compare('near_transfer',p)

@pytest.mark.parametrize('field',['source_features','target_features'])
def test_nontext_schema_matching_feature_names_rejected(field):
 from app.modules.m20_general_cognitive_worker.near_far_transfer import compare
 p=payload();p['transfer_schema'][0]['feature_id']=5;p['source_features']={5:'add','context':'shop'};p['target_features']={5:'add','context':'lab'}
 with pytest.raises(ValueError,match='^feature_id requires bounded nonempty string$'):compare('near_transfer',p)

@pytest.mark.parametrize('field,label',[('task_id','task_id'),('source','answer key source')])
def test_nontext_task_fields_core_errors(field,label):
 from app.modules.m20_general_cognitive_worker.near_far_transfer import compare
 p=payload();p['independent_target_task'][field]=[]
 with pytest.raises(ValueError,match='^'+label+' requires bounded nonempty string$'):compare('near_transfer',p)

def test_answer_key_exact_cap_and_response_shapes():
 from app.modules.m20_general_cognitive_worker.near_far_transfer import compare
 p=payload();p['independent_target_task']['accepted_answers']=[str(i)for i in range(64)];assert compare('near_transfer',p)['target_performance']['correct'] is True
 p['independent_target_task']['accepted_answers'].append('64')
 with pytest.raises(ValueError,match='^accepted_answers requires bounded text list$'):compare('near_transfer',p)
 for value in [[],'response']:
  p=payload();p['independent_target_response']=value
  with pytest.raises(ValueError,match='^independent_target_response object required$'):compare('near_transfer',p)

@pytest.mark.parametrize('answer,correct',[('4',True),('wrong',False)])
def test_scored_status_and_evidence_for_both_outcomes(answer,correct):
 p=payload();p['independent_target_response']['answer']=answer;r=run(p=p)
 assert r['status']=='scored_target_performance' and r['transfer_evidence_recorded'] is True and r['target_performance']['correct'] is correct
