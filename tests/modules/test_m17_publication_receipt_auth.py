import base64,json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/narrative-architect/revision-publication/receipts/verify';H={'X-Atlas-Tenant':'owner','X-Atlas-Actor':'u'}
def p():
 private=Ed25519PrivateKey.generate();public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);r={'provider':'publisher','provider_id':'p1','essay_id':'e','revision_sha256':'a'*64,'audience_boundary':'admissions','published_at':'2026-09-22T04:00:00Z','key_id':'k'};r['signature_base64']=base64.b64encode(private.sign(json.dumps(r,sort_keys=True,separators=(',',':')).encode())).decode();return {'expected_essay_id':'e','expected_revision_sha256':'a'*64,'expected_audience_boundary':'admissions','receipt':r,'trusted_ed25519_public_keys':{'k':base64.b64encode(public).decode()}}
def test_verifies_signed_publication_receipt_binding():
 r=C.post(U,json=p(),headers=H);assert r.status_code==200 and r.json()['verified'] and r.json()['signature_algorithm']=='Ed25519'
def test_rejects_tamper_binding_mismatch_and_unknown_key():
 x=p();x['receipt']['provider_id']='p2';r=C.post(U,json=x,headers=H);assert r.status_code==422 and 'invalid publication receipt signature' in r.text
 x=p();x['expected_audience_boundary']='public';r=C.post(U,json=x,headers=H);assert r.status_code==422 and 'binding mismatch' in r.text
 x=p();x['receipt']['key_id']='other';r=C.post(U,json=x,headers=H);assert r.status_code==422 and 'untrusted publication provider' in r.text
