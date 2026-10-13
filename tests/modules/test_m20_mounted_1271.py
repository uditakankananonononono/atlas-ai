"""Row 1271: real mounted app, caller-declared bookkeeping only."""
import copy
import pytest
from fastapi.testclient import TestClient
from app.main import app
PATH = '/api/v1/api/modules/20/international-law-1271/support'
PAYLOAD = {'jurisdiction': 'J', 'as_of': '2026-01-31', 'authorities': [{'id': 's1', 'citation_text': 'Caller citation', 'jurisdiction': 'J', 'effective_date': '2020-01-01'}], 'items': [{'id': 'i1', 'source_ids': ['s1'], 'source_kind': 'treaty', 'forum': 'international_court', 'actor': 'state', 'obligation_declared': 'owed', 'domestic_effect': 'direct_effect'}]}
client = TestClient(app)
def post(p):
    response = client.post(PATH,json=p,headers={'x-atlas-tenant':'row-1271','x-atlas-actor':'tester'})
    assert response.status_code == 200, response.text
    return response.json()
def test_row_1271_mounted_golden():
    body = post(copy.deepcopy(PAYLOAD))
    assert body['row'] == 1271
    assert body['classified'] == [{'id': 'i1', 'source_kind': 'treaty', 'forum': 'international_court', 'actor': 'state', 'obligation_declared': 'owed', 'domestic_effect': 'direct_effect', 'unclassified_fields': [], 'missing_source_ids': []}]
    assert body['counts'] == {'items':1,'unclassified':0,'blocked_items':0}
    assert body['review_state'] == 'counsel_review_required'
    assert body['obligation_determined'] is False
    assert body['authorities_independently_verified'] is False
    assert body['legal_conclusion'] is None
    assert body['filing_or_external_effect'] is False
    assert body['requires_licensed_counsel'] is True
    assert 'not legal advice' in body['disclaimer']
def test_row_1271_discriminating_bookkeeping():
    p = copy.deepcopy(PAYLOAD)
    p['items'][0]['source_kind'] = 'unknown'
    p['items'][0]['source_ids'] = ['missing']
    p['authorities'][0]['jurisdiction'] = 'Other'
    p['authorities'][0]['effective_date'] = '2026-02-01'
    b = post(p)
    assert b['classified'][0]['unclassified_fields'] == ['source_kind']
    assert b['classified'][0]['missing_source_ids'] == ['missing']
    assert b['authority_flags'] == [{'id':'s1','jurisdiction_mismatch':True,'effective_after_as_of':True,'independently_verified':False}]
    assert b['counts'] == {'items':1,'unclassified':1,'blocked_items':1}
    assert b['review_state'] == 'blocked'
def test_row_1271_malformed_date_refused():
    p = copy.deepcopy(PAYLOAD); p['as_of'] = '2026-02-30'
    response = client.post(PATH,json=p)
    assert response.status_code == 422
    assert response.json() == {'detail':'INTL1271:BAD_DATE:as_of'}
def test_row_1271_cap_refused():
    p = copy.deepcopy(PAYLOAD)
    p['items'] = [dict(p['items'][0],id=str(i)) for i in range(17)]
    response = client.post(PATH,json=p)
    assert response.status_code == 422
    assert response.json() == {'detail':'INTL1271:TOO_MANY:items'}
def test_row_1271_unknown_key_not_echoed():
    p = copy.deepcopy(PAYLOAD); p['private-secret-canary'] = 'must not echo'
    response = client.post(PATH,json=p)
    assert response.status_code == 422
    assert response.json() == {'detail':'INTL1271:UNKNOWN_KEY'}
    assert 'private-secret' not in response.text
    assert 'must not echo' not in response.text
def test_row_1271_strict_json_types():
    response = client.post(PATH,json=[])
    assert response.status_code == 422
    assert response.json() == {'detail':'INTL1271:BAD_TYPE:payload'}
def test_row_1271_no_external_effect_request():
    p = copy.deepcopy(PAYLOAD); p['send'] = True
    response = client.post(PATH,json=p)
    assert response.status_code == 422
    assert response.json() == {'detail':'INTL1271:EXTERNAL_EFFECT_REFUSED'}
def test_row_1271_mount_method_and_identity():
    response = client.get(PATH)
    assert response.status_code == 405
    schema = client.get('/openapi.json').json()
    assert schema['paths'][PATH]['post']['operationId'].startswith('support_1271_')
def test_row_1271_production_auth_required(monkeypatch,oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV','production'); monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0')
    response = client.post(PATH,json=PAYLOAD)
    assert response.status_code == 401
    response = client.post(PATH,json=PAYLOAD,headers=oidc_auth_headers(tenant='row-1271'))
    assert response.status_code == 200
    assert response.json()['legal_conclusion'] is None
def test_row_1271_deterministic_isolated_output():
    p = copy.deepcopy(PAYLOAD); original = copy.deepcopy(p)
    first = post(p); second = post(p)
    assert p == original and first == second
    first['legal_conclusion'] = 'not retained'
    assert post(p) == second
