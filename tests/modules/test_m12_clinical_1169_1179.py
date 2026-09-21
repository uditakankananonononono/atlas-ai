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

def test_1178_mens_health_keeps_screening_and_symptoms_for_clinician_review():
 o=clinical_support('mens_health',{'profile':{'age':30},'concerns':['symptom'],'recommendations':[{'name':'blood pressure screening',**SRC}]})
 assert o['mode']=='mens_health' and o['recommendations_for_shared_review'][0]['topic'] is None and 'clinician' in o['boundary'].lower()


def test_1171_prenatal_marks_unrecorded_visits_without_assuming_missed():
 d={'observations':{},'milestones':[{'name':'anatomy_scan','due_at':'week20'},{'name':'glucose_screen','due_at':'week26'}],'completed_visits':['anatomy_scan'],'source':SRC}
 o=clinical_support('prenatal_care',d)
 assert o['unrecorded_visits']==['glucose_screen'] and o['visit_schedule_review'][0]['recorded']=='completed'

def test_1172_labor_preserves_documented_timeline_order():
 d={'observations':{},'milestones':[{'name':'m'}],'events':[{'event':'rupture','at':'10:00','documented_by':'rn'},{'event':'admission','at':'08:00'}],'source':SRC}
 o=clinical_support('labor_and_delivery_management',d)
 assert [e['event'] for e in o['labor_timeline']]==['admission','rupture']

def test_1173_neonatal_screening_review_marks_not_recorded():
 d={'observations':{},'milestones':[{'name':'m'}],'required_screenings':['hearing','metabolic'],'screenings':[{'name':'hearing','status':'done','result':'pass'}],'source':SRC}
 o=clinical_support('neonatal_care',d)
 assert o['newborn_screening_review'][1]=={'screening':'metabolic','status':'not_recorded','result_for_clinician_review':None}

def test_1174_pediatric_bands_only_from_supplied_age_and_keeps_growth_inputs():
 d={'profile':{'age_years':3},'concerns':[],'growth_measurements':[{'metric':'height','value':95,'unit':'cm','observed_at':'2026-09-01'}],'recommendations':[{**SRC}]}
 o=clinical_support('pediatric_care',d)
 assert o['age_band_from_supplied_age']=='child' and o['growth_inputs'][0]['unit']=='cm'
 with pytest.raises(ValueError):clinical_support('pediatric_care',{'profile':{'age_years':-1},'recommendations':[{**SRC}]})

def test_1175_adolescent_surfaces_confidentiality_topics_and_consent_fields():
 d={'profile':{'age_group':'adolescent'},'concerns':[],'consent':{'confidential_visit':True},'recommendations':[{**SRC,'topic':'confidentiality'},{**SRC,'topic':'vaccines'}]}
 o=clinical_support('adolescent_medicine',d)
 assert o['confidentiality_review']=={'confidentiality_topics':['confidentiality'],'consent_fields_supplied':['confidential_visit']}

def test_1176_geriatric_counts_medications_for_polypharmacy_review_prompt():
 d={'profile':{'medications':['a','b','c','d','e'],'fall_history':'none'},'concerns':[],'recommendations':[{**SRC}]}
 o=clinical_support('geriatric_care',d)
 assert o['medication_count']==5 and o['polypharmacy_review_prompt'] is True
 assert {'field':'cognition','documented':False} in o['geriatric_screen_fields']

def test_1177_1179_distinct_inclusive_outputs_keyed_to_anatomy_and_identity():
 recs=[{**SRC,'topic':'cervical screen','organ':'cervix'}]
 w=clinical_support('womens_health',{'profile':{'organs':['cervix']},'concerns':[],'recommendations':recs})
 m=clinical_support('mens_health',{'profile':{'organs':['prostate']},'concerns':['urinary'], 'recommendations':recs})
 q=clinical_support('lgbtq_health',{'profile':{'chosen_name':'A','pronouns':'they/them','organs':['cervix']},'concerns':[],'recommendations':recs})
 assert w['anatomy_keyed_screening'][0]['applicable'] is True and m['anatomy_keyed_screening'][0]['applicable'] is False
 assert m['symptom_review_inputs']==['urinary'] and q['affirming_care_inputs']['pronouns']=='they/them'
