"""Named per-row executable evidence for AI-systems feature rows 1910-1959.

Each row has its own named test asserting row-specific outputs; shared-shape
tests then cover the envelope contract, handler distinctness and validation.
"""
import math
import pytest
from app.modules.m16_executive_dashboard import analysis
from app.modules.m16_executive_dashboard import ai_systems_1910_1959 as ai


def test_row_1910_large_language_models():
 r=analysis.run('large_language_models',{'token_log_probabilities':[-.1,-.2,-.3],'context_window':10})
 o=r['output'];assert r['feature_row']==1910
 assert o['token_count']==3 and o['negative_log_likelihood']==pytest.approx(.2)
 assert o['perplexity']==pytest.approx(math.exp(.2)) and o['bits_per_token']==pytest.approx(.2/math.log(2))
 assert o['context_utilization']==pytest.approx(.3)

def test_row_1911_multimodal_ai():
 o=analysis.run('multimodal_ai',{'modalities':['text','image','audio'],'modality_scores':[.9,.5,.7],'weights':[.5,.25,.25]})['output']
 assert o['fused_score']==pytest.approx(.75) and o['weakest_modality']=='image'
 assert o['modality_gap']==pytest.approx(.4) and o['fusion_weight_entropy']>0

def test_row_1912_vision_language_models():
 o=analysis.run('vision_language_models',{'image_ids':['a','b','c'],'captions':['x','y','z'],'similarities':[.8,.3,.6]},{'threshold':.5})['output']
 assert o['grounded_pairs']==2 and o['grounding_rate']==pytest.approx(2/3) and o['below_threshold_images']==['b']

def test_row_1913_text_to_image_generation():
 o=analysis.run('text_to_image_generation',{'prompt':'red fox forest','artifact_description':'red fox in a forest','quality_scores':[.8,.9],'width':512,'height':512,'requested_width':1024,'requested_height':512,'provenance':'c2pa','watermark':True})['output']
 assert o['resolution_match'] is False and o['prompt_adherence']==pytest.approx(1.0)
 assert o['megapixels']==pytest.approx(.2621,abs=1e-3) and o['provenance_present'] and o['watermark_present']

def test_row_1914_text_to_video_generation():
 o=analysis.run('text_to_video_generation',{'prompt':'waves','artifact_description':'ocean waves','frame_quality_scores':[.9,.8,.4,.85],'fps':2,'duration_seconds':2})['output']
 assert o['worst_frame_index']==2 and o['temporal_flicker']==pytest.approx((.1+.4+.45)/3)
 assert o['expected_frame_count']==4 and o['scored_frame_coverage']==pytest.approx(1)

def test_row_1915_text_to_3d_generation():
 o=analysis.run('text_to_3d_generation',{'vertex_count':100,'face_count':180,'non_manifold_edges':0,'watertight':True,'bounding_box':{'x':2,'y':3,'z':4}},{'max_faces':200})['output']
 assert o['bounding_volume']==24 and o['manifold_ok'] and o['within_triangle_budget']
 assert o['face_to_vertex_ratio']==pytest.approx(1.8)

def test_row_1916_text_to_audio_generation():
 o=analysis.run('text_to_audio_generation',{'sample_rate_hz':44100,'duration_seconds':2,'peak_amplitude':.9,'rms_amplitude':.3,'clipping_samples':10,'total_samples':88200})['output']
 assert o['sample_rate_ok'] and o['crest_factor']==pytest.approx(3)
 assert o['estimated_loudness_dbfs']==pytest.approx(20*math.log10(.3)) and o['clipping_rate']==pytest.approx(10/88200)

def test_row_1917_music_generation():
 o=analysis.run('music_generation',{'note_events':[{'pitch_class':0,'duration':1},{'pitch_class':4,'duration':1},{'pitch_class':7,'duration':2}],'declared_key':0,'tempo_bpm_samples':[120,120,121]})['output']
 assert o['note_count']==3 and o['key_correlation']>.5 and o['mean_tempo_bpm']==pytest.approx(120.333,abs=.001)
 assert o['tempo_stability']==pytest.approx(1/(1+math.sqrt(2/9)))

