import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://health.test/source','source_title':'Source'}
def test_1199_equity_analysis_computes_gap_and_preserves_missing_groups():
 o=clinical_support('health_equity_analysis',{'groups':[{'group_token':'a','values':{'access':.8}},{'group_token':'b','values':{'access':.5}}],'metrics':['access'],'source':SRC});assert o['metric_gaps'][0]['absolute_gap']==pytest.approx(.3) and 'do not identify causes' in o['boundary']
def test_1200_social_needs_preserves_declined_unknown_and_referral_consent():
 o=clinical_support('social_determinants_assessment',{'responses':{'food':'yes','housing':'decline_to_answer'},'domains':[{'id':'food','need_values':['yes']},{'id':'housing','need_values':['yes']},{'id':'transport','need_values':['yes']}],'resources':[{'name':'pantry','domains':['food']}],'consent_to_referral':{'food':False},'source':SRC});assert o['declined_domains']==['housing'] and o['unknown_domains']==['transport'] and not o['consent_to_referral']['food']
def test_1201_community_assessment_requires_voice_and_marks_representation_gap():
 o=clinical_support('community_health_assessment',{'indicators':[{'topic':'air'}],'community_inputs':[{'group':'residents','topics':['air']}],'missing_representation':['workers'],'source':SRC});assert o['candidate_priorities'][0]['evidence_complete'] and o['missing_representation']==['workers']
def test_1202_policy_analysis_exposes_missing_criteria_not_fake_score():
 o=clinical_support('health_policy_analysis',{'options':[{'name':'a','scores':{'cost':2}}],'criteria':[{'id':'cost','weight':1},{'id':'equity','weight':2}],'source':SRC});assert o['option_matrix'][0]['weighted_score'] is None and o['option_matrix'][0]['missing_criteria']==['equity']
def test_1203_quality_improvement_handles_zero_denominator_and_balancing_measures():
 o=clinical_support('healthcare_quality_improvement',{'measures':[{'name':'x','numerator':1,'denominator':0}],'balancing_measures':['harm'],'source':SRC});assert o['measure_results'][0]['rate'] is None and o['balancing_measures']==['harm']
def safety(method):return clinical_support(method,{'event':{'known_facts':['fact'],'unknowns':['why'],'timeline':['t']},'contributing_factors':[{'id':'f','hypothesis':'workflow'}],'controls':[{'name':'check','addresses':['f']}],'source':SRC})
def test_1204_patient_safety_uses_just_culture_and_separates_unknowns():
 o=safety('patient_safety');assert o['unknowns']==['why'] and o['candidate_system_controls'][0]['review_status']=='candidate' and 'not culpability' in o['boundary']
def test_1205_error_prevention_links_system_control_to_factor():assert safety('medical_error_prevention')['candidate_system_controls'][0]['matched_factors']==['f']
def operations(method):return clinical_support(method,{'demand':[{'units':12}],'capacity':[{'units':10}],'constraints':['staffing'],'equity_and_safety_checks':['acuity'],'source':SRC})
def test_1206_healthcare_operations_computes_aggregate_gap_without_allocating_care():assert operations('healthcare_operations')['capacity_gap']==-2
def test_1207_hospital_administration_keeps_constraints_and_safety_checks():
 o=operations('hospital_administration');assert o['constraints']==['staffing'] and o['equity_and_safety_checks']==['acuity']
def test_1208_healthcare_finance_cannot_execute_changes():assert 'execute financial changes' in operations('healthcare_finance')['boundary']
def test_1209_medical_education_maps_objectives_and_requires_safe_cases():
 o=clinical_support('medical_education',{'objectives':[{'id':'o'}],'cases':[{'id':'c','objective_ids':['o'],'deidentified_or_synthetic':True,'answer_key':'review'}],'rubric':[{'criterion':'x'}],'source':SRC});assert o['case_map'][0]['objective_ids']==['o'] and o['case_map'][0]['deidentified_or_synthetic']
