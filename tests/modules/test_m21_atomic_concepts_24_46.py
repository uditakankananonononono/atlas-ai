import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m21_claire.atomic_concepts_24_46 import *
from app.modules.m21_claire.atomic_concepts_routes_24_46 import router
@pytest.fixture
def s():return AtomicService(lambda text:[float(text.lower().count('formal')+1),float(text.lower().count('short')+1),float(len(text.split()))])
def sample(s,t='u',i=0):return s.add_sample(t,('My own writing sample number %d with enough original words to validate provenance.'%i),f'doc-{i}',True)
def test_exact_23_concepts():assert list(ROWS)==['3.2','3.3','3.4','4.1','4.2','4.3','4.4','4.5','4.6','5.1','5.2','5.3','5.4','5.5','6.1','6.2','6.3','6.4','6.5','7.1','7.2','7.3','7.4']
def test_3_2_correction_vector_retrieval_tenant_ranked(s):
 a=s.correction('u','Too formal','Make it short','essay');s.correction('v','Too formal','private','essay');r=s.retrieve_corrections('u','formal essay');assert r[0]['correction_id']==a['id'] and len(r)==1
def test_3_3_corrections_become_scoped_few_shot_messages(s):
 s.correction('u','Too formal','Make it short');o=s.few_shot('u','formal');assert [x['role'] for x in o['messages']]==['assistant','user'] and not o['generated_output'] and 'Current request wins' in o['instruction']
def test_3_4_repeat_error_blocks_repeated_original(s):
 s.correction('u','Too formal','Make it short');o=s.repeat_error('u','Too formal', 'formal',0);assert o['repeat_error'] and o['candidate_blocked']
def test_correction_negative_identical(s):
 with pytest.raises(AtomicError):s.correction('u','same','same')
def test_4_1_consented_owner_sample_and_hash(s):assert sample(s)['consent'] and len(s.store.samples[0]['sha256'])==64
def test_4_1_rejects_nonconsent_and_third_party(s):
 with pytest.raises(AtomicError):s.add_sample('u','A sufficiently long third party sample text here.','x',False)
 with pytest.raises(AtomicError):s.add_sample('u','A sufficiently long third party sample text here.','x',True,False)
def test_4_2_dataset_validation_counts_dedup_and_honest_target(s):
 sample(s,i=1);sample(s,i=1);o=s.validate_dataset('u');assert o['sample_count']==1 and o['duplicate_count']==1 and not o['target_met'] and o['provenance_complete']
def fill50(s):
 for i in range(50):sample(s,i=i)
def config():return {'rank':8,'alpha':16,'dropout':.05,'target_modules':['q_proj','v_proj'],'epochs':3,'learning_rate':.0002}
def test_4_3_lora_proposal_peft_split_no_fake_training(s):
 fill50(s);o=s.lora_proposal('u','Llama-3.1-8B',config());assert o['job_type']=='peft_lora_causal_lm' and o['split']['test']==.1 and not o['adapter_trained'] and o['reference']==RESEARCH['peft_lora']
def test_4_3_requires_50_samples(s):
 sample(s)
 with pytest.raises(AtomicError,match='50-200'):s.lora_proposal('u','model',config())
def test_4_4_ollama_target_is_pending_import_not_installed(s):
 fill50(s);p=s.lora_proposal('u','Llama-3.1-8B',config());o=s.ollama_target(p,'udita-voice');assert 'ADAPTER ./adapter' in o['modelfile_template'] and not o['installed'] and o['compatible_claim'].startswith('pending')
def test_4_5_readiness_and_cost_are_evidence_based_estimates(s):
 o=s.readiness({'vram_gb':24,'ram_gb':32,'free_disk_gb':100,'accelerator':'cuda','currency':'USD'},{'quantization_bits':16},2,3);assert o['local_ready'] and o['estimated_cloud_cost']==6 and o['estimate_only'] and not o['training_started']
def test_4_5_insufficient_gpu_not_ready(s):assert not s.readiness({'vram_gb':4,'ram_gb':8,'free_disk_gb':5},{'quantization_bits':16})['local_ready']
def test_4_6_activation_requires_voice_factuality_and_memorization_thresholds(s):
 o=s.evaluate_voice([{'voice_preference':.8,'factuality':.99,'memorization_match':.01}],{'voice_preference':.7,'factuality':.98,'memorization_match':.05});assert o['activation_recommended'] and not o['activated']
def test_4_6_factuality_failure_blocks(s):
 o=s.evaluate_voice([{'voice_preference':.9,'factuality':.7,'memorization_match':.01}],{'voice_preference':.7,'factuality':.98,'memorization_match':.05});assert not o['activation_recommended'] and 'factuality' in o['failure_reasons']
def test_5_1_owner_reasoning_note_capture_only(s):
 o=s.reasoning_note('u','Choose project',['list evidence','compare fit'],'select strongest',True);assert o['owner_authored'] and not o['hidden_model_chain_of_thought']
def test_5_1_rejects_model_or_one_step(s):
 with pytest.raises(AtomicError):s.reasoning_note('u','x',['one'],'y',False)
def test_5_2_embedding_retrieval_is_tenant_scoped(s):
 n=s.reasoning_note('u','formal choice',['a','b'],'c',True);s.reasoning_note('v','formal private',['a','b'],'c',True);r=s.retrieve_reasoning('u','formal');assert r[0]['note_id']==n['id'] and len(r)==1
