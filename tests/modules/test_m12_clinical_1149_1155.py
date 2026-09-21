import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://clinical.test/chronic','source_title':'Care standard'}
def test_1149_medication_management_reconciles_origins_and_exposes_discrepancies():
 data={'medication_lists':[{'origin':'patient','medications':[{'name':'Drug A','dose':'5mg','route':'oral','frequency':'daily','status':'active'}]},{'origin':'chart','medications':[{'name':'drug a','dose':'10mg','route':'oral','frequency':'daily','status':'active'}]}],'source':SRC}
 o=clinical_support('medication_management',data);assert o['reconciled_medications'][0]['consistent'] is False and o['discrepancies'][0]['resolution']=='prescriber_or_pharmacist_review' and 'does not start, stop' in o['boundary']
def chronic(method,observations={'metric':12}):
 return clinical_support(method,{'observations':observations,'observed_at':'2026-09-21','targets':[{'metric':'metric','minimum':4,'maximum':10,'unit':'u'}],'actions':[{'name':'review','trigger_metric':'metric'}],'patient_goals':['function'],'source':SRC})
def test_1150_chronic_management_tracks_timestamp_target_and_goal():
 o=chronic('chronic_disease_management');assert o['metric_status'][0]['observed_at']=='2026-09-21' and o['patient_goals']==['function']
def test_1151_diabetes_management_flags_outside_target_without_titrating():
 o=chronic('diabetes_management');assert o['outside_target'] and o['candidate_actions_for_shared_review'][0]['name']=='review' and 'does not diagnose exacerbation' in o['boundary']
def test_1152_hypertension_management_preserves_missing_measurements():
 o=chronic('hypertension_management',{});assert o['missing_metrics']==['metric'] and not o['outside_target']
def test_1153_asthma_management_filters_contraindicated_candidate_actions():
 o=clinical_support('asthma_management',{'observations':{'metric':12},'targets':[{'metric':'metric','maximum':10}],'actions':[{'name':'x','trigger_metric':'metric','contraindications':['allergy']}],'contraindications':['allergy'],'source':SRC});assert o['candidate_actions_for_shared_review']==[]
def test_1154_copd_management_reports_within_target_transparently():assert chronic('copd_management',{'metric':8})['metric_status'][0]['status']=='within_target'
def test_1155_heart_failure_management_is_shared_review_not_prescription():assert 'licensed review' in chronic('heart_failure_management')['boundary']
def test_chronic_plan_requires_cited_targets():
 with pytest.raises(ValueError):clinical_support('diabetes_management',{'targets':[],'source':SRC})


def test_1150_registry_counts_control_across_supplied_targets():
 o=chronic('chronic_disease_management')
 assert o['control_summary']=={'metrics_measured':1,'metrics_within_target':0,'control_fraction':0.0} and o['condition_registry']==[]

def test_1151_diabetes_flags_urgent_low_glucose_and_computes_time_in_range():
 d={'observations':{'glucose':50},'observed_at':'2026-09-21','targets':[{'metric':'glucose','minimum':70,'maximum':180,'severe_minimum':54,'unit':'mg/dL'}],'actions':[],'readings':[80,200,120,90],'source':SRC}
 o=clinical_support('diabetes_management',d)
 assert o['glucose_safety_review'][0]['urgent_low_glucose'] is True and o['immediate_human_response_required'] is True
 assert o['time_in_range_fraction']==pytest.approx(0.75)

def test_1152_hypertension_averages_supplied_reading_pairs():
 d={'observations':{},'targets':[{'metric':'sbp','maximum':140}],'actions':[],'readings':[{'systolic':120,'diastolic':80,'observed_at':'a'},{'systolic':140,'diastolic':90,'observed_at':'b'}],'source':SRC}
 o=clinical_support('hypertension_management',d)
 assert o['reading_pair_summary']['average_systolic']==130 and o['reading_pair_summary']['reading_count']==2

def test_1153_asthma_assigns_only_clinician_authored_zones():
 d={'observations':{'pef':300},'targets':[{'metric':'pef','minimum':100,'maximum':500}],'actions':[],'zone_rules':[{'zone':'green','minimum':250},{'zone':'red','maximum':100}],'source':SRC}
 o=clinical_support('asthma_management',d)
 assert o['action_plan_zones'][0]['clinician_authored_zone']=='green' and o['zone_rules_supplied']

def test_1154_copd_summarizes_exacerbation_history_without_judging():
 d={'observations':{'metric':8},'targets':[{'metric':'metric','minimum':4,'maximum':10}],'actions':[],'exacerbations':[{'date':'2026-01-01'},{'date':'2026-03-01'},{}],'symptom_scores':[{'date':'2026-02-01','score':20,'instrument':'CAT'}],'source':SRC}
 o=clinical_support('copd_management',d)
 assert o['exacerbation_history_summary']=={'recorded_count':3,'most_recent':'2026-03-01','undated_records':1} and o['symptom_score_trend'][0]['instrument']=='CAT'

def test_1155_heart_failure_flags_weight_gain_window_for_team_review():
 d={'observations':{'metric':5},'targets':[{'metric':'metric','minimum':4,'maximum':10}],'actions':[],'daily_weights':[{'date':'2026-09-18','weight_kg':70},{'date':'2026-09-19','weight_kg':71},{'date':'2026-09-20','weight_kg':73}],'alert_gain_kg':2,'source':SRC}
 o=clinical_support('heart_failure_management',d)
 assert o['daily_weight_trend']['max_window_gain_kg']==3 and o['daily_weight_trend']['weight_review_flag'] is True

def test_chronic_rows_have_distinct_keyed_outputs():
 base={'observations':{'metric':8},'targets':[{'metric':'metric','minimum':4,'maximum':10}],'actions':[],'source':SRC}
 keys={m:set(clinical_support(m,dict(base))) for m in ['chronic_disease_management','diabetes_management','hypertension_management','asthma_management','copd_management','heart_failure_management']}
 distinctive=['condition_registry','glucose_safety_review','reading_pair_summary','action_plan_zones','exacerbation_history_summary','daily_weight_trend']
 for m,k in zip(keys,distinctive):
  assert k in keys[m] and all(k not in keys[o] for o in keys if o!=m)

def test_chronic_rows_reject_malformed_typed_inputs():
 with pytest.raises(ValueError):clinical_support('diabetes_management',{'observations':{'g':'abc'},'targets':[{'metric':'g','minimum':1}],'source':SRC})
 with pytest.raises(ValueError):clinical_support('hypertension_management',{'observations':{},'targets':[{'metric':'s'}],'readings':[{'systolic':120}],'source':SRC})
 with pytest.raises(ValueError):clinical_support('heart_failure_management',{'observations':{},'targets':[{'metric':'w'}],'daily_weights':'heavy','source':SRC})
