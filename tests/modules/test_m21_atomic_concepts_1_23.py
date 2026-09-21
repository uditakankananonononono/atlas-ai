import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m21_claire.atomic_concepts_1_23 import *
from app.modules.m21_claire.atomic_concepts_routes_1_23 import router
SRC=[{'id':'s','title':'Official','url':'https://official.example/page','official':True}]
def run(r,**d):return execute_atomic(r,d)['result']
def test_exact_23():assert [x['atomic_row_id'] for x in capabilities()]==['1.'+str(i) for i in range(1,18)]+['2.'+str(i) for i in range(1,6)]+['3.1']
def test_1_1_rigorous_research_project():
 o=run('1.1',question='q',sources=SRC,acceptance_tests=['reproduce result']);assert o['rigor']['reference']==RESEARCH['nih_rigor'] and o['data_management']['reference']==RESEARCH['nih_dms'] and o['claims_not_completion']
def test_1_2_bioinformatics_is_reproducible_and_bounded():
 o=run('1.2',question='q',sources=SRC,acceptance_tests=['QC pass'],input_accessions=['SRR1'],reference_build='GRCh38',pipeline_stages=['QC','align']);assert o['workflow']['FAIR_outputs'] and 'invented biological samples' in o['prohibit']
def test_1_3_cs_has_threat_model_tests_benchmark_no_fake_deploy():
 o=run('1.3',question='q',sources=SRC,acceptance_tests=['tests pass']);assert o['engineering']['test_pyramid']==['unit','integration','end-to-end'] and o['engineering']['deployment_is_unproven_until_observed']
@pytest.mark.parametrize('r,kind',[('1.4','summer_program'),('1.5','competition')])
def test_1_4_1_5_application_grounding_blocks_unsupported(r,kind):
 o=run(r,requirements=[{'name':'essay','official_text':'write','source_url':'https://x','owner_source_ids':['missing']}],owner_sources=[{'id':'real'}]);assert o['application_type']==kind and o['unsupported_requirements']==['essay'] and o['submission_state']=='not_submitted'
@pytest.mark.parametrize('r,step',[('1.6','prompt parse'),('1.7','motion research'),('1.8','country policy brief'),('1.9','syllabus map'),('1.10','rules and judging matrix')])
def test_1_6_1_10_distinct_opportunity_workflows(r,step):
 o=run(r,listings=[{'title':'x','official_url':'https://x','deadline':'2027','eligibility':'student'}]);assert step in o['opportunities'][0]['workflow'] and not o['auto_signup']
def test_1_11_official_tool_discovery_claim_provenance():assert run('1.11',sources=SRC,products=[{'name':'x','claims':[{'claim':'c','source_id':'s'}]}])['products'][0]['official_sources_only']
def test_1_12_named_comparison_ranked_without_invented_claim():
 o=run('1.12',sources=SRC,products=[{'name':'Instinct','fit_score':.9,'claims':[]},{'name':'Replit','fit_score':.5,'claims':[{'claim':'x','source_id':'missing'}]}]);assert o['ranked_names'][0]=='Instinct' and o['products'][1]['claims'][0]['status']=='unverified'
def test_1_13_fallback_selects_only_feasible_without_bypass():
 o=run('1.13',paths=[{'name':'bad','priority':1,'requirements':['api']},{'name':'good','priority':2,'requirements':['export']}],available_capabilities=['export']);assert o['selected']['name']=='good' and o['never_bypass_security_or_terms']
def test_1_14_signup_is_exact_review_proposal_never_submission():
 o=run('1.14',destination='https://competition',fields={'name':'U'});assert o['state']=='awaiting_exact_owner_review' and not o['submitted'] and o['review_hash']
def test_1_15_humanization_factual_not_detection_evasion():
 o=run('1.15',text='I built it',owner_facts=['built'],claims=['invented']);assert not o['ready'] and not o['detection_evasion'] and o['unsupported_claims']==['invented']
def test_1_16_advice_provenance_and_contradictions():
 o=run('1.16',sources=SRC,claims=[{'claim':'x','source_ids':['s']},{'claim':'y','source_ids':[]}],contradictions=['x vs y']);assert [x['status'] for x in o['claims']]==['supported','unsupported'] and o['retrieved_not_implemented']
def test_1_17_advice_plan_requires_verification_rollback_no_effects():
 o=run('1.17',advice=[{'claim':'x','action':'do','evidence':'s','acceptance_test':'observed','rollback':'undo'}]);assert o['steps'][0]['status']=='proposed' and not o['external_effects_executed']
@pytest.fixture
def journal():return DecisionJournal(lambda t:[float(t.count('competition')+1),float(t.count('essay')+1)])
def test_2_1_capture_one_line_reason(journal):assert journal.capture('t','Choose competition','strong fit')['reason']=='strong fit'
def test_2_2_persistent_tenant_record_and_isolation(journal):
 r=journal.capture('a','Choose x','reason');assert r['persistent_record'] and journal.retrieve('b','x')==[]
def test_2_3_embedding_is_stored_nonempty(journal):assert len(journal.capture('t','competition','fit')['embedding'])==2
def test_2_4_similarity_retrieval_ranks_related(journal):
 journal.capture('t','competition A','fit');journal.capture('t','essay B','voice');assert journal.retrieve('t','competition')[0]['decision']=='competition A'
def test_2_5_adaptation_uses_reasons_as_evidence_not_permanent_rules(journal):
 journal.capture('t','competition A','fit');o=journal.adapt('t',{'choice':'B'},'competition');assert o['owner_review_required'] and not o['claimed_owner_preference']
def test_3_1_correction_pair_capture_for_few_shot(journal):
 o=journal.correction('t','Too formal','Use my short direct voice','essay');assert o['few_shot_example'] and o['original']!=o['correction']
def test_negative_paths_and_mounted_http():
 with pytest.raises(AtomicConceptError):run('1.1',question='q',sources=SRC,acceptance_tests=[])
 with pytest.raises(AtomicConceptError):run('1.17',advice=[{'claim':'x'}])
 with pytest.raises(AtomicConceptError):DecisionJournal(lambda x:[1]).capture('t','x','two\nlines')
 a=FastAPI();a.include_router(router,prefix='/claire');c=TestClient(a);assert len(c.get('/claire/atomic-concepts-1-23/capabilities').json())==23
 assert c.post('/claire/atomic-concepts-1-23/run',json={'row_id':'1.14','data':{}}).status_code==422
