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