def test_row_1918_voice_cloning():
 ok=analysis.run('voice_cloning',{'consent_verified':True,'provenance':'signed','watermark':True,'identity_similarity':.92,'speaker_verification_score':.88})['output']
 assert ok['release_allowed'] and ok['similarity_above_threshold'] and ok['risk_flags']==[]
 no=analysis.run('voice_cloning',{'consent_verified':False,'provenance':None,'watermark':True,'identity_similarity':.92,'speaker_verification_score':.88})['output']
 assert not no['release_allowed'] and 'missing_consent' in no['risk_flags'] and 'missing_provenance' in no['risk_flags']

def test_row_1919_deepfakes():
 o=analysis.run('deepfakes',{'consent_verified':False,'provenance':None,'watermark':False,'face_swap_artifact_score':.9,'temporal_inconsistency':.8,'identity_similarity':.95})['output']
 assert o['release_blocked'] and o['recommended_action']=='block_release'
 assert o['manipulation_risk_score']==pytest.approx(.5*.9+.3*.8+.2*.95)
 assert set(o['risk_flags'])>={'missing_consent','missing_provenance','missing_watermark'}

def test_row_1920_ai_art():
 o=analysis.run('ai_art',{'palette':['#ff0000','#00ff00'],'reference_palette':['#fe0000','#00fe00'],'composition_focal_point':{'x':33,'y':33},'canvas':{'width':99,'height':99},'style_match_scores':[.8,.9],'provenance':'c2pa'})['output']
 assert o['palette_mean_distance']==pytest.approx(1.0) and o['rule_of_thirds_score']==pytest.approx(1.0)
 assert o['mean_style_match']==pytest.approx(.85)

def test_row_1921_ai_writing():
 o=analysis.run('ai_writing',{'text':'A sourced claim. Another short sentence.','sources':['s1'],'claims':['c1','c2']})['output']
 assert o['word_count']==6 and o['sentence_count']==2 and o['citation_coverage']==pytest.approx(.5)
 assert o['uncited_claims']==1 and isinstance(o['flesch_kincaid_grade'],float)

def test_row_1922_ai_coding():
 o=analysis.run('ai_coding',{'tests_passed':[10,6],'tests_total':[10,6],'coverage_percent':85,'static_analysis_issues':0,'dependency_scan_clean':True})['output']
 assert o['pass_rate']==1 and o['coverage_ok'] and o['quality_gate_passed'] and o['failing_suites']==[]
 bad=analysis.run('ai_coding',{'tests_passed':[5],'tests_total':[10],'coverage_percent':50,'static_analysis_issues':3,'dependency_scan_clean':False})['output']
 assert not bad['quality_gate_passed'] and bad['failing_suites']==[0]

def test_row_1923_ai_agents():
 o=analysis.run('ai_agents',{'steps':[{'irreversible':False},{'irreversible':True,'approved':True}],'goal_completed':True,'human_overrides':1})['output']
 assert o['approval_coverage']==1 and o['safe_to_execute'] and o['human_overrides']==1
 unsafe=analysis.run('ai_agents',{'steps':[{'irreversible':True,'approved':False}]})['output']
 assert not unsafe['safe_to_execute'] and unsafe['approval_coverage']==0

def test_row_1924_autonomous_agents():
 o=analysis.run('autonomous_agents',{'steps':[{'human_assisted':False},{'human_assisted':False},{'human_assisted':True}],'human_overrides':1,'escalation_events':1,'constraint_violations':[],'goal_completed':True},{'max_overrides':1})['output']
 assert o['autonomy_index']==pytest.approx(2/3) and o['override_rate']==pytest.approx(1/3) and o['autonomy_acceptable']
 viol=analysis.run('autonomous_agents',{'steps':[{'human_assisted':False}],'constraint_violations':['speed']})['output']
 assert not viol['autonomy_acceptable'] and viol['constraint_violation_count']==1

def test_row_1925_multi_agent_systems():
 o=analysis.run('multi_agent_systems',{'agents':['a','b','c'],'delegations':[{'from':'a','to':'b'},{'from':'b','to':'c'},{'from':'a','to':'zz'}]})['output']
 assert len(o['invalid_delegations'])==1 and o['max_delegation_depth']==3 and o['delegation_cycles']==[]
 cyc=analysis.run('multi_agent_systems',{'agents':['a','b'],'delegations':[{'from':'a','to':'b'},{'from':'b','to':'a'}]})['output']
 assert cyc['delegation_cycles']

