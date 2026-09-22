import base64,json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/project-builder/proof-status/live-receipts/ed25519/verify'
def payload():
 private=Ed25519PrivateKey.generate();public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);r={'receipt_id':'r','requirement_id':'req','deployed_version':'v1','environment':'prod','acceptance_inputs_sha256':'a'*64,'result_sha256':'b'*64,'status':'passed','issued_at':'2026-09-22T04:00:00Z','key_id':'issuer'};r['signature_base64']=base64.b64encode(private.sign(json.dumps(r,sort_keys=True,separators=(',',':')).encode())).decode();return {'expected_version':'v1','expected_environment':'prod','expected_inputs_sha256':'a'*64,'receipts':[r],'trusted_ed25519_public_keys':{'issuer':base64.b64encode(public).decode()}}
def test_verifies_ed25519_receipt_and_exact_live_binding():
 r=C.post(U,json=payload());assert r.status_code==200;b=r.json();assert b['valid'] and b['receipts'][0]['signature_algorithm']=='Ed25519' and len(b['proof_sha256'])==64
def test_rejects_tampering_wrong_binding_and_unknown_key():
 p=payload();p['receipts'][0]['status']='failed';r=C.post(U,json=p);assert r.status_code==422 and 'invalid receipt signature' in r.text
 p=payload();p['expected_version']='v2';r=C.post(U,json=p);assert r.status_code==422 and 'binding mismatch' in r.text
 p=payload();p['receipts'][0]['key_id']='other';r=C.post(U,json=p);assert r.status_code==422 and 'untrusted issuer' in r.text
