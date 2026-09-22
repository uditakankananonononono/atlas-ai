import hashlib,hmac,json
from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/executive-dashboard/proof-gaps/events/subscription-delivery/verify';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'};K='key'
def p():
 e={'producer':'ci','delivery_id':'d','payload':{'event_id':'e'},'key_id':'k'};e['signature_hmac_sha256']=hmac.new(K.encode(),json.dumps(e,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest();return {'envelope':e,'trusted_delivery_keys':{'k':K}}
def test_verifies_pushed_producer_delivery():
 r=C.post(U,json=p(),headers=H);assert r.status_code==200 and r.json()['verified'] and r.json()['payload']['event_id']=='e'
def test_rejects_tampered_or_unknown_delivery_key():
 x=p();x['envelope']['payload']['event_id']='other';r=C.post(U,json=x,headers=H);assert r.status_code==422 and 'invalid producer delivery signature' in r.text
 x=p();x['envelope']['key_id']='other';r=C.post(U,json=x,headers=H);assert r.status_code==422 and 'untrusted producer delivery key' in r.text
