"""Real authenticated host helper, server permits and canonical policy classifier."""
import importlib
import pathlib
import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).parents[2] / 'backend/app/modules/m20_general_cognitive_worker'
PKG = 'tunit_host_fixture'
pkg = types.ModuleType(PKG)
pkg.__path__ = [str(ROOT)]
sys.modules[PKG] = pkg
routes = importlib.import_module(PKG + '.training_data_routes')
units = importlib.import_module(PKG + '.training_data_units')


@pytest.fixture
def host(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    routes._STORES.clear()
    app = FastAPI()
    routes.mount_training_routes(app)
    return TestClient(app)


def permit():
    return units.SourcePermit('fixture', 'https://example.org', 'CC0',
                              'https://example.org/terms', '2026-10-11', True)


def payload(action=None):
    return {'records': [{'source_id': 'fixture', 'url': 'https://example.org/book',
                         'text': 'Always verify.', 'as_of': '2026-10-11'}],
            'action': {} if action is None else action}


def test_real_auth_offline_hook_and_tenant_isolation(host, oidc_auth_headers):
    routes.configure_training_units('tenant-a', {'fixture': permit()})
    routes.configure_training_units('tenant-b', {'fixture': permit()})
    assert host.post('/api/v1/c32/books/run', json=payload()).status_code == 401
    a = oidc_auth_headers('tenant-a')
    result = host.post('/api/v1/c32/books/run', json=payload(), headers=a)
    assert result.status_code == 200
    assert result.json()['model_trained'] is False
    assert host.get('/api/v1/c32/books/report', headers=a).status_code == 200
    assert host.get('/api/v1/c32/books/report', headers=oidc_auth_headers('tenant-b')).status_code == 404
    assert host.post('/api/v1/c32/books/run', json=payload(), headers=oidc_auth_headers('unbound')).status_code == 503


@pytest.mark.parametrize('action', [{flag: True} for flag in ('spend', 'outreach', 'fakeacct', 'autopost', 'scrape', 'trade')]
                         + [{'type': 'execute'}, {'allowed': True}, {'type': 'analyze', 'spend': 'false'},
                            {'type': 'analyze', 'approved': True}, {'type': None}])
def test_client_actions_cannot_grant_permission(host, oidc_auth_headers, action):
    routes.configure_training_units('tenant-a', {'fixture': permit()})
    response = host.post('/api/v1/c32/books/run', json=payload(action), headers=oidc_auth_headers())
    assert response.status_code == 422
    assert 'POLICY_REFUSED_' in response.json()['detail']


def test_no_client_source_grant_or_default_allow(host, oidc_auth_headers):
    routes.configure_training_units('tenant-a', {})
    assert host.post('/api/v1/c32/books/run', json=payload(), headers=oidc_auth_headers()).status_code == 422
    routes.bind_training_units('tenant-a', units.TrainingUnits({'fixture': permit()}))
    response = host.post('/api/v1/c32/books/run', json=payload(), headers=oidc_auth_headers())
    assert response.status_code == 422
    assert response.json()['detail'] == 'TREND_REFUSED_UNKNOWN:analyze'


def test_canonical_classifier_used_and_permits_detached(host, oidc_auth_headers, monkeypatch):
    from app.modules.c30 import policy
    seen = []
    real = policy.classify
    def recorded(descriptor):
        seen.append(descriptor)
        return real(descriptor)
    monkeypatch.setattr(policy, 'classify', recorded)
    permits = {'fixture': permit()}
    routes.configure_training_units('tenant-a', permits)
    permits.clear()
    assert host.post('/api/v1/c32/books/run', json=payload(), headers=oidc_auth_headers()).status_code == 200
    assert seen == [{'class': 'offline', 'module_id': 20, 'tenant_id': 'tenant-a',
                     'action_type': 'analyze', 'payload': {}}]
    monkeypatch.setattr(policy, 'classify', lambda d: {'decision': 'needs_approval', 'code': None})
    assert host.post('/api/v1/c32/books/run', json=payload(), headers=oidc_auth_headers()).status_code == 422


def test_main_uses_same_mount_helper():
    import ast
    tree = ast.parse((ROOT.parents[1] / 'main.py').read_text())
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == 'mount_training_routes' and len(n.args) == 1
               and isinstance(n.args[0], ast.Name) and n.args[0].id == 'app'
               for n in ast.walk(tree))
