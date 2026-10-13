import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from test_forecast import ROOT, pred

name='j1_private_route_package';pkg=types.ModuleType(name)
pkg.__path__=[str(ROOT/'backend/app/modules/m20_general_cognitive_worker')];sys.modules[name]=pkg
r=importlib.import_module(name+'.j1_forecast_routes')

class Routes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();r._ledgers.clear()
        for tenant in ['a','b']:
            r.bind_forecast_ledger(r.ForecastLedger(Path(self.tmp.name)/(tenant+'.jsonl'),tenant_id=tenant))
        self.app=FastAPI();self.app.include_router(r.router)
        self.app.dependency_overrides[require_tenant]=lambda:TenantContext('a','owner')
        self.client=TestClient(self.app)
    def tearDown(self):self.tmp.cleanup()
    def test_end_to_end_and_tenant_isolation(self):
        p=pred();del p['prediction_id'];p['action']='predict'
        response=self.client.post('/api/v1/c37/forecast/run',json=p)
        self.assertEqual(response.status_code,200);ident=response.json()['record']['prediction_id']
        self.assertEqual(self.client.get('/api/v1/c37/forecast/report').status_code,422)
        self.assertEqual(self.client.post('/api/v1/c37/forecast/run',json={'action':'resolve','prediction_id':ident,'outcome':True,'resolved_at':'2026-10-12T01:00:00Z'}).status_code,200)
        self.assertAlmostEqual(self.client.get('/api/v1/c37/forecast/report').json()['brier_score'],.04)
        self.app.dependency_overrides[require_tenant]=lambda:TenantContext('b','owner')
        self.assertEqual(self.client.get('/api/v1/c37/forecast/report').json()['detail']['code'],'INTEL_REFUSED_UNSCORED')
        self.app.dependency_overrides[require_tenant]=lambda:TenantContext('unknown','owner')
        self.assertEqual(self.client.get('/api/v1/c37/forecast/report').status_code,503)
    def test_effects_refused(self):
        for action in ['spend','outreach','fakeacct','autopost','scrape','trade','unknown']:
            response=self.client.post('/api/v1/c37/forecast/run',json={'action':action})
            self.assertEqual(response.status_code,422)
            self.assertTrue(response.json()['detail']['code'].startswith('INTEL_REFUSED_'))
    def test_missing_horizon_and_unknown_field(self):
        p=pred();del p['prediction_id'];del p['horizon'];p['action']='predict'
        self.assertEqual(self.client.post('/api/v1/c37/forecast/run',json=p).json()['detail']['code'],'INTEL_REFUSED_NOHORIZON')
        p['horizon']='2026-10-12T00:00:00Z';p['tenant_id']='other'
        self.assertEqual(self.client.post('/api/v1/c37/forecast/run',json=p).json()['detail']['code'],'INTEL_REFUSED_SCHEMA')
    def test_auth_required(self):
        import os
        from unittest.mock import patch
        self.app.dependency_overrides.clear()
        with patch.dict(os.environ,{'ATLAS_DEV_NO_AUTH':'0','ATLAS_ENV':'production'}):
            self.assertEqual(self.client.get('/api/v1/c37/forecast/report').status_code,401)

if __name__=='__main__':unittest.main()