def test_row_1926_agent_communication():
 msgs=[{'sender':'a','recipient':'b','type':'request','correlation_id':'1'},{'sender':'b','recipient':'a','type':'reply','correlation_id':'1','in_reply_to':'m0'},{'sender':'a','recipient':'b','type':'request','correlation_id':'2'},{'sender':'a','type':'shout','correlation_id':'3'}]
 o=analysis.run('agent_communication',{'messages':msgs})['output']
 assert o['schema_valid_rate']==pytest.approx(.75) and o['orphan_request_correlations']==['2']
 assert o['protocol_violations']==[3] and o['correlation_ids']==3

def test_row_1927_agent_coordination():
 o=analysis.run('agent_coordination',{'tasks':[{'id':'a','owner':'x','depends_on':[]},{'id':'b','owner':None,'depends_on':['a']},{'id':'c','owner':'y','depends_on':['b']}]})['output']
 assert o['unowned_tasks']==1 and o['ready_tasks']==['a'] and o['critical_path_length']==3 and not o['has_cycle']

def test_row_1928_agent_negotiation():
 o=analysis.run('agent_negotiation',{'offers':['x','y','z'],'utilities':[.4,.8,.6]},{'reservation_utility':.5})['output']
 assert o['agreement_possible'] and o['selected_offer']=='y' and o['utility_gap_to_reservation']==pytest.approx(.3)
 none=analysis.run('agent_negotiation',{'offers':['x'],'utilities':[.1]},{'reservation_utility':.5})['output']
 assert not none['agreement_possible'] and none['selected_offer'] is None

def test_row_1929_agent_learning():
 o=analysis.run('agent_learning',{'before_scores':[.5,.6],'after_scores':[.7,.55]})['output']
 assert o['mean_gain']==pytest.approx(.075) and o['improved_fraction']==pytest.approx(.5) and o['regressions']==[1]

def test_row_1930_reinforcement_learning_from_human_feedback():
 o=analysis.run('reinforcement_learning_from_human_feedback',{'chosen_rewards':[1,2,3,0],'rejected_rewards':[0,1,2,1]})['output']
 assert o['preference_accuracy']==pytest.approx(.75) and o['ties']==0 and o['pair_count']==4
 lo,hi=o['accuracy_ci95'];assert lo<.75<hi

def test_row_1931_constitutional_ai():
 o=analysis.run('constitutional_ai',{'principles':['safe','honest'],'critiques':['safe critique','honest critique'],'revisions':['r1','r2']})['output']
 assert o['chain_complete'] and o['principle_critique_coverage']==1
 gap=analysis.run('constitutional_ai',{'principles':['safe','fair'],'critiques':['safe critique'],'revisions':[]})['output']
 assert gap['uncritiqued_principles']==['fair'] and not gap['chain_complete']

def test_row_1932_ai_alignment():
 o=analysis.run('ai_alignment',{'intended_scores':[1,.5],'observed_scores':[.9,.2]},{'tolerance':.15})['output']
 assert o['within_tolerance_rate']==pytest.approx(.5) and o['misaligned_cases']==[1] and o['worst_case_index']==1

def test_row_1933_ai_safety():
 o=analysis.run('ai_safety',{'hazard_severity':[3,2],'hazard_likelihood':[.2,.1],'detectability':[1,2]},{'threshold':.5})['output']
 assert o['risk_priority_numbers']==[pytest.approx(.6),pytest.approx(.4)]
 assert o['unacceptable_hazards']==[0] and o['top_hazard_index']==0

def test_row_1934_ai_ethics():
 o=analysis.run('ai_ethics',{'principles':['privacy','fairness'],'evidence':{'privacy':'impact-assessment.pdf'}})['output']
 assert o['coverage']==pytest.approx(.5) and o['gaps']==['fairness']
 assert o['review_recommendation']=='close_gaps_before_claiming_conformance'
 assert o['per_principle_status']==[{'principle':'privacy','evidenced':True},{'principle':'fairness','evidenced':False}]

def test_row_1935_explainable_ai():
 o=analysis.run('explainable_ai',{'feature_names':['age','income'],'feature_importance':[.2,.8],'score_full':.9,'score_without_top':.5})['output']
 assert o['top_feature']=='income' and o['faithfulness_drop']==pytest.approx(.4) and o['faithful']
 assert o['ranked_features'][0]['share']==pytest.approx(.8)

