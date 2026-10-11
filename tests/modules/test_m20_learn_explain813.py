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
 assert c.post(path,headers=h,json={'payload':{**payload(),'resource_refs':[{'tenant_id':'b'}]}}).status_code==403

def test_target_ancestors_only_and_every_step_valid():
 p=payload();p['explanation_rules'].append({'id':'irrelevant','if':['seed'],'then':'junk','source':'fixture:junk'})
 r=execute('self_explanation',p)['result']['explanation_practice']
 assert 'junk' in r['derived_atoms'] and 'junk' not in [step['conclusion']for step in r['derivation']]
 p['explanation_attempts']=[{'evidence_id':'a','source':'fixture:a','steps':steps()+[{'rule_id':'absent','conclusion':'junk','premises':[]}]}]
 a=execute('self_explanation',p)['result']['explanation_practice']['attempt_results'][0]
 assert a['target_reached'] is True and a['correct'] is False

def test_first_pass_and_pass_then_pass_no_improvement_and_feedback():
 r=run(explanation_attempts=[{'evidence_id':str(i),'source':'fixture:a','steps':steps()}for i in range(2)])['result']['explanation_practice']
 assert all(a['improved_from_previous'] is False for a in r['attempt_results'])
 assert r['attempt_results'][0]['step_feedback'][0]=={'step_index':0,'rule_id':'germinate','accepted':True,'missing_premises':[],'rule_matches':True,'expected_conclusion':'sprout','expected_premises':['seed'],'rule_source':'fixture:rule1'}
 assert r['task']['question']=='Which supplied rules and prerequisite facts justify plant?'
 assert r['task']['condition_question']=='Which supplied fact removals prevent deriving plant?'
 assert r['boundary']=='Finite positive Horn structured explanation and counterfactual fact-deletion checks only; exact rule/premise/ordered-step validation, not free-text semantics or learner understanding. Source records are supplied premises, not verified truth.'

def test_exact_caps_and_optional_attempts():
 p=payload();p.pop('explanation_attempts');assert execute('self_explanation',p)['result']['explanation_practice']['attempt_results']==[]
 for field,rows in [('explanation_facts',[{'atom':str(i),'source':'fixture'}for i in range(64)]),('explanation_rules',[{'id':str(i),'if':[],'then':str(i),'source':'fixture'}for i in range(64)]),('explanation_attempts',[{'evidence_id':str(i),'source':'fixture','steps':[]}for i in range(100)])]:
  assert execute('self_explanation',{**payload(),field:rows})['evaluation']['capability_executed']
  extra={**rows[0]}
  if field=='explanation_facts':extra['atom']='extra'
  elif field=='explanation_rules':extra.update(id='extra',then='extra')
  else:extra['evidence_id']='extra'
  with pytest.raises(LearningReasoningError):execute('self_explanation',{**payload(),field:rows+[extra]})
 atoms=[str(i)for i in range(64)]
 p=payload();p['explanation_rules']=[{'id':'r','if':atoms,'then':'plant','source':'fixture'}];execute('self_explanation',p)
 with pytest.raises(LearningReasoningError):execute('self_explanation',{**p,'explanation_rules':[{**p['explanation_rules'][0],'if':atoms+['extra']}]})
 for n in [64,65]:
  attempt={'evidence_id':'a','source':'fixture','steps':[steps()[0]]*n}
  if n==64:execute('self_explanation',{**payload(),'explanation_attempts':[attempt]})
  else:
   with pytest.raises(LearningReasoningError):execute('self_explanation',{**payload(),'explanation_attempts':[attempt]})

@pytest.mark.parametrize('value',['seed',[''],['seed','seed']])
def test_premise_list_text_and_duplicate_guards(value):
 p=payload();p['explanation_rules'][0]['if']=value
 with pytest.raises(LearningReasoningError):execute('self_explanation',p)

