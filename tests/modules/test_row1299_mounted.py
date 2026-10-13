"""Row 1299 mounted app tests; bookkeeping, no discovery execution claim."""
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

PATH='/api/v1/modules/20/rows/1299/run'
H={'x-atlas-tenant':'row1299','x-atlas-actor':'tester'}
V=['hold_scope','custodians','sources','collection_provenance','processing','production_gates']

def entry(element,status='supplied',ref='private-ref',date=None):
    e={'element':element,'status':status}
    if ref is not None:e['source_ref']=ref
    if date is not None:e['entry_date']=date
    return e

def payload(entries=None,**kw):
    p={'row':1299,'as_of':'2026-10-12','entries':entries if entries is not None else [entry('hold_scope')]}
    p.update(kw);return p

def call(p):return TestClient(app).post(PATH,json=p,headers=H)

def success(p):
    r=call(p);assert r.status_code==200,r.text
    return r.json()

def test_row1299_mounted_partition_and_missing_flag():
    r=success(payload([entry(V[0],date='2026-10-01'),entry(V[0],'missing',None),entry(V[1]),
                       entry(V[1],'disputed','disputed-ref'),entry(V[2],'missing',None)]))
    assert [e['element'] for e in r['elements']]==V
    assert [e['status'] for e in r['elements']]==['referenced','disputed','declared_missing','unaddressed','unaddressed','unaddressed']
    assert r['elements'][0]['also_declared_missing'] is True
    assert r['elements'][1]['also_declared_missing'] is False
    assert r['coverage']=={'elements_total':6,'referenced':1,'disputed':1,'declared_missing':1,'unaddressed':3}

def test_row1299_latest_supplied_date_only():
    r=success(payload([entry(V[0],ref='old',date='2026-10-01'),entry(V[0],ref='new',date='2026-10-10'),
                       entry(V[0],'disputed','d','2026-10-11')]))
    assert r['elements'][0]['latest_entry_date']=='2026-10-10'
    assert r['elements'][0]['days_since_latest']==2

def test_row1299_source_refs_not_echoed_boundaries():
    r=success(payload())
    assert 'private-ref' not in json.dumps(r)
    assert r['row']==1299
    assert r['counsel_review_required'] is True
    assert r['legal_conclusion'] is False
    assert r['references_verified'] is False
    assert 'never collects or produces anything' in r['scope']

@pytest.mark.parametrize('p,code',[
    (payload([],),'EMPTY:entries'),
    (payload([entry('unknown')]),'UNKNOWN:element'),
    (payload([entry(V[0],'verified')]),'UNKNOWN:status'),
    (payload([entry(V[0],date='2026-10-13')]),'BAD_TYPE:entry_date'),
    (payload([entry(V[0]),entry(V[0])]),'BAD_TYPE:entries'),
    (payload([entry(V[0],ref='x'*201)]),'BAD_TYPE:source_ref'),
    (payload([entry(V[0],ref='a\u200bb')]),'BAD_TYPE:source_ref'),
    (payload([entry(V[0])]*201),'OVERSIZE:entries'),
    (payload(row=True),'UNKNOWN:row'),
    (payload(as_of='2026-02-30'),'BAD_TYPE:as_of'),
    (payload(send=True),'SEND:send'),
    (payload(entries=[{'element':V[0],'status':'supplied','source_ref':'safe','extra':{'password':'not-a-secret'}}]),'NOCREDS:password'),
])
def test_row1299_refusals(p,code):
    r=call(p);assert r.status_code==400,r.text
    assert r.json()=={'detail':'EDISCO1299: '+code}

def test_row1299_production_identity_no_override(monkeypatch,oidc_auth_headers):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    monkeypatch.setenv('ATLAS_ENV','production')
    c=TestClient(app)
    assert c.post(PATH,json=payload()).status_code==401
    r=c.post(PATH,json=payload(),headers=oidc_auth_headers('row1299','alice'))
    assert r.status_code==200,r.text
    assert r.json()['coverage']['referenced']==1
