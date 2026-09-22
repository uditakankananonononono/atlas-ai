import hashlib,hmac,json
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/executive-dashboard/proof-gaps/events/verify';K='key'
def payload():
 e={'event_id':'e','producer':'ci','module_id':'16','requirement_id':'r','event_type':'deployment_receipt','proof_sha256':'a'*64,'deployment_version':'v1','environment':'prod','issued_at':'2026-09-22T04:00:00Z','key_id':'k'};e['signature_hmac_sha256']=hmac.new(K.encode(),json.dumps(e,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest();return {'events':[e],'trusted_producer_keys':{'k':K}}
def test_authenticates_producer_event_with_deployment_binding():
 r=C.post(U,json=payload());assert r.status_code==200;b=r.json();assert b['valid'] and b['events'][0]['signature_verified'] and len(b['events_sha256'])==64
def test_rejects_tamper_and_incomplete_deployment_receipt():
 p=payload();p['events'][0]['environment']='stage';r=C.post(U,json=p);assert r.status_code==422 and 'invalid producer' in r.text
 p=payload();p['events'][0]['environment']=None;r=C.post(U,json=p);assert r.status_code==422 and 'requires version and environment' in r.text
