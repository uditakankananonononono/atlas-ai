import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.atomic_concepts_round9_139_160 import ConceptError,Corpus,execute
from app.modules.m20_general_cognitive_worker.atomic_concepts_routes_round9_139_160 import router

def market(cid):return execute(cid,{'currency':'USD','segments':[{'name':'college','customers':1000,'annual_revenue_per_customer':100,'serviceable_fraction':.5,'obtainable_fraction':.1,'assumptions':['verified enrollment']}]})['result']
def test_139_sam_calculation_is_serviceable_subset():assert market('360.2')['selected_value']==50000
def test_140_som_calculation_is_obtainable_subset():
 o=market('360.3');assert o['selected_value']==5000 and not o['captured_revenue_claimed']
def competitors(cid):return execute(cid,{'criteria':[{'id':'ux','weight':2,'max_score':5},{'id':'price','weight':1,'max_score':5}],'competitors':[{'name':'A','scores':{'ux':5,'price':2},'evidence':['review-1']},{'name':'B','scores':{'ux':2,'price':5},'evidence':['review-2']} ]})['result']
def test_141_strength_ranking_is_weighted_and_evidenced():assert competitors('361.1')['ranking'][0]['name']=='A'
def test_142_weakness_is_inverse_not_missing_data():assert competitors('361.2')['unknown_is_not_weakness']
def test_143_value_design_observable_behavior_and_tradeoff():
 o=execute('483.1',{'purpose':'help students','values':[{'name':'candor','behavioral_examples':['name risks'],'counterexamples':['hide risks']}]})['result'];assert o['values'][0]['observable'] and not o['adoption_claimed']
def test_144_norm_design_links_values_and_repairs():
 o=execute('483.2',{'values':['candor'],'norms':[{'trigger':'review','behavior':'name a risk','linked_value':'candor','repair':'correct record'}]})['result'];assert o['norms'][0]['repair']=='correct record'
def test_145_objective_is_qualitative_direction():assert execute('492.1',{'objective':'Make applications easier','strategic_context':'student access','owner':'team','horizon':'Q1'})['result']['qualities']['directional']
def test_146_key_results_have_baseline_target_and_formula():
 o=execute('492.2',{'objective':'Make applications easier','key_results':[{'metric':'completion rate','baseline':.4,'target':.7,'deadline':'Q1','owner':'A'}]})['result'];assert o['key_results'][0]['direction']=='increase' and not o['achievement_claimed']
def test_147_performance_evaluation_retains_missing_evidence():
 o=execute('495.1',{'criteria':[{'id':'quality'},{'id':'speed'}],'observations':[{'criterion_id':'quality','rating':4}]})['result'];assert o['criteria_evaluation'][1]['insufficient_evidence'] and not o['employment_decision_made']
def test_148_improvement_plan_requires_support_and_employee_voice():
 o=execute('495.2',{'gap':'late review','target_outcome':'on time','supports':['training'],'checkpoints':['week 1'],'owner':'manager','employee_input':'agreed cadence'})['result'];assert o['hr_review_required'] and not o['punitive_action_automated']
def test_149_data_movement_is_idempotent_plan_not_fake_run():
 o=execute('535.1',{'source':'s3','destination':'warehouse','schema':{'id':'int'},'checkpoint':'cursor','idempotency_key':'id'})['result'];assert o['lineage_recorded'] and not o['executed']
def test_150_transform_pipeline_validates_field_lineage():
 o=execute('535.2',{'input_schema':['a'],'output_schema':['b'],'steps':[{'operation':'rename','inputs':['a'],'outputs':['b']}],'quality_checks':['not_null']})['result'];assert o['schema_contract']['output']==['b'] and o['test_before_promote']
def test_151_emotion_signals_are_tentative_and_non_diagnostic():
 o=execute('716.1',{'signals':[{'type':'message_wording','value':'overwhelmed','confidence':.6},{'type':'camera_face','value':'sad','confidence':.9}]})['result'];assert len(o['recognized_signals'])==1 and not o['emotion_claimed_as_fact'] and o['diagnosis'] is None
