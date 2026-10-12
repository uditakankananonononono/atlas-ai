"""Mounted CTQ/DMADV bookkeeping only, no Six Sigma certification."""
import copy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.design_for_six_sigma1530 import run

PATH = '/api/v1/api/modules/20/design-for-six-sigma/1530/run'
DATA = {'dmadv_phase': 'verify', 'ctqs': [
    {'id': 'c1', 'name': 'Width', 'specification': {'unit': 'mm', 'lower': 1, 'target': 2, 'upper': 3}},
    {'id': 'c2', 'name': 'Finish'}],
    'verification_plan': [{'id': 'p1', 'ctq_id': 'c1', 'method': 'caller inspection plan'}]}


def test_dfss1530_mounted_real_engine_and_owner(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post(PATH, json={'data': DATA}).status_code == 401
    native = run(copy.deepcopy(DATA))
    assert native['summary'] == {'ctq_count': 2, 'open_count': 1, 'unverified_count': 1, 'plan_item_count': 1}
    assert native['phase_index'] == 4
    assert native['open_ctq_ids'] == ['c2'] and native['unverified_ctq_ids'] == ['c2']
    for tenant, actor in [('a', 'owner'), ('b', 'other')]:
        response = client.post(PATH, headers=oidc_auth_headers(tenant, actor), json={'data': DATA})
        assert response.status_code == 200, response.text
        assert response.json() == {**native, 'tenant_id': tenant, 'actor_id': actor}
        assert response.json()['statistical_validation_claimed'] is False
        assert response.json()['sigma_level_computed'] is False
    headers = oidc_auth_headers('a', 'owner')
    for extra in [{'tenant_id': 'b'}, {'actor_id': 'other'}, {'resource_refs': [{'tenant_id': 'b'}]}]:
        assert client.post(PATH, headers=headers, json={'data': DATA, **extra}).status_code == 403
    invalid = client.post(PATH, headers=headers, json={'data': {}})
    assert invalid.status_code == 422 and invalid.json()['detail'] == 'DFSS1530:invalid_phase'


@pytest.mark.parametrize('exc', [ValueError, TypeError, KeyError])
def test_dfss1530_refusal_mapping(monkeypatch, oidc_auth_headers, exc):
    from app.modules.m20_general_cognitive_worker import design_for_six_sigma_routes1530 as route
    monkeypatch.setenv('ATLAS_ENV', 'production')
    def fail(data):
        raise exc('supplied refusal')
    monkeypatch.setattr(route, 'run', fail)
    response = TestClient(app, raise_server_exceptions=False).post(PATH, headers=oidc_auth_headers('a', 'owner'), json={'data': DATA})
    assert response.status_code == 422


def test_dfss1530_envelope_and_ref_boundary(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    headers = oidc_auth_headers('a', 'owner')
    for body in [{}, {'data': []}, {'data': DATA, 'resource_refs': [{'tenant_id': 'a'}] * 65}]:
        assert client.post(PATH, headers=headers, json=body).status_code == 422
    response = client.post(PATH, headers=headers, json={'data': DATA, 'resource_refs': [{'tenant_id': 'a'}] * 64})
    assert response.status_code == 200, response.text


def test_dfss1530_surrogate_and_cross_actor_ref(monkeypatch, oidc_auth_headers):
    import json
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    headers = oidc_auth_headers('a', 'owner')
    response = client.post(PATH, headers={**headers, 'Content-Type': 'application/json'}, content=json.dumps({'data': {'bad': '\ud800'}}))
    assert response.status_code == 422
    assert client.post(PATH, headers=headers, json={'data': DATA, 'resource_refs': [{'tenant_id': 'a', 'actor_id': 'other'}]}).status_code == 403


def test_dfss1530_lone_surrogate_data_value_refused_before_model(monkeypatch, oidc_auth_headers):
    import json
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(PATH, headers={**oidc_auth_headers('a', 'owner'), 'Content-Type': 'application/json'}, content=json.dumps({'data': '\ud800'}))
    assert response.status_code == 422
    assert response.json() == {'detail': 'source contains invalid Unicode surrogate'}
