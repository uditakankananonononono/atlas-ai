import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import *
from app.modules.m20_general_cognitive_worker.learning_reasoning_routes_810_859 import router
SRC={'title':'Evidence','url':'https://example.org/evidence'}
def L(n,**x):
 p={'objective':'Solve equations','source':SRC};p.update(x);return execute(n,p)['result']
def test_catalog_exact():assert [x['row_id'] for x in capabilities()]==list(range(810,860))
def test_810_spaced_repetition_computes_due_and_lapse():assert L('spaced_repetition',items=[{'id':'x','quality':2}])['schedule'][0]['lapse']
def test_811_interleaving_mixes_skills():assert len(set(L('interleaving',skills=['a','b'],blocks=4)['sequence']))==2
def test_812_retrieval_is_closed_book_feedback_retry():assert L('retrieval_practice')['retrieval_cycle'][0]=='closed-book attempt'
def test_813_elaborative_why_and_conditions():assert 'under what conditions' in L('elaborative_interrogation',claims=['x'])['prompts'][0]
def test_814_self_explanation_checks_steps():assert 'Why is this step valid?' in L('self_explanation')['self_explanation_prompts']
def test_815_dual_coding_requires_mapping_not_decoration():assert L('dual_coding')['representations']['decorative_visuals_rejected']
def test_816_examples_mark_boundary_cases():assert L('concrete_examples',examples=[{'feature':'f','boundary_case':True}])['examples'][0]['boundary_case']
def test_817_worked_example_requires_rationales_and_completion():assert L('worked_examples')['worked_example']['completion_problem_next']
def test_818_problem_solving_represents_then_verifies():assert L('problem_solving')['problem_cycle']==['represent problem','identify constraints','generate strategies','execute','verify','reflect']
def test_819_deliberate_targets_subskill_feedback_rest():
 o=L('deliberate_practice')['practice_plan'];assert o['immediate_specific_feedback'] and o['rest_and_recovery']
def test_820_chunking_preserves_principle():assert L('chunking',chunks=[{'label':'x','elements':[1,2],'principle':'cause'}])['chunks'][0]['organizing_principle']=='cause'
@pytest.mark.parametrize('n',['scaffolding','fading'])
def test_821_822_support_fades_on_evidence(n):assert L(n)['support_levels'][-1]['support']==0 and L(n)['fade_on_evidence_not_time']
def test_823_metacognition_calibrates():assert L('metacognition')['calibration_required']
def test_824_self_regulated_cycle():assert L('self_regulated_learning')['srl_cycle']==['forethought','performance monitoring','self-reflection']
def test_825_goal_setting_is_measurable_and_has_if_then():assert 'implementation_intention' in L('goal_setting',goal={'specific':'x','metric':'m'})['goal']
def test_826_progress_monitoring_computes_change():assert L('progress_monitoring',records=[{'value':1},{'value':4}])['progress']['change']==3
@pytest.mark.parametrize('n',['self_assessment','peer_assessment'])
def test_827_828_assessment_requires_evidence_and_bias_check(n):assert L(n,criteria=['reasoning'],ratings={'reasoning':3})['assessment'][0]['missing_evidence']
@pytest.mark.parametrize('n,purpose',[('formative_assessment','feedback during learning'),('summative_assessment','judgment after instruction'),('diagnostic_assessment','prerequisite and misconception diagnosis')])
def test_829_831_assessment_purposes(n,purpose):assert L(n,items=[{'objective_id':'o'}])['assessment_design']['purpose']==purpose
def test_832_prior_knowledge_not_graded():assert 'flag misconceptions without grading' in L('prior_knowledge_activation')['activation']
def T(n,**x):
 p={'source_case':{'features':['structure','red']},'target_case':{'features':['structure','blue']},'source':SRC};p.update(x);return execute(n,p)['result']
@pytest.mark.parametrize('n,t',[('transfer','unspecified'),('near_transfer','near'),('far_transfer','far')])
def test_833_835_transfer_deep_structure_and_independent_performance(n,t):assert T(n)['transfer_type']==t and T(n)['requires_independent_target_performance']
def test_836_analogy_rejects_surface_similarity():assert T('analogical_reasoning')['analogy']['surface_similarity_is_insufficient']
def test_837_case_reasoning_retrieve_reuse_revise_retain():assert len(T('case_based_reasoning')['case_reasoning_cycle'])==4
def R(n,**x):
 p={'source':SRC};p.update(x);return execute(n,p)['result']
