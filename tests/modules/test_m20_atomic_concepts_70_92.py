import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.atomic_concepts_70_92 import *
def D(r):
 if r=='17.2':return {'skill':5,'available_minutes':60,'tasks':[{'id':'a','challenge':5.5},{'id':'b','challenge':9}]}
 if r in ('19.1','19.2'):return {'claims':[{'id':'c','considered_alternatives':0,'sample_size':3}]}
 if r=='19.3':return {'flags':['confirmation-risk','base-rate-omission']}
 if r in ('20.1','20.2'):return {'options':[{'id':'a','salience':3,'scores':{'quality':1}},{'id':'b','salience':2,'scores':{'quality':5}}],'criteria':[{'id':'quality','weight':1}]}
 if r in ('21.1','21.2'):return {'models':[{'id':'a','prior':.5,'falsifier':'x'},{'id':'b','prior':.5,'falsifier':'y'}],'evidence':{'id':'e','likelihood_by_model':{'a':.2,'b':.8}}}
 if r in ('22.1','22.2'):return {'terminal_values':['health'],'subgoals':[{'id':'work','violates':['health'],'alternative':'bounded work'}]}
 if r in ('27.1','27.2'):return {'uncertainty':.7,'minutes':20}
 if r in ('32.1','32.2','33.1','33.2'):return {'today':'2026-09-21','beliefs':[{'id':'b','formed_at':'2026-01-01','volatility':.8,'confidence':.5}]}
 if r in ('36.1','36.2'):return {'idea':'test a memory aid','captured_at':'2026-09-21','claim':'helps recall','smallest_test':'A/B quiz','next_action':'make cards'}
 if r in ('46.1','46.2'):return {'drivers':[{'id':'demand','states':['high','low']},{'id':'supply','states':['open','closed']}],'no_regret_actions':['monitor'],'triggers':{'high-open':'demand > 10'}}
 if r in ('47.1','47.2'):return {'failure_story':'launch failed','causes':[{'id':'capacity','leading_indicator':'latency','mitigation':'load test','owner':'ops','due':'2026-10-01'}]}
 return {'nodes':['growth','load'],'edges':[{'from':'growth','to':'load','sign':1,'delay':True},{'from':'load','to':'growth','sign':-1}]}
@pytest.mark.parametrize('r',ROWS)
def test_each_atomic_concept_has_distinctive_real_output(r):
 o=run(r,D(r));assert o['atomic_row_id']==r and o['concept']==FEATURES[r] and o['result'] and o['review_required']
def test_flow_picks_challenge_skill_match_and_protects_bounded_block():
 o=run('17.2',D('17.2'))['result'];assert o['next_task']=='a' and o['protected_block_minutes']==60 and o['interruptions_batched']
def test_bias_is_signal_not_diagnosis_and_mitigation_does_not_rewrite():
 x=run('19.1',D('19.1'))['result']['flags'][0];assert {'confirmation-risk','base-rate-omission','small-sample-risk'}<=set(x['signals']) and x['not_a_bias_diagnosis'];assert not run('19.3',D('19.3'))['result']['automatic_rewrite']
def test_fast_intuition_is_unvalidated_then_slow_check_can_disagree():
 assert run('20.1',D('20.1'))['result']['candidate']=='a';x=run('20.2',D('20.2'))['result'];assert x['validated_choice']=='b' and not x['intuition_confirmed']
def test_bayesian_model_update_retains_competitors():
 x=run('21.2',D('21.2'))['result'];assert x['posteriors']['b']==.8 and x['models_retained']
def test_terminal_values_are_not_rewritten_and_proposals_not_applied():
 assert run('22.1',D('22.1'))['result']['terminal_values_immutable_by_engine'];assert not run('22.2',D('22.2'))['result']['applied']
def test_epistemic_calendar_staleness_and_review_are_explicit_heuristics():
 x=run('33.2',D('33.2'))['result'];assert x['schedule_generated'] and x['beliefs'][0]['predicted_staleness']>0 and 'heuristic' in x['model']
def test_scenario_matrix_has_four_nonprobabilistic_futures_and_strategies():
 assert len(run('46.1',D('46.1'))['result']['scenarios'])==4;assert len(run('46.2',D('46.2'))['result']['strategies'])==4
def test_premortem_preventions_have_owner_indicator_due_and_are_unapplied():
 x=run('47.2',D('47.2'))['result'];assert x['preventions'][0]['owner']=='ops' and x['preventions'][0]['leading_indicator']=='latency' and not x['applied']
def test_feedback_loop_polarity_and_delay_without_emergence_claim():
 x=run('50.1',D('50.1'))['result'];assert x['loops'][0]['polarity']=='balancing' and x['loops'][0]['delay_present'] and x['emergent_behavior_not_proven']
@pytest.mark.parametrize('r',ROWS)
def test_every_atomic_concept_fails_closed_on_empty_input(r):
 with pytest.raises((AtomicError,ValueError,KeyError,TypeError)):run(r,{})
def test_mounted_http_success_and_failure():
 c=TestClient(app);ok=c.post('/api/v1/api/modules/20/atomic-concepts-70-92',json={'atomic_row_id':'46.1','data':D('46.1')});assert ok.status_code==200 and len(ok.json()['result']['scenarios'])==4
 assert c.post('/api/v1/api/modules/20/atomic-concepts-70-92',json={'atomic_row_id':'46.1','data':{}}).status_code==422
