import pytest
from app.modules.m12_ai_research_lab.clinical_support import clinical_support
SRC={'source_url':'https://care.test/g','source_title':'Care guideline'}
def plan(method):return clinical_support(method,{'goals':[{'id':'g','measure':'mobility','target':'independent','review_cadence':'weekly'}],'interventions':[{'name':'practice','goal_ids':['g']}],'baseline':{'mobility':'assisted'},'source':SRC})
def test_row_1131_surgical_plan_links_goals_and_review_not_execution():
 o=plan('surgical_planning');assert o['goals'][0]['linked_interventions'][0]['name']=='practice' and o['approval_status']=='draft_for_multidisciplinary_review'
def test_row_1132_anesthesia_monitoring_flags_cited_thresholds_without_control():
 r=[{'metric':'spo2','lt':90,'severity':'critical','response_protocol':'team protocol',**SRC}];o=clinical_support('anesthesia_monitoring',{'observations':[{'metric':'spo2','value':85,'observed_at':'t'}],'thresholds':r});assert o['alerts_for_anesthesia_team'][0]['severity']=='critical' and 'does not control equipment' in o['boundary']
def test_row_1133_postop_tracks_milestones_and_escalates():
 r=[{'metric':'temp','gt':38,'reason':'fever','next_step':'review',**SRC}];o=clinical_support('post_operative_care',{'observations':{'walking':'yes','temp':39},'milestones':[{'name':'ambulate','measure':'walking','target':'yes','target_by':'day1'}],'escalation_rules':r});assert o['milestone_status'][0]['met'] and o['escalation_flags'][0]['reason']=='fever'
def test_row_1134_rehab_plan_has_baseline_target_and_cadence():
 o=plan('rehabilitation_planning');assert o['goals'][0]['baseline']=='assisted' and o['goals'][0]['target']=='independent' and o['goals'][0]['review_cadence']=='weekly'
def therapy(method):return clinical_support(method,{'assessment':{'contraindications':['fall']},'goals':[{'domain':'motor','measure':'score','review_after_sessions':3}],'activities':[{'name':'safe','domains':['motor'],'contraindications':[]},{'name':'unsafe','domains':['motor'],'contraindications':['fall']}],'source':SRC})
def test_row_1135_physical_therapy_filters_contraindicated_activity():
 o=therapy('physical_therapy_design');assert [a['name'] for a in o['goal_plans'][0]['candidate_activities']]==['safe']
def test_row_1136_occupational_therapy_preserves_progress_measure():
 o=therapy('occupational_therapy_design');assert o['goal_plans'][0]['progress_measure']=='score' and o['goal_plans'][0]['review_after_sessions']==3
def test_row_1137_speech_therapy_requires_licensed_review():
 o=therapy('speech_therapy_design');assert 'licensed_therapist' in o['approval_status'] and 'supervise execution' in o['boundary']
def test_care_plans_require_source_and_goals():
 with pytest.raises(ValueError):clinical_support('surgical_planning',{'goals':[],'interventions':[],'source':SRC})
