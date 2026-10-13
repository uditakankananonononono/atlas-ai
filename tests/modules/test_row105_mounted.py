"""Row105: exercise the real app mount and production-auth verifier."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

PATH = '/m20/pre-suasion105/review'


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    with TestClient(app) as c:
        yield c


def body(**changes):
    return dict({'context': 'agenda', 'disclosed': True, 'attention_weights': [3, 1]}, **changes)


def test_row105_mounted_exact_shares_and_limits(client, oidc_auth_headers):
    response = client.post(PATH, headers=oidc_auth_headers(), json=body())
    assert response.status_code == 200, response.text
    r = response.json()
    assert r == {'row': 105, 'context': 'agenda', 'disclosed': True,
                 'shares': ['3/4', '1/4'], 'max_share': '3/4', 'max_share_index': [0],
                 'balance': 0.811278, 'concentration_check': False,
                 'covert_influence_blocked': False, 'allowed': True,
                 'limits': [
                     "Supplied weights only; nothing here measures where anyone's attention goes.",
                     'Context-setting must be disclosed to the people it concerns; an undisclosed plan is never allowed.',
                     'Not persuasion, not a measurement and not advice; the balance figure describes the supplied numbers only.']}


def test_row105_mounted_undisclosed_refuses_deployment(client, oidc_auth_headers):
    response = client.post(PATH, headers=oidc_auth_headers(), json=body(disclosed=False))
    assert response.status_code == 200, response.text
    assert response.json()['allowed'] is False
    assert response.json()['covert_influence_blocked'] is True


@pytest.mark.parametrize('changes,field', [
    ({'disclosed': 1}, 'disclosed'), ({'attention_weights': [True, 1]}, 'attention_weights'),
    ({'attention_weights': [1]}, 'attention_weights'), ({'attention_weights': [1]*21}, 'attention_weights'),
    ({'attention_weights': [0, 0]}, 'attention_weights'), ({'context': 'x'*201}, 'context'),
    ({'context': 'ZZSECRET9\x00'}, 'context'), ({'unknown': 'ZZSECRET9'}, 'too many keys'),
])
def test_row105_mounted_strict_refusals(client, oidc_auth_headers, changes, field):
    response = client.post(PATH, headers=oidc_auth_headers(), json=body(**changes))
    assert response.status_code == 422, response.text
    assert response.json()['detail'].startswith('PRESUA105: ')
    assert field in response.json()['detail']
    assert 'ZZSECRET9' not in response.text


@pytest.mark.parametrize('raw', ['[]', 'null', '{broken',
    '{"context":"agenda","disclosed":true,"disclosed":false,"attention_weights":[1,1]}'])
def test_row105_mounted_bad_json(client, oidc_auth_headers, raw):
    response = client.post(PATH, headers={**oidc_auth_headers(), 'Content-Type': 'application/json'}, content=raw)
    assert response.status_code == 422, response.text
    assert response.json()['detail'].startswith('PRESUA105: ')


def test_row105_mounted_envelope_and_media_boundaries(client, oidc_auth_headers):
    headers = oidc_auth_headers()
    r = client.post(PATH, headers={**headers, 'Content-Type': 'text/plain'}, content='ZZSECRET9')
    assert r.status_code == 415, r.text
    r = client.post(PATH, headers={**headers, 'Content-Type': 'application/json'}, content=' '*8193)
    assert r.status_code == 413, r.text
    assert 'ZZSECRET9' not in r.text


def test_row105_mounted_auth_before_review(client, monkeypatch):
    from app.modules.m20_general_cognitive_worker import pre_suasion105
    def forbidden(_):
        raise AssertionError('unauthenticated review reached helper')
    monkeypatch.setattr(pre_suasion105, 'review', forbidden)
    response = client.post(PATH, json=body())
    assert response.status_code == 401


def test_row105_mounted_boundary_and_tenant_repeat(client, oidc_auth_headers):
    data = body(context='x'*200, attention_weights=[10**9]*20)
    a = client.post(PATH, headers=oidc_auth_headers('tenant-a'), json=data)
    b = client.post(PATH, headers=oidc_auth_headers('tenant-b'), json=data)
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    assert a.json() == b.json()
    assert a.json()['shares'] == ['1/20']*20
    assert a.json()['max_share_index'] == list(range(20))
    assert a.json()['balance'] == 1.0


def test_row105_mounted_json_byte_limit_exact_boundary(client, oidc_auth_headers):
    import json
    headers = {**oidc_auth_headers(), 'Content-Type': 'application/json'}
    raw = json.dumps(body()).encode()
    at_limit = raw + b' '*(8192-len(raw))
    r = client.post(PATH, headers=headers, content=at_limit)
    assert r.status_code == 200, r.text
    r = client.post(PATH, headers=headers, content=at_limit+b' ')
    assert r.status_code == 413, r.text


@pytest.mark.parametrize('raw', [b'\xff', b'{"context":"agenda","disclosed":true,"attention_weights":[NaN,1]}', b'['*3500], ids=['invalid-utf8', 'nonfinite', 'deep-incomplete-json'])
def test_row105_mounted_decoder_failures_safe(client, oidc_auth_headers, raw):
    r = client.post(PATH, headers={**oidc_auth_headers(), 'Content-Type': 'application/json'}, content=raw)
    assert r.status_code == 422, r.text
    assert r.json() == {'detail': 'PRESUA105: invalid JSON'}
