import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m23_study_abroad.interview import IdentityInterviewRepository
from app.modules.m23_study_abroad._commit_contract import CommitOutcomeUnknown, IntegrityWriteError, UnclassifiedIntegrityError
from app.modules.m23_study_abroad._fit_match import program_match

@pytest.mark.parametrize('exc,code',[(CommitOutcomeUnknown('SECRET'), 'commit_outcome_unknown'),(IntegrityWriteError('SECRET'),'integrity_write_failed'),(UnclassifiedIntegrityError('SECRET'),'integrity_unclassified')])
def test_real_http_failure_contract(monkeypatch,exc,code):
 def bad(*args,**kwargs):raise exc
 monkeypatch.setattr(IdentityInterviewRepository,'answer',bad)
 c=TestClient(app,raise_server_exceptions=False)
 r=c.post('/api/v1/study-abroad/identity-interviews/anything/turns',headers={'x-atlas-tenant':'own-m23'},json={'student_response':'Long enough concrete answer to this question','expected_question_index':0})
 assert r.status_code==500
 assert r.json()['detail']['code']==code
 assert 'SECRET' not in r.text

def test_real_http_compare_then_read():
 c=TestClient(app);h={'x-atlas-tenant':'own-m23-success','x-atlas-actor':'student'}
 r=c.post('/api/v1/study-abroad/identity-interviews',headers=h,json={'track':'college'});sid=r.json()['id'];url=f'/api/v1/study-abroad/identity-interviews/{sid}/turns'
 body={'student_response':'I organized science lessons for children in my neighborhood','expected_question_index':0}
 assert c.post(url,headers=h,json=body).status_code==200
 assert c.post(url,headers=h,json=body).status_code==409
 read=c.get(f'/api/v1/study-abroad/identity-interviews/{sid}',headers=h).json()
 assert read['question_index']==1 and len(read['turns'])==1
 assert c.post(url,headers={'x-atlas-tenant':'another-tenant'},json=body).status_code==404
 body['expected_question_index']=True
 assert c.post(url,headers=h,json=body).status_code==422

def test_name_match_reference_grid():
 # Explicit token arrays, no regex or substring oracle. ASCII scope intentionally.
 programs=[['art'],['data','science'],['robotics'],['a'],['biology']]
 for gw in [[],['a'],['arts'],['science'],['data','science'],['robot'],['robotics'],['biology','research']]:
  expected=any(any(gw[i:i+len(p)]==p for i in range(len(gw)-len(p)+1)) or bool({w for w in gw if len(w)>=4}&set(p)) for p in programs)
  assert program_match([' '.join(gw)],[' '.join(p) for p in programs])==int(expected)
 assert program_match(['a new start'],['art'])==0
