"""Row1279 full mounted app sensitivity; development identity headers only."""
import pytest

URL='/api/v1/api/modules/20/legal-1260-1309/support'
HEADERS={'X-Atlas-Tenant':'t1','X-Atlas-Actor':'u1'}
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','1');monkeypatch.setenv('ATLAS_ENV','development')
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:yield c

def body():
    authority={'id':'a1','citation_text':'Supplied citation','jurisdiction':'J-1','effective_date':'2020-01-01'}
    shared={'id':'a1','title':'t','citation':'c','source_url':'https://example.invalid/a','jurisdiction':'J-1','effective_date':'2020-01-01','last_checked_at':'2026-01-01','authority_type':'statute'}
    item={'id':'i1','request_kind':'interrogatory','relevance_basis':'claim_or_defense','proportionality':'proportional','custody':'unknown','objection_kind':'privilege','response_approval':'approved','source_ids':['missing']}
    return {'feature_id':1279,'tenant_id':'t1','actor_id':'u1','data':{'jurisdiction':'J-1','as_of':'2026-01-01','authorities':[shared],'discovery':{'jurisdiction':'J-1','as_of':'2026-01-01','authorities':[authority],'items':[item]}}}

def test_row1279_mounted_bounded_discovery_output(client):
    r=client.post(URL,json=body(),headers=HEADERS);assert r.status_code==200,r.text
    result=r.json()['result'];d=result['discovery_bookkeeping']
    assert d['row']==1279 and d['review_state']=='blocked'
    assert d['classified'][0]['unclassified_fields']==['custody']
    assert d['classified'][0]['missing_source_ids']==['missing']
    assert d['production_authorized'] is False
    assert result['isolation']=={'tenant_id':'t1','actor_id':'u1','cross_tenant_data':False}
    assert result['legal_conclusion'] is None and result['named_capability_executed'] is False

def test_row1279_mounted_engine_refusal_422(client):
    p=body();p['data']['discovery']['file']=True
    r=client.post(URL,json=p,headers=HEADERS);assert r.status_code==422 and 'DISC1279:EXTERNAL_EFFECT_REFUSED' in r.text

@pytest.mark.parametrize('where,key,value',[('outer','tenant_id','other'),('outer','actor_id','other'),('data','tenant_id','other'),('data','actor_id','other')])
def test_row1279_mounted_identity_mismatch_403(client,where,key,value):
    p=body();(p if where=='outer' else p['data'])[key]=value
    r=client.post(URL,json=p,headers=HEADERS);assert r.status_code==403,r.text

def test_row1279_development_default_identity_mismatch_403(client):
    r=client.post(URL,json=body());assert r.status_code==403,r.text

def test_row1279_mounted_legacy_without_nested_data_unchanged(client):
    p=body();del p['data']['discovery'];r=client.post(URL,json=p,headers=HEADERS)
    assert r.status_code==200 and 'discovery_bookkeeping' not in r.json()['result']

def test_row1278_mounted_unchanged(client):
    p=body();p['feature_id']=1278;r=client.post(URL,json=p,headers=HEADERS)
    assert r.status_code==200 and 'discovery_bookkeeping' not in r.json()['result']
