import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://guideline.test/current','source_title':'Guideline'}
def test_row_1121_pharmacogenomics_matches_versioned_rules_and_keeps_unknowns():
 rules=[{'gene':'G','diplotype':'*1/*2','phenotype':'intermediate','drug':'D','guideline_text':'consider alternative','version':'2026',**SRC}];o=clinical_support('pharmacogenomic_recommendations',{'genotypes':[{'gene':'G','diplotype':'*1/*2'},{'gene':'X','diplotype':'*1/*1'}],'guideline_rules':rules});assert o['matched_guidelines'][0]['drug']=='D' and o['unmatched_genotypes']==[{'gene':'X','diplotype':'*1/*1'}] and 'lookup only' in o['boundary']
def test_row_1122_trial_matching_distinguishes_missing_from_excluded():
 trials=[{'trial_id':'t1','title':'T','inclusion':{'adult':True,'stage':'II'},'exclusion':{'pregnant':True},'last_verified_at':'2026-09-20',**SRC}];a=clinical_support('clinical_trial_matching',{'profile':{'adult':True},'trials':trials})['matches'][0];b=clinical_support('clinical_trial_matching',{'profile':{'adult':True,'stage':'II','pregnant':True},'trials':trials})['matches'][0];assert a['status']=='needs_information' and a['unmet_or_missing_inclusion'][0]['reason']=='missing' and b['status']=='not_matched' and b['matched_exclusions']==['pregnant']
def test_row_1123_adverse_event_detection_is_review_signal_not_causality():
 o=clinical_support('adverse_event_detection',{'notes':[{'text':'rash after dose','occurred_at':'2026-01-01','provenance':'patient report'}],'event_terms':['rash','fever']});assert o['signal_count']==1 and o['signals_for_review'][0]['provenance']=='patient report' and 'not causality' in o['boundary']
def test_row_1124_risk_stratification_requires_complete_cited_validated_model():
 model={'name':'r','version':'1','intercept':1,'coefficients':{'age':.1,'marker':2},'thresholds':[{'minimum':0,'label':'low'},{'minimum':5,'label':'high'}],'calibration_context':'population x', 'source':SRC};missing=clinical_support('patient_risk_stratification',{'factors':{'age':20},'model':model});scored=clinical_support('patient_risk_stratification',{'factors':{'age':20,'marker':1},'model':model});assert missing['status']=='insufficient_data' and missing['missing_factors']==['marker'] and scored['score']==5 and scored['risk_band']=='high' and scored['calibration_context']=='population x'
def test_new_clinical_support_requires_cited_rules():
 with pytest.raises(ValueError):clinical_support('pharmacogenomic_recommendations',{'genotypes':[],'guideline_rules':[{}]})
