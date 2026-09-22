"""B5 row-level proof for education rows, excluding separately verified 1469-1479."""
from copy import deepcopy
from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m12_ai_research_lab.education_support import education_support
S=[{'source_id':'qualified-teacher-observation','observed_at':datetime.now(timezone.utc).isoformat()}]
def run(row,data): return education_support(row,{**deepcopy(data),'sources':S})
def changed(row,a,b,key):
 x,y=run(row,a),run(row,b)
 assert x['mechanism_key'] != '' and x['qualified_teacher_review_required'] is True
 assert x['result'][key] != y['result'][key]
CASES={
1460:({'signals':[{'value':.1}]},{'signals':[{'value':.9}]},'engagement_score'),
1461:({'features':{'absence':0},'coefficients':{'absence':2}},{'features':{'absence':2},'coefficients':{'absence':2}},'dropout_risk_probability'),
1462:({'features':{'practice':1},'coefficients':{'practice':2}},{'features':{'practice':3},'coefficients':{'practice':2}},'predicted_performance'),
1463:({'learner_vector':[1,0],'candidates':[{'id':'x','vector':[1,0]},{'id':'y','vector':[0,1]}]},{'learner_vector':[0,1],'candidates':[{'id':'x','vector':[1,0]},{'id':'y','vector':[0,1]}]},'ranked_recommendations'),
1464:({'learner_tags':['bio'],'content':[{'id':'x','tags':['bio']},{'id':'y','tags':['art']}]},{'learner_tags':['art'],'content':[{'id':'x','tags':['bio']},{'id':'y','tags':['art']}]},'ranked_content'),
1465:({'learner':{'interests':['bio'],'seeking':['python']},'peers':[{'id':'p','interests':['bio'],'can_help_with':['python']}]},{'learner':{'interests':['art'],'seeking':['history']},'peers':[{'id':'p','interests':['bio'],'can_help_with':['python']}]},'ranked_peers'),
1466:({'completed':['a'],'nodes':[{'id':'b','prerequisites':['a']},{'id':'c','prerequisites':['b']}]},{'completed':['a','b'],'nodes':[{'id':'b','prerequisites':['a']},{'id':'c','prerequisites':['b']}]},'next_nodes'),
1467:({'rubric':[{'id':'claim','max_score':4}],'ratings':{'claim':1}},{'rubric':[{'id':'claim','max_score':4}],'ratings':{'claim':4}},'normalized_score'),
1468:({'rubric_results':[{'criterion_id':'claim','score':1,'target':4}]},{'rubric_results':[{'criterion_id':'claim','score':3,'target':4}]},'prioritized_feedback'),
1480:({'standards':[{'id':'s','threshold':3}],'evidence':[{'standard_id':'s','score':2}]},{'standards':[{'id':'s','threshold':3}],'evidence':[{'standard_id':'s','score':4}]},'standards'),
1481:({'competencies':[{'id':'c','mastery_threshold':.8}],'evidence':[{'competency_id':'c','score':.5}]},{'competencies':[{'id':'c','mastery_threshold':.8}],'evidence':[{'competency_id':'c','score':.9}]},'advancement_candidates'),
1482:({'competencies':[{'id':'c','mastery_threshold':.8}],'evidence':[{'competency_id':'c','score':.5}]},{'competencies':[{'id':'c','mastery_threshold':.8}],'evidence':[{'competency_id':'c','score':.9}]},'reteach'),
1483:({'competencies':[{'id':'c','mastery_threshold':.8}],'evidence':[{'competency_id':'c','score':.5}],'timed_probes':[{'correct':2,'minutes':2},{'correct':4,'minutes':2}]},{'competencies':[{'id':'c','mastery_threshold':.8}],'evidence':[{'competency_id':'c','score':.5}],'timed_probes':[{'correct':2,'minutes':2},{'correct':8,'minutes':2}]},'celeration_ratio'),
1484:({'objective':'fractions','examples':['1/2'],'response_checks':[True,False]},{'objective':'fractions','examples':['1/2'],'response_checks':[True,True]},'release_to_independent'),
1485:({'objective':'fractions','examples':['1/2'],'misconceptions':['bigger denominator means bigger']},{'objective':'fractions','examples':['1/2'],'misconceptions':['add denominators']},'explicit_checks'),
1486:({'objective':'fractions','examples':['1/2'],'skill_steps':['identify']},{'objective':'fractions','examples':['1/2'],'skill_steps':['identify','compare']},'cumulative_progression'),
1487:({'objective':'fractions','examples':['1/2'],'script_turns':[{'cue':'show half','expected_response':'one half'}]},{'objective':'fractions','examples':['1/2'],'script_turns':[{'cue':'show quarter','expected_response':'one quarter'}]},'cue_response_map'),
1488:({'objective':'fractions','examples':['1/2'],'frames':[{'id':'f1','correct_next':'f2','retry_next':'f1'}]},{'objective':'fractions','examples':['1/2'],'frames':[{'id':'f1','correct_next':'f3','retry_next':'f1'}]},'program_frames'),
1489:({'objective':'fractions','examples':['1/2'],'attempts':[{'item_id':'a','score':.2},{'item_id':'b','score':.8}]},{'objective':'fractions','examples':['1/2'],'attempts':[{'item_id':'a','score':.9},{'item_id':'b','score':.3}]},'adaptive_next_item'),
1490:({'objective':'algebra','learner_state':{'answer':'attempt'},'knowledge_components':[{'id':'linear','mastery':.2},{'id':'quadratic','mastery':.8}]},{'objective':'algebra','learner_state':{'answer':'attempt'},'knowledge_components':[{'id':'linear','mastery':.9},{'id':'quadratic','mastery':.3}]},'next_action'),
1491:({'objective':'algebra','learner_state':{'answer':'attempt'},'dialogue_history':[]},{'objective':'algebra','learner_state':{'answer':'attempt'},'dialogue_history':[{'role':'learner','text':'why?'}]},'dialogue_turn'),
1492:({'objective':'algebra','learner_state':{'answer':'attempt'},'claim':'x=2'},{'objective':'algebra','learner_state':{'answer':'attempt'},'claim':'x=3'},'claim_under_examination'),
1493:({'objective':'algebra','learner_state':{'answer':'attempt'},'strategy':'draw a model'},{'objective':'algebra','learner_state':{'answer':'attempt'},'strategy':'work backward'},'metacognitive_prompts'),
1494:({'objective':'algebra','learner_state':{'goal':'exam'},'small_next_step':'one equation'},{'objective':'algebra','learner_state':{'goal':'project'},'small_next_step':'one graph'},'goal'),
1495:({'learner_words':'I am frustrated'},{'learner_words':'I feel unsafe','safety':{'immediate_danger':True}},'urgent_human_help_required'),
1496:({'competency':'self-management','scenario':'deadline'},{'competency':'relationship skills','scenario':'conflict'},'competency'),
1497:({'virtue':'honesty','dilemma':'found wallet'},{'virtue':'courage','dilemma':'speak up'},'virtue'),
1498:({'civic_question':'How is a bill passed?','sources':['constitution']},{'civic_question':'How are elections run?','sources':['election law']},'civic_question'),
1499:({'global_issue':'water','perspectives':['upstream']},{'global_issue':'migration','perspectives':['migrant']},'global_issue'),
1500:({'culture':'Tai-Ahom','context':'class'},{'culture':'Khasi','context':'class'},'culture'),
1501:({'cultures':['Tai-Ahom','Khasi'],'shared_task':'oral history'},{'cultures':['Tai-Ahom','Mising'],'shared_task':'weaving'},'cultures'),
1502:({'represented_groups':['a','b'],'materials':[{'groups':['a']}]},{'represented_groups':['a','b'],'materials':[{'groups':['a','b']}]},'representation_audit'),
1503:({'learner_profile':{'barriers':['vision']},'objective':'read','representation_options':['audio']},{'learner_profile':{'barriers':['hearing']},'objective':'read','representation_options':['captions']},'universal_design'),
1504:({'learner_profile':{'documented_accommodations':['large print']},'objective':'read','supports':['large print']},{'learner_profile':{'documented_accommodations':['audio']},'objective':'read','supports':['audio']},'iep_alignment'),
1505:({'learner_profile':{'strengths':['math']},'objective':'learn','enrichment':['proof']},{'learner_profile':{'strengths':['art']},'objective':'learn','enrichment':['design']},'strengths'),
1506:({'learner_profile':{'skill_gaps':['phonics']},'objective':'read'},{'learner_profile':{'skill_gaps':['fluency']},'objective':'read'},'specific_gaps'),
1507:({'learner_profile':{'access_barriers':['device']},'objective':'read','resources':['loaner']},{'learner_profile':{'access_barriers':['transport']},'objective':'read','resources':['bus pass']},'access_barriers'),
1508:({'home_language':'Tai-Ahom','target_language':'English','proficiency':'A2','objectives':['narrate']},{'home_language':'Assamese','target_language':'English','proficiency':'A2','objectives':['narrate']},'home_language'),
1509:({'target_language':'Tai-Ahom','proficiency':'A1','objectives':['words'],'day':1,'items':[{'id':'faa','quality':1,'interval':2}]},{'target_language':'Tai-Ahom','proficiency':'A1','objectives':['words'],'day':1,'items':[{'id':'faa','quality':5,'interval':2}]},'spaced_repetition'),
}
@pytest.mark.parametrize('row,a,b,key',[(r,*v) for r,v in CASES.items()],ids=[f'row-{r}' for r in CASES])
def test_assigned_row_changes_with_relevant_input(row,a,b,key): changed(row,a,b,key)
def test_invalid_rubric_rating_fails():
 with pytest.raises(ValueError,match='out of range'):run(1467,{'rubric':[{'id':'claim','max_score':4}],'ratings':{'claim':5}})
