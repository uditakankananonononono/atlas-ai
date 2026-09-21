import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://care.test/guidance','source_title':'Guidance'}
def test_1187_adherence_distinguishes_missing_data_and_patient_barriers():
 o=clinical_support('medication_adherence',{'regimen':[{'name':'a'}],'checkins':[],'source':SRC});assert o['adherence_summary'][0]['observed_fraction'] is None and 'Missing data is not nonadherence' in o['boundary']
def wellbeing(method):return clinical_support(method,{'baseline':{'metric':1},'goals':[{'id':'g','target':2}],'options':[{'name':'ok','goal_ids':['g']},{'name':'bad','goal_ids':['g'],'contraindications':['x']}],'contraindications':['x'],'patient_preferences':['gradual'],'source':SRC})
@pytest.mark.parametrize('method',['lifestyle_modification','nutrition_planning','exercise_prescription','sleep_hygiene','stress_management'])
def test_1188_1192_wellbeing_plans_link_goals_filter_risk_and_remain_drafts(method):
 o=wellbeing(method);assert [x['name'] for x in o['candidate_steps']]==['ok'] and o['patient_preferences']==['gradual'] and o['approval_status']=='draft_for_patient_and_qualified_professional'
def substance(method):return clinical_support(method,{'assessment':{'readiness':'considering','overdose':True},'goals':['safer use'],'services':[{'name':'naloxone','goal_tags':['safer use']}],'source':SRC})
def test_1193_substance_treatment_escalates_overdose_without_compulsion():
 o=substance('substance_abuse_treatment');assert o['immediate_human_response_required'] and 'does not detoxify' in o['boundary']
def test_1194_harm_reduction_respects_current_goal():assert substance('harm_reduction')['candidate_services_and_supplies'][0]['name']=='naloxone'
def crisis(method,safety):return clinical_support(method,{'safety':safety,'safety_plan':{'contact':'trusted person'},'resources':[{'name':'local crisis'}],'source':SRC})
def test_1195_crisis_intervention_requires_immediate_human_response_for_danger():
 o=crisis('crisis_intervention',{'imminent_intent':True,'active_attempt':False,'immediate_danger':False,'cannot_stay_safe':False});assert o['safety_status']=='immediate_response' and o['immediate_human_response_required']
def test_1196_suicide_prevention_never_assumes_missing_means_safe():
 o=crisis('suicide_prevention',{'imminent_intent':False});assert o['safety_status']=='incomplete' and 'cannot_stay_safe' in o['missing_safety_fields']
def cultural(method):return clinical_support(method,{'preferences':{'declined':['touch'],'language':'x'},'needs':['interpreter'],'options':[{'name':'interpreter'},{'name':'exam','conflicts_with':['touch']}],'consent_checkpoints':['before exam'],'source':SRC})
def test_1197_trauma_informed_care_preserves_choice_and_consent():
 o=cultural('trauma_informed_care');assert [x['name'] for x in o['candidate_accommodations']]==['interpreter'] and o['consent_checkpoints']==['before exam']
def test_1198_culturally_competent_care_uses_stated_identity_not_stereotypes():assert 'without inference or stereotypes' in cultural('culturally_competent_care')['boundary']
def test_crisis_requires_direct_assessment():
 with pytest.raises(ValueError):clinical_support('crisis_intervention',{'safety':{},'source':SRC})
