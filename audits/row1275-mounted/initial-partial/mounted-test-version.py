"""Dedicated mounted arbitration declaration bookkeeping, not legal decisions."""
import copy,json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker import arbitration1275 as engine
PATH='/api/v1/api/modules/20/arbitration/1275/organize'
DATA={'jurisdiction':'Declared-Jurisdiction','as_of':'2026-01-01','authorities':[{'id':'a1','citation_text':'Supplied citation','jurisdiction':'Declared-Jurisdiction','effective_date':'2020-01-01'}],'items':[{'id':'i1','consent':'written_agreement','seat':'declared_seat','rules_kind':'institutional','scope':'all_disputes','arbitrability':'arbitrable','tribunal_status':'constituted','award_review':'none_declared','source_ids':['a1']}]}
@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    monkeypatch.setenv('ATLAS_ENV','production')
    return TestClient(app,raise_server_exceptions=False)

def test_actual_dedicated_engine_output_and_tenant_identity(client,oidc_auth_headers):
    for tenant,actor in [('t1','a1'),('t2','a2')]:
        r=client.post(PATH,headers=oidc_auth_headers(tenant,actor),json=DATA)
        assert r.status_code==200,r.text
        assert r.json()=={**engine.organize(copy.deepcopy(DATA)),'tenant_id':tenant,'actor_id':actor}
        assert r.json()['arbitrability_decided'] is False
        assert r.json()['legal_conclusion'] is None
        assert r.json()['filing_or_external_effect'] is False

def test_same_dedicated_items_payload_unknown_vocab_refused(client,oidc_auth_headers):
    data=copy.deepcopy(DATA);data['items'][0]['consent']='PRIVATE_BAD_VALUE'
    r=client.post(PATH,headers=oidc_auth_headers(),json=data)
    assert r.status_code==422,r.text
    assert r.json()=={'detail':'ARB1275:UNKNOWN_VALUE:consent'}
    assert 'PRIVATE_BAD_VALUE' not in r.text

@pytest.mark.parametrize('key,code',[('decide','CONCLUSION_REFUSED'),('send','EXTERNAL_EFFECT_REFUSED'),('tenant_id','UNKNOWN_KEY'),('actor_id','UNKNOWN_KEY')])
def test_forbidden_or_owner_fields_not_accepted(client,oidc_auth_headers,key,code):
    r=client.post(PATH,headers=oidc_auth_headers(),json={**DATA,key:'other'})
    assert r.status_code==422 and r.json()=={'detail':'ARB1275:'+code}

def test_auth_before_body_or_engine(client,monkeypatch):
    monkeypatch.setattr(engine,'organize',lambda data:pytest.fail('unauthenticated engine reached'))
    assert client.post(PATH,json=DATA).status_code==401
    assert client.post(PATH,content=b'{broken').status_code==401

@pytest.mark.parametrize('raw',[b'null',b'[]',b'{broken',b'\xff',b'{"jurisdiction":NaN}',b'{"items":[],"items":[]}'])
def test_decoder_or_engine_refuses_bad_input(client,oidc_auth_headers,raw):
    r=client.post(PATH,headers={**oidc_auth_headers(),'Content-Type':'application/json'},content=raw)
    assert r.status_code==422,r.text
    assert r.json()['detail'].startswith('ARB1275:')

def test_media_and_body_byte_cap(client,oidc_auth_headers):
    headers=oidc_auth_headers()
    assert client.post(PATH,headers={**headers,'Content-Type':'text/plain'},content='private').status_code==415
    raw=json.dumps(DATA).encode();raw+=b' '*(32768-len(raw))
    assert client.post(PATH,headers={**headers,'Content-Type':'application/json'},content=raw).status_code==200
    assert client.post(PATH,headers={**headers,'Content-Type':'application/json'},content=raw+b' ').status_code==413

def test_unknown_missing_source_and_authority_flags(client,oidc_auth_headers):
    data=copy.deepcopy(DATA);data['items'][0]['consent']='unknown';data['items'][0]['source_ids']=['missing']
    data['authorities'][0]['jurisdiction']='Other';data['authorities'][0]['effective_date']='2027-01-01'
    r=client.post(PATH,headers=oidc_auth_headers(),json=data)
    assert r.status_code==200,r.text
    assert r.json()['review_state']=='blocked'
    assert r.json()['classified'][0]['missing_source_ids']==['missing']
    assert r.json()['classified'][0]['unclassified_fields']==['consent']
    assert r.json()['authority_flags'][0]['jurisdiction_mismatch'] is True
    assert r.json()['authority_flags'][0]['effective_after_as_of'] is True

@pytest.mark.parametrize('case,detail',[('items','TOO_MANY:items'),('sources','TOO_MANY:source_ids'),('date','BAD_DATE:as_of')])
def test_engine_caps_and_dates_pass_through(client,oidc_auth_headers,case,detail):
    data=copy.deepcopy(DATA)
    if case=='items':data['items']=[dict(data['items'][0],id=str(i)) for i in range(17)]
    if case=='sources':data['items'][0]['source_ids']=['a1']*9
    if case=='date':data['as_of']='2026-02-30'
    r=client.post(PATH,headers=oidc_auth_headers(),json=data)
    assert r.status_code==422 and r.json()=={'detail':'ARB1275:'+detail}
