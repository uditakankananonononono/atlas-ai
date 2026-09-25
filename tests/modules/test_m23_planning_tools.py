from datetime import date
import pytest
from app.modules.m23_study_abroad.planning_tools import TOOLS

EXAMPLES = {
 'deadline_triage': ({'today':'2026-09-25','deadlines':[{'id':'a','due':'2026-09-26'},{'id':'b','due':'2026-09-24'}]},lambda x:x['upcoming'][0]['days_left']==1 and x['overdue'][0]['id']=='b'),
 'workload_calendar': ({'weeks':4,'total_hours':20,'max_hours_per_week':4},lambda x:x['weekly_hours']==[5]*4 and x['capacity_warning']),
 'requirement_gap': ({'required':['passport','essay'],'completed':['essay']},lambda x:x['missing']==['passport'] and not x['ready']),
 'school_list_balance': ({'schools':[{'name':'X','student_assessed_category':'reach'},{'name':'Y'}]},lambda x:x['counts']['reach']==1 and x['unclassified']==['Y']),
 'program_language_fit': ({'languages':['English'],'programs':[{'id':'a','instruction_language':'English'},{'id':'b','instruction_language':'French'}]},lambda x:x['matches'][0]['id']=='a' and x['needs_language_review'][0]['id']=='b'),
 'tuition_scenario': ({'tuition':20000,'living':10000,'confirmed_aid':5000,'years':2},lambda x:x['annual_gap']==25000 and x['program_gap']==50000),
 'scholarship_eligibility': ({'student_facts':{'country':'IN'},'scholarships':[{'id':'a','requirements':{'country':'IN'}},{'id':'b','requirements':{'country':'US'}},{'id':'c','requirements':{'grade':12}}]},lambda x:[r['status'] for r in x['results']]==['candidate','ineligible','unknown']),
 'document_inventory': ({'requirements':[{'kind':'transcript'},{'kind':'passport'}],'documents':[{'kind':'transcript','student_confirmed':True}]},lambda x:[r['kind'] for r in x['needed']]==['passport']),
 'recommender_timeline': ({'due':'2026-10-20','lead_days':21},lambda x:x['request_by']=='2026-09-29' and not x['request_sent']),
 'essay_prompt_matrix': ({'prompts':[{'id':'p','text':'Describe your robotics project'}],'evidence':[{'id':'e','description':'My robotics project','student_confirmed':True}]},lambda x:x['prompts'][0]['evidence_candidates'][0]['id']=='e' and x['prompts'][0]['student_writes_prose']),
 'essay_overlap': ({'drafts':[{'id':'a','student_text':'robotics team leadership'},{'id':'b','student_text':'robotics team chemistry'}]},lambda x:x['pairs'][0]['jaccard']>0),
 'word_limit': ({'student_text':'one two three','limit':2},lambda x:x['over_limit'] and x['remaining']==-1),
 'activity_evidence': ({'activities':[{'id':'a','student_confirmed':True,'source':'link','description':'Science fair'},{'id':'b'}]},lambda x:x['rows'][0]['ready'] and not x['rows'][1]['ready']),
 'interview_question_bank': ({'activities':[{'id':'a','title':'robotics','student_confirmed':True},{'id':'b','student_confirmed':False}]},lambda x:len(x['practice_questions'])==1 and x['generated_answers'] is None),
 'application_status': ({'applications':[{'id':'a','status':'in_progress'},{'id':'b','status':'submitted'}]},lambda x:x['counts']['submitted']==1 and x['follow_up'][0]['id']=='a'),
 'decision_comparison': ({'offers':[{'id':'a','annual_cost':50000,'confirmed_aid':20000},{'id':'b'}]},lambda x:x['offers'][0]['net_annual_cost']==30000 and x['offers'][1]['unknown_cost'] and x['recommendation'] is None),
 'visa_checklist': ({'requirements':[{'id':'a'},{'id':'b','official_url':'https://gov.example'}]},lambda x:x['official_source_required'][0]['id']=='a' and not x['legal_advice']),
 'source_freshness': ({'today':'2026-09-25','max_age_days':30,'sources':[{'id':'a','checked_on':'2026-09-24'},{'id':'b','checked_on':'2026-07-01'}]},lambda x:x['fresh'][0]['id']=='a' and x['stale'][0]['id']=='b'),
 'source_domain_check': ({'sources':[{'id':'a','url':'https://uni.edu/x','official':True},{'id':'b','url':'http://bad.example'}]},lambda x:x['results'][0]['https'] and not x['results'][1]['https'] and x['results'][0]['official_claim_unverified']),
 'privacy_minimization': ({'records':[{'id':'a','ssn':'secret','school':'X'},{'id':'b','school':'Y'}]},lambda x:x['records'][0]['sensitive_fields_to_remove']==['ssn'] and x['records'][1]['minimal']),
}

def test_exactly_twenty_functional_tools():
    assert set(TOOLS)==set(EXAMPLES) and len(TOOLS)==20

@pytest.mark.parametrize('name',sorted(EXAMPLES))
def test_each_planning_capability_has_verified_example(name):
    data,check=EXAMPLES[name]
    assert check(TOOLS[name](data)),name

@pytest.mark.parametrize('name,data', [
    ('deadline_triage',{'today':'bad','deadlines':[]}),
    ('workload_calendar',{'weeks':0,'total_hours':5}),
    ('word_limit',{'student_text':'a','limit':0}),
    ('tuition_scenario',{'tuition':-1}),
    ('source_freshness',{'today':'2026-09-25','sources':[],'max_age_days':-1}),
    ('requirement_gap',{'required':[],'completed':[],'unused':None})
])
def test_invalid_inputs(name,data):
    if name=='requirement_gap':
        assert TOOLS[name](data)['ready']
    else:
        with pytest.raises((ValueError,TypeError,KeyError)): TOOLS[name](data)

def test_api_route_dispatch_and_errors():
    from fastapi import HTTPException
    from app.modules.m23_study_abroad.routes import planning_tool, EnhancedParityIn
    assert planning_tool('word_limit', EnhancedParityIn(data={'student_text':'my own essay','limit':4}))['words']==3
    with pytest.raises(HTTPException) as unknown:
        planning_tool('not_a_tool', EnhancedParityIn(data={}))
    assert unknown.value.status_code == 404
    with pytest.raises(HTTPException) as invalid:
        planning_tool('word_limit', EnhancedParityIn(data={'student_text':'text','limit':0}))
    assert invalid.value.status_code == 422