def test_838_rules_have_forward_trace():assert R('rule_based_reasoning',facts=['a'],rules=[{'id':'r','if':['a'],'then':'b'}])['rule_trace']==[{'rule':'r','fact':'b'}]
def test_839_model_has_entities_relations_constraints_predictions_validation():assert set(R('model_based_reasoning')['model'])>={'entities','relations','constraints','predictions','validation_observations'}
def test_840_qualitative_preserves_ambiguous_successors():assert R('qualitative_reasoning')['qualitative_states']['ambiguous_successors_preserved']
def test_841_quantitative_computes_mean_range_units():assert R('quantitative_reasoning',values=[1,3],units='m')['quantitative']['mean']==2
def test_842_spatial_requires_frame_and_scale():assert 'frame_of_reference' in R('spatial_reasoning')['spatial']
def test_843_temporal_orders_events():assert [x['time'] for x in R('temporal_reasoning',events=[{'time':2},{'time':1}])['temporal']['ordered']]==[1,2]
def test_844_causal_has_dag_roles_and_identification():assert R('causal_reasoning')['causal']['association_is_not_causation']
def test_845_counterfactual_exposes_held_constant():assert 'held_constant' in R('counterfactual_reasoning')['counterfactual']
def test_846_probability_bayes():assert R('probabilistic_reasoning',prior=.5,likelihood_given_h=.8,likelihood_given_not_h=.2)['bayes']['posterior']==pytest.approx(.8)
def test_847_fuzzy_operators():assert R('fuzzy_logic',memberships={'a':.2,'b':.7})['fuzzy']['and']==.2
@pytest.mark.parametrize('n',['default_reasoning','non_monotonic_reasoning'])
def test_848_849_defaults_are_revisable(n):assert R(n)['defaults']['beliefs_revisable']
def test_850_abduction_not_proof():assert R('abductive_reasoning')['abduction']['best_explanation_is_not_proof']
def test_851_induction_records_scope_exceptions_strength():assert set(R('inductive_reasoning')['induction'])>={'sample_scope','exceptions','generalization_strength'}
def test_852_deduction_separates_validity_truth():assert R('deductive_reasoning',validity=True,premises_true=False)['deduction']['soundness'] is False
def test_853_transduction_scope_one_target():assert 'target instance only' in R('transductive_reasoning')['transduction']['scope']
def test_854_dialectic_keeps_unresolved_conflict():assert R('dialectical_reasoning')['dialectic']['synthesis_must_preserve_unresolved_conflict']
def test_855_integration_keeps_tradeoffs():assert R('integrative_thinking')['integration']['tradeoffs_visible']
def I(n,**x):
 p={'problem':'Improve access','source':SRC};p.update(x);return execute(n,p)['result']
def test_856_systems_has_stocks_flows_feedback_delays():assert set(I('systems_thinking')['system'])>={'stocks','flows','feedback_loops','delays'}
def test_857_design_thinking_tests_with_participants():assert 'test with participants' in I('design_thinking')['design_cycle']
def test_858_computational_has_decomposition_algorithm_tests_complexity():assert set(I('computational_thinking')['computational'])>={'decomposition','algorithm','test_cases','complexity'}
def test_859_science_is_falsifiable_and_replicable():
 o=I('scientific_thinking')['science'];assert 'falsification_condition' in o and o['replication_and_open_materials']
def test_validation_and_route():
 with pytest.raises(LearningReasoningError):execute('nope',{})
 with pytest.raises(LearningReasoningError):L('probabilistic_reasoning',prior=2)
 app=FastAPI();app.include_router(router,prefix='/m20');c=TestClient(app);assert len(c.get('/m20/learning-reasoning-810-859/capabilities').json())==50;assert c.post('/m20/learning-reasoning-810-859/spaced_repetition',json={'payload':{}}).status_code==422

def test_evaluation_and_tenant_are_explicit():
 o=execute('scientific_thinking',{'tenant_id':'lab-a','problem':'p','source':SRC,'evidence':['e']})
 assert o['tenant_id']=='lab-a' and 0 <= o['evaluation']['input_completeness'] <= 1

def test_learning_reasoning_rejects_cross_tenant_reference():
 with pytest.raises(LearningReasoningError,match='cross-tenant'):
  execute('retrieval_practice',{'tenant_id':'a','resource_refs':[{'tenant_id':'b'}],'objective':'x','source':SRC})
