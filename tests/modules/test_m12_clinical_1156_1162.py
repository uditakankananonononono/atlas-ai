import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://oncology.test/guideline','source_title':'Oncology guideline'}
def test_1156_cancer_coordination_detects_unowned_and_undated_milestones():
 o=clinical_support('cancer_care_coordination',{'plan':{'diagnosis':'supplied','stage':'II','pathology_version':'v1'},'team':[{'role':'oncologist','name':'A'}],'milestones':[{'name':'review','owner_role':'nurse'}],'patient_priorities':['function'],'source':SRC});assert o['coordination_gaps']==['review'] and o['diagnosis_and_stage_as_supplied']['pathology_version']=='v1'
def onc(method,facts={'marker':'positive','organ':70}):return clinical_support(method,{'regimen':{'name':'candidate','version':'2'},'patient_facts':facts,'criteria':[{'field':'marker','equals':'positive','reason':'biomarker'},{'field':'organ','minimum':50,'reason':'function'}],'source':SRC})
def test_1157_chemo_plan_checks_all_criteria_without_dosing():
 o=onc('chemotherapy_planning');assert o['status']=='eligible_for_specialist_review' and 'never selects, doses' in o['boundary']
def test_1158_radiation_plan_preserves_missing_facts():assert onc('radiation_therapy_planning',{'marker':'positive'})['missing_facts']==['organ']
def test_1159_immunotherapy_selection_exposes_blocker():
 o=onc('immunotherapy_selection',{'marker':'negative','organ':70});assert o['status']=='not_eligible_for_reviewed_option' and o['blockers'][0]['field']=='marker'
def pall(method):return clinical_support(method,{'symptoms':[{'name':'breathlessness','urgent':True}],'goals':['comfort'],'preferences':{'declined':['hospital']},'options':[{'name':'home support','goal_tags':['comfort']},{'name':'hospital','goal_tags':['comfort'],'conflicts_with':['hospital']}],'unresolved_decisions':['location'],'source':SRC})
def test_1160_palliative_plan_centers_goals_and_urgent_symptom_review():
 o=pall('palliative_care_planning');assert o['patient_goals']==['comfort'] and o['urgent_review'][0]['name']=='breathlessness' and [x['name'] for x in o['candidate_support_for_shared_decision']]==['home support']
def test_1161_hospice_coordination_does_not_enroll_or_change_code_status():assert 'never enrolls' in pall('hospice_care_coordination')['boundary']
def test_1162_pain_management_tracks_trajectory_function_and_contraindications():
 o=clinical_support('pain_management',{'observations':[{'score':8,'observed_at':'b'},{'score':5,'observed_at':'a'}],'goals':['walk'],'options':[{'name':'safe'},{'name':'bad','contraindications':['renal']}],'contraindications':['renal'],'red_flags':['weakness'],'source':SRC});assert o['pain_trajectory'][0]['score']==5 and [x['name'] for x in o['candidate_options_for_shared_review']]==['safe'] and o['functional_goals']==['walk']
def test_oncology_requires_source_and_regimen():
 with pytest.raises(ValueError):clinical_support('chemotherapy_planning',{'regimen':{},'source':SRC})
