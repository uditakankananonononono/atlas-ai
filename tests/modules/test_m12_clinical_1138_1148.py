import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://clinical.test/guideline','source_title':'Guideline'}
def instrument():return {'name':'Cited screen','version':'1','source':SRC,'items':[{'id':'a','allowed_values':[0,1,2,3]},{'id':'safety','allowed_values':[0,1,2,3],'urgent_if_at_or_above':1}],'bands':[{'minimum':0,'label':'low'},{'minimum':3,'label':'elevated'}]}
def screen(method,answers={'a':2,'safety':1}):return clinical_support(method,{'instrument':instrument(),'answers':answers})
def test_1138_assessment_preserves_patient_words_and_requires_safety_review():
 o=clinical_support('mental_health_assessment',{'domains':[{'name':'mood','patient_words':'tired'}],'safety':{'suicidal_intent':False,'self_harm_risk':False,'harm_to_others':False,'unable_to_care_for_self':False},'sources':[SRC]});assert o['domains'][0]['patient_words']=='tired' and o['safety_status']=='no_supplied_urgent_flag'
def test_1139_depression_screen_is_not_diagnosis_and_escalates_safety_item():
 o=screen('depression_screening');assert o['score']==3 and o['urgent_response_required'] and 'not a diagnosis' in o['boundary']
def test_1140_anxiety_assessment_rejects_incomplete_instrument():
 o=screen('anxiety_assessment',{'a':2});assert o['status']=='incomplete' and o['missing_items']==['safety']
def test_1141_ptsd_evaluation_validates_answer_range():
 o=screen('ptsd_evaluation',{'a':9,'safety':0});assert o['status']=='incomplete' and o['invalid_items']==['a']
def test_1142_addiction_plan_respects_readiness_contraindications_and_urgent_risk():
 o=clinical_support('addiction_treatment_planning',{'assessment':{'readiness_stage':'action','contraindications':['x'],'overdose_risk':True},'goals':['reduce harm'],'options':[{'name':'ok','readiness_stages':['action']},{'name':'no','readiness_stages':['action'],'contraindications':['x']}],'source':SRC});assert [x['name'] for x in o['candidate_options_for_shared_decision']]==['ok'] and o['urgent_medical_review']
def profile(method):return clinical_support(method,{'test_results':[{'domain':'memory','score':70,'norm_mean':100,'norm_sd':15,'norm_group':'age peers'}],'context':{'language':'en'},'source':SRC})
def test_1143_cognitive_assessment_computes_transparent_norm_score():
 o=profile('cognitive_assessment');assert o['domain_profile'][0]['z_score']==-2 and o['domain_profile'][0]['interpretation']=='below_expected'
def test_1144_dementia_screening_remains_screen_not_diagnosis():assert 'not a diagnosis' in screen('dementia_screening')['boundary']
def test_1145_neuropsych_testing_preserves_norm_group_and_validity_boundary():
 o=profile('neuropsychological_testing');assert o['domain_profile'][0]['norm_group']=='age peers' and 'test validity' in o['boundary']
def therapy(method):return clinical_support(method,{'formulation':{'maintaining_factors':['avoidance'],'contraindications':['flooding']},'goals':[{'target':'avoidance'}],'interventions':[{'name':'graded','targets':['avoidance']},{'name':'flood','targets':['avoidance'],'contraindications':['flooding']}],'outcome_measures':['weekly function'],'source':SRC})
def test_1146_psychotherapy_plan_is_collaborative_and_filters_contraindications():
 o=therapy('psychotherapy_planning');assert [x['name'] for x in o['candidate_interventions']]==['graded'] and 'patient_and_licensed_therapist' in o['approval_status']
def test_1147_cbt_protocol_is_draft_not_autonomous_therapy():assert 'does not conduct psychotherapy' in therapy('cbt_protocol_design')['boundary']
def test_1148_dbt_skill_selection_excludes_supervised_skills_and_has_crisis_boundary():
 o=clinical_support('dbt_skill_selection',{'target':'distress','skills':[{'name':'grounding','targets':['distress']},{'name':'special','targets':['distress'],'requires_supervision':True}],'crisis':True,'source':SRC});assert [x['name'] for x in o['candidate_skills']]==['grounding'] and 'immediate local crisis' in o['boundary']
def test_source_and_instrument_are_mandatory():
 with pytest.raises(ValueError):clinical_support('depression_screening',{'instrument':{},'answers':{}})
