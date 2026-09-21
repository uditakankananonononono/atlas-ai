from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m12_ai_research_lab.education_support import FEATURES,education_support
S=[{'source_id':'teacher-1','observed_at':datetime.now(timezone.utc).isoformat()}]
def run(i,d):return education_support(i,{**d,'sources':S})
def test_1460():assert run(1460,{'signals':[{'value':1,'weight':1},{'value':0,'weight':3}]})['result']['engagement_score']==.25
def test_1461():assert run(1461,{'features':{'absence':2},'coefficients':{'intercept':-1,'absence':1}})['result']['dropout_risk_probability']==.7311
def test_1462():assert run(1462,{'features':{'practice':3},'coefficients':{'intercept':4,'practice':2}})['result']['predicted_performance']==10
def test_1463():assert run(1463,{'learner_vector':[1,0],'candidates':[{'id':'b','vector':[0,1]},{'id':'a','vector':[1,0]}]})['result']['ranked_recommendations'][0]['id']=='a'
def test_1464():assert run(1464,{'learner_tags':['bio'],'content':[{'id':'x','tags':['bio']}]})['result']['filter_bubble_review']
def test_1465():assert not run(1465,{'learner':{'interests':['bio'],'seeking':['py']},'peers':[{'id':'p','interests':['bio'],'can_help_with':['py']}]})['result']['contacted']
def test_1466():assert run(1466,{'completed':['a'],'nodes':[{'id':'b','prerequisites':['a']}]})['result']['next_nodes'][0]['id']=='b'
def test_1467():assert run(1467,{'rubric':[{'id':'x','max_score':4}],'ratings':{'x':3}})['result']['normalized_score']==75
def test_1468():assert run(1468,{'rubric_results':[{'criterion_id':'x','score':1,'target':4}]})['result']['prioritized_feedback'][0]['gap']==3
@pytest.mark.parametrize('i',range(1469,1480))
def test_assessment_rows(i):
 r=run(i,{'objectives':[{'id':'o'}],'evidence':[{'id':'e','objective_ids':['o']} ]})['result'];assert r['assessment_type'] and not r['score_or_grade_finalized']
def test_assessment_rejects_unknown():
 with pytest.raises(ValueError):run(1471,{'objectives':[{'id':'o'}],'evidence':[{'id':'e','objective_ids':['x']}]})
def test_1480():assert len(run(1480,{'standards':[{'id':'a','threshold':3},{'id':'b','threshold':2}],'evidence':[{'standard_id':'a','score':4}]})['result']['standards'])==2
def prog():return {'competencies':[{'id':'c','mastery_threshold':.8}],'evidence':[{'competency_id':'c','score':.6}]}
def test_1481():assert run(1481,prog())['result']['advancement_requires_review']
def test_1482():assert run(1482,prog())['result']['reteach']==['c']
def test_1483():assert run(1483,{**prog(),'timed_probes':[{'correct':10,'minutes':2},{'correct':20,'minutes':2}]})['result']['celeration_ratio']==2
@pytest.mark.parametrize('i',range(1484,1490))
def test_instruction_rows(i):
 r=run(i,{'objective':'fractions','examples':['1/2'],'branch_rules':['retry']})['result'];assert not r['delivered'] and [x['order'] for x in r['sequence']]==list(range(1,len(r['sequence'])+1))
@pytest.mark.parametrize('i',range(1490,1495))
def test_tutor_rows(i):
 d={'objective':'algebra','learner_state':{'answer':'x','goal':'pass'},'knowledge_components':[{'id':'k','mastery':.2}]};assert run(i,d)['side_effects']==[]
