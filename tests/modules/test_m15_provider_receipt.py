import hashlib,hmac,json
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/document-generator/publication-receipts/provider/verify';H={'X-Atlas-Tenant':'t'};K='key'
def payload():
 r={'approval_id':'a','version_id':'v','provider':'store','object_key':'private/v','access':'private','download_url':'https://files.example/v','published_sha256':'a'*64,'byte_size':42,'uploaded_at':'2026-09-22T04:00:00Z','key_id':'k'};r['signature_hmac_sha256']=hmac.new(K.encode(),json.dumps(r,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest();return {'expected_sha256':'a'*64,'approval_consumed':True,'receipt':r,'trusted_provider_keys':{'k':K}}
def test_authenticates_private_provider_receipt_and_render_hash():
 r=C.post(U,json=payload(),headers=H);assert r.status_code==200;b=r.json();assert b['verified'] and b['provider_signature_verified'] and len(b['receipt_sha256'])==64
def test_rejects_tampering_public_access_or_unconsumed_approval():
 p=payload();p['receipt']['byte_size']=43;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'invalid provider receipt signature' in r.text
 p=payload();p['approval_consumed']=False;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'approval must be consumed' in r.text
 p=payload();p['receipt']['access']='public';r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'must be private' in r.text
