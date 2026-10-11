"""Structured symbolic representation and example validation only."""
from copy import deepcopy
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Synthetic concepts','url':'https://example.org/concepts'}
def pack():return {'source':SRC,'objective':'Represent shape concepts','concepts':[{'concept_id':'triangle','invariants':{'sides':'three','closed':'yes'},'source':'fixture:definition'}],'verbal_propositions':[{'id':'v','concept_id':'triangle','features':{'sides':'three','closed':'yes'},'text':'A closed three-sided shape','source':'fixture:verbal'}],'visual_elements':[{'id':'img','concept_id':'triangle','features':{'sides':'three','closed':'yes'},'alt_text':'A closed triangle','source':'fixture:visual'}],'representation_mappings':[{'verbal_id':'v','visual_id':'img','concept_id':'triangle'}],'example_items':[{'example_id':'positive','concept_id':'triangle','features':{'sides':'three','closed':'yes','color':'red'},'variant_features':['color'],'role':'example','source':'fixture:positive'},{'example_id':'boundary','concept_id':'triangle','features':{'sides':'four','closed':'yes','color':'red'},'variant_features':['color'],'role':'counterexample','source':'fixture:boundary'}]}
def run(method='dual_coding',**changes):return execute(method,{**pack(),**changes})

def test_dual_mapping_exact_coverage_accessibility_and_honesty():
 r=run()['result']['representation_pack']
 assert r['status']=='validated' and r['valid'] is True
 assert r['concept_reports']==[{'concept_id':'triangle','verbal_ids':['v'],'visual_ids':['img'],'mapped_pairs':[['v','img']],'missing_verbal':False,'missing_visual':False,'missing_mapping':False}]
 assert r['mapping_reports']==[{'verbal_id':'v','visual_id':'img','concept_id':'triangle','conflicting_features':[],'missing_verbal_invariants':[],'missing_visual_invariants':[],'valid':True}]
 assert r['visual_accessibility']==[{'visual_id':'img','alt_text':'A closed triangle','source':'fixture:visual'}]
 assert r['source_truth_verified'] is False and r['image_understanding_executed'] is False and r['learning_improvement'] is None
 assert run()['evaluation']['capability_executed'] is True

def test_missing_and_conflicting_mapping_report_not_fabricated_success():
 p=pack();p['visual_elements'][0]['features']['sides']='four'
 r=execute('dual_coding',p)['result']['representation_pack']
 assert r['valid'] is False and r['mapping_reports'][0]['conflicting_features']==['sides']
 p=pack();p['visual_elements'][0]['features'].pop('closed');r=execute('dual_coding',p)['result']['representation_pack']
 assert r['mapping_reports'][0]['missing_visual_invariants']==['closed'] and r['valid'] is False
 r=run(representation_mappings=[])['result']['representation_pack'];assert r['valid'] is False and r['concept_reports'][0]['missing_mapping'] is True
 r=run(visual_elements=[],representation_mappings=[])['result']['representation_pack'];assert r['valid'] is False and r['concept_reports'][0]['missing_visual'] is True
 r=run(verbal_propositions=[],representation_mappings=[])['result']['representation_pack'];assert r['concept_reports'][0]['missing_verbal'] is True

def test_concrete_invariant_variant_counterexample_computation():
 r=run('concrete_examples')['result']['example_pack']
 assert r['valid'] is True and r['concept_reports']==[{'concept_id':'triangle','valid_example_ids':['positive'],'valid_counterexample_ids':['boundary'],'coverage_complete':True}]
 assert r['example_reports']==[{'example_id':'positive','concept_id':'triangle','role':'example','violated_invariants':[],'missing_invariants':[],'variant_features':['color'],'valid':True,'source':'fixture:positive'},{'example_id':'boundary','concept_id':'triangle','role':'counterexample','violated_invariants':['sides'],'missing_invariants':[],'variant_features':['color'],'valid':True,'source':'fixture:boundary'}]
 assert r['source_truth_verified'] is False and r['learning_improvement'] is None
 assert run('concrete_examples')['evaluation']['capability_executed'] is True

def test_wrong_example_role_missing_feature_and_invariant_variants():
 p=pack();p['example_items'][1]['features']['sides']='three'
 r=execute('concrete_examples',p)['result']['example_pack'];assert r['valid'] is False and r['example_reports'][1]['valid'] is False
 p=pack();p['example_items'][0]['features'].pop('closed');r=execute('concrete_examples',p)['result']['example_pack'];assert r['example_reports'][0]['missing_invariants']==['closed'] and r['valid'] is False
 p=pack();p['example_items'][0]['variant_features']=['sides']
 with pytest.raises(LearningReasoningError):execute('concrete_examples',p)
 r=run('concrete_examples',example_items=pack()['example_items'][:1])['result']['example_pack'];assert r['valid'] is False and r['concept_reports'][0]['coverage_complete'] is False

@pytest.mark.parametrize('change',[{'concepts':[]},{'concepts':[{'concept_id':'c','invariants':{},'source':'fixture'}]},{'visual_elements':[{'id':'img','concept_id':'triangle','features':{},'alt_text':'','source':'fixture'}]},{'representation_mappings':[{'verbal_id':'unknown','visual_id':'img','concept_id':'triangle'}]},{'verbal_propositions':[[]]}])
def test_malformed_rep_records_and_nonmutation(change):
 p={**pack(),**change};before=deepcopy(p)
 with pytest.raises(LearningReasoningError):execute('dual_coding',p)
 assert p==before

def test_unknown_example_duplicate_ids_and_source_guards():
 for field in ['concepts','verbal_propositions','visual_elements','example_items']:
  p=pack();p[field][0]['source']=''
  with pytest.raises(LearningReasoningError):execute('concrete_examples'if field=='example_items'else 'dual_coding',p)
  p=pack();p[field].append(deepcopy(p[field][0]))
  with pytest.raises(LearningReasoningError):execute('concrete_examples'if field=='example_items'else 'dual_coding',p)
 p=pack();p['example_items'][0]['concept_id']='unknown'
 with pytest.raises(LearningReasoningError):execute('concrete_examples',p)

def test_mounted_auth_tenant_and_minimal_payload_refusal(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method in ['dual_coding','concrete_examples']:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':pack()}).status_code==401
  r=c.post(path,headers=h,json={'payload':pack()});assert r.status_code==200 and r.json()['tenant_id']=='a' and r.json()['evaluation']['capability_executed'] is True
  assert c.post(path,headers=h,json={'payload':{'source':SRC,'objective':'x'}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**pack(),'resource_refs':[{'tenant_id':'b'}]}}).status_code==403
