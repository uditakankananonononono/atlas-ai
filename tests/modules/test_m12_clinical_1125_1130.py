import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://validated.test/model','source_title':'Validated model'}
def model(link='logistic'):return {'name':'M','version':'2','intercept':-2,'coefficients':{'age':.1,'marker':1},'link':link,'thresholds':[{'minimum':0,'label':'low'},{'minimum':.5,'label':'high'}] if link=='logistic' else [{'minimum':0,'label':'short'},{'minimum':5,'label':'long'}],'source':SRC,'validation_population':'cohort x','calibration':{'slope':1}}
def score(method,link='logistic'):return clinical_support(method,{'factors':{'age':20,'marker':1},'model':model(link)})
def test_row_1125_readmission_prediction_returns_probability_and_validation_context():
 o=score('readmission_prediction');assert 0<o['probability']<1 and o['risk_band']=='high' and o['validation_population']=='cohort x'
def test_row_1126_sepsis_warning_refuses_missing_factors():
 o=clinical_support('sepsis_early_warning',{'factors':{'age':20},'model':model()});assert o['status']=='insufficient_data' and o['missing_factors']==['marker']
def test_row_1127_mortality_prediction_has_nonautonomous_boundary():
 o=score('mortality_prediction');assert o['outcome']=='mortality_prediction' and 'does not determine' in o['boundary']
def test_row_1128_length_of_stay_supports_identity_link_without_false_probability():
 o=score('length_of_stay_prediction','identity');assert o['probability'] is None and o['predicted_value']==1 and o['risk_band']=='short'
def test_row_1129_icu_allocation_is_score_only_not_resource_decision():
 o=score('icu_resource_allocation');assert o['status']=='scored' and 'resource access' in o['boundary']
def test_row_1130_triage_returns_highest_transparent_rule_and_missing_inputs():
 rules=[{'level':'urgent','reason':'tachycardia','recommended_next_step':'clinician now','when':{'hr':{'gte':120}},**SRC},{'level':'emergent','reason':'hypoxia','recommended_next_step':'emergency response','when':{'spo2':{'lt':90}},**SRC}];o=clinical_support('emergency_triage',{'observations':{'hr':130,'spo2':85},'required_observations':['hr','spo2','bp'],'rules':rules});assert o['highest_priority_match']['level']=='emergent' and o['missing_observations']==['bp'] and 'Never delay emergency services' in o['boundary']
def test_predictors_require_cited_models_and_supported_links():
 with pytest.raises(ValueError):clinical_support('readmission_prediction',{'factors':{},'model':{}})
