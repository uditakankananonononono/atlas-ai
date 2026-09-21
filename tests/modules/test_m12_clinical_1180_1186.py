import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://public.test/current','source_title':'Public health source'}
def test_1180_global_health_prioritizes_transparently_and_marks_unmet_need():
 o=clinical_support('global_health',{'needs':[{'name':'a','severity':2,'people_affected':10},{'name':'b','severity':5,'people_affected':1}],'resources':[{'name':'r','addresses':['a']}],'constraints':{},'sources':[SRC]});assert o['prioritized_needs'][0]['name']=='b' and o['resource_options'][0]['unmet']
def test_1181_surveillance_computes_signal_and_small_cell_privacy_flag():
 o=clinical_support('public_health_surveillance',{'series':[{'period':'p','count':3},{'period':'q','count':20}],'baseline':{'mean':5,'sd':5},'minimum_cell_size':5,'z_threshold':2,'source':SRC});assert o['statistical_signals'][0]['period']=='q' and o['privacy_check']['suppressed_cells']==['p']
def test_1182_epidemic_response_exposes_assumptions_equity_and_authority_gate():
 o=clinical_support('epidemic_response',{'scenario':{'name':'x'},'interventions':[{'name':'option','equity_considerations':['access']}],'assumptions':{'baseline_cases':100,'effectiveness':.5,'uptake':.8},'source':SRC});assert o['response_options'][0]['projected_cases_under_shared_assumptions']==60 and o['decision_status']=='draft_for_public_health_authority'
def test_1183_contact_tracing_requires_authority_and_uses_tokens_not_identity():
 o=clinical_support('contact_tracing',{'index_case':{'consent_or_legal_basis':'consent'},'encounters':[{'contact_token':'opaque','duration_minutes':20,'distance_meters':1}],'exposure_definition':{'min_duration_minutes':15,'max_distance_meters':2},'retention_until':'date','source':SRC});assert o['potential_exposures'][0]=={'contact_token':'opaque','qualifies':True,'encounter_at':None,'reason':'definition_matched'} and 'never deanonymizes' in o['boundary']
def test_1184_quarantine_management_preserves_support_and_review_route():
 p={'version':'v','required_fields':['exposure_date'],'appeal_or_review_route':'official','source':SRC};o=clinical_support('quarantine_management',{'cases':[{'case_token':'x','support_needs':['food']}],'policy':p});assert o['case_reviews'][0]['status']=='insufficient_information' and o['case_reviews'][0]['support_needs']==['food']
def education(method):return clinical_support(method,{'audience':{'language':'en'},'messages':[{'topic':'prevention','plain_language':'Do x','uncertainty':'evidence evolving','source_ids':['s']}],'review':{'accessible':True},'sources':[SRC]})
def test_1185_health_education_preserves_uncertainty_and_citations():
 o=education('health_education');assert o['educational_messages'][0]['uncertainty']=='evidence evolving' and o['sources'][0]['source_url']==SRC['source_url']
def test_1186_behavior_change_is_voluntary_not_manipulative():assert 'never shame, coerce, manipulate' in education('behavior_change_support')['boundary']
def test_contact_tracing_refuses_missing_authority():
 with pytest.raises(ValueError):clinical_support('contact_tracing',{'index_case':{},'exposure_definition':{},'source':SRC})