@pytest.mark.parametrize('field',['explanation_facts','explanation_rules','explanation_attempts'])
def test_record_shapes_and_empty_rules(field):
 with pytest.raises(LearningReasoningError):execute('self_explanation',{**payload(),field:[[]]})
 with pytest.raises(LearningReasoningError):run(explanation_rules=[])
 with pytest.raises(LearningReasoningError):run(explanation_attempts=[{'evidence_id':'a','source':'fixture','steps':[[]]}])

def test_text_identity_and_negation_guards():
 for field,key in [('explanation_facts','atom'),('explanation_rules','id'),('explanation_rules','then')]:
  p=payload();p[field][0][key]=''
  with pytest.raises(LearningReasoningError):execute('self_explanation',p)
 for field in ['explanation_facts','explanation_rules']:
  p=payload();p[field].append(dict(p[field][0]))
  with pytest.raises(LearningReasoningError):execute('self_explanation',p)
 for key in ['evidence_id','step_rule_id','step_conclusion']:
  attempt={'evidence_id':'a','source':'fixture','steps':steps()}
  if key=='evidence_id':attempt[key]=''
  else:attempt['steps'][0]['rule_id'if key=='step_rule_id'else 'conclusion']=''
  with pytest.raises(LearningReasoningError):run(explanation_attempts=[attempt])
 p=payload();p['explanation_rules'][0]['unless']=['negated']
 with pytest.raises(LearningReasoningError):execute('self_explanation',p)

def test_submitted_premise_atom_cap_and_guards():
 for value in ['seed',[''],['seed','seed'],[str(i)for i in range(65)]]:
  attempt={'evidence_id':'a','source':'fixture','steps':[{'rule_id':'germinate','conclusion':'sprout','premises':value}]}
  with pytest.raises(LearningReasoningError):run(explanation_attempts=[attempt])
 attempt={'evidence_id':'a','source':'fixture','steps':[{'rule_id':'germinate','conclusion':'sprout','premises':[str(i)for i in range(64)]}]}
 assert run(explanation_attempts=[attempt])['result']['explanation_practice']['attempt_results'][0]['correct'] is False

def test_single_character_string_premises_never_atom_list():
 p=payload();p['explanation_rules'][0]['if']='s'
 with pytest.raises(LearningReasoningError):execute('self_explanation',p)
 attempt={'evidence_id':'a','source':'fixture','steps':[{'rule_id':'germinate','conclusion':'sprout','premises':'s'}]}
 with pytest.raises(LearningReasoningError):run(explanation_attempts=[attempt])

def test_sorted_three_premise_derivation_feedback_and_fixed_seed():
 import os,subprocess,sys
 p=payload();p['explanation_facts']=[{'atom':name,'source':'fixture:'+name}for name in ['zebra','middle','alpha']]
 p['explanation_rules']=[{'id':'r','if':['zebra','middle','alpha'],'then':'plant','source':'fixture:r'}]
 p['explanation_attempts']=[{'evidence_id':'a','source':'fixture:a','steps':[{'rule_id':'r','conclusion':'plant','premises':['zebra','middle','alpha']}]}]
 r=execute('self_explanation',p)['result']['explanation_practice']
 assert r['derivation'][0]['premises']==['alpha','middle','zebra']
 assert r['attempt_results'][0]['step_feedback'][0]['expected_premises']==['alpha','middle','zebra']
 # An unsorted set can accidentally be sorted on any given process hash seed.
 # Fixed seed proves this concrete case isn't relying on that luck.
 code="from app.modules.m20_general_cognitive_worker.explanation_practice import practice; p="+repr(p)+"; r=practice('self_explanation',p); assert r['derivation'][0]['premises']==['alpha','middle','zebra']; assert r['attempt_results'][0]['step_feedback'][0]['expected_premises']==['alpha','middle','zebra']"
 result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'PYTHONHASHSEED':'6'},capture_output=True,text=True)
 assert result.returncode==0,result.stdout+result.stderr
