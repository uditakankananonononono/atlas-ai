from fastapi.testclient import TestClient
from app.main import app
from app.modules.m23_study_abroad.interview import IdentityInterviewRepository
from app.modules.m23_study_abroad.story import BrandIdRow
from app.core.database import SessionLocal

client=TestClient(app)

def test_identity_interview_is_resumable_evidence_grounded_and_student_owned():
 headers={"x-atlas-tenant":"interview-a","x-atlas-actor":"student"}
 started=client.post('/api/v1/study-abroad/identity-interviews',headers=headers,json={"track":"college"})
 assert started.status_code==201
 session=started.json(); assert session['question_index']==0 and session['final_essay_prose'] is None
 answered=client.post(f"/api/v1/study-abroad/identity-interviews/{session['id']}/turns",headers=headers,json={"modality":"voice","student_response":"I organized a neighborhood science club after our school lab closed.","evidence_tags":["initiative","strength:leadership"]})
 assert answered.status_code==200
 resumed=client.get(f"/api/v1/study-abroad/identity-interviews/{session['id']}",headers=headers).json()
 assert resumed['question_index']==1 and resumed['turns'][0]['modality']=='voice'
 assert resumed['turns'][0]['student_response'].startswith('I organized')
 assert resumed['student_owned'] is True and resumed['final_essay_prose'] is None
 with SessionLocal() as db:
  brand=db.get(BrandIdRow,'interview-a')
  assert brand.evidence[0]['student_response']==resumed['turns'][0]['student_response']
  assert 'leadership' in brand.strengths

def test_identity_interview_is_tenant_scoped():
 a=IdentityInterviewRepository('interview-owner').start('career')
 try:
  IdentityInterviewRepository('different-tenant').get(a['id'])
  assert False,'cross-tenant read should fail'
 except LookupError:pass