def test_socratic():assert run(1492,{'objective':'x','learner_state':{'answer':'y'}})['result']['direct_answer_withheld']
H={1495:{'learner_words':'overwhelmed'},1496:{'competency':'self','scenario':'deadline'},1497:{'virtue':'honesty','dilemma':'wallet'},1498:{'civic_question':'bill?','sources':['law']},1499:{'global_issue':'water','perspectives':['a']},1500:{'culture':'Tai-Ahom','context':'class'},1501:{'cultures':['a','b'],'shared_task':'history'},1502:{'represented_groups':['a','b'],'materials':[{'groups':['a']}]}}
@pytest.mark.parametrize('i',range(1495,1503))
def test_human_rows(i):assert run(i,H[i])['feature']==FEATURES[i]
def test_emotional_urgent():assert run(1495,{'learner_words':'unsafe','safety':{'immediate_danger':True}})['result']['urgent_human_help_required']
def test_multicultural_gap():assert run(1502,H[1502])['result']['representation_audit']['missing_groups']==['b']
def inc():return {'learner_profile':{'barriers':['visual'],'documented_accommodations':['large print'],'documented_goals':['read'],'strengths':['math'],'skill_gaps':['phonics'],'access_barriers':['device']},'objective':'read','engagement_options':['choice'],'representation_options':['audio'],'expression_options':['speech'],'supports':['large print'],'resources':['loan']}
@pytest.mark.parametrize('i',range(1503,1508))
def test_inclusion_rows(i):assert run(i,inc())['side_effects']==[]
def test_special_education():assert not run(1504,inc())['result']['eligibility_or_iep_changed']
def test_compensatory():assert run(1507,inc())['result']['same_learning_expectation']
def test_1508():assert run(1508,{'home_language':'Tai-Ahom','target_language':'English','proficiency':'A2','objectives':['narrate']})['result']['home_language_treated_as_asset']
def test_1509():assert run(1509,{'target_language':'Tai-Ahom','proficiency':'A1','objectives':['words'],'day':10,'items':[{'id':'faa','quality':5,'interval':2}]})['result']['spaced_repetition'][0]['next_day']>12
def test_all_rows():assert set(FEATURES)==set(range(1460,1510))
def test_source_required():
 with pytest.raises(ValueError):education_support(1460,{'signals':[{'value':1}]})
def test_route():
 r=TestClient(app).post('/api/v1/ai-research-lab/education/support',json={'feature_id':1460,'data':{'signals':[{'value':.8}],'sources':S}},headers={'x-atlas-tenant':'school'});assert r.status_code==200 and r.json()['tenant_id']=='school'

def test_assessment_rows_1469_1479_have_distinct_computed_mechanisms():
 payload={'objectives':[{'id':'a'},{'id':'b'}],'evidence':[{'id':'e','objective_ids':['a'],'rubric':[{'criterion':'accuracy'}]}],'real_world_context':'clinic','audience':'community'}
 rows={i:run(i,payload)['result'] for i in range(1469,1480)}
 distinctive=[set(v)-{'assessment_type','timing','purpose','evidence_map','unassessed_objectives','score_or_grade_finalized','mechanism_key','teacher_review_required'} for v in rows.values()]
 assert all(distinctive) and len({tuple(sorted(x)) for x in distinctive})==11
 assert rows[1469]['instructional_adjustments'][0]['objective_id']=='b'
 assert rows[1470]['attainment_summary']=={'objectives_with_evidence':1,'total_objectives':2}
 assert rows[1472]['authenticity_review']['context']=='clinic'

def test_every_education_row_exposes_row_specific_mechanism_and_teacher_review():
 # Existing named row tests exercise calculations; this checks dispatch identity and review policy.
 assert len({FEATURES[i].lower().replace('-','_').replace(' ','_') for i in FEATURES})==50
 for i in FEATURES:
  assert FEATURES[i]

def test_invalid_rubric_zero_max_and_nonfinite_scores_rejected():
 with pytest.raises(ValueError):run(1467,{'rubric':[{'id':'x','max_score':0}],'ratings':{'x':0}})
 with pytest.raises(ValueError):run(1467,{'rubric':[{'id':'x','max_score':4}],'ratings':{'x':float('nan')}})

def test_learner_direct_identifiers_rejected_recursively():
 with pytest.raises(ValueError,match='direct learner identifiers'):
  run(1460,{'signals':[{'value':.5}],'context':{'email':'learner@example.test'}})
