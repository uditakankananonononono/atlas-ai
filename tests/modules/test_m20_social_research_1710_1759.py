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

# --- audit family D: distinctive per-row metrics, failure paths, tenant boundary
def M(n,p,**x):return execute(n,p,**x)['result']['metrics'] if x else execute(n,p)['result']['metrics']
def test_1710_1711_questionnaire_metrics():
 m=execute('survey_design',{'research_question':'q','population':{'target':'students'},'questions':[{'text':'How easy?','type':'scale'}],'source':SRC})['result']['metrics']
 assert m['item_count']==1 and m['closed_items_without_response_options']==['q1'] and m['flag_rate']==0
 m=execute('questionnaire_construction',{'research_question':'q','population':{'target':'students'},'questions':[{'text':'Always easy and fast','type':'scale','id':'a'},{'text':'ok'}],'source':SRC})['result']['metrics']
 assert m['flagged_item_ids']==['a'] and m['flag_rate']==.5
def test_1712_1714_frame_metrics():
 base={'research_question':'q','population':{'target':'students'},'source':SRC}
 assert execute('sampling_methods',{**base,'sampling_frame':['a','b','c','d']})['result']['metrics']['inclusion_probability_per_unit']==.25
 assert execute('probability_sampling',{**base,'sampling_frame':['a','a','b']})['result']['metrics']['duplicate_units']==1
 assert execute('non_probability_sampling',{**base,'sampling_frame':['a','b','c']})['result']['metrics']['inclusion_probability_per_unit'] is None
def test_1715_finite_population_correction():
 m=execute('sample_size_determination',{'research_question':'q','population':{'target':'students'},'source':SRC,'population_size':1000})['result']['metrics']
 assert m['finite_population_correction']==279 and m['population_size_supplied'] is True
 assert execute('sample_size_determination',{'research_question':'q','population':{'target':'students'},'source':SRC})['result']['metrics']['finite_population_correction'] is None
def test_1716_wave_response_rates():
 m=execute('response_rate_improvement',{'research_question':'q','population':{'target':'students'},'source':SRC,'contacts':[{'wave':1,'invited':100,'completed':40},{'wave':2,'invited':60,'completed':20}]})['result']['metrics']
 assert m['overall_response_rate']==.375 and m['wave_response_rates'][0]['response_rate']==.4
def test_1717_mode_rate_difference():
 m=execute('survey_mode_effects',{'research_question':'q','population':{'target':'students'},'source':SRC,'modes':{'phone':{'invited':100,'responded':50},'web':{'invited':100,'responded':30}}})['result']['metrics']
 assert m['response_rate_by_mode']=={'phone':.5,'web':.3} and m['max_pairwise_mode_difference']==.2
def test_1718_1719_design_metrics():
 m=execute('interview_design',{'research_question':'q','population':{'target':'students'},'source':SRC,'topics':['a','b']})['result']['metrics'];assert m['probes_per_topic']==1.5
 assert execute('focus_group_design',{'research_question':'q','population':{'target':'students'},'source':SRC,'size':12})['result']['metrics']['size_within_recommended_4_to_10'] is False
def test_1720_1722_field_metrics():
 f=lambda n,**x:execute(n,{'research_question':'q','sites':['s'],'source':SRC,**x})['result']['metrics']
 assert f('ethnography',schedule=[{'hours':2},{'hours':3.5}])['total_immersion_hours']==5.5
 m=f('participant_observation',dimensions=['setting','actors']);assert m['dimensions_missing']==['activities','interactions','time']
 m=f('field_research',access_plan='x',contingencies=['c1','c2']);assert m['access_defined'] and m['contingency_count']==2 and not m['safety_defined']
def test_1723_1725_design_metrics():
 f=lambda n,**x:execute(n,{'research_question':'q','sites':['s'],'source':SRC,**x})['result']['metrics']
 m=f('case_study_design',case_boundary={'p':'x'},evidence_sources=[{'type':'archive'},{'type':'interview'}]);assert m['triangulation_possible'] and m['distinct_source_types']==['archive','interview']
 m=f('comparative_research',cases=[{'name':'A','attributes':['x','y']},{'name':'B','attributes':['y','z']}]);assert m['pairwise_case_similarity'][0]['jaccard_similarity']==.3333
 m=f('cross_cultural_research',constructs=[{'name':'c1','forward_translated':True,'back_translated':True}]);assert m['construct_translation_completeness'][0]['steps_done']==2 and not m['construct_translation_completeness'][0]['complete']
