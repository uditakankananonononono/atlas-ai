from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);B='/api/v1/study-abroad/enhanced-parity/'
def p(tool,data):r=C.post(B+tool,json={'data':data});assert r.status_code==200,r.text;return r.json()
EV=[{'id':'e','description':'I built a community app','tags':['service'],'source':'portfolio','change':'learned','tension':'limited access','reflection':'listen first'}]
def test_02_narrative_intelligence_is_traceable_not_generated_prose():
 o=p('narrative_intelligence',{'evidence':EV,'opportunity':{'themes':['service']}});assert o['evidence_arcs'][0]['matched_opportunity_themes']==['service'] and o['generated_narrative_prose'] is None
def test_06_college_track_is_integrated_identity_grounded_suite():assert 'common_app_export' in p('college_track',{'profile':{'evidence':EV}})['tools']
def test_08_college_match_exposes_missing_facts_and_official_url():
 o=p('college_opportunity_match',{'profile':{'interests':['science']},'opportunities':[{'id':'x','name':'X','programs':['science'],'required_fields':['gpa'],'official_url':'https://x.test'}]});assert o['matches'][0]['status']=='needs_information' and o['matches'][0]['official_url']=='https://x.test'
def test_10_story_strategy_preserves_student_choice():assert p('story_strategy',{'prompt':'why','evidence':EV,'opportunity':{'themes':['service']}})['student_choice_required']
def test_16_supplemental_assistant_tracks_each_limit_without_writing():
 o=p('supplemental_assistant',{'prompts':[{'id':'s','prompt':'why','word_limit':100}],'evidence':EV,'opportunity':{}});assert o['supplements'][0]['word_limit']==100 and o['generated_essay_prose'] is None
def test_29_adaptation_changes_selection_not_identity():
 o=p('adapted_brand',{'brand':{'values':['care'],'strengths':['build'],'evidence':[{'student_response':'I build','tags':['tech']}]},'opportunity':{'skills':['tech']}});assert o['adaptation_changes_presentation_not_identity'] and o['stable_identity']['values']==['care']
def test_30_entitlement_is_explicit_and_never_bills():
 o=p('entitlement_check',{'plan':'single','existing_projects':1});assert not o['can_create'] and not o['billing_mutation_performed']
def test_31_common_app_export_requires_confirmation_and_never_submits():
 o=p('common_app_export',{'profile':{'legal_name':'A'},'activities':[{'id':'a','source':'record','student_confirmed':False}],'essays':[]});assert o['status']=='needs_review' and not o['submitted'] and 'graduation_year' in o['missing_profile_fields']
def test_32_essay_suite_keeps_final_prose_student_owned():assert p('essay_suite',{'prompt':'why','evidence':EV,'student_draft':'mine'})['generated_final_prose'] is None
def test_34_admin_visibility_requires_consent_and_suppresses_small_groups():
 data={'records':[{'cohort':'c','student_token':'1','sessions':2,'completed':True}],'consent':{'scope':'aggregate_engagement','active':True,'minimum_group_size':5}};o=p('administrator_visibility',data);assert o['aggregate_engagement'][0]['suppressed'] and not o['individual_content_visible']
