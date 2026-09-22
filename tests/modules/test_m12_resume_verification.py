import base64,hashlib,hmac,json
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/ai-research-lab/reproducible-run/resume/verify';H={'X-Atlas-Tenant':'science','X-Atlas-Actor':'owner'};KEY='secret';RAW=b'dataset bytes';DS=hashlib.sha256(RAW).hexdigest()
def sign(p):return hmac.new(KEY.encode(),json.dumps(p,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
def payload():
 r={'node_id':'n1','provider':'lab','model':'m','input_sha256':'a'*64,'output_sha256':'b'*64,'spent_cents':4,'issued_at':'2026-09-22T04:00:00Z','key_id':'lab-v1'};r['signature_sha256_hmac']=sign(r)
 return {'checkpoint_sha256':'c'*64,'resume_from_node_id':'n2','datasets':[{'dataset_id':'d1','expected_sha256':DS,'content_base64':base64.b64encode(RAW).decode(),'source_ref':'doi:1','retrieved_at':'2026-09-22T03:00:00Z'}],'provider_receipts':[r],'trusted_hmac_keys':{'lab-v1':KEY}}
def test_verifies_dataset_bytes_and_signed_receipt_before_resume():
 r=C.post(U,json=payload(),headers=H);assert r.status_code==200;b=r.json();assert b['valid'] and b['datasets'][0]['byte_count']==len(RAW) and b['provider_receipts'][0]['signature_verified'];assert len(b['verification_sha256'])==64 and 'does not persist' in b['boundary']
def test_fails_closed_on_dataset_or_signature_mismatch():
 p=payload();p['datasets'][0]['content_base64']=base64.b64encode(b'tampered').decode();r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'byte hash mismatch' in r.text
 p=payload();p['provider_receipts'][0]['spent_cents']=9;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'invalid provider receipt signature' in r.text
def test_rejects_untrusted_key_and_duplicate_evidence():
 p=payload();p['trusted_hmac_keys']={'other':KEY};r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'untrusted' in r.text
 p=payload();p['datasets']*=2;r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'duplicate dataset_id' in r.text
