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

# Static exact nodes with row-distinctive transformed-result equality.
def test_exact_row_860_historical_thinking_transformation():
 assert execute(860,payload(860))['result']=={'changes': [], 'chronology': ['early', 'later'], 'continuities': []}
def test_exact_row_861_critical_thinking_transformation():
 assert execute(861,payload(861))['result']=={'argument_score': 0.6, 'verdict': 'supported'}
def test_exact_row_862_creative_thinking_transformation():
 assert execute(862,payload(862))['result']=={'ideas': ['new-a', 'new-b'], 'novelty_score': 1.0}
def test_exact_row_863_lateral_thinking_transformation():
 assert execute(863,payload(863))['result']=={'indirect_candidate': 'distributed path', 'provocation': 'What if centralize were reversed?'}
def test_exact_row_864_divergent_thinking_transformation():
 assert execute(864,payload(864))['result']=={'flexibility': 0, 'fluency': 2, 'ideas': ['new-a', 'new-b']}
def test_exact_row_865_convergent_thinking_transformation():
 assert execute(865,payload(865))['result']=={'ranking': [{'option': 'a', 'score': 0.8}, {'option': 'b', 'score': 0.4}], 'selected': 'a'}
def test_exact_row_866_associative_thinking_transformation():
 assert execute(866,payload(866))['result']=={'association_path': ['a', 'm', 'z'], 'remote_distance': 2}
def test_exact_row_867_reframing_transformation():
 assert execute(867,payload(867))['result']=={'implication_delta': [], 'new_frame': 'investment', 'old_frame': 'cost'}
def test_exact_row_868_perspective_shifting_transformation():
 assert execute(868,payload(868))['result']=={'perspectives': [{'priority': 'access', 'stakeholder': 'learner'}], 'unresolved': ['u']}
def test_exact_row_869_paradigm_shifting_transformation():
 assert execute(869,payload(869))['result']=={'anomaly_coverage': 1.0, 'transition_cost': 0.2}
def test_exact_row_870_concept_formation_transformation():
 assert execute(870,payload(870))['result']=={'category_rule': 'living', 'defining_attributes': ['living']}
def test_exact_row_871_concept_mapping_transformation():
 assert execute(871,payload(871))['result']=={'cross_link_count': 0, 'edges': [{'from': 'a', 'to': 'b', 'type': 'causes'}], 'nodes': ['a', 'b']}
def test_exact_row_872_mind_mapping_transformation():
 assert execute(872,payload(872))['result']=={'branches': [{'depth': 2, 'name': 'b'}], 'radial_depth': 2, 'root': 'topic'}
def test_exact_row_873_knowledge_organization_transformation():
 assert execute(873,payload(873))['result']=={'groups': {'g': ['i']}, 'retrieval_index': {'i': 'g'}}
def test_exact_row_874_taxonomy_creation_transformation():
 assert execute(874,payload(874))['result']=={'parent_by_term': {'leaf': 'root', 'root': None}, 'roots': ['root']}
def test_exact_row_875_ontology_development_transformation():
 assert execute(875,payload(875))['result']=={'classes': ['A'], 'constraint_violations': [], 'relations': [{'from': 'a', 'to': 'b', 'type': 'is_a'}]}
def test_exact_row_876_semantic_networks_transformation():
 assert execute(876,payload(876))['result']=={'adjacency': {'a': ['b'], 'b': []}, 'edge_types': ['related']}
def test_exact_row_877_schema_development_transformation():
 assert execute(877,payload(877))['result']=={'accommodated': [], 'assimilated': [], 'schema_version': 2}
def test_exact_row_878_mental_model_construction_transformation():
 assert execute(878,payload(878))['result']=={'assumptions_to_test': 'assumptions evidence', 'entities': 'entities evidence', 'predictions': 'predictions evidence'}
def test_exact_row_879_model_updating_transformation():
 assert execute(879,payload(879))['result']=={'prediction_error': 0.6000000000000001,
 'revised_estimate': 0.5,
 'transition': 'prior_model->evidence_checked->revised_model'}
def test_exact_row_880_belief_revision_transformation():
 assert execute(880,payload(880))['result']=={'prior_confidence': 0.4, 'revised_confidence': 0.7, 'revision': 0.29999999999999993}
def test_exact_row_881_theory_change_transformation():
 assert execute(881,payload(881))['result']=={'comparative_fit': {'t1': 0.85, 't2': 0.3}, 'preferred_theory': 't1'}
def test_exact_row_882_conceptual_change_transformation():
 assert execute(882,payload(882))['result']=={'initial_conception': 'old', 'reconstructed_conception': 'new', 'transfer_accuracy': 0.8}
def test_exact_row_883_learning_by_teaching_transformation():
 assert execute(883,payload(883))['result']=={'comprehension_gain': 0.49999999999999994, 'explanation_gaps': ['why'], 'teach_back_revision': 'because'}
def test_exact_row_884_learning_by_doing_transformation():
 assert execute(884,payload(884))['result']=={'attempt_delta': 0.5, 'next_task': 'harder'}
