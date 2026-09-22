import base64,json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/executive-dashboard/proof-gaps/events/ed25519/verify'
def payload():
 private=Ed25519PrivateKey.generate();public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);e={'event_id':'e','producer':'ci','module_id':'16','requirement_id':'r','event_type':'deployment_receipt','proof_sha256':'a'*64,'deployment_version':'v1','environment':'prod','issued_at':'2026-09-22T04:00:00Z','key_id':'k'};e['signature_base64']=base64.b64encode(private.sign(json.dumps(e,sort_keys=True,separators=(',',':')).encode())).decode();return {'events':[e],'trusted_ed25519_public_keys':{'k':base64.b64encode(public).decode()}}
def test_verifies_ed25519_producer_event_and_deployment_binding():
 r=C.post(U,json=payload());assert r.status_code==200;b=r.json();assert b['valid'] and b['events'][0]['signature_algorithm']=='Ed25519' and len(b['events_sha256'])==64
def test_rejects_tamper_unknown_key_and_incomplete_deployment():
 p=payload();p['events'][0]['environment']='stage';r=C.post(U,json=p);assert r.status_code==422 and 'invalid producer' in r.text
 p=payload();p['events'][0]['key_id']='other';r=C.post(U,json=p);assert r.status_code==422 and 'untrusted producer' in r.text
 p=payload();p['events'][0]['environment']=None;r=C.post(U,json=p);assert r.status_code==422 and 'requires version and environment' in r.text
