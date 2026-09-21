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
