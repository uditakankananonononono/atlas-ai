import base64,json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/document-generator/publication-receipts/provider/ed25519/verify';H={'X-Atlas-Tenant':'t'}
def payload():
 private=Ed25519PrivateKey.generate();public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);r={'approval_id':'a','version_id':'v','provider':'store','object_key':'private/v','access':'private','download_url':'https://files.example/v','published_sha256':'a'*64,'byte_size':42,'uploaded_at':'2026-09-22T04:00:00Z','key_id':'k'};r['signature_base64']=base64.b64encode(private.sign(json.dumps(r,sort_keys=True,separators=(',',':')).encode())).decode();return {'expected_sha256':'a'*64,'approval_consumed':True,'receipt':r,'trusted_ed25519_public_keys':{'k':base64.b64encode(public).decode()}}
def test_verifies_ed25519_private_publication_receipt():
 r=C.post(U,json=payload(),headers=H);assert r.status_code==200;b=r.json();assert b['verified'] and b['signature_algorithm']=='Ed25519' and len(b['receipt_sha256'])==64
def test_rejects_tamper_public_access_and_unconsumed_approval():
 p=payload();p['receipt']['byte_size']=43;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'invalid provider receipt signature' in r.text
 p=payload();p['receipt']['access']='public';r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'must be private' in r.text
 p=payload();p['approval_consumed']=False;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'approval must be consumed' in r.text
