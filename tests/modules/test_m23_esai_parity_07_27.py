from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app); BASE='/api/v1/study-abroad/parity/'
def post(tool,data):r=C.post(BASE+tool,json={'data':data});assert r.status_code==200,r.text;return r.json()
def test_07_career_track_is_integrated_brand_grounded_suite():
 o=post('career_track',{});assert o['brand_grounded'] and 'linkedin_headline' in o['tools'] and o['cross_tool_evidence_reuse']
def test_09_career_matching_explains_evidence_unknowns_and_provenance():
 o=post('career_opportunity_match',{'profile':{'skills':['python']},'opportunities':[{'id':'j','name':'Job','skills':['python'],'required_fields':['work_auth'],'official_url':'https://job.test'}]});assert o['matches'][0]['status']=='needs_information' and o['matches'][0]['matched_student_evidence']==['python'] and o['not_an_admission_or_hiring_prediction']
def test_21_personal_stat_excludes_unverified_values():
 o=post('personal_stat',{'records':[{'metric':'gpa','value':4,'source':'transcript','verified':True},{'metric':'gpa','value':5}]});assert o['verified_metrics']['gpa']['latest']==4 and len(o['excluded_unverified_records'])==1
def test_22_scholarship_guide_keeps_official_source_and_private_need():
 o=post('scholarship_guide',{'profile':{'interests':['science']},'scholarships':[{'id':'s','name':'S','themes':['science'],'official_url':'https://s.test'}]});assert o['matches'][0]['official_url']=='https://s.test' and o['financial_need_private_by_default']
def test_23_loci_is_evidence_filtered_student_authored_outline():
 o=post('loci',{'context':{'school':'X','decision':'waitlist','submitted_application_summary':'v1'},'evidence':[{'id':'new','occurred_after_submission':True,'source':'certificate'},{'id':'old','source':'x'}]});assert [x['id'] for x in o['eligible_updates']]==['new'] and o['generated_letter_prose'] is None
def test_24_interview_prep_retrieves_brand_evidence_but_not_answers():
 o=post('interview_prep',{'opportunity':{'name':'Role'},'brand':{'evidence':[{'id':'e','tags':['leadership']}]},'questions':[{'question':'Tell me','evidence_tags':['leadership'],'rubric':['specificity']} ]});assert o['practice_turns'][0]['evidence_options'][0]['id']=='e' and not o['answer_prose_generated']
def facts():return {'opportunity':{'name':'Role','role':'Engineer','skills':['python']},'brand':{'values':['care'],'strengths':['analysis']},'student_facts':[{'id':'e','description':'built with python','tags':['python'],'source':'portfolio'},{'id':'u','description':'magic'}]}
def test_25_resume_narrative_maps_only_sourced_evidence():
 o=post('resume_narrative',facts());assert o['sections'][0]['evidence_ids']==['e'] and o['generated_resume_prose'] is None
def test_26_cover_letter_keeps_student_as_author():
 o=post('cover_letter_narrative',facts());assert o['student_review_required'] and o['generated_letter_prose'] is None
def test_27_linkedin_positioning_exposes_building_blocks_not_fake_headline():
 o=post('linkedin_headline',facts());assert o['headline_building_blocks']['role']=='Engineer' and o['generated_headline'] is None