def test_row_1936_interpretable_ai():
 o=analysis.run('interpretable_ai',{'num_features_used':5,'max_rule_depth':2,'num_rules':8,'monotonicity_checks':[{'feature':'income','violations':0}],'surrogate_fidelity':.95})['output']
 assert o['globally_interpretable'] and o['monotonicity_ok'] and o['complexity_score']==5*3+8
 bad=analysis.run('interpretable_ai',{'num_features_used':5,'max_rule_depth':6,'num_rules':50,'monotonicity_checks':[{'feature':'x','violations':2}]})['output']
 assert not bad['globally_interpretable'] and bad['monotonicity_violations']==2

def test_row_1937_fair_ai():
 o=analysis.run('fair_ai',{'groups':['a','a','b','b'],'selected':[1,0,1,1],'positive_labels':[1,1,1,1]})['output']
 assert o['demographic_parity_difference']==pytest.approx(.5) and o['selection_rate_ratio']==pytest.approx(.5)
 assert o['equal_opportunity_difference']==pytest.approx(.5) and o['group_metrics']['a']['n']==2

def test_row_1938_responsible_ai():
 o=analysis.run('responsible_ai',{'dimensions':['safety','fairness'],'scores':[.9,.8],'weights':[1,1]},{'threshold':.7})['output']
 assert o['weighted_score']==pytest.approx(.85) and o['weakest_dimension']=='fairness'
 assert o['all_thresholds_met'] and o['maturity_level']=='established'

def test_row_1939_trustworthy_ai():
 o=analysis.run('trustworthy_ai',{'calibration_errors':[.02,.04],'robustness_scores':[.9,.85],'privacy_budget_epsilon':.5})['output']
 assert o['expected_calibration_error']==pytest.approx(.03) and o['trust_certificate_ready']
 over=analysis.run('trustworthy_ai',{'calibration_errors':[.2],'robustness_scores':[.5],'privacy_budget_epsilon':3})['output']
 assert not over['trust_certificate_ready'] and not over['privacy_ok'] and not over['robustness_ok']

def test_row_1940_ai_governance():
 o=analysis.run('ai_governance',{'roles':[{'name':'owner','responsibilities':['risk'],'filled':True},{'name':'reviewer','responsibilities':[],'filled':False}],'policies':['p1'],'review_cadence_days':90,'incident_process_documented':True})['output']
 assert o['unfilled_roles']==['reviewer'] and o['roles_without_responsibilities']==['reviewer']
 assert o['cadence_ok'] and not o['board_ready']

def test_row_1941_ai_regulation():
 o=analysis.run('ai_regulation',{'jurisdiction':'EU','requirements':['notice','records'],'evidence':{'notice':'disclosure-page'}})['output']
 assert o['decision']=='evidence_incomplete' and o['gaps']==['records'] and o['compliance_rate']==pytest.approx(.5)
 full=analysis.run('ai_regulation',{'jurisdiction':'EU','requirements':['notice'],'evidence':{'notice':'x'}})['output']
 assert full['decision']=='ready_for_counsel_review'

def test_row_1942_ai_policy():
 o=analysis.run('ai_policy',{'policy_statements':['no-pii-in-logs','human-approval'],'controls':{'no-pii-in-logs':'log-scrubber'},'violations':[{'statement':'human-approval','severity':'high'}]})['output']
 assert o['conformance_rate']==pytest.approx(.5) and o['uncontrolled_statements']==['human-approval']
 assert o['violations_by_severity']=={'high':1} and o['enforcement_review_needed']

def test_row_1943_ai_standards():
 o=analysis.run('ai_standards',{'standard':'ISO/IEC 42001:2023','clauses':['c4','c5','c6'],'conformity':{'c4':{'conforms':True},'c5':{'conforms':False,'severity':'minor'}}})['output']
 assert o['clause_coverage']==pytest.approx(1/3) and o['major_nonconformities']==1
 assert o['certification_body_review']=='not_eligible'

def test_row_1944_ai_auditing():
 o=analysis.run('ai_auditing',{'controls':[{'id':'c1','result':'pass','evidence':'log'},{'id':'c2','result':'fail','evidence':'ticket'},{'id':'c3','result':'pass'}]})['output']
 assert o['exception_rate']==pytest.approx(1/3) and o['controls_without_evidence']==['c3']
 assert o['audit_opinion']=='qualified'

def test_row_1945_ai_certification():
 o=analysis.run('ai_certification',{'required_artifacts':['audit-report','scope'],'submitted':{'audit-report':'doc1'},'accredited_body':True,'surveillance_audit_due_days':15})['output']
 assert o['missing_artifacts']==['scope'] and o['expiry_risk'] and not o['certification_eligible']

