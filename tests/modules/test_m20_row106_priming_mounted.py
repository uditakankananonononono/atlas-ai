"""Row 106 Priming Effects: mounted HTTP behavior through the real app.

Claim scope: ledger row 106, "Priming Effects - Activates related concepts unconsciously", only as a mounted
descriptive-difference endpoint over supplied counts. NOT claimed: any unconscious effect, persuasion, cause, or that
anything is effective. Development identity headers only; no production auth proof.
The app is imported inside the fixture, never at collection.
"""
import pytest

PREFIX = '/api/v1/api/modules/20'
ROUTE = PREFIX + '/priming-effects/106/review'
HEADERS = {'X-Atlas-Tenant': 'fixture-owner', 'X-Atlas-Actor': 'fixture-actor'}
COUNTS = {'exposed_successes': 30, 'exposed_total': 100, 'control_successes': 20, 'control_total': 100}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH', '1')
    monkeypatch.setenv('ATLAS_ENV', 'development')
    monkeypatch.setenv('ATLAS_M10_TIMESTAMP_SCHEME', 'off')
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as mounted:
        yield mounted


def post(client, data, headers=HEADERS):
    return client.post(ROUTE, json={'data': data}, headers=headers)


def test_row106_mounted_disclosed_difference(client):
    r = post(client, {'context': 'reading task A', 'disclosed': True, **COUNTS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['row'] == 106
    assert body['effect'] == '1/10'
    assert body['effect_decimal'] == '0.100000'
    assert body['allowed'] is True
    assert body['causal_estimate_available'] is False
    assert body['covert_influence_blocked'] is False
    assert body['tenant_id'] == 'fixture-owner'
    assert body['actor_id'] == 'fixture-actor'


def test_row106_mounted_undisclosed_is_not_allowed(client):
    r = post(client, {'context': 'reading task A', 'disclosed': False, **COUNTS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['allowed'] is False
    assert body['covert_influence_blocked'] is True
    assert body['causal_estimate_available'] is False


def test_row106_mounted_refuses_partial_counts(client):
    r = post(client, {'context': 'x', 'disclosed': True, 'exposed_successes': 1})
    assert r.status_code == 422, r.text
    assert 'PRIME106' in r.text


def test_row106_mounted_refuses_non_bool_disclosed(client):
    r = post(client, {'context': 'x', 'disclosed': 'yes'})
    assert r.status_code == 422, r.text
    assert 'PRIME106' in r.text


def test_row106_mounted_refuses_unknown_key(client):
    r = post(client, {'context': 'x', 'disclosed': True, 'persuade': True})
    assert r.status_code == 422, r.text
    assert 'PRIME106' in r.text
