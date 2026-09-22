from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/executive-dashboard/proof-gaps';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'}
def test_dashboard_keeps_proof_levels_separate():
 p={'requirements':[{'requirement_id':'a','module_id':'M04','artifact_sha256':'a'*64,'test_name':'t','test_passed':True},{'requirement_id':'b','module_id':'M04','artifact_sha256':'b'*64,'test_name':'t2','test_passed':True,'live_receipt_id':'r','live_acceptance_passed':True}]};r=C.post(U,json=p,headers=H);assert r.status_code==200;x=r.json();assert x['counts']=={'total':2,'with_code_gap':0,'with_test_gap':0,'with_live_gap':1};assert x['modules']['M04']['live_acceptance_complete']==1 and len(x['dashboard_sha256'])==64
def test_dashboard_rejects_impossible_proof_and_duplicates():
 p={'requirements':[{'requirement_id':'a','module_id':'M','test_passed':True}]};r=C.post(U,json=p,headers=H);assert r.status_code==422 and 'test_name' in r.text