def test_row_1946_ai_testing():
 o=analysis.run('ai_testing',{'partitions':[{'name':'nominal','cases':10,'passed':10},{'name':'boundary','cases':5,'passed':4}],'edge_cases_total':8,'edge_cases_tested':8})['output']
 assert o['overall_pass_rate']==pytest.approx(14/15) and o['edge_case_coverage']==1 and o['adequacy_decision']=='inadequate'
 assert o['partition_results'][1]['pass_rate']==pytest.approx(.8)

def test_row_1947_ai_verification():
 o=analysis.run('ai_verification',{'properties':[{'name':'no-negative-balance','holds':True,'checked_cases':1000},{'name':'idempotent-retry','holds':False,'checked_cases':40},{'name':'bounded-queue','holds':True,'checked_cases':0}]})['output']
 assert o['counterexample_properties']==['idempotent-retry'] and o['unchecked_properties']==['bounded-queue']
 assert not o['verification_complete'] and o['proof_obligation_coverage']==pytest.approx(2/3)

def test_row_1948_ai_validation():
 o=analysis.run('ai_validation',{'stakeholder_needs':[{'id':'n1','acceptance_criteria':['fast','accurate'],'met_criteria':['fast','accurate']},{'id':'n2','acceptance_criteria':['cheap'],'met_criteria':[]}]})['output']
 assert o['validation_rate']==pytest.approx(.5) and o['unmet_needs']==['n2'] and not o['fit_for_purpose']

def test_row_1949_ai_assurance():
 o=analysis.run('ai_assurance',{'claims':[{'id':'c1','evidence_ids':['e1']},{'id':'c2','evidence_ids':[]}],'evidence_items':[{'id':'e1','independent':True}],'critical_claim_ids':['c2']})['output']
 assert o['claim_support_rate']==pytest.approx(.5) and o['unsupported_critical_claims']==['c2']
 assert not o['assurance_ready'] and o['independent_evidence_rate']==pytest.approx(.5)

def test_row_1950_foundation_models():
 o=analysis.run('foundation_models',{'benchmark_categories':[{'category':'reasoning','score':.8,'baseline':.6},{'category':'coding','score':.5,'baseline':.7}]})['output']
 assert o['aggregate_score']==pytest.approx(.65) and o['strongest_category']=='reasoning'
 assert o['weakest_category']=='coding' and o['capability_breadth']==pytest.approx(.5)

def test_row_1951_pre_trained_models():
 o=analysis.run('pre_trained_models',{'downstream_tasks':['a','b'],'scores':[.8,.7],'baselines':[.5,.7]})['output']
 assert o['mean_gain_over_baseline']==pytest.approx(.15) and o['tasks_below_baseline']==[]
 assert o['mean_transfer_ratio']==pytest.approx((1.6+1)/2)

def test_row_1952_fine_tuning():
 o=analysis.run('fine_tuning',{'before_scores':[.5,.6],'after_scores':[.8,.7],'retained_base_scores':[.48,.59]},{'min_gain':.05})['output']
 assert o['mean_task_gain']==pytest.approx(.2) and o['gain_material']
 assert o['forgetting_rate']==pytest.approx(1-1.07/1.1) and o['regressed_tasks']==[]

def test_row_1953_transfer_learning():
 o=analysis.run('transfer_learning',{'scratch_scores':[.5,.5],'transfer_scores':[.7,.8],'scratch_examples':[100,100],'transfer_examples':[20,25]})['output']
 assert o['mean_performance_gain']==pytest.approx(.25) and o['positive_transfer_rate']==1
 assert o['data_savings_percent']==pytest.approx(77.5)

def test_row_1954_few_shot_learning():
 o=analysis.run('few_shot_learning',{'predictions':['a','b','c'],'targets':['a','c','c'],'shots':4,'zero_shot_baseline_accuracy':.3,'prompt_tokens':120})['output']
 assert o['accuracy']==pytest.approx(2/3) and o['lift_over_zero_shot']==pytest.approx(2/3-.3)
 assert o['accuracy_per_shot']==pytest.approx((2/3-.3)/4)

def test_row_1955_zero_shot_learning():
 o=analysis.run('zero_shot_learning',{'predictions':['a','b'],'targets':['a','b'],'shots':0,'prompt_tokens':20})['output']
 assert o['shots']==0 and o['accuracy']==1 and o['instruction_only']

