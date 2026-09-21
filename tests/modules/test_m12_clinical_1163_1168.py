import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://public-health.test/g','source_title':'Current guideline'}
def test_1163_wound_care_tracks_dimensions_and_rule_escalation():
 o=clinical_support('wound_care',{'observations':[{'observed_at':'a','length_cm':3,'redness':False},{'observed_at':'b','length_cm':4,'redness':True}],'plan':{'dressing':'clinician supplied'},'escalation_rules':[{'field':'redness','equals':True,'reason':'review','next_step':'call team'}],'source':SRC});assert o['latest_dimension_changes_cm']['length_cm']==1 and o['escalation_flags'][0]['reason']=='review'
def test_1164_infection_control_preserves_unresolved_exposure():
 p={**SRC,'id':'p','pathogen':'x','setting':'hospital','precautions':['contact'],'version':'2'};o=clinical_support('infection_control',{'exposures':[{'pathogen':'y','setting':'hospital'}],'policies':[p]});assert o['exposure_reviews'][0]['status']=='unresolved'
def test_1165_stewardship_reports_missing_review_fields_and_cited_rule():
 r={**SRC,'when':{'drug':'a','susceptible_to':'b'},'type':'deescalation','message':'review narrower therapy'};o=clinical_support('antimicrobial_stewardship',{'antimicrobial_order':{'drug':'a','indication':'i'},'microbiology':{'susceptible_to':'b'},'rules':[r]});assert 'planned_review_at' in o['missing_stewardship_fields'] and o['rule_findings'][0]['type']=='deescalation'
def test_1166_vaccine_schedule_uses_history_age_and_contraindications():
 rec=[{'vaccine':'v','dose_number':1,'min_age_years':1,'max_age_years':99},{'vaccine':'w','dose_number':1,'min_age_years':1,'max_age_years':99,'contraindications':['allergy']}];o=clinical_support('vaccination_scheduling',{'history':[],'patient':{'age_years':20,'contraindications':['allergy']},'recommendations':rec,'source':SRC});assert [x['vaccine'] for x in o['due_for_clinician_review']]==['v'] and o['blocked_for_review'][0]['vaccine']=='w'
def preventive(method,profile):
 return clinical_support(method,{'profile':profile,'recommendations':[{**SRC,'service':'screen','grade':'B','shared_decision':True,'eligibility':{'age':{'minimum':40,'maximum':60},'risk':'average'}}]})
def test_1167_preventive_plan_preserves_shared_decision_grade():
 o=preventive('preventive_care_planning',{'age':50,'risk':'average'});assert o['recommendations_for_review'][0]['grade']=='B' and o['recommendations_for_review'][0]['shared_decision']
def test_1168_screening_recommendations_report_missing_risk_not_guess():assert preventive('health_screening_recommendations',{'age':50})['insufficient_information'][0]['missing_fields']==['risk']
def test_cited_policies_are_required():
 with pytest.raises(ValueError):clinical_support('infection_control',{'exposures':[],'policies':[{'pathogen':'x'}]})