def test_152_response_selection_rewards_acknowledgment_choice_boundaries():
 o=execute('716.2',{'context':'deadline stress','candidate_responses':[{'text':'You are depressed','diagnoses':True},{'text':'Sounds hard. Want options?','acknowledges':True,'asks_preference':True,'respects_boundary':True}]})['result'];assert o['selected']['text'].startswith('Sounds') and not o['send_executed']
def test_153_aic_formula_and_aicc_are_exact():
 o=execute('1106.1',{'log_likelihood':-100,'parameter_count':5,'sample_size':100})['result'];assert o['aic']==210 and o['aicc']>o['aic']
def test_154_bic_penalizes_with_log_sample_size():
 o=execute('1106.2',{'log_likelihood':-100,'parameter_count':5,'sample_size':100})['result'];assert o['bic']==pytest.approx(5*__import__('math').log(100)+200) and o['not_absolute_fit']
def source(cid,kind):return execute(cid,{'owner_id':'u','sources':[{'source_id':'d1','title':'My '+kind,'owner_confirmed':True,'connected':False}]})['result']
def test_155_writing_selection_never_claims_connection():assert source('2010.1','writing')['selected_sources'][0]['kind']=='writing' and not source('2010.1','writing')['connection_claimed']
def test_156_essay_selection_is_owner_confirmed():assert source('2010.2','essay')['selected_sources'][0]['kind']=='essay'
def test_157_activity_selection_is_distinct_source_kind():assert source('2010.3','activity')['selected_sources'][0]['kind']=='activity'
def test_158_indexing_hashes_and_chunks_owner_corpus():
 c=Corpus();o=execute('2010.4',{'owner_id':'u','documents':[{'source_id':'d1','kind':'essay','text':'Tai Ahom heritage and woven faa sin are central to my story.'}]},c)['result'];assert len(o['indexed'][0]['content_sha256'])==64 and o['source_of_truth'] and not o['embedding_claimed']
def test_159_retrieval_is_tenant_scoped_and_cited_without_fake_draft():
 c=Corpus();execute('2010.4',{'owner_id':'u','documents':[{'source_id':'d1','kind':'essay','text':'Tai Ahom heritage and woven faa sin are central to my story.'}]},c);execute('2010.4',{'owner_id':'other','documents':[{'source_id':'d2','kind':'essay','text':'Tai Ahom content belonging to someone else entirely.'}]},c)
 o=execute('2010.5',{'owner_id':'u','query':'Tai Ahom'},c)['result'];assert len(o['citations'])==1 and o['citations'][0]['source_id']=='d1' and not o['draft_generated']
@pytest.mark.parametrize('cid,payload',[('360.2',{}),('361.1',{'criteria':[]}),('483.2',{'values':['x'],'norms':[{'trigger':'t','behavior':'b','linked_value':'missing','repair':'r'}]}),('492.1',{'objective':'Grow 20 percent','strategic_context':'x','owner':'a','horizon':'q'}),('495.2',{'gap':'x','target_outcome':'y','supports':['z'],'checkpoints':['w'],'owner':'a'}),('535.1',{'source':'x','destination':'x','schema':{},'checkpoint':'c'}),('716.1',{'signals':[{'type':'message_wording','confidence':2}]}),('1106.1',{'log_likelihood':-1,'parameter_count':5,'sample_size':6}),('2010.1',{'owner_id':'u','sources':[{'source_id':'x','title':'t','owner_confirmed':False}]})])
def test_negative_paths_fail_closed(cid,payload):
 with pytest.raises(ConceptError):execute(cid,payload)
def test_mounted_http_boundary_and_unknown_concept():
 app=FastAPI();app.include_router(router,prefix='/m20');c=TestClient(app)
 assert len(c.get('/m20/atomic-concepts/139-160').json())==22
 good=c.post('/m20/atomic-concepts/139-160/1106.1',json={'payload':{'log_likelihood':-100,'parameter_count':5,'sample_size':100}});assert good.status_code==200 and good.json()['result']['aic']==210
 assert c.post('/m20/atomic-concepts/139-160/nope',json={'payload':{}}).status_code==422