def test_1726_1729_longitudinal_metrics():
 obs=[{'id':'a','time':v,'value':v} for v in (1,2,3,4,5)]
 g=lambda n,**x:execute(n,{'observations':obs,'source':SRC,**x})['result']['metrics']
 assert g('longitudinal_research')['wave_count']==5
 assert g('panel_studies')['retention_rate']==1
 assert g('cohort_studies',entry_definition='e',exposure_definition='x')['definition_completeness']==round(2/3,4)
 assert g('time_series_analysis')['lag1_autocorrelation']==.4
def test_1730_1735_interpretive_metrics():
 i=lambda n,**x:execute(n,{'texts':x.pop('texts',[{'id':'t','text':'We must change institutions and power. The decision was made.'}]),'source':SRC,**x})['result']['metrics']
 assert i('content_analysis',codebook=['power'])['code_frequencies']=={'power':1}
 m=i('discourse_analysis');assert m['modality_marker_counts']['must']==1 and m['nominalization_count']>=1
 m=i('conversation_analysis',texts=[{'speaker':'a','text':'um yes [overlap'},{'speaker':'b','text':'ok'}]);assert m['turn_counts_by_speaker']=={'a':1,'b':1} and m['overlap_markers']==1 and m['repair_markers']==1
 m=i('narrative_analysis',texts=['We met. Then we left and finally ate.']);assert m['temporal_markers_per_text'][0]['temporal_marker_count']==2
 m=i('thematic_analysis',texts=['power grows','power fades','calm'],codes=[{'code':'power'}]);assert m['code_document_coverage']=={'power':2}
 m=i('grounded_theory',texts=['cat dog','cat fish','cat']);assert m['saturation_curve'][1]['new_unique_terms']==1 and m['plateau_reached'] is True
def test_1736_1740_interpretive_metrics():
 i=lambda n,**x:execute(n,{'texts':x.pop('texts',['I felt afraid. The sky was blue.']),'source':SRC,**x})['result']['metrics']
 assert i('phenomenology')['significant_statement_candidates']==1
 assert i('hermeneutics',texts=['power shapes institutions','power and norms'])['shared_vocabulary']==['power']
 assert i('semiotics',signs=[{'signifier':'red','signified':'danger','relation':'symbol'}])['sign_relation_counts']=={'symbol':1}
 assert i('structuralism',binary_oppositions=[['nature','culture']])['opposition_count']==1
 assert i('post_structuralism',binary_oppositions=[['nature','culture']])['axes']==['nature']
def test_1741_1746_lens_mentions():
 for n,concept in [('critical_theory','ideology'),('feminist_theory','standpoint'),('queer_theory','performativity'),('critical_race_theory','racialization'),('postcolonial_theory','coloniality'),('actor_network_theory','translation')]:
  m=execute(n,{'texts':[f'this text discusses {concept} and power'],'source':SRC})['result']['metrics']
  assert m['concept_mentions'][concept]==1
def test_1747_1750_systems_metrics():
 y=lambda n,**x:execute(n,{'actors':['a','b','c'],'source':SRC,**x})['result']['metrics']
 m=y('social_network_analysis',edges=[{'source':'a','target':'b'}]);assert m['connected_components']==2 and m['isolates']==['c']
 m=y('organizational_analysis',structure={'a':['b'],'b':['c']});assert m['hierarchy_depth']==3 and m['max_span_of_control']==1
 m=y('institutional_analysis',rules=[{'pillar':'regulative'},{'pillar':'normative'}]);assert m['pillar_coverage_fraction']==round(2/3,4)
 m=y('political_economy',resources=[{'owner':'a','value':80},{'owner':'b','value':20}]);assert m['top_owner_share']==.8
