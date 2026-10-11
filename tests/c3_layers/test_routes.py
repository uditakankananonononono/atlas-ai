"""Route tests load only C3 files, without the heavy M20 package initializer."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_layers import packet

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'backend') not in sys.path:
    sys.path.insert(0, str(ROOT / 'backend'))
name = 'c3_route_private_test_package'
pkg = types.ModuleType(name)
pkg.__path__ = [str(ROOT / 'backend/app/modules/m20_general_cognitive_worker')]
sys.modules[name] = pkg
from app.auth.context import TenantContext, require_tenant
import importlib
r = importlib.import_module(name + '.c3_layers_routes')


class RoutesTests(unittest.TestCase):
    def setUp(self):
        r._reports.clear()
        r.bind_layers_tenant('a'); r.bind_layers_tenant('b')
        self.app = FastAPI(); self.app.include_router(r.router)
        self.app.dependency_overrides[require_tenant] = lambda: TenantContext('a', 'owner')
        self.client = TestClient(self.app)

    def test_run_report_and_copy_isolation(self):
        self.assertEqual(self.client.get('/api/v1/c31/layers/report').status_code, 404)
        response = self.client.post('/api/v1/c31/layers/run', json=packet())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/v1/c31/layers/report').json(), response.json())
        value = r.report_layers(TenantContext('a', 'owner')); value['draft'] = 'corrupt'
        self.assertNotEqual(self.client.get('/api/v1/c31/layers/report').json()['draft'], 'corrupt')

    def test_tenant_isolation(self):
        self.client.post('/api/v1/c31/layers/run', json=packet())
        self.app.dependency_overrides[require_tenant] = lambda: TenantContext('b', 'owner')
        self.assertEqual(self.client.get('/api/v1/c31/layers/report').status_code, 404)
        self.app.dependency_overrides[require_tenant] = lambda: TenantContext('unknown', 'owner')
        self.assertEqual(self.client.get('/api/v1/c31/layers/report').status_code, 503)

    def test_policy_refusal_keeps_last_good_report(self):
        self.client.post('/api/v1/c31/layers/run', json=packet())
        p = packet(); p['action'] = 'send'
        response = self.client.post('/api/v1/c31/layers/run', json=p)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['detail']['code'], 'POLICY_REFUSED_OUTREACH')
        self.assertEqual(self.client.get('/api/v1/c31/layers/report').json()['goal'], p['goal'])

    def test_auth_required(self):
        import os
        self.app.dependency_overrides.clear()
        from unittest.mock import patch
        with patch.dict(os.environ, {'ATLAS_DEV_NO_AUTH': '0', 'ATLAS_ENV': 'production'}):
            self.assertEqual(self.client.get('/api/v1/c31/layers/report').status_code, 401)

    def test_capacity(self):
        r._reports.clear()
        for i in range(128): r.bind_layers_tenant(str(i))
        with self.assertRaises(ValueError): r.bind_layers_tenant('over-cap')
        r.bind_layers_tenant('0')

if __name__ == '__main__': unittest.main()
