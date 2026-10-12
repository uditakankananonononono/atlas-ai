"""Coexistence pin: the near-duplicate legal paths are intentional and distinct.

/api/v1/api/modules/20/legal/support covers ledger rows 1210-1259 (method-literal
request, mount-level auth only); /api/v1/api/modules/20/legal-1260-1309/support
covers rows 1260-1309 (feature_id request, per-route principal binding). The two
empty-body 422 signatures are pinned so the overlap stays deliberate.
"""
from fastapi.testclient import TestClient
from app.main import app


def test_legal_support_paths_coexist_with_distinct_422_signatures(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    c = TestClient(app, raise_server_exceptions=False)
    h = oidc_auth_headers('a', 'owner')
    rows_1210_1259 = c.post('/api/v1/api/modules/20/legal/support', json={}, headers=h)
    assert rows_1210_1259.status_code == 422
    assert [e['loc'] for e in rows_1210_1259.json()['detail']] == [['body', 'method']]
    rows_1260_1309 = c.post('/api/v1/api/modules/20/legal-1260-1309/support', json={}, headers=h)
    assert rows_1260_1309.status_code == 422
    assert [e['loc'] for e in rows_1260_1309.json()['detail']] == [['body', 'feature_id'], ['body', 'actor_id'], ['body', 'tenant_id']]
