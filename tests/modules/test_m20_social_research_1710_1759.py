import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.social_research_1710_1759 import *
from app.modules.m20_general_cognitive_worker.social_research_routes_1710_1759 import router
SRC={'title':'Methods','url':'https://example.org/methods'};ETH={'consent':True,'withdrawal':True,'data_minimization':True}
def S(name,**x):
 p={'research_question':'What shapes access?','population':{'target':'students'},'questions':[{'text':'How easy was access?','type':'scale'}],'source':SRC,'ethics':ETH};p.update(x);return execute(name,p)['result']
def test_exact_catalog():assert [x['row_id'] for x in capabilities()]==list(range(1710,1760))
@pytest.mark.parametrize('n',['survey_design','questionnaire_construction'])
def test_1710_1711_question_review_and_pilot(n):assert S(n)['pilot_plan'] and S(n,questions=[{'text':'Always useful and easy','type':'scale'}])['questionnaire'][0]['flags']==['absolute_or_leading_language','possible_double_barrel']
@pytest.mark.parametrize('n,prob',[('sampling_methods',True),('probability_sampling',True),('non_probability_sampling',False)])
def test_1712_1714_sampling_generalization(n,prob):assert S(n)['sampling_plan']['probability_sample'] is prob
def test_1715_sample_size_and_nonresponse_inflation():
 o=S('sample_size_determination',expected_response_rate=.5)['sample_size'];assert o['invitations_needed']==2*o['completed_needed']
def test_1716_response_improvement_is_noncoercive():assert 'coercion' in S('response_rate_improvement')['response_plan']['prohibited']
def test_1717_mode_effects_keep_calibration_need():assert S('survey_mode_effects',modes={'phone':{'coverage':'listed numbers'}})['mode_effects'][0]['measurement_difference']
def test_1718_interview_has_consent_and_probes():assert 'permission to record' in S('interview_design')['interview_guide']['opening']
def test_1719_focus_group_treats_interaction_as_data():assert 'interaction' in S('focus_group_design')['focus_group']['analysis_unit']
def F(n,**x):
 p={'research_question':'How does work happen?','sites':['site-a'],'source':SRC,'ethics':ETH};p.update(x);return execute(n,p)['result']
def test_1720_ethnography_keeps_three_fieldnote_types():assert F('ethnography')['ethnographic_plan']['fieldnotes']==['descriptive','analytic','reflexive']
def test_1721_participant_observation_blocks_covert_default():assert F('participant_observation')['observation_protocol']['no_covert_observation_without_ethics_approval']
def test_1722_field_research_has_access_safety_contingency():assert set(F('field_research')['field_plan'])>={'access','safety','contingencies'}
def test_1723_case_study_bounds_case_and_rivals():assert F('case_study_design',case_boundary={'place':'x'})['case_design']['rival_explanations_required']
def test_1724_comparative_research_names_selection_logic():assert F('comparative_research')['comparison']['most_similar_or_different']=='most_similar'
def test_1725_cross_cultural_requires_invariance_and_local_review():
 o=F('cross_cultural_research');assert o['cross_cultural']['measurement_invariance_required_before_mean_comparison'] and o['cross_cultural']['local_collaborator_review']
def L(n,obs=None,**x):
 p={'observations':obs or [{'id':'a','time':1,'value':2},{'id':'a','time':2,'value':5}],'source':SRC};p.update(x);return execute(n,p)['result']
def test_1726_longitudinal_preserves_waves_and_confounder_check():assert L('longitudinal_research')['design']['waves']==['1','2']
def test_1727_panel_retention_uses_repeated_ids():assert L('panel_studies')['panel_retention']=={'participants':1,'complete_cases':1}
def test_1728_cohort_checks_immortal_time():assert L('cohort_studies')['cohort_design']['immortal_time_bias_check']
def test_1729_time_series_computes_difference_not_causality():
 o=L('time_series_analysis')['time_series'];assert o['first_difference']==[3.0] and o['causal_claim_requires_identification_strategy']
def I(n,**x):
 p={'texts':[{'id':'t','text':'We can change institutions and power.','context':'meeting'}],'source':SRC};p.update(x);return execute(n,p)['result']
