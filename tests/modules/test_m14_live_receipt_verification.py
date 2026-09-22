import hashlib,hmac,json
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/project-builder/proof-status/live-receipts/verify';K='secret'
def payload():
 r={'receipt_id':'r','requirement_id':'req','deployed_version':'v1','environment':'prod','acceptance_inputs_sha256':'a'*64,'result_sha256':'b'*64,'status':'passed','issued_at':'2026-09-22T04:00:00Z','key_id':'k'};r['signature_hmac_sha256']=hmac.new(K.encode(),json.dumps(r,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest();return {'expected_version':'v1','expected_environment':'prod','expected_inputs_sha256':'a'*64,'receipts':[r],'trusted_keys':{'k':K}}
def test_verifies_exact_live_binding_and_signature():
 r=C.post(U,json=payload());assert r.status_code==200;b=r.json();assert b['valid'] and b['receipts'][0]['signature_verified'] and len(b['proof_sha256'])==64
def test_rejects_wrong_binding_or_signature():
 p=payload();p['expected_version']='v2';r=C.post(U,json=p);assert r.status_code==422 and 'binding mismatch' in r.text
 p=payload();p['receipts'][0]['status']='failed';r=C.post(U,json=p);assert r.status_code==422 and 'invalid receipt signature' in r.text
