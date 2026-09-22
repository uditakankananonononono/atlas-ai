from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/knowledge-workspace/contradiction-revisions/verify';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'};A='a'*64;B='b'*64
def rev(i,prev=None,action='retain_both'):
 return {'revision_id':str(i),'claim_key':'sample size','action':action,'preferred_evidence_id':'e1' if action=='prefer' else None,'rationale':'review','decided_at':f'2026-09-2{i}T08:00:00Z','actor_id':'owner','previous_revision_sha256':prev,'source_snapshots':[{'evidence_id':'e1','content_sha256':A},{'evidence_id':'e2','content_sha256':B}]}
def test_append_only_chain_binds_source_hashes_and_decisions():
 first=rev(1);r=C.post(U,json={'revisions':[first]},headers=H);assert r.status_code==200;head=r.json()['head_sha256'];second=rev(2,head,'prefer');x=C.post(U,json={'revisions':[first,second]},headers=H).json();assert x['valid'] and x['revision_count']==2 and x['latest_decision']['preferred_evidence_id']=='e1' and len(x['head_sha256'])==64
def test_rejects_chain_break_and_unsnapshotted_preference():
 r=C.post(U,json={'revisions':[rev(1),rev(2,'f'*64)]},headers=H);assert r.status_code==422 and 'chain break' in r.text
 x=rev(1,action='prefer');x['preferred_evidence_id']='missing';r=C.post(U,json={'revisions':[x]},headers=H);assert r.status_code==422 and 'not snapshotted' in r.text
