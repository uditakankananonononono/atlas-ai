from copy import deepcopy
import importlib
import pytest
from fastapi.testclient import TestClient
from app.main import app

CASES=[
('statistical_process_control1536','chart_baseline',{'series_id':'hand','values':['0','2']},'center_line','1'),
('process_capability1537','capability_indices',{'study_id':'hand','values':['0','2'],'lower_spec':'-2','upper_spec':'4'},'mean','1'),
('measurement_systems_analysis1538','gauge_rr_study',{'study_id':'hand','measurements':[{'part':p,'operator':o,'values':v} for p,o,v in [('p1','o1',['0','2']),('p1','o2',['0','2']),('p2','o1',['4','6']),('p2','o2',['4','6'])]]},'grand_mean','3'),
('design_of_experiments1539','plan_two_level_design',{'design_id':'hand','factors':['A','B'],'generators':[]},'run_count',4),
('taguchi_methods1540','analyze_taguchi_runs',{'goal':'smaller','factors':['A'],'runs':[{'id':'one','levels':[1],'responses':['1']}]},'run_count',1),
('response_surface_methodology1541','prepare',{'factors':['x'],'points':[{'x':'0'},{'x':'1'},{'x':'2'}],'responses':['1','2','5']},'response_mean','8/3'),
('robust_design1542','prepare',{'control_factors':['c'],'noise_factors':['n'],'objective':'maximize','scenarios':[{'id':'a','control':{'c':'1'},'noise':{'n':'0'},'response':'1/3'},{'id':'b','control':{'c':'1'},'noise':{'n':'1'},'response':'2/3'}]},'response_mean','1/2')]

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    return TestClient(app)

@pytest.mark.parametrize('engine,entry,payload,key,value',CASES)
def test_actual_dedicated_engine_over_app(client,oidc_auth_headers,monkeypatch,engine,entry,payload,key,value):
    base='app.modules.m20_general_cognitive_worker.'
    module=importlib.import_module(base+engine)
    expected=getattr(module,entry)(deepcopy(payload));assert expected[key]==value
    routes=importlib.import_module(base+engine+'_routes')
    calls=[];original=getattr(routes,entry)
    def observed(packet):calls.append(deepcopy(packet));return original(packet)
    monkeypatch.setattr(routes,entry,observed)
    path='/api/v1/api/modules/20/engineering/'+engine+'/run'
    r=client.post(path,json={'data':payload},headers=oidc_auth_headers('tenant-a','owner'))
    assert r.status_code==200,r.text
    assert r.json()==dict(expected,tenant_id='tenant-a',actor_id='owner')
    assert calls==[payload]
    assert client.post(path,json={'data':payload}).status_code==401
    for claim in [{'tenant_id':'tenant-b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'tenant-b'}]}]:
        assert client.post(path,json={'data':payload,**claim},headers=oidc_auth_headers('tenant-a','owner')).status_code==403
    invalid=client.post(path,json={'data':{}},headers=oidc_auth_headers('tenant-a','owner'))
    assert invalid.status_code==422
    assert client.post(path,json={'data':payload,'unexpected':True},headers=oidc_auth_headers()).status_code==422
