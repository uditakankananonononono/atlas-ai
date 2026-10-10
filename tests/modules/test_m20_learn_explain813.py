"""Structured symbolic explanation practice, no free-text semantic grading."""
from copy import deepcopy
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Synthetic Horn lesson','url':'https://example.org/lesson'}
def payload():
 return {'source':SRC,'objective':'Explain symbolic consequence','explanation_facts':[{'atom':'seed','source':'fixture:seed'},{'atom':'light','source':'fixture:light'}],'explanation_rules':[{'id':'germinate','if':['seed'],'then':'sprout','source':'fixture:rule1'},{'id':'grow','if':['sprout','light'],'then':'plant','source':'fixture:rule2'}],'explanation_target':'plant','explanation_attempts':[]}
def steps():return [{'rule_id':'germinate','conclusion':'sprout','premises':['seed']},{'rule_id':'grow','conclusion':'plant','premises':['sprout','light']}]
def run(method='elaborative_interrogation',**changes):return execute(method,{**payload(),**changes})

@pytest.mark.parametrize('method',['elaborative_interrogation','self_explanation'])
def test_target_specific_generated_derivation_and_conditions(method):
 r=run(method)['result']['explanation_practice']
 assert r['target_entailed'] is True and r['derived_atoms']==['light','plant','seed','sprout']
 assert r['derivation']==[{'rule_id':'germinate','conclusion':'sprout','premises':['seed'],'source':'fixture:rule1'},{'rule_id':'grow','conclusion':'plant','premises':['light','sprout'],'source':'fixture:rule2'}]
 assert r['condition_checks']==[{'removed_fact':'light','target_still_entailed':False},{'removed_fact':'seed','target_still_entailed':False}]
 assert r['task']['target']=='plant' and r['task']['mode']==method
 assert r['fact_provenance']==[{'atom':'light','source':'fixture:light'},{'atom':'seed','source':'fixture:seed'}]
 assert r['source_truth_verified'] is False and r['learner_understanding'] is None
 assert run(method)['evaluation']['capability_executed'] is True

def test_invalid_explanation_feedback_retry_and_reordered_valid_proof():
 attempts=[{'evidence_id':'first','source':'fixture:attempt1','steps':steps()[::-1]},{'evidence_id':'retry','source':'fixture:attempt2','steps':steps()}]
 r=run('self_explanation',explanation_attempts=attempts)['result']['explanation_practice']
 a,b=r['attempt_results'];assert a['correct'] is False and a['target_reached'] is False
 assert a['step_feedback'][0]['missing_premises']==['sprout'] and a['step_feedback'][0]['accepted'] is False
 assert b['correct'] is True and b['target_reached'] is True and b['improved_from_previous'] is True
 assert b['evidence_id']=='retry' and b['source']=='fixture:attempt2' and b['retry_recommended'] is False
 assert a['retry_recommended'] is True

@pytest.mark.parametrize('bad',[{'rule_id':'missing','conclusion':'sprout','premises':['seed']},{'rule_id':'germinate','conclusion':'plant','premises':['seed']},{'rule_id':'germinate','conclusion':'sprout','premises':[]}])
def test_wrong_rules_conclusion_and_premises_do_not_pass(bad):
 r=run(explanation_attempts=[{'evidence_id':'a','source':'fixture:a','steps':[bad,steps()[1]]}])['result']['explanation_practice']['attempt_results'][0]
 assert r['correct'] is False and r['step_feedback'][0]['accepted'] is False

def test_alternative_valid_derivation_and_unsupported_cycle():
 p=payload();p['explanation_rules']+=[{'id':'direct','if':['seed','light'],'then':'plant','source':'fixture:alternate'}]
 p['explanation_attempts']=[{'evidence_id':'a','source':'fixture:a','steps':[{'rule_id':'direct','conclusion':'plant','premises':['seed','light']}]}]
 assert execute('self_explanation',p)['result']['explanation_practice']['attempt_results'][0]['correct'] is True
 p=payload();p['explanation_facts']=[];p['explanation_rules']=[{'id':'a','if':['plant'],'then':'sprout','source':'fixture:a'},{'id':'b','if':['sprout'],'then':'plant','source':'fixture:b'}]
 r=execute('elaborative_interrogation',p)['result']['explanation_practice'];assert r['target_entailed'] is False and r['derivation']==[] and r['status']=='target_not_entailed'

def test_deletion_redundancy_and_heldout_chain():
 p=payload();p['explanation_rules'].append({'id':'shortcut','if':['light'],'then':'plant','source':'fixture:shortcut'})
 r=execute('elaborative_interrogation',p)['result']['explanation_practice'];assert r['condition_checks']==[{'removed_fact':'light','target_still_entailed':False},{'removed_fact':'seed','target_still_entailed':True}]
 for n in range(1,7):
  facts=[{'atom':'held0','source':'fixture:held'}];rules=[{'id':str(i),'if':[f'held{i}'],'then':f'held{i+1}','source':f'fixture:r{i}'}for i in range(n)]
  r=run(explanation_facts=facts,explanation_rules=rules,explanation_target=f'held{n}')['result']['explanation_practice']
  assert r['target_entailed'] is True and len(r['derivation'])==n and r['condition_checks'][0]['target_still_entailed'] is False

@pytest.mark.parametrize('change',[{'explanation_facts':[{'atom':'seed','source':''}]},{'explanation_rules':[{'id':'r','if':['seed'],'then':'plant','source':''}]},{'explanation_target':''},{'explanation_attempts':[{'evidence_id':'a','source':'','steps':steps()}]},{'explanation_attempts':[{'evidence_id':'a','source':'fixture','steps':steps()},{'evidence_id':'a','source':'fixture','steps':steps()}]}])
def test_provenance_invalid_ids_and_input_nonmutation(change):
 p={**payload(),**change};before=deepcopy(p)
 with pytest.raises(LearningReasoningError):execute('self_explanation',p)
 assert p==before

def test_mounted_auth_tenant_and_bad_inputs(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);path='/api/v1/api/modules/20/learning-reasoning-810-859/self_explanation';h=oidc_auth_headers('a','owner')
 assert c.post(path,json={'payload':payload()}).status_code==401
 r=c.post(path,headers=h,json={'payload':payload()});assert r.status_code==200 and r.json()['tenant_id']=='a' and r.json()['evaluation']['capability_executed'] is True
 assert c.post(path,headers=h,json={'payload':{'objective':'x','source':SRC}}).status_code==422
 assert c.post(path,headers=h,json={'payload':{**payload(),'resource_refs':[{'tenant_id':'b'}]}}).status_code==422
