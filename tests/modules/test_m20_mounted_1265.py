"""Row 1265: real mounted app, caller-declared bookkeeping only."""
import copy
import pytest
from fastapi.testclient import TestClient
from app.main import app
PATH = '/api/v1/api/modules/20/due-process-1265/support'
PAYLOAD = {'jurisdiction': 'J', 'as_of': '2026-01-31', 'sources': [{'source_id': 's1', 'label': 'Caller supplied'}], 'protected_interest': {'description': 'Declared benefit', 'source_ids': ['s1']}, 'deprivation': {'description': 'Declared termination', 'date': '2026-01-10', 'source_ids': ['s1']}, 'notice': {'given': True, 'date': '2026-01-05', 'source_ids': ['s1']}, 'hearing': {'held': True, 'date': '2026-01-08', 'source_ids': ['s1']}, 'balancing_factors': [{'label': 'Declared factor', 'statement': 'Caller statement', 'source_ids': ['s1']}]}
client = TestClient(app)
def post(p):
    response = client.post(PATH,json=p,headers={'x-atlas-tenant':'row-1265','x-atlas-actor':'tester'})
    assert response.status_code == 200, response.text
    return response.json()
def test_row_1265_mounted_golden():
    body = post(copy.deepcopy(PAYLOAD))
    assert body['sequence'] == {'notice_vs_deprivation':'before','hearing_vs_deprivation':'before','notice_vs_hearing':'before'}
    assert body['gaps'] == []
    assert body['summary'] == {'elements_declared':5,'gap_count':0}
    assert all(e['status'] == 'DECLARED_SOURCED' for e in body['elements'].values())
    assert body['adequacy_judged'] is False
    assert body['authority_independently_verified'] is False
    assert body['legal_conclusion'] is None
    assert body['filing_or_external_effect'] is False
    assert body['requires_licensed_counsel'] is True
    assert 'not legal advice' in body['disclaimer']
def test_row_1265_discriminating_bookkeeping():
    p = copy.deepcopy(PAYLOAD)
    p['notice']['date'] = '2026-01-12'
    p['hearing']['date'] = '2026-02-01'
    p['protected_interest']['source_ids'] = ['missing']
    b = post(p)
    assert b['sequence']['notice_vs_deprivation'] == 'after'
    assert b['elements']['protected_interest']['status'] == 'DECLARED_UNSOURCED'
    assert [(g['element'],g['code']) for g in b['gaps']] == [('protected_interest','UNKNOWN_SOURCE_ID'),('hearing','DATE_AFTER_AS_OF')]
def test_row_1265_malformed_date_refused():
    p = copy.deepcopy(PAYLOAD); p['as_of'] = '2026-02-30'
    response = client.post(PATH,json=p)
    assert response.status_code == 422
    assert response.json() == {'detail':'DUEPRO1265:BAD_DATE:as_of'}
def test_row_1265_cap_refused():
    p = copy.deepcopy(PAYLOAD)
    p['sources'] = [{'source_id':str(i),'label':'L'} for i in range(65)]
    response = client.post(PATH,json=p)
    assert response.status_code == 422
    assert response.json() == {'detail':'DUEPRO1265:TOO_MANY:sources'}
def test_row_1265_unknown_key_not_echoed():
    p = copy.deepcopy(PAYLOAD); p['private-secret-canary'] = 'must not echo'
    response = client.post(PATH,json=p)
    assert response.status_code == 422
    assert response.json() == {'detail':'DUEPRO1265:UNKNOWN_KEY:request'}
    assert 'private-secret' not in response.text
    assert 'must not echo' not in response.text
def test_row_1265_strict_json_types():
    response = client.post(PATH,json=[])
    assert response.status_code == 422
    assert response.json() == {'detail':'DUEPRO1265:BAD_TYPE:request'}
def test_row_1265_no_external_effect_request():
    p = copy.deepcopy(PAYLOAD); p['send'] = True
    response = client.post(PATH,json=p)
    assert response.status_code == 422
    assert response.json() == {'detail':'DUEPRO1265:UNKNOWN_KEY:request'}
def test_row_1265_mount_method_and_identity():
    response = client.get(PATH)
    assert response.status_code == 405
    schema = client.get('/openapi.json').json()
    assert schema['paths'][PATH]['post']['operationId'].startswith('support_1265_')
def test_row_1265_production_auth_required(monkeypatch,oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV','production'); monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0')
    response = client.post(PATH,json=PAYLOAD)
    assert response.status_code == 401
    response = client.post(PATH,json=PAYLOAD,headers=oidc_auth_headers(tenant='row-1265'))
    assert response.status_code == 200
    assert response.json()['legal_conclusion'] is None
def test_row_1265_deterministic_isolated_output():
    p = copy.deepcopy(PAYLOAD); original = copy.deepcopy(p)
    first = post(p); second = post(p)
    assert p == original and first == second
    first['legal_conclusion'] = 'not retained'
    assert post(p) == second
