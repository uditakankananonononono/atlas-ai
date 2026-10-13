"""Row1293: dedicated authenticated route; strict engine keys, principal-bound."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
PATH = '/api/v1/api/modules/20/legal/1293/support'
VOCAB = ['communication', 'participants', 'purpose', 'confidentiality', 'waiver', 'exceptions']

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    with TestClient(app) as c:
        yield c

def data(**changes):
    return dict({'row': 1293, 'as_of': '2026-10-12', 'entries': [
        {'element': VOCAB[0], 'status': 'supplied', 'source_ref': 'PRIVATE_REF', 'entry_date': '2026-10-10'},
        {'element': VOCAB[1], 'status': 'missing'}]}, **changes)

def body(d=None, tenant='tenant-a', actor='tester'):
    return {'tenant_id': tenant, 'actor_id': actor, 'data': data() if d is None else d}

def test_success_shape(client, oidc_auth_headers):
    r = client.post(PATH, headers=oidc_auth_headers(), json=body())
    assert r.status_code == 200, r.text
    out = r.json()
    assert set(out) == {'module_id', 'tenant_id', 'actor_id', 'result', 'requires_licensed_counsel'}
    assert out['module_id'] == 20 and out['tenant_id'] == 'tenant-a' and out['actor_id'] == 'tester'
    assert out['requires_licensed_counsel'] is True
    res = out['result']
    assert res['row'] == 1293 and [e['element'] for e in res['elements']] == VOCAB
    assert res['coverage']['referenced'] == 1 and res['coverage']['declared_missing'] == 1
    assert res['legal_conclusion'] is False and res['references_verified'] is False
    assert 'status' not in out and 'PRIVATE_REF' not in r.text

def test_requires_auth(client, oidc_auth_headers):
    assert client.post(PATH, headers=oidc_auth_headers(), json=body()).status_code == 200  # route exists
    assert client.post(PATH, json=body()).status_code in (401, 403)
    assert client.post(PATH, headers={'Authorization': 'Bearer bogus'}, json=body()).status_code in (401, 403)

@pytest.mark.parametrize('kw', [{'tenant': 'other'}, {'actor': 'other'}])
def test_outer_identity_mismatch_403(client, oidc_auth_headers, kw):
    r = client.post(PATH, headers=oidc_auth_headers(), json=body(**kw))
    assert r.status_code == 403

@pytest.mark.parametrize('k', ['tenant_id', 'actor_id'])
def test_nested_identity_mismatch_403(client, oidc_auth_headers, k):
    r = client.post(PATH, headers=oidc_auth_headers(), json=body(data(**{k: 'other'})))
    assert r.status_code == 403

@pytest.mark.parametrize('k,v', [('tenant_id', 'tenant-a'), ('actor_id', 'tester')])
def test_matching_nested_identity_not_stripped(client, oidc_auth_headers, k, v):
    r = client.post(PATH, headers=oidc_auth_headers(), json=body(data(**{k: v})))
    assert r.status_code == 422, r.text
    assert r.json() == {'detail': 'ATTORN1293: UNKNOWN:request'}

def test_unknown_key_refused(client, oidc_auth_headers):
    r = client.post(PATH, headers=oidc_auth_headers(), json=body(data(extra=1)))
    assert r.status_code == 422 and r.json() == {'detail': 'ATTORN1293: UNKNOWN:request'}

def test_engine_refusals(client, oidc_auth_headers):
    h = oidc_auth_headers()
    for d, reason in [(data(row=1292), 'UNKNOWN:row'), (data(entries=[]), 'EMPTY:entries'),
                      (data(as_of='20260230'), 'BAD_TYPE:as_of'), (data(send=1), 'SEND:send')]:
        r = client.post(PATH, headers=h, json=body(d))
        assert r.status_code == 422, r.text
        assert r.json() == {'detail': 'ATTORN1293: ' + reason}

def test_wrapper_extra_field_and_missing_data(client, oidc_auth_headers):
    h = oidc_auth_headers()
    b = body(); b['feature_id'] = 1293
    assert client.post(PATH, headers=h, json=b).status_code == 200
    assert client.post(PATH, headers=h, json={'tenant_id': 'tenant-a', 'actor_id': 'tester'}).status_code == 422

def test_shared_template_route_untouched(client, oidc_auth_headers):
    r = client.post('/api/v1/api/modules/20/legal-1260-1309/support', headers=oidc_auth_headers(),
                    json={'feature_id': 1293, 'tenant_id': 'tenant-a', 'actor_id': 'tester', 'data': {}})
    assert r.status_code == 422 and 'jurisdiction' in r.text

def test_principal_comes_from_token_not_default(client, oidc_auth_headers):
    h = oidc_auth_headers(tenant='tenant-b', subject='someone-else')
    r = client.post(PATH, headers=h, json=body(tenant='tenant-b', actor='someone-else'))
    assert r.status_code == 200, r.text
    assert r.json()['tenant_id'] == 'tenant-b' and r.json()['actor_id'] == 'someone-else'
    assert client.post(PATH, headers=h, json=body()).status_code == 403
