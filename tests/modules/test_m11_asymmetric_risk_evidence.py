import base64,json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/calendar-intelligence/schedule-risk/live-evidence/ed25519/verify';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'}
def payload():
 private=Ed25519PrivateKey.generate();public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);s={'evidence_id':'e','kind':'travel_estimate','source_uri':'https://maps.example/r','retrieved_at':'2026-09-22T04:00:00Z','content_sha256':'a'*64,'provider':'maps','key_id':'k'};s['signature_base64']=base64.b64encode(private.sign(json.dumps(s,sort_keys=True,separators=(',',':')).encode())).decode();return {'snapshots':[s],'trusted_ed25519_public_keys':{'k':base64.b64encode(public).decode()}}
def test_verifies_signed_risk_snapshot():
 r=C.post(U,json=payload(),headers=H);assert r.status_code==200;b=r.json();assert b['valid'] and b['snapshots'][0]['signature_algorithm']=='Ed25519' and len(b['artifact_sha256'])==64
def test_rejects_tamper_unknown_key_and_duplicates():
 p=payload();p['snapshots'][0]['provider']='other';r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'invalid risk evidence signature' in r.text
 p=payload();p['snapshots'][0]['key_id']='other';r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'untrusted provider' in r.text
 p=payload();p['snapshots']*=2;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'duplicate evidence_id' in r.text
