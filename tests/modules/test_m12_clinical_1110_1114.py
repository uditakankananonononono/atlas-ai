import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://guideline.test/v1','source_title':'Guideline v1'}
def test_row_1110_clinical_support_composes_cited_bounded_sections():
 data={'differential':{'findings':['fever'],'candidates':[{'name':'A','supporting_findings':['fever'],'source_url':'https://a.test'}]},'protocols':{'patient_facts':{'adult':True},'protocols':[{'id':'p','title':'P','requires':{'adult':True},**SRC}]}}
 o=clinical_support('clinical_decision_support',data);assert o['sections']['differential']['ranked_differential'][0]['condition']=='A' and o['sections']['protocols']['eligible_for_clinician_review'][0]['protocol_id']=='p' and 'clinician' in o['disclaimer'].lower()
def test_row_1111_differential_preserves_support_conflicts_and_missing_discriminators():
 o=clinical_support('differential_diagnosis',{'findings':['fever','rash'],'candidates':[{'name':'A','supporting_findings':['fever'],'contradicting_findings':['rash'],'discriminating_tests':['culture'],'source_url':'https://a.test'},{'name':'B','supporting_findings':['fever','rash'],'source_url':'https://b.test'}]});assert [r['condition'] for r in o['ranked_differential']]==['B','A'] and o['ranked_differential'][1]['missing_discriminators']==['culture'] and 'not disease probability' in o['uncertainty']
def test_row_1112_protocol_selection_enforces_requirements_contraindications_and_provenance():
 ps=[{'id':'a','title':'A','requires':{'adult':True},'contraindications':{'allergy':True},**SRC},{'id':'b','title':'B','requires':{'pregnant':False},**SRC}];o=clinical_support('treatment_protocol_selection',{'patient_facts':{'adult':True,'allergy':True},'protocols':ps});assert not o['eligible_for_clinician_review'] and o['excluded_or_incomplete'][0]['matched_contraindications']==['allergy']
def test_row_1113_interaction_checker_never_claims_no_match_means_safe():
 rules=[{'pair':['A','B'],'severity':'major','mechanism':'x','recommended_action':'review',**SRC}];o=clinical_support('drug_interaction_check',{'medications':[{'name':'a'},{'name':'b'}],'interaction_rules':rules});assert o['interactions'][0]['severity']=='major' and 'does not prove safety' in o['coverage_warning']
def test_row_1114_dosage_calculation_caps_daily_total_and_lists_verification():
 o=clinical_support('dosage_calculation',{'weight_kg':30,'mg_per_kg':10,'doses_per_day':4,'max_daily_mg':1000,'source':SRC});assert o['raw_mg_per_dose']==300 and o['capped_mg_per_dose']==250 and o['cap_applied'] and len(o['verification_checks'])>=4
def test_clinical_support_rejects_uncited_or_invalid_inputs():
 with pytest.raises(ValueError):clinical_support('drug_interaction_check',{'medications':[],'interaction_rules':[{'pair':['a','b']}]})
 with pytest.raises(ValueError):clinical_support('dosage_calculation',{'weight_kg':0,'mg_per_kg':1,'doses_per_day':1,'max_daily_mg':1,'source':SRC})
