from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app); URL='/api/v1/calendar-intelligence/schedule-risk'; HEADERS={'X-Atlas-Tenant':'lab','X-Atlas-Actor':'owner'}

def test_combines_buffer_dependency_and_cancellation_risks_without_mutation():
 payload={'as_of':'2026-09-22T04:00:00Z','completed_dependency_ids':[], 'items':[
  {'item_id':'prep-source','title':'Lab work','start':'2026-09-22T08:00:00Z','end':'2026-09-22T09:30:00Z'},
  {'item_id':'conference','title':'Conference','start':'2026-09-22T10:00:00Z','end':'2026-09-22T12:00:00Z','travel_minutes_before':45,'prep_minutes':30,'depends_on':['slides','unknown-record'],'cancellation':{'free_cancel_until':'2026-09-22T03:00:00Z','cancellation_fee':150,'currency':'USD','source_ref':'terms-v2'}},
 ]}
 r=client.post(URL,json=payload,headers=HEADERS); assert r.status_code==200; b=r.json()
 assert b['tenant_id']=='lab' and b['risk_count']==3 and b['high_risk_count']==3
 kinds={x['kind'] for x in b['risks']}; assert kinds=={'insufficient_buffer','dependency_incomplete','cancellation_exposure'}
 dep=next(x for x in b['risks'] if x['kind']=='dependency_incomplete'); assert dep['evidence']['unknown_dependency_ids']==['slides','unknown-record']
 cancel=next(x for x in b['risks'] if x['kind']=='cancellation_exposure'); assert cancel['evidence']['state']=='free_window_expired' and cancel['evidence']['terms_unverified'] is False
 assert len(b['risk_sha256'])==64 and 'read-only' in b['boundary']

def test_rejects_duplicate_items_naive_time_and_partial_money():
 item={'item_id':'a','title':'A','start':'2026-09-22T10:00:00Z','end':'2026-09-22T11:00:00Z'}
 r=client.post(URL,json={'items':[item,item]},headers=HEADERS); assert r.status_code==422 and 'duplicate item_id' in r.text
 item['item_id']='b';item['start']='2026-09-22T10:00:00'; r=client.post(URL,json={'items':[item]},headers=HEADERS); assert r.status_code==422 and 'timezone-aware' in r.text
 item['start']='2026-09-22T10:00:00Z';item['cancellation']={'cancellation_fee':5}; r=client.post(URL,json={'items':[item]},headers=HEADERS); assert r.status_code==422 and 'supplied together' in r.text
