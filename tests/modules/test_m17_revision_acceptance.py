from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/narrative-architect/evidence-completeness/revision-acceptance/verify';H={'X-Atlas-Tenant':'owner','X-Atlas-Actor':'u'}
def payload():return {'essay_id':'e','from_version':'v1','to_version':'v2','revision_sha256':'a'*64,'accepted_suggestions':[{'suggestion_id':'s','suggestion_sha256':'b'*64,'owner_record_sha256':'c'*64}],'reviewed_by_owner':True,'reviewed_at':'2026-09-22T04:00:00Z','audience_boundary':'admissions','disclosure_approved':False}
def test_binds_owner_review_to_revision_without_implying_disclosure():
 r=C.post(U,json=payload(),headers=H);assert r.status_code==200;b=r.json();assert b['valid'] and not b['may_cross_audience_boundary'] and len(b['acceptance_sha256'])==64;assert 'does not edit' in b['boundary']
def test_fails_closed_without_owner_review_or_distinct_version():
 p=payload();p['reviewed_by_owner']=False;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'owner review is required' in r.text
 p=payload();p['to_version']='v1';r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'versions must differ' in r.text
