from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/browser-agent/submit/readback-diff';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'}
def test_readback_detects_every_load_bearing_change():
 a={'destination':'https://shop.example/confirm','fields':{'email':'a@x','qty':'1'},'total':'10.00','currency':'USD','irreversible_controls':['place order']};b={**a,'destination':'https://other.example/pay','fields':{'email':'a@x','qty':'2'},'total':'15.00','irreversible_controls':['place order','subscribe']};r=C.post(U,json={'approved':a,'current':b},headers=H);assert r.status_code==200;x=r.json();assert x['requires_new_approval'] and x['destination_changed'] and x['price_changed'];assert x['field_changes'][0]['field']=='qty' and x['new_irreversible_controls']==['subscribe'];assert len(x['diff_sha256'])==64 and 'never submits' in x['boundary']
def test_unchanged_snapshot_keeps_approval_match():
 a={'destination':'https://x.example','fields':{'q':'v'}};x=C.post(U,json={'approved':a,'current':a},headers=H).json();assert not x['requires_new_approval']
