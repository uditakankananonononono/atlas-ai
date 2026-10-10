from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m23_study_abroad.lifecycle_routes_01_62 import router


def test_additive_contract_endpoints_reject_invalid_and_label_boundaries():
    app=FastAPI();app.include_router(router)
    with TestClient(app) as c:
        x=c.post('/lifecycle-workbench/source-freshness',json={'records':[{'source_url':'https://example.org','checked_at':'2026-10-10T00:00:00Z'}],'now':'2026-10-10T00:00:00Z','max_age_days':1})
        assert x.status_code==200 and x.json()['facts'][0]['provenance']['official_status_attested'] is False
        assert c.post('/lifecycle-workbench/validated-cosine',json={'left':[1,2],'right':[1]}).status_code==422
        assert c.post('/lifecycle-workbench/validated-cosine',json={'left':[True],'right':[1]}).status_code==422
        x=c.post('/lifecycle-workbench/lexical-vector',json={'text':'essay advice'})
        assert x.status_code==200 and x.json()['kind']=='lexical_hash'
        x=c.post('/lifecycle-workbench/cost-estimate',json={'data':{'currency':'USD'}})
        assert x.status_code==200 and x.json()['status']=='unknown_inputs'