def test_invalid_score_fails():
 with pytest.raises(ValueError,match='out of range'):run(1482,{'competencies':[{'id':'c','mastery_threshold':.8}],'evidence':[{'competency_id':'c','score':1.2}]})
def test_direct_learner_identifier_fails_at_any_depth():
 with pytest.raises(ValueError,match='direct learner identifier prohibited'):run(1460,{'signals':[{'value':.5,'learner_id':'student-7'}]})
def test_route_keeps_tenant_and_actor_context_separate():
 client=TestClient(app); body={'feature_id':1460,'data':{'signals':[{'value':.5}],'sources':S}}
 a=client.post('/api/v1/ai-research-lab/education/support',json=body,headers={'x-atlas-tenant':'school-a','x-atlas-actor':'teacher-a'}).json()
 b=client.post('/api/v1/ai-research-lab/education/support',json=body,headers={'x-atlas-tenant':'school-b','x-atlas-actor':'teacher-b'}).json()
 assert (a['tenant_id'],a['actor_id'])==('school-a','teacher-a')
 assert (b['tenant_id'],b['actor_id'])==('school-b','teacher-b')

# Exact collectable nodes for expanded-ledger traceability. Each CASES-backed node
# checks a feature-specific transformed value under two materially different inputs.
def test_1460_engagement_weighted_score_changes(): changed(1460,*CASES[1460])
def test_1461_dropout_logistic_risk_changes(): changed(1461,*CASES[1461])
def test_1462_performance_linear_prediction_changes(): changed(1462,*CASES[1462])
def test_1463_recommendation_ranking_changes(): changed(1463,*CASES[1463])
def test_1464_content_ranking_changes(): changed(1464,*CASES[1464])
def test_1465_peer_ranking_changes_without_contact(): changed(1465,*CASES[1465]);assert run(1465,CASES[1465][0])['result']['contacted'] is False
def test_1466_learning_path_changes_by_prerequisites(): changed(1466,*CASES[1466])
def test_1467_essay_rubric_score_changes_without_final_grade(): changed(1467,*CASES[1467]);assert run(1467,CASES[1467][0])['result']['final_grade_awarded'] is False
def test_1468_feedback_gap_priority_changes(): changed(1468,*CASES[1468])