def test_5_3_similar_problem_decision_time_rank(s):
 s.reasoning_note('u','formal essay',['a','b'],'c',True);s.reasoning_note('u','short code',['a','b'],'c',True);assert s.retrieve_reasoning('u','formal essay')[0]['problem']=='formal essay'
def test_5_4_decision_template_analogy_not_copy(s):
 s.reasoning_note('u','choose grant',['source','score'],'pick',True);o=s.decision_template('u','choose grant');assert o['template']['apply_by_analogy_not_copy'] and o['template']['verify_current_facts'] and o['template']['current_owner_review_required']
def test_5_5_reject_hidden_model_cot_accept_owner_note(s):
 assert not s.reject_hidden_cot('model_hidden_cot')['accepted'] and s.reject_hidden_cot('owner_authored_note')['accepted']
def opts():return [{'id':'a','tradeoffs':['fast']},{'id':'b','tradeoffs':['cheap']},{'id':'c','tradeoffs':['quality']}]
def test_6_1_generates_exact_3_to_5_distinct_tradeoff_options(s):assert s.generate_options(opts())['count']==3
def test_6_1_rejects_two_or_duplicate(s):
 with pytest.raises(AtomicError):s.generate_options(opts()[:2])
def test_6_2_complete_owner_ranking_permutation(s):assert s.capture_ranking('u',opts(),['b','a','c'])['ranking']==['b','a','c']
def test_6_2_rejects_partial_ranking(s):
 with pytest.raises(AtomicError):s.capture_ranking('u',opts(),['a','b'])
def test_6_3_pairwise_dataset_has_n_choose_2(s):
 r=s.capture_ranking('u',opts(),['b','a','c']);o=s.pairwise(r);assert o['pair_count']==3 and o['pairs'][0]['winner']=='b' and o['complete']
def test_6_4_bradley_terry_proposal_group_split_and_assumptions(s):
 r=s.capture_ranking('u',opts(),['b','a','c']);o=s.preference_proposal(s.pairwise(r)['pairs'],['length','tone']);assert o['model_family'].startswith('Bradley-Terry') and 'ranking_id' in o['split'] and len(o['assumption_checks'])==3 and o['status']=='proposal_not_trained'
def test_6_4_needs_three_pairs(s):
 with pytest.raises(AtomicError):s.preference_proposal([{'winner':'a','loser':'b'}],[])
def test_6_5_heldout_accuracy_brier_activation_not_automatic(s):
 o=s.evaluate_preference([{'probability':.9,'label':1},{'probability':.1,'label':0}],.8);assert o['pairwise_accuracy']==1 and o['brier_score']==pytest.approx(.01) and o['activation_recommended'] and not o['activated']
def test_6_5_invalid_probability(s):
 with pytest.raises(AtomicError):s.evaluate_preference([{'probability':2,'label':1}])
def test_7_1_explicit_scoped_consent_retention_and_revocation(s):
 c=s.consent('u',['link_click'],30,True);assert c['data_minimization'] and c['reference']==RESEARCH['nist_privacy'];assert s.revoke('u')['future_collection_blocked']
def test_7_1_rejects_silent_or_unknown_scope(s):
 with pytest.raises(AtomicError):s.consent('u',['link_click'],30,False)
 with pytest.raises(AtomicError):s.consent('u',['keystrokes'],30,True)
def test_7_2_link_click_records_minimal_scoped_event(s):
 s.consent('u',['link_click'],30,True);o=s.telemetry_event('u','link_click',{'url':'https://x','resource_id':'r'});assert o['url']=='https://x' and 'page_body' not in o
def test_7_3_application_submission_claim_requires_receipt(s):
 s.consent('u',['opportunity_application'],30,True);o=s.telemetry_event('u','opportunity_application',{'opportunity_id':'o','status':'submitted'});assert not o['submission_claim_verified'];o=s.telemetry_event('u','opportunity_application',{'opportunity_id':'o','status':'submitted','provider_receipt':'id'});assert o['submission_claim_verified']
def test_7_4_edit_duration_uses_active_seconds_not_wallclock(s):
 s.consent('u',['draft_edit_duration'],30,True);o=s.telemetry_event('u','draft_edit_duration',{'draft_id':'d','active_seconds':120});assert o['active_seconds']==120 and o['wall_clock_not_used']
def test_telemetry_without_or_after_consent_blocked(s):
 with pytest.raises(AtomicError):s.telemetry_event('u','link_click',{'url':'x','resource_id':'r'})
 s.consent('u',['link_click'],30,True);s.revoke('u')
 with pytest.raises(AtomicError):s.telemetry_event('u','link_click',{'url':'x','resource_id':'r'})
def test_mounted_http_and_negative():
 a=FastAPI();a.include_router(router,prefix='/claire');c=TestClient(a);assert len(c.get('/claire/atomic-concepts-24-46/capabilities').json())==23
 r=c.post('/claire/atomic-concepts-24-46/run',json={'atomic_row_id':'5.5','tenant_id':'u','data':{'source_type':'model_hidden_cot'}});assert r.status_code==200 and not r.json()['result']['accepted']
 assert c.post('/claire/atomic-concepts-24-46/run',json={'atomic_row_id':'7.2','tenant_id':'u','data':{}}).status_code==422
