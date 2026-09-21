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


def test_1157_chemo_reviews_cycle_structure_and_dosing_inputs_without_dosing():
 d={'regimen':{'name':'c','cycles':[{'cycle':1,'days':[1],'agents':['a']},{'cycle':2}]},'patient_facts':{'marker':'positive','organ':70,'weight_kg':60},'criteria':[{'field':'marker','equals':'positive'},{'field':'organ','minimum':50}],'source':SRC}
 o=clinical_support('chemotherapy_planning',d)
 assert o['cycle_structure_review']['incomplete_cycles']==[{'cycle':2,'missing':['days','agents']}]
 assert o['dosing_input_fields_for_pharmacist_review']['weight_kg']==60 and o['dosing_input_fields_for_pharmacist_review']['body_surface_area'] is None

def test_1158_radiation_checks_fractionation_arithmetic_and_consistency():
 d={'regimen':{'total_dose_gy':60,'fractions':30,'dose_per_fraction_gy':2.5},'patient_facts':{},'criteria':[],'source':SRC}
 o=clinical_support('radiation_therapy_planning',d)
 assert o['dose_per_fraction_gy']==2 and o['consistency_with_stated']=='inconsistent'

def test_1159_immunotherapy_reviews_biomarker_panel_and_immune_risk_fields():
 d={'regimen':{'name':'i'},'patient_facts':{'pdl1':'50%'},'criteria':[{'field':'pdl1','reason':'biomarker','equals':'50%'}],'immune_risk_fields':['thyroid','colitis_history'],'source':SRC}
 o=clinical_support('immunotherapy_selection',d)
 assert o['biomarker_panel_review'][0]['result_documented'] is True
 assert o['immune_risk_checklist']==[{'field':'thyroid','value':None,'documented':False},{'field':'colitis_history','value':None,'documented':False}]

def test_1160_palliative_summarizes_symptom_burden():
 o=pall('palliative_care_planning')
 assert o['symptom_burden_summary']['symptom_count']==1 and o['symptom_burden_summary']['urgent_count']==1 and o['symptom_burden_summary']['review_order']==['breathlessness']

def test_1161_hospice_maps_unowned_coordination_tasks_and_eligibility_docs():
 d={'symptoms':[],'goals':['comfort'],'preferences':{},'options':[],'team':[{'role':'nurse'}],'milestones':[{'name':'intake','owner_role':'nurse'},{'name':'review','owner_role':'chaplain'}],'eligibility_fields':['prognosis_months'],'eligibility_documentation':{},'source':SRC}
 o=clinical_support('hospice_care_coordination',d)
 assert o['unowned_milestones']==['review'] and o['eligibility_documentation_status']==[{'field':'prognosis_months','documented':False}]

def test_oncology_rows_have_distinct_keyed_outputs():
 base={'regimen':{'name':'r'},'patient_facts':{'marker':'positive'},'criteria':[{'field':'marker','equals':'positive'}],'source':SRC}
 keys={m:set(clinical_support(m,dict(base))) for m in ['chemotherapy_planning','radiation_therapy_planning','immunotherapy_selection']}
 assert 'cycle_structure_review' in keys['chemotherapy_planning'] and 'missing_fractionation_inputs' in keys['radiation_therapy_planning'] and 'biomarker_panel_review' in keys['immunotherapy_selection']
 assert 'cycle_structure_review' not in keys['radiation_therapy_planning'] and 'biomarker_panel_review' not in keys['chemotherapy_planning']

def test_oncology_rejects_impossible_fractionation():
 with pytest.raises(ValueError):clinical_support('radiation_therapy_planning',{'regimen':{'total_dose_gy':60,'fractions':0},'patient_facts':{},'source':SRC})
