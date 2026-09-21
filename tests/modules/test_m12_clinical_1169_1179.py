import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://care.test/current','source_title':'Current guidance'}
def test_1169_genetic_counseling_preserves_unresolved_variants_and_consent():
 o=clinical_support('genetic_counseling',{'pedigree':[{'relative':'parent'}],'test_results':[{'gene':'G','variant':'V'}],'knowledge':[{**SRC,'gene':'X','variant':'Y','classification':'benign'}],'consent_status':'discussion_pending'});assert o['result_context'][0]['classification']=='not_in_supplied_knowledge' and o['consent_status']=='discussion_pending'
def test_1170_fertility_plan_exposes_missing_facts_and_never_selects():
 o=clinical_support('fertility_treatment_planning',{'goals':['pregnancy'],'patient_facts':{},'options':[{'name':'option','required_facts':['reserve']}],'source':SRC});assert o['option_review'][0]['review_status']=='incomplete' and 'never selects treatment' in o['boundary']
def perinatal(method,obs={'bp':170}):return clinical_support(method,{'observations':obs,'milestones':[{'name':'visit','measure':'visit','due_at':'week20'}],'escalation_rules':[{'field':'bp','gt':160,'reason':'severe','urgency':'immediate','next_step':'team'}],'preferences':{'support':'partner'},'source':SRC})
def test_1171_prenatal_care_preserves_unknown_milestone_and_escalation():
 o=perinatal('prenatal_care');assert o['milestone_status'][0]['status']=='unknown' and o['escalation_flags'][0]['urgency']=='immediate'
def test_1172_labor_support_does_not_determine_delivery_mode():assert 'choose delivery mode' in perinatal('labor_and_delivery_management')['boundary']
def test_1173_neonatal_support_does_not_resuscitate_or_discharge():assert 'resuscitate' in perinatal('neonatal_care')['boundary']
def life(method,profile={'age_group':'adolescent','organs':['cervix']}):return clinical_support(method,{'profile':profile,'concerns':['care'],'recommendations':[{**SRC,'topic':'confidentiality','required_fields':['age_group'],'match':{'age_group':'adolescent'},'shared_decision':True}]})
def test_1174_pediatric_care_matches_cited_profile_not_assumption():assert life('pediatric_care')['recommendations_for_shared_review'][0]['topic']=='confidentiality'
def test_1175_adolescent_medicine_preserves_concerns_and_shared_decision():
 o=life('adolescent_medicine');assert o['patient_concerns']==['care'] and o['recommendations_for_shared_review'][0]['shared_decision']
def test_1176_geriatric_care_reports_insufficient_information():assert life('geriatric_care',{})['insufficient_information'][0]['missing_fields']==['age_group']
@pytest.mark.parametrize('method',['womens_health','mens_health','lgbtq_health'])
def test_1177_1179_inclusive_health_uses_relevant_anatomy_not_identity_inference(method):assert 'rather than assumptions' in life(method)['boundary']
def test_knowledge_citations_are_required():
 with pytest.raises(ValueError):clinical_support('genetic_counseling',{'pedigree':[{}],'knowledge':[{}]})