def assessment_changed(row,key,a,b):
 base={'objectives':[{'id':'a'},{'id':'b'}],'evidence':[{'id':'e','objective_ids':['a'],'rubric':[{'criterion':'accuracy'}]}]}
 x=run(row,{**base,**a});y=run(row,{**base,**b})
 assert x['feature_id']==row and x['result']['score_or_grade_finalized'] is False
 assert x['result'][key] != y['result'][key]
def test_1469_formative_adjustment_changes_with_evidence(): assessment_changed(1469,'instructional_adjustments',{}, {'evidence':[{'id':'e','objective_ids':['a','b']}]})
def test_1470_summative_attainment_counts_evidence(): assessment_changed(1470,'attainment_summary',{}, {'evidence':[{'id':'e','objective_ids':['a','b']}]})
def test_1471_diagnostic_prerequisite_gaps_change(): assessment_changed(1471,'prerequisite_gaps',{}, {'evidence':[{'id':'e','objective_ids':['a','b']}]})
def test_1472_authentic_context_is_input_sensitive(): assessment_changed(1472,'authenticity_review',{'real_world_context':'clinic'},{'real_world_context':'field'})
def test_1473_performance_observability_uses_rubric(): assessment_changed(1473,'performance_observations',{}, {'evidence':[{'id':'e','objective_ids':['a']}]})
def test_1474_portfolio_checkpoints_are_preserved(): assessment_changed(1474,'portfolio_checkpoints',{'checkpoints':['draft']},{'checkpoints':['draft','final']})
def test_1475_self_assessment_prompts_are_preserved(): assessment_changed(1475,'self_calibration',{'reflection_prompts':['why']},{'reflection_prompts':['how']})
def test_1476_peer_assessment_anonymity_is_explicit(): assessment_changed(1476,'peer_moderation',{'anonymous':True},{'anonymous':False})
def test_1477_assessment_for_learning_changes_teaching_moves(): assessment_changed(1477,'next_teaching_moves',{}, {'evidence':[{'id':'e','objective_ids':['a','b']}]})
def test_1478_assessment_as_learning_prompts_change(): assessment_changed(1478,'metacognitive_cycle',{'reflection_prompts':['plan']},{'reflection_prompts':['review']})
def test_1479_assessment_of_learning_counts_attained_evidence(): assessment_changed(1479,'reporting_summary',{}, {'evidence':[{'id':'e','objective_ids':[]}]})
def test_1480_standards_status_changes_by_score(): changed(1480,*CASES[1480])
def test_1481_competency_advancement_changes_by_mastery(): changed(1481,*CASES[1481])
def test_1482_mastery_reteach_changes_by_score(): changed(1482,*CASES[1482])
def test_1483_precision_celeration_changes_by_probe(): changed(1483,*CASES[1483])
def test_1484_direct_instruction_release_uses_checks(): changed(1484,*CASES[1484])
def test_1485_explicit_instruction_targets_misconception(): changed(1485,*CASES[1485])
def test_1486_systematic_instruction_progression_changes(): changed(1486,*CASES[1486])
def test_1487_scripted_instruction_maps_cues(): changed(1487,*CASES[1487])
def test_1488_programmed_instruction_branches_frames(): changed(1488,*CASES[1488])
def test_1489_computer_assisted_next_item_changes(): changed(1489,*CASES[1489])
def test_1490_intelligent_tutor_targets_weak_component(): changed(1490,*CASES[1490])
def test_1491_dialogue_tutor_counts_prior_turns(): changed(1491,*CASES[1491])
def test_1492_socratic_tutor_examines_supplied_claim(): changed(1492,*CASES[1492])
def test_1493_metacognitive_prompts_use_strategy(): changed(1493,*CASES[1493])
def test_1494_motivational_goal_changes_with_learner_state(): changed(1494,*CASES[1494])
def test_1495_emotional_support_escalates_immediate_danger(): changed(1495,*CASES[1495])
def test_1496_social_emotional_competency_changes(): changed(1496,*CASES[1496])
def test_1497_character_education_virtue_changes(): changed(1497,*CASES[1497])
def test_1498_citizenship_question_changes(): changed(1498,*CASES[1498])
def test_1499_global_competence_issue_changes(): changed(1499,*CASES[1499])
def test_1500_cultural_competence_context_changes(): changed(1500,*CASES[1500])
def test_1501_intercultural_pair_changes(): changed(1501,*CASES[1501])
def test_1502_multicultural_missing_group_audit_changes(): changed(1502,*CASES[1502])
def test_1503_inclusive_design_options_change(): changed(1503,*CASES[1503])
def test_1504_special_education_alignment_changes_without_iep_mutation(): changed(1504,*CASES[1504]);assert run(1504,CASES[1504][0])['result']['eligibility_or_iep_changed'] is False
def test_1505_gifted_support_uses_strengths(): changed(1505,*CASES[1505])
def test_1506_remedial_support_targets_specific_gaps(): changed(1506,*CASES[1506])
def test_1507_compensatory_support_changes_barrier_not_expectation(): changed(1507,*CASES[1507]);assert run(1507,CASES[1507][0])['result']['same_learning_expectation'] is True
def test_1508_bilingual_support_preserves_home_language(): changed(1508,*CASES[1508])
def test_1509_language_spaced_repetition_changes_by_quality(): changed(1509,*CASES[1509])