def test_1730_content_analysis_has_unit_codebook_reliability():assert I('content_analysis')['content_analysis']['double_code_and_reconcile']
def test_1731_discourse_attends_power_and_sayability():assert 'What is made sayable or unsayable?' in I('discourse_analysis')['discourse_analysis']['questions']
def test_1732_conversation_analysis_preserves_turn_structure():assert 'turns' in I('conversation_analysis')['conversation_analysis']['transcription']
def test_1733_narrative_preserves_counter_narratives():assert I('narrative_analysis')['narrative_analysis']['preserve_counter_narratives']
def test_1734_thematic_has_six_phases_and_negative_cases():assert len(I('thematic_analysis')['thematic_analysis']['phases'])==6
def test_1735_grounded_theory_uses_constant_comparison_and_sampling():assert 'theoretical sampling' in I('grounded_theory')['grounded_theory']['cycle']
def test_1736_phenomenology_has_textural_and_structural_descriptions():assert {'textural description','structural description'}<=set(I('phenomenology')['phenomenology']['steps'])
def test_1737_hermeneutic_circle_and_alternatives():assert I('hermeneutics')['hermeneutics']['alternative_readings_required']
def test_1738_semiotics_separates_signifier_signified():assert set(I('semiotics',signs=[{'signifier':'red','signified':'danger'}])['semiotics']['signs'][0])>={'signifier','signified'}
def test_1739_structuralism_relations():assert I('structuralism')['structure_reading']['relations_over_isolated_elements']
def test_1740_post_structuralism_refuses_final_meaning():assert not I('post_structuralism')['structure_reading']['authoritative_final_meaning']
@pytest.mark.parametrize('n,concept',[('critical_theory','ideology'),('feminist_theory','intersectionality'),('queer_theory','performativity'),('critical_race_theory','racialization'),('postcolonial_theory','coloniality'),('actor_network_theory','translation')])
def test_1741_1746_theoretical_lenses_are_concept_specific(n,concept):assert concept in I(n)['theoretical_lens']['concepts']
def Y(n,**x):
 p={'actors':[{'id':'a'},{'id':'b'}],'source':SRC};p.update(x);return execute(n,p)['result']
def test_1747_sna_degree_density_and_missing_tie_warning():
 o=Y('social_network_analysis',edges=[{'source':'a','target':'b'}])['network'];assert o['density']==1 and o['degree']['a']==1 and o['missing_ties_are_not_absent_ties']
def test_1748_org_multi_level_and_formal_informal():assert Y('organizational_analysis')['organization']['informal_vs_formal_gap']
def test_1749_institutional_three_pillars():assert Y('institutional_analysis')['institutions']['pillars']==['regulative','normative','cultural-cognitive']
def test_1750_political_economy_keeps_distribution_and_power():assert Y('political_economy')['political_economy']['power_not_reduced_to_price']
@pytest.mark.parametrize('n',['public_choice','rational_choice'])
def test_1751_1752_choice_marks_preferences_as_assumptions(n):assert Y(n)['choice_model']['preferences_are_assumptions_not_observations']
def test_1753_game_theory_equilibrium_not_endorsement():assert Y('game_theory',payoffs={'a':{},'b':{}})['game']['equilibrium_is_not_moral_endorsement']
def test_1754_bargaining_requires_verified_zopa():assert Y('bargaining_theory')['bargaining']['zone_of_possible_agreement_requires_verified_values']
def test_1755_coalition_does_not_erase_ideology():assert Y('coalition_theory')['coalitions']['ideology_and_commitment_not_assumed_away']
def test_1756_voting_counts_ballots_and_requires_turnout_denominator():
 o=Y('voting_theory',ballots=[{'choice':'a'},{'choice':'b'},{'choice':'a'}])['voting'];assert o['winner']=='a' and o['turnout_denominator_required_for_turnout_claim']
def test_1757_social_choice_discloses_impossibility_tradeoffs():assert Y('social_choice')['social_choice']['impossibility_tradeoffs_disclosed']
def test_1758_collective_action_has_free_rider_mechanisms():assert 'monitoring' in Y('collective_action')['collective_action']['mechanisms']
def test_1759_social_movements_distinguishes_visibility_support():assert Y('social_movements')['movement']['do_not_equate_online_visibility_with_support']
def test_validation_and_route_mount():
 with pytest.raises(SocialResearchError):execute('nope',{})
 with pytest.raises(SocialResearchError):execute('survey_design',{'source':SRC})
 app=FastAPI();app.include_router(router,prefix='/m20');c=TestClient(app);assert len(c.get('/m20/social-research-1710-1759/capabilities').json())==50;assert c.post('/m20/social-research-1710-1759/survey_design',json={'payload':{}}).status_code==422
