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


def test_1204_patient_safety_records_factor_types_without_inferring_culpability():
 o=safety('patient_safety')
 assert o['just_culture_inputs']==[{'factor_id':'f','factor_type_as_supplied':None,'typed':False}]

def test_1205_error_prevention_reports_unmitigated_factors_and_coverage():
 d={'event':{'known_facts':['fact']},'contributing_factors':[{'id':'f1'},{'id':'f2'}],'controls':[{'name':'check','addresses':['f1']}],'source':SRC}
 o=clinical_support('medical_error_prevention',d)
 assert o['prevention_gap_analysis']=={'unmitigated_factors':['f2'],'control_coverage':0.5}

def test_1206_operations_projects_scenario_gaps_from_supplied_multipliers():
 d={'demand':[{'units':12}],'capacity':[{'units':10}],'scenarios':[{'name':'surge','demand_multiplier':1.5}],'source':SRC}
 o=clinical_support('healthcare_operations',d)
 assert o['scenario_review']==[{'scenario':'surge','demand_multiplier':1.5,'projected_demand':18.0,'projected_gap':-8.0}]

def test_1207_administration_tracks_policy_ownership_and_review_dates():
 d={'demand':[{'units':1}],'capacity':[{'units':1}],'policies':[{'name':'handoff','owner':'cmo','review_date':'2026-01-01','status':'current'}],'source':SRC}
 o=clinical_support('hospital_administration',d)
 assert o['policy_checklist'][0]['owner']=='cmo' and o['policy_checklist'][0]['status']=='current'

def test_1208_finance_computes_variance_without_executing_changes():
 d={'demand':[{'units':1}],'capacity':[{'units':1}],'budget_lines':[{'line':'agency','budgeted':100,'actual':140},{'line':'supplies','budgeted':50,'actual':40}],'source':SRC}
 o=clinical_support('healthcare_finance',d)
 assert o['budget_variance'][0]=={'line':'agency','budgeted':100.0,'actual':140.0,'variance':40.0,'variance_note':'over'}
 assert o['budget_variance'][1]['variance_note']=='under'

def test_operations_rows_have_distinct_keyed_outputs():
 base={'demand':[{'units':1}],'capacity':[{'units':1}],'source':SRC}
 keys={m:set(clinical_support(m,dict(base))) for m in ['healthcare_operations','hospital_administration','healthcare_finance']}
 for m,k in [('healthcare_operations','scenario_review'),('hospital_administration','policy_checklist'),('healthcare_finance','budget_variance')]:
  assert k in keys[m] and all(k not in keys[o] for o in keys if o!=m)

def test_operations_rows_reject_malformed_typed_inputs():
 base={'demand':[{'units':1}],'capacity':[{'units':1}],'source':SRC}
 with pytest.raises(ValueError):clinical_support('healthcare_finance',{**base,'budget_lines':'lots'})
 with pytest.raises(ValueError):clinical_support('healthcare_operations',{**base,'scenarios':[{'name':'x','demand_multiplier':-1}]})
 with pytest.raises(ValueError):clinical_support('healthcare_operations',{'demand':[{'units':'many'}],'capacity':[{'units':1}],'source':SRC})