def test_row_1956_in_context_learning():
 o=analysis.run('in_context_learning',{'demonstration_counts':[0,2,4],'accuracies':[.5,.7,.705],'context_tokens_used':900,'context_window':1000})['output']
 assert o['gain_per_demonstration']==pytest.approx((.705-.5)/4) and o['plateau_detected']
 assert o['context_utilization']==pytest.approx(.9) and not o['context_exhausted']

def test_row_1957_prompt_engineering():
 o=analysis.run('prompt_engineering',{'variants':['short','long','mid'],'scores':[.8,.9,.85],'token_counts':[10,100,40]},{'token_penalty':.001})['output']
 assert o['selected_variant']=='mid' and o['efficiency_score_per_token']==pytest.approx(.85/40)
 assert set(o['pareto_optimal_variants'])=={'short','long','mid'}

def test_row_1958_chain_of_thought():
 o=analysis.run('chain_of_thought',{'steps':['identify','calculate','verify'],'final_answer':4,'expected_answer':4,'step_verifications':[True,False,False]},{'return_trace':False})['output']
 assert o['final_correct'] and o['verification_rate']==pytest.approx(1/3) and o['first_unverified_step_index']==1
 assert not o['trace_exposed']

def test_row_1959_tree_of_thought():
 nodes=[{'id':'root','parent':None,'score':0},{'id':'a','parent':'root','score':.7},{'id':'b','parent':'root','score':.9},{'id':'b1','parent':'b','score':.95}]
 o=analysis.run('tree_of_thought',{'nodes':nodes})['output']
 assert o['best_leaf_id']=='b1' and o['best_path']==['root','b','b1'] and o['explored_depth']==3
 assert o['pruned_node_count']==1 and o['mean_branching_factor']==pytest.approx(1.5)


def test_every_row_has_its_own_handler_summary_and_inputs():
 assert len(ai.ROWS)==50 and sorted(ai.ROWS.values())==list(range(1910,1960))
 funcs={id(f) for f in ai.HANDLERS.values()}
 assert len(funcs)==50,'rows must not share a handler function'
 assert set(ai.HANDLERS)==set(ai.ROWS)==set(ai.SUMMARIES)==set(ai.INPUTS)
 assert len(set(ai.SUMMARIES.values()))==50 and len({tuple(v) for v in ai.INPUTS.values()})==50

def test_envelope_contract_echoes_inputs_and_declares_no_external_effects():
 data={'predictions':['a'],'targets':['a'],'shots':0}
 r=analysis.run('zero_shot_learning',data,{'k':'v'},seed=3)
 assert r['feature_row']==1955 and r['method']=='zero_shot_learning' and r['inputs']=={'data':data,'params':{'k':'v'}}
 assert r['external_effects'].startswith('none') and isinstance(r['assumptions'],list) and isinstance(r['method_limits'],list)

def test_unknown_method_and_bad_envelope_inputs_fail():
 with pytest.raises(ValueError):analysis.run('not_a_row_method',{})
 with pytest.raises(ValueError):ai.run('zero_shot_learning',['not-a-dict'])

def test_invalid_row_inputs_fail_loudly():
 with pytest.raises(ValueError):analysis.run('zero_shot_learning',{'predictions':[1],'targets':[1],'shots':1})
 with pytest.raises(ValueError):analysis.run('few_shot_learning',{'predictions':[1],'targets':[1],'shots':0})
 with pytest.raises(ValueError):analysis.run('ai_coding',{'tests_passed':[2],'tests_total':[1],'coverage_percent':90,'static_analysis_issues':0,'dependency_scan_clean':True})
 with pytest.raises(ValueError):analysis.run('fair_ai',{'groups':['a'],'selected':[1,0],'positive_labels':[1]})
 with pytest.raises(ValueError):analysis.run('large_language_models',{'token_log_probabilities':[float('nan')]})
 with pytest.raises(ValueError):analysis.run('ai_coordination'.replace('ai_','agent_'),{'tasks':[{'id':'a','depends_on':['a']}]})
 with pytest.raises(ValueError):analysis.run('text_to_audio_generation',{'sample_rate_hz':44100,'duration_seconds':1,'peak_amplitude':.5,'rms_amplitude':.9,'clipping_samples':0,'total_samples':44100})
 with pytest.raises(ValueError):analysis.run('tree_of_thought',{'nodes':[{'id':'a','parent':None},{'id':'a','parent':None}]})
