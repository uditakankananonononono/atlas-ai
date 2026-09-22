from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/document-generator/publication-receipts/verify';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'};A='a'*64
def test_private_publication_receipt_requires_consumed_approval_and_hash_match():
 p={'approval_id':'ap','version_id':'v','expected_sha256':A,'published_sha256':A,'access':'private','download_url':'https://files.example/x','byte_size':42,'approval_consumed':True};r=C.post(U,json=p,headers=H);assert r.status_code==200;x=r.json();assert x['verified'] and x['access']=='private' and len(x['receipt_sha256'])==64
 p['published_sha256']='b'*64;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'does not match' in r.text
def test_receipt_rejects_public_or_unconsumed():
 p={'approval_id':'ap','version_id':'v','expected_sha256':A,'published_sha256':A,'access':'public','download_url':'https://x.example/f','byte_size':1,'approval_consumed':False};r=C.post(U,json=p,headers=H);assert r.status_code==422
