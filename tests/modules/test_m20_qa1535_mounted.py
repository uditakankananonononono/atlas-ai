"""Mounted supplied QA evidence evaluator, never test execution/release."""
import copy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.qa_evidence1535 import evaluate_qa_evidence

PATH = '/api/v1/api/modules/20/quality-assurance/1535/evaluate'
DATA = {'defect_policy': 'refuse', 'requirements': [
    {'id': 'r1', 'conditions': [{'test_id': 't1', 'metric': 'width', 'op': '>=', 'threshold': 2}]}],
    'observations': [{'id': 'o1', 'test_id': 't1', 'metric': 'width', 'value': 3,
                      'run_id': 'run1', 'signed': True, 'source': 'caller', 'time': '2026-10-11T10:00:00Z'}],
    'caller_release_requested': True}


def test_qa1535_mounted_real_engine_and_owner(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post(PATH, json={'data': DATA}).status_code == 401
    native = evaluate_qa_evidence(copy.deepcopy(DATA))
    assert native['coverage'] == {'requirements_total': 1, 'satisfied_ids': ['r1'], 'unsupported': {}}
    assert native['audit_trace'][0]['conditions'][0]['distinct_supporting_runs'] == 1
    for tenant, actor in [('a', 'owner'), ('b', 'other')]:
        response = client.post(PATH, headers=oidc_auth_headers(tenant, actor), json={'data': DATA})
        assert response.status_code == 200, response.text
        assert response.json() == {**native, 'tenant_id': tenant, 'actor_id': actor}
        for flag in ('release_authority', 'release_granted', 'physical_test_claimed', 'persisted'):
            assert response.json()[flag] is False
        assert response.json()['effects'] == []
    headers = oidc_auth_headers('a', 'owner')
    for extra in [{'tenant_id': 'b'}, {'actor_id': 'other'}, {'resource_refs': [{'tenant_id': 'b'}]}]:
        assert client.post(PATH, headers=headers, json={'data': DATA, **extra}).status_code == 403
    invalid = client.post(PATH, headers=headers, json={'data': {}})
    assert invalid.status_code == 422 and invalid.json()['detail'] == "defect_policy must be 'refuse' or 'flag'"


@pytest.mark.parametrize('exc', [ValueError, TypeError, KeyError])
def test_qa1535_refusal_mapping(monkeypatch, oidc_auth_headers, exc):
    from app.modules.m20_general_cognitive_worker import qa_evidence_routes1535 as route
    monkeypatch.setenv('ATLAS_ENV', 'production')
    def fail(data):
        raise exc('supplied refusal')
    monkeypatch.setattr(route, 'evaluate_qa_evidence', fail)
    response = TestClient(app, raise_server_exceptions=False).post(PATH, headers=oidc_auth_headers('a', 'owner'), json={'data': DATA})
    assert response.status_code == 422


def test_qa1535_envelope_and_ref_boundary(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    headers = oidc_auth_headers('a', 'owner')
    for body in [{}, {'data': []}, {'data': DATA, 'resource_refs': [{'tenant_id': 'a'}] * 65}]:
        assert client.post(PATH, headers=headers, json=body).status_code == 422
    response = client.post(PATH, headers=headers, json={'data': DATA, 'resource_refs': [{'tenant_id': 'a'}] * 64})
    assert response.status_code == 200, response.text


def test_qa1535_surrogate_and_cross_actor_ref(monkeypatch, oidc_auth_headers):
    import json
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    headers = oidc_auth_headers('a', 'owner')
    response = client.post(PATH, headers={**headers, 'Content-Type': 'application/json'}, content=json.dumps({'data': {'bad': '\ud800'}}))
    assert response.status_code == 422
    assert client.post(PATH, headers=headers, json={'data': DATA, 'resource_refs': [{'tenant_id': 'a', 'actor_id': 'other'}]}).status_code == 403


def test_qa1535_lone_surrogate_data_value_refused_before_model(monkeypatch, oidc_auth_headers):
    import json
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(PATH, headers={**oidc_auth_headers('a', 'owner'), 'Content-Type': 'application/json'}, content=json.dumps({'data': '\ud800'}))
    assert response.status_code == 422
    assert response.json() == {'detail': 'source contains invalid Unicode surrogate'}
