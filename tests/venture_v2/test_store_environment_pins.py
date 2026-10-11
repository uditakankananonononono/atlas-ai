"""Real environment-configured report paths, without store dependency override."""
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.context import require_tenant,TenantContext
from app.modules.m20_general_cognitive_worker import venture_v2_routes as routes
from test_engines import request

class StoreEnvironmentPins(unittest.TestCase):
    def setUp(self):
        routes._open_store.cache_clear()
        self.app=FastAPI();self.app.include_router(routes.router,prefix='/api/v1')
        self.app.dependency_overrides[require_tenant]=lambda:TenantContext('environment-tenant','owner')
        self.client=TestClient(self.app)
    def tearDown(self):routes._open_store.cache_clear()
    def test_configured_file_post_and_get(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict('os.environ',{'ATLAS_VENTURE_REPORT_DB':folder+'/reports.sqlite'}):
            response=self.client.post('/api/v1/c32/problems/run',json=request(mode='linear',matrix=[[1]],rhs=[7]))
            self.assertEqual(response.status_code,200)
            report=response.json();self.assertEqual(report['solution'],['7'])
            response=self.client.get('/api/v1/c32/problems/report',params={'run_id':report['run_id']})
            self.assertEqual(response.status_code,200);self.assertEqual(response.json(),report)
            routes._open_store.cache_clear()
            response=self.client.get('/api/v1/c32/problems/report')
            self.assertEqual(response.status_code,200);self.assertEqual(response.json(),report)
    def test_configured_directory_is_exact_503(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict('os.environ',{'ATLAS_VENTURE_REPORT_DB':folder}):
            response=self.client.post('/api/v1/c32/problems/run',json=request(mode='linear',matrix=[[1]],rhs=[7]))
            self.assertEqual(response.status_code,503)
            self.assertEqual(response.json(),{'detail':'venture report store unavailable'})
            response=self.client.get('/api/v1/c32/problems/report')
            self.assertEqual(response.status_code,503)
            self.assertEqual(response.json(),{'detail':'venture report store unavailable'})
