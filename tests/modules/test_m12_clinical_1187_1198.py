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


def test_1188_lifestyle_reviews_goal_specificity():
 o=wellbeing('lifestyle_modification')
 assert o['goal_quality_review']==[{'goal_id':'g','well_specified':False,'missing_elements':['timeframe']}]

def test_1189_nutrition_computes_energy_balance_only_from_complete_inputs():
 d={'baseline':{'weight_kg':70,'daily_intake_kcal':2400,'daily_expenditure_kcal':2100},'goals':[{'id':'g','target':2}],'options':[],'source':SRC}
 o=clinical_support('nutrition_planning',d)
 assert o['energy_balance_kcal_estimate']==300 and o['missing_energy_inputs']==[]
 o2=clinical_support('nutrition_planning',{'baseline':{'weight_kg':70},'goals':[{'id':'g','target':2}],'options':[],'source':SRC})
 assert o2['energy_balance_kcal_estimate'] is None and o2['missing_energy_inputs']==['daily_intake_kcal','daily_expenditure_kcal']

def test_1190_exercise_reports_fitt_completeness_and_safety_screen_gaps():
 d={'baseline':{},'goals':[{'id':'g','target':2}],'options':[{'name':'walk','goal_ids':['g'],'frequency':'5x/week','type':'aerobic'}],'safety_screen':{'injury':'none'},'source':SRC}
 o=clinical_support('exercise_prescription',d)
 assert o['fitt_components'][0]['fitt_complete'] is False
 assert {'field':'cardiac_symptoms','documented':False} in o['safety_screen_fields']

def test_1191_sleep_computes_diary_efficiency_and_skips_incomplete_entries():
 d={'baseline':{},'goals':[{'id':'g','target':2}],'options':[],'sleep_diary':[{'date':'2026-09-19','time_in_bed_minutes':480,'time_asleep_minutes':360},{'date':'2026-09-20'}],'source':SRC}
 o=clinical_support('sleep_hygiene',d)
 assert o['sleep_diary_metrics']['average_sleep_efficiency']==0.75 and o['sleep_diary_metrics']['entries_skipped_missing_fields']==1

def test_1192_stress_tracks_score_deltas_without_diagnosing():
 d={'baseline':{},'goals':[{'id':'g','target':2}],'options':[],'stress_scores':[{'date':'2026-09-20','score':12,'instrument':'PSS'},{'date':'2026-09-10','score':16,'instrument':'PSS'}],'source':SRC}
 o=clinical_support('stress_management',d)
 assert o['stress_score_trend']['scores'][0]['date']=='2026-09-10' and o['stress_score_trend']['deltas']==[{'from':'2026-09-10','to':'2026-09-20','delta':-4}]

def test_1193_treatment_tracks_placement_dimensions_as_supplied():
 d={'assessment':{'readiness':'ready'},'goals':['recovery'],'services':[],'placement_dimensions':[{'dimension':'withdrawal_risk','status':'low'},{'dimension':'recovery_environment'}],'source':SRC}
 o=clinical_support('substance_abuse_treatment',d)
 assert o['level_of_care_review'][1]=={'dimension':'recovery_environment','status_as_supplied':None,'documented':False}

def test_1194_harm_reduction_separates_supplies_and_overdose_resources():
 d={'assessment':{'readiness':'considering'},'goals':['safer use'],'services':[{'name':'naloxone','kind':'supply','overdose_response':True,'goal_tags':['safer use']},{'name':'therapy','goal_tags':['safer use']}],'source':SRC}
 o=clinical_support('harm_reduction',d)
 assert o['supply_review']==[{'name':'naloxone','available_as_supplied':None}] and o['overdose_response_resources'][0]['name']=='naloxone'

def test_1195_crisis_builds_handoff_steps_from_supplied_plan_and_resources():
 o=crisis('crisis_intervention',{'imminent_intent':False,'active_attempt':False,'immediate_danger':False,'cannot_stay_safe':False})
 assert o['handoff_steps'][0]['detail']=='trusted person' and o['handoff_steps'][1]['detail']=='local crisis'

def test_1196_suicide_prevention_marks_unassessed_means_never_safe():
 d={'safety':{'imminent_intent':False,'active_attempt':False,'immediate_danger':False,'cannot_stay_safe':False},'safety_plan':{},'resources':[],'means':[{'item':'medication','secured':True},{'item':'firearm'}],'source':SRC}
 o=clinical_support('suicide_prevention',d)
 assert o['means_safety_review'][1]['secured_status']=='not_assessed' and o['unsecured_means']==['firearm']

def test_1197_trauma_maps_declinable_options_and_grounding_choices():
 d={'preferences':{'declined':['touch']},'needs':[],'options':[{'name':'exam','conflicts_with':['touch']},{'name':'music'}],'coping_options':[{'name':'breathing','patient_endorsed':True}],'source':SRC}
 o=clinical_support('trauma_informed_care',d)
 assert o['choice_and_control_map']['declinable_options']==['exam','music'] and o['grounding_options'][0]['patient_endorsed'] is True

def test_1198_cultural_care_checks_language_resource_match():
 d={'preferences':{'language':'fr'},'needs':['interpreter'],'options':[],'language_resources':[{'language':'en'}],'source':SRC}
 o=clinical_support('culturally_competent_care',d)
 assert o['language_access_review']['resource_available'] is False and o['language_access_review']['unmatched_needs']==['interpreter']

def test_wellbeing_rows_reject_malformed_typed_inputs():
 base={'baseline':{},'goals':[{'id':'g','target':2}],'options':[],'source':SRC}
 with pytest.raises(ValueError):clinical_support('sleep_hygiene',{**base,'sleep_diary':'restful'})
 with pytest.raises(ValueError):clinical_support('stress_management',{**base,'stress_scores':'calm'})
 with pytest.raises(ValueError):clinical_support('sleep_hygiene',{**base,'sleep_diary':[{'time_in_bed_minutes':0,'time_asleep_minutes':0}]})
 with pytest.raises(ValueError):clinical_support('suicide_prevention',{'safety':{'imminent_intent':False},'means':'pills','source':SRC})
