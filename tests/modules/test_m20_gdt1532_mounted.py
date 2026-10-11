import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.engineering_1510_1559 import engineering_support_1510_1559

def packet():return {'geometry':'linear_1d','unit':'mm','datums':[{'id':'d','offset':0,'unit':'mm','source_ref':'d'}],'components':[{'id':'c','datum':'d','nominal':2,'lower':1,'upper':3,'sign':1,'unit':'mm','source_ref':'c'}],'fit_limits':[]}

def test_gdt_mounted_auth_and_cross_tenant(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner');path='/api/v1/api/modules/20/engineering/1510-1559/analyze'
 assert c.post(path,json={'method':'gdt','data':packet()}).status_code==401
 r=c.post(path,headers=h,json={'method':'gdt','data':packet()});assert r.status_code==200,r.text
 assert r.json()['result']['feature_id']==1532 and r.json()['result']['full_gdt_claimed'] is False
 assert c.post(path,headers=h,json={'method':'gdt','data':{**packet(),'resource_refs':[{'tenant_id':'b'}]}}).status_code==403
 assert c.post(path,headers=h,json={'method':'gdt','data':{'feature_control_frames':[]}}).status_code==422

def test_legacy_frame_only_payload_refuses_explicitly():
 legacy={'feature_control_frames':[{'id':'f','characteristic':'position','tolerance':.1,'requires_datum':True}]}
 with pytest.raises(ValueError)as e:engineering_support_1510_1559('gdt',legacy)
 assert str(e.value)=='GDT1532:unknown_fields:packet'

def test_owner_transport_context_and_actor_refusal(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner');path='/api/v1/api/modules/20/engineering/1510-1559/analyze'
 r=c.post(path,headers=h,json={'method':'gdt','data':{**packet(),'tenant_id':'a','actor_id':'owner','resource_refs':[{'tenant_id':'a'}]}})
 assert r.status_code==200 and r.json()['tenant_id']=='a' and r.json()['actor_id']=='owner'
 for field,value in [('tenant_id','b'),('actor_id','other')]:
  assert c.post(path,headers=h,json={'method':'gdt','data':{**packet(),field:value}}).status_code==403
