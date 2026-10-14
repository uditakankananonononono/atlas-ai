"""Production OIDC refusal pins for six stateless supplied-input routes."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

PATHS = ['/api/v1/c32/psyche', '/api/v1/c33/niches', '/api/v1/c33/persona',
         '/api/v1/c33/content', '/api/v1/c34/industry', '/api/v1/c34/tool']

@pytest.mark.parametrize('path', PATHS)
def test_bad_token_and_unmapped_tenant_refused(path, oidc_auth_headers, monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH', '0')
    monkeypatch.setenv('ATLAS_ENV', 'production')
    with TestClient(app) as client:
        assert client.post(path, json={}, headers={'Authorization': 'Bearer not.a.jwt'}).status_code == 401
        assert client.post(path, json={}, headers=oidc_auth_headers(tenant='')).status_code == 403
        assert client.post(path, json={}, headers={'X-Atlas-Tenant': 'tenant-a', 'X-Atlas-Actor': 'owner'}).status_code == 401

@pytest.mark.parametrize('tenant', ['tenant-a', 'tenant-b'])
def test_stateless_route_uses_valid_oidc_not_forged_tenant_header(tenant, oidc_auth_headers, monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH', '0')
    monkeypatch.setenv('ATLAS_ENV', 'production')
    headers = dict(oidc_auth_headers(tenant=tenant), **{'X-Atlas-Tenant': 'forged-other'})
    with TestClient(app) as client:
        response = client.post(PATHS[0], json={'text': 'happy'}, headers=headers)
        assert response.status_code == 200
        assert response.json()['claims_feeling'] is False
        response = client.post(PATHS[0], json={'text': 'happy', 'tenant_id': 'forged-other'}, headers=headers)
        assert response.status_code == 400
        assert response.json()['detail'] == 'TREND_REFUSED_FIELDS'
