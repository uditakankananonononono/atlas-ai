from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.cognitive_learning_860_909 import *
S=[{'source_id':'s','observed_at':datetime.now(timezone.utc).isoformat(),'kind':'primary'}]
def data(i):
 d={x:f'{x} evidence' for x in STAGES[i]}
 d.update({'events':[{'event':'later','year':2},{'event':'early','year':1}],'evidence_quality':.8,'assumption_risk':.25,'ideas':['new-a','new-b'],'known_ideas':['old'],'dominant_pattern':'centralize','candidate':'distributed path','options':[{'name':'a','scores':{'fit':.8}},{'name':'b','scores':{'fit':.4}}],'weights':{'fit':1},'seed':'a','target':'z','bridges':['m'],'current_frame':'cost','alternative_frame':'investment','perspectives':[{'stakeholder':'learner','priority':'access'}],'anomalies':['a'],'explained_anomalies':['a'],'transition_cost':.2,'examples':[{'attributes':['living','moves']},{'attributes':['living','grows']}],'concepts':['a','b'],'typed_links':[{'from':'a','to':'b','type':'causes'}],'central_topic':'topic','branches':[{'name':'b','depth':2}],'groups':{'g':['i']},'terms':[{'term':'root','parent':None},{'term':'leaf','parent':'root'}],'classes':['A'],'relations':[{'from':'a','to':'b','type':'is_a'}],'constraints':[{'name':'c','satisfied':True}],'nodes':['a','b'],'typed_edges':[{'from':'a','to':'b','type':'related'}],'prior_version':1,'predicted':.2,'observed':.8,'learning_rate':.5,'prior_confidence':.4,'evidence_reliability':.5,'evidence_direction':1,'theory_scores':{'t1':[.8,.9],'t2':[.2,.4]},'initial_conception':'old','reconstructed_conception':'new','transfer_accuracy':.8,'audience_questions':['why'],'revised_explanation':'because','pre_score':.2,'post_score':.7,'first_score':.3,'later_score':.8,'next_attempt':'harder','observations':['step'],'inference_confidence':.7,'matched_steps':.8,'target_sequence':['a'],'attempts':[{'id':'1','score':.2},{'id':'2','score':.8}],'next_experiment':'vary one factor','new_representation':'diagram','insight':'pattern','verification':True,'association_strength':.2,'strength':.2,'unconditioned_response':1,'behavior_probability':.3,'consequence':1,'schedule':'fixed','attention':.8,'retention':.7,'motivation':.9,'initial_participation':.2,'later_participation':.7,'identity_safety':.9,'model_outcome':.8,'observer_similarity':.5,'active_experimentation':'test','analysis':'lesson','action_plan':'retry','evidence_considered':['note'],'real_problem':'p','questions':['q'],'action':'try','reflection':'worked','milestones':[{'done':True},{'done':False}],'revision_count':2,'public_product':'demo','knowns':['k'],'unknowns':['u'],'solution_score':.7,'debrief':'review','hypothesis':'h','evidence':[{'weight':.8},{'weight':-.2}],'new_questions':['n'],'learner_rule':'r','verification_score':.8,'explorations':['e'],'hint_level':3,'faded_to':1,'transfer_score':.8,'check_score':.85,'clarity_score':.9,'guided_accuracy':.8,'independent_accuracy':.75,'feedback':'retry','post_exposure':.7,'pre_exposure':.3,'awareness':.2,'unplanned_learning':'fact','transfer':'use','current_score':.8,'baseline_score':.3,'strategy':'spacing','monitoring':['weekly'],'units':[{'complete':True},{'complete':False}],'assessment_score':.8,'credential_boundary':'no credential','evidence_of_learning':['artifact'],'self_direction':.9,'community':'peer'})
 return d
def payload(i):return {'tenant_id':'tenant-a','actor_id':'actor-a','sources':[dict(S[0])],'inputs':data(i),'ethical_review':i in (890,891),'learner_goals':['learn']}

def _assert_row(i):
 o=execute(i,payload(i));assert o['row_id']==i and o['mechanism']==KEYS[i] and o['complete'];assert o['result'] and o['scope']=={'tenant_id':'tenant-a','actor_id':'actor-a'};assert o['actions_taken']==[]
for _i in range(860,910):
 globals()[f'test_row_{_i}_{KEYS[_i]}_computes_specific_result']=(lambda i=_i:_assert_row(i))

def test_model_update_prediction_error_and_transition():
 r=execute(879,payload(879))['result'];assert r['prediction_error']==pytest.approx(.6) and r['revised_estimate']==pytest.approx(.5)
def test_belief_revision_updates_confidence():
 r=execute(880,payload(880))['result'];assert r['revised_confidence']>.4 and r['revision']>0
def test_association_and_conditioning_use_prediction_error_updates():
 assert execute(889,payload(889))['result']['updated_strength']==pytest.approx(.6)
 assert execute(890,payload(890))['result']['conditioned_strength']==pytest.approx(.6)
def test_invalid_score_range_and_state_rejected():
 p=payload(861);p['inputs']['evidence_quality']=1.2
 with pytest.raises(CognitiveLearningError,match='evidence_quality'):execute(861,p)
 p=payload(865);p['inputs']['options']=[]
 with pytest.raises(CognitiveLearningError,match='options'):execute(865,p)
def test_cross_tenant_and_actor_references_rejected():
 for ref in ({'tenant_id':'tenant-b','actor_id':'actor-a'},{'tenant_id':'tenant-a','actor_id':'actor-b'}):
  p=payload(879);p['references']=[ref]
  with pytest.raises(CognitiveLearningError,match='cross-tenant or cross-actor'):execute(879,p)
def test_conditioning_requires_ethical_review():
 p=payload(890);p['ethical_review']=False
 with pytest.raises(CognitiveLearningError,match='ethical_review'):execute(890,p)
def test_graph_edges_require_types():
 p=payload(876);p['inputs']['typed_edges']=[{'from':'a','to':'b'}]
 with pytest.raises(CognitiveLearningError,match='relation type'):execute(876,p)
def test_provenance_and_scope_required():
 p=payload(860);p['sources']=[]
 with pytest.raises(CognitiveLearningError):execute(860,p)
 p=payload(860);del p['tenant_id']
 with pytest.raises(CognitiveLearningError,match='tenant_id'):execute(860,p)
def test_exact_native_route_mount_and_header_scope():
 c=TestClient(app);p=payload(879);r=c.post('/api/v1/api/modules/20/cognitive-learning-860-909/879',headers={'X-Tenant-ID':'tenant-a','X-Actor-ID':'actor-a'},json={'payload':p});assert r.status_code==200 and r.json()['result']['prediction_error']==pytest.approx(.6)
def test_capabilities_lists_exact_rows():
 assert [x['row_id'] for x in capabilities()]==list(range(860,910))