def test_1751_1752_choice_metrics():
 y=lambda n,**x:execute(n,{'actors':['a'],'source':SRC,**x})['result']['metrics']
 opts=[{'name':'o1','scores':{'eff':5,'cost':2}},{'name':'o2','scores':{'eff':3,'cost':1}}]
 m=y('public_choice',options=opts,weights={'eff':2,'cost':1});assert m['utility_maximizing_option']=='o1' and m['option_scores'][0]['weighted_score']==12
 m=y('rational_choice',options=opts,weights={'eff':2,'cost':1},constraints=[{'field':'cost','max':1}]);assert m['utility_maximizing_option']=='o2' and m['option_scores'][0]['constraint_violations']==['cost']
def test_1753_1755_game_bargaining_coalition_metrics():
 y=lambda n,**x:execute(n,{'actors':['a','b','c'],'source':SRC,**x})['result']['metrics']
 m=y('game_theory',payoffs={'a':{},'b':{}},matrix={'players':['r','c'],'strategies':{'r':['T','B'],'c':['L','R']},'payoffs':{'T|L':[2,1],'T|R':[0,0],'B|L':[0,0],'B|R':[1,2]}})
 assert m['equilibrium_count']==2 and {'strategy_profile':['T','L'],'payoffs':[2,1]} in m['pure_nash_equilibria']
 m=y('bargaining_theory',reservation_values={'buyer_max':100,'seller_min':80});assert m['zopa']==[80,100] and m['nash_bargaining_point']==90
 m=y('coalition_theory',weights={'a':4,'b':3,'c':2},winning_threshold=5);assert m['banzhaf_power_index']=={'a':.3333,'b':.3333,'c':.3333}
def test_1756_1759_voting_choice_action_movement_metrics():
 y=lambda n,**x:execute(n,{'actors':['a'],'source':SRC,**x})['result']['metrics']
 m=y('voting_theory',ballots=[{'choice':'a','ranking':['a','b']},{'choice':'b','ranking':['b','a']},{'choice':'a','ranking':['a','b']}])
 assert m['majority_winner'] is True and m['borda_scores']=={'a':5,'b':4}
 m=y('social_choice',rankings=[['a','b','c'],['a','b','c'],['b','a','c']]);assert m['condorcet_winner']=='a' and m['majority_first_choice']=='a' and m['borda_violates_majority'] is False
 m=y('collective_action',thresholds=[1,2,2,5]);assert m['participation_equilibria']==[0,1,2]
 m=y('social_movements',frames=['justice'],claims=[{'text':'we demand justice now'},{'text':'other'}]);assert m['frame_mention_counts']=={'justice':1}
def test_social_research_failure_paths():
 with pytest.raises(SocialResearchError,match='unknown method'):execute('nope',{'source':SRC})
 with pytest.raises(SocialResearchError,match='source requires'):execute('survey_design',{'research_question':'q','population':{'target':'students'},'source':{'title':'t','url':'ftp://x'}})
 with pytest.raises(SocialResearchError,match='invalid sample-size'):execute('sample_size_determination',{'research_question':'q','population':{'target':'students'},'source':SRC,'margin_error':2})
 with pytest.raises(SocialResearchError,match='unknown actor'):execute('social_network_analysis',{'actors':['a'],'source':SRC,'edges':[{'source':'a','target':'zzz'}]})
 with pytest.raises(SocialResearchError,match='time and value'):execute('time_series_analysis',{'observations':[{'time':1}],'source':SRC})
 with pytest.raises(SocialResearchError,match='at most 20'):execute('coalition_theory',{'actors':['a'],'source':SRC,'weights':{str(i):1 for i in range(21)},'winning_threshold':3})
def test_social_research_tenant_boundary(monkeypatch):
 from app.main import app
 monkeypatch.setenv('ATLAS_ENV','production')
 c=TestClient(app)
 assert c.get('/api/v1/api/modules/20/social-research-1710-1759/capabilities').status_code==401
 h={'X-Atlas-Tenant':'tenant-a','X-Atlas-Actor':'tester'}
 r=c.get('/api/v1/api/modules/20/social-research-1710-1759/capabilities',headers=h);assert r.status_code==200 and len(r.json())==50
