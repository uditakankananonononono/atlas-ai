import base64,json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/ai-research-lab/reproducible-run/resume/provider-receipts/verify';H={'X-Atlas-Tenant':'science','X-Atlas-Actor':'owner'}
def payload():
 private=Ed25519PrivateKey.generate();public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);r={'node_id':'n','provider':'p','model':'m','input_sha256':'a'*64,'output_sha256':'b'*64,'spent_cents':3,'issued_at':'2026-09-22T04:00:00Z','key_id':'p-v1'};sig=private.sign(json.dumps(r,sort_keys=True,separators=(',',':')).encode());r['signature_base64']=base64.b64encode(sig).decode();return {'checkpoint_sha256':'c'*64,'resume_from_node_id':'next','provider_receipts':[r],'trusted_ed25519_public_keys':{'p-v1':base64.b64encode(public).decode()}}
def test_verifies_provider_issued_ed25519_receipt():
 r=C.post(U,json=payload(),headers=H);assert r.status_code==200;b=r.json();assert b['valid'] and b['provider_receipts'][0]['signature_algorithm']=='Ed25519' and b['provider_receipts'][0]['signature_verified'];assert len(b['verification_sha256'])==64
def test_rejects_tampering_and_untrusted_public_key():
 p=payload();p['provider_receipts'][0]['spent_cents']=4;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'invalid provider receipt signature' in r.text
 p=payload();p['provider_receipts'][0]['key_id']='other';r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'untrusted provider public key' in r.text
def test_rejects_duplicate_node_receipts():
 p=payload();p['provider_receipts']*=2;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'duplicate node_id' in r.text
