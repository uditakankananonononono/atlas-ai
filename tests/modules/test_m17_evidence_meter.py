from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/narrative-architect/evidence-completeness';H={'X-Atlas-Tenant':'owner','X-Atlas-Actor':'u'}
def test_meter_exposes_grounded_and_missing_claims():
 p={'materials':[{'material_id':'m1','kind':'owner_record','sha256':'a'*64,'excerpt':'Built a community lab.'}],'claims':[{'claim_id':'c1','kind':'concept','text':'Community builder','material_ids':['m1']},{'claim_id':'c2','kind':'critique_suggestion','text':'Add a leadership example','material_ids':['missing']}]};r=C.post(U,json=p,headers=H);assert r.status_code==200;x=r.json();assert x['tenant_id']=='owner' and x['coverage']==.5 and x['counts']['needs_owner_input']==1;assert x['claims'][1]['missing_material_ids']==['missing'] and len(x['meter_sha256'])==64
def test_meter_rejects_duplicate_claim_ids():
 c={'claim_id':'x','kind':'concept','text':'t'};r=C.post(U,json={'claims':[c,c]},headers=H);assert r.status_code==422 and 'duplicate claim_id' in r.text