def test_exact_row_885_learning_by_observing_transformation():
 assert execute(885,payload(885))['result']=={'check_required': True, 'inference_confidence': 0.7, 'observed_steps': ['step']}
def test_exact_row_886_learning_by_imitating_transformation():
 assert execute(886,payload(886))['result']=={'adaptations': [], 'fidelity': 0.8, 'sequence': ['a']}
def test_exact_row_887_learning_by_trial_and_error_transformation():
 assert execute(887,payload(887))['result']=={'best_attempt': '2', 'error_reduction': 0.6000000000000001, 'next_experiment': 'vary one factor'}
def test_exact_row_888_learning_by_insight_transformation():
 assert execute(888,payload(888))['result']=={'impasse_restructured_as': 'diagram', 'insight': 'pattern', 'verified': True}
def test_exact_row_889_learning_by_association_transformation():
 assert execute(889,payload(889))['result']=={'prediction_error': 0.8, 'prior_strength': 0.2, 'updated_strength': 0.6}
def test_exact_row_890_classical_conditioning_transformation():
 assert execute(890,payload(890))['result']=={'conditioned_strength': 0.6, 'prediction_error': 0.8, 'transition': 'neutral->paired->conditioned'}
def test_exact_row_891_operant_conditioning_transformation():
 assert execute(891,payload(891))['result']=={'prior_probability': 0.3, 'schedule': 'fixed', 'updated_probability': 0.6499999999999999}
def test_exact_row_892_observational_learning_transformation():
 assert execute(892,payload(892))['result']=={'attention': 0.8, 'reproduction_readiness': 0.504, 'retention': 0.7}
def test_exact_row_893_social_learning_transformation():
 assert execute(893,payload(893))['result']=={'identity_safety': 0.9, 'participation_change': 0.49999999999999994, 'shared_artifacts': 'shared_artifacts evidence'}
def test_exact_row_894_vicarious_learning_transformation():
 assert execute(894,payload(894))['result']=={'direct_practice_needed': True, 'similarity_limits': 'similarity_limits evidence', 'vicarious_value': 0.4}
def test_exact_row_895_experiential_learning_transformation():
 assert execute(895,payload(895))['result']=={'cycle': ['concrete_experience', 'reflective_observation', 'abstract_conceptualization', 'active_experimentation'],
 'next_experiment': 'test'}
def test_exact_row_896_reflective_practice_transformation():
 assert execute(896,payload(896))['result']=={'action_plan': 'retry', 'lesson': 'lesson', 'reflection_depth': 1}
def test_exact_row_897_action_learning_transformation():
 assert execute(897,payload(897))['result']=={'action': 'try', 'problem': 'p', 'question_count': 1, 'reflection': 'worked'}
def test_exact_row_898_project_based_learning_transformation():
 assert execute(898,payload(898))['result']=={'milestone_progress': 0.5, 'product': 'demo', 'revision_count': 2}
def test_exact_row_899_problem_based_learning_transformation():
 assert execute(899,payload(899))['result']=={'debrief': 'review', 'knowns': ['k'], 'learning_issues': ['u'], 'solution_score': 0.7}
def test_exact_row_900_inquiry_based_learning_transformation():
 assert execute(900,payload(900))['result']=={'evidence_balance': 0.6000000000000001, 'hypothesis': 'h', 'new_questions': ['n']}
def test_exact_row_901_discovery_learning_transformation():
 assert execute(901,payload(901))['result']=={'discovered_rule': 'r', 'exploration_count': 1, 'verification_score': 0.8}
def test_exact_row_902_guided_discovery_transformation():
 assert execute(902,payload(902))['result']=={'faded_to': 1, 'hint_level': 3, 'transfer_score': 0.8}
def test_exact_row_903_direct_instruction_transformation():
 assert execute(903,payload(903))['result']=={'instruction_sequence': ['review', 'model', 'guided_practice', 'independent_practice', 'check'],
 'mastery': 0.85,
 'reteach': False}
def test_exact_row_904_explicit_instruction_transformation():
 assert execute(904,payload(904))['result']=={'clarity_check': 0.9, 'feedback': 'retry', 'guided_accuracy': 0.8, 'independent_accuracy': 0.75}
def test_exact_row_905_implicit_learning_transformation():
 assert execute(905,payload(905))['result']=={'awareness': 0.2, 'implicit_evidence': True, 'performance_change': 0.39999999999999997}
def test_exact_row_906_incidental_learning_transformation():
 assert execute(906,payload(906))['result']=={'incidental_gain': 0.49999999999999994, 'transfer': 'use', 'unplanned_learning': 'fact'}
def test_exact_row_907_intentional_learning_transformation():
 assert execute(907,payload(907))['result']=={'goal_progress': 0.5, 'monitoring_points': ['weekly'], 'strategy': 'spacing'}
def test_exact_row_908_formal_learning_transformation():
 assert execute(908,payload(908))['result']=={'assessment_score': 0.8, 'credential_awarded': False, 'curriculum_progress': 0.5}
def test_exact_row_909_informal_learning_transformation():
 assert execute(909,payload(909))['result']=={'community': 'peer', 'daily_learning_evidence': ['artifact'], 'self_direction': 0.9}
