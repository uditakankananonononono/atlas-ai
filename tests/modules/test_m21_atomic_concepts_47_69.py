import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m21_claire.atomic_concepts_47_69 import ROWS,run
from app.modules.m21_claire.atomic_concepts_routes_47_69 import router

def d(r):return {'7.5':{'consent_scope':{'consent_id':'c','event_types':['chosen'],'fields':['option']},'events':[{'event_id':'e','type':'chosen','data':{'option':'a','secret':'x'}},{'event_id':'x','type':'other','data':{}}]},'7.6':{'consented_events':[{'event_id':'e','option_id':'a','event_type':'chosen'}]},'7.7':{'records':[{'record_id':'r','subject_id':'u'}],'subject_id':'u','action':'delete_subject_data'},'8.1':{'text':'sample','embedding':[1,0]},'8.2':{'text':'decision','embedding':[0,1]},'8.3':{'text':'correction','embedding':[1,1]},'8.4':{'entries':[{'id':'a','kind':'writing','model':'m','vector':[1,0]},{'id':'b','kind':'decision','model':'m','vector':[0,1]}]},'8.5':{'query_vector':[1,0],'entries':[{'id':'a','kind':'writing','vector':[1,0]},{'id':'b','kind':'decision','vector':[0,1]}]},'8.6':{'options':[{'id':'a','attributes':{'tone':'short'}},{'id':'b','attributes':{'tone':'long'}}],'preference_signals':[{'id':'s','attribute':'tone','preferred_value':'short','confidence':.8}]},'9.1':{'start_at':'2026-01-01T10:00:00+00:00','weeks':3},'9.2':{'actions':[{'id':'a','completed_at':'t','outcome':'ok'}]},'9.3':{'labels':[{'action_id':'a','label':'unclear'}]},'9.4':{'reviews':[{'action_id':'a','label':'good','note':'matched intent'}]},'9.5':{'preference_pairs':[{'chosen_id':'a','rejected_id':'b'},{'chosen_id':'c','rejected_id':'d'}]},'9.6':{'evaluations':[{'at':'1','alignment_score':.5},{'at':'2','alignment_score':.7}]},'10.1':{'metrics':[{'name':'accuracy','values':[.5,.8]}]},'10.2':{'current':'prompt old','proposal':'prompt new','evidence':['e'],'evaluation_plan':['ab test']},'10.3':{'current':'algo old','proposal':'algo new','evidence':['e'],'evaluation_plan':['offline benchmark']},'11.1':{'cases':[{'domain':'bio','relations':['feedback']},{'domain':'economics','relations':['feedback']}]},'11.2':{'pattern':{'roles':['stock','flow']},'target_domain':{'name':'learning'},'mapping':[{'pattern_role':'stock','target':'knowledge'},{'pattern_role':'flow','target':'practice'}],'falsification_test':'measure'},'13.1':{'claims':[{'id':'c','evidence_coverage':1,'freshness':.8,'source_agreement':1}]},'13.2':{'claim':'x','boundary':{'knowledge_score':.4},'action_driving':True},'17.1':{'challenge':8,'skill':5}}[r]
@pytest.mark.parametrize('r',list(ROWS))
def test_every_atomic_concept_distinctive(r):
 o=run(r,d(r));assert o['atomic_row_id']==r and o['result'] and o['effects_performed']==[]
@pytest.mark.parametrize('r',list(ROWS))
def test_every_atomic_concept_rejects_empty(r):
 with pytest.raises((ValueError,KeyError,TypeError)):run(r,{})
def test_75_consent_scope_minimizes_fields_and_drops_events():
 o=run('7.5',d('7.5'))['result'];assert o['accepted_events'][0]['data']=={'option':'a'} and o['dropped_count']==1 and not o['network_export']
def test_76_revealed_signal_not_stable_preference():assert run('7.6',d('7.6'))['result']['scores'][0]['interpretation']=='revealed signal, not stable preference'
def test_77_deletion_includes_derived_and_not_executed():
 x=d('7.7');x['derived_embedding_ids']=['v'];o=run('7.7',x)['result'];assert o['deletion_plan']['derived_embeddings']==['v'] and not o['executed']
@pytest.mark.parametrize('r,kind',[('8.1','writing_sample'),('8.2','decision'),('8.3','correction')])
def test_81_83_embeddings_are_typed(r,kind):assert run(r,d(r))['result']['kind']==kind
def test_84_index_dimension_rejection():
 x=d('8.4');x['entries'][1]['vector']=[1]
 with pytest.raises(ValueError):run('8.4',x)
def test_85_cosine_retrieval():assert run('8.5',d('8.5'))['result']['query_results'][0]['id']=='a'
def test_86_uncertain_default_asks():
 x=d('8.6');x['preference_signals']=[]
 with pytest.raises(ValueError):run('8.6',x)
def test_91_weekly_cadence():assert len(run('9.1',d('9.1'))['result']['occurrences'])==3
def test_92_only_completed_reviewable():assert run('9.2',d('9.2'))['result']['review_items'][0]['reviewable']
def test_93_unclear_preserved():assert run('9.3',d('9.3'))['result']['unclear_preserved_not_forced']
def test_94_unclear_not_binary():
 x=d('9.4');x['reviews'][0]['label']='unclear';assert not run('9.4',x)['result']['training_signals'][0]['eligible_for_pairwise_training']
def test_95_reward_model_is_proposal_only():
 o=run('9.5',d('9.5'))['result'];assert not o['training_executed'] and not o['behavior_changed']
def test_96_alignment_trend_no_causality():assert run('9.6',d('9.6'))['result']['direction']=='improving' and run('9.6',d('9.6'))['result']['causality_not_inferred']
def test_101_metric_math():assert run('10.1',d('10.1'))['result']['metrics'][0]['change']==pytest.approx(.3)
@pytest.mark.parametrize('r', ['10.2','10.3'])
def test_102_103_self_change_review_gated(r):assert run(r,d(r))['result']['review_state']=='awaiting_exact_review' and not run(r,d(r))['result']['applied']
def test_111_pattern_requires_cross_domain():
 x=d('11.1');x['cases'][1]['domain']='bio'
 with pytest.raises(ValueError):run('11.1',x)
def test_112_transfer_requires_full_mapping_and_test():assert run('11.2',d('11.2'))['result']['ready_for_test'] and not run('11.2',d('11.2'))['result']['transfer_validated']
def test_131_boundary_is_heuristic():assert run('13.1',d('13.1'))['result']['knowledge_score_is_heuristic']
def test_132_uncertain_action_claim_blocks():assert run('13.2',d('13.2'))['result']['block_action_driving_claim']
def test_171_challenge_skill_state():assert run('17.1',d('17.1'))['result']['state']=='anxiety_risk' and run('17.1',d('17.1'))['result']['not_a_diagnosis']
def test_mounted_http_and_invalid():
 a=FastAPI();a.include_router(router);c=TestClient(a)
 assert c.post('/atomic-concepts/47-69/analyze',json={'atomic_row_id':'8.5','data':d('8.5')}).status_code==200
 assert c.post('/atomic-concepts/47-69/analyze',json={'atomic_row_id':'8.5','data':{}}).status_code==422
