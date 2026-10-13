import importlib
import sys
import types
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_paper import ROOT,packet
from app.auth.context import TenantContext,require_tenant
pkg=types.ModuleType('s72_test_pkg');pkg.__path__=[str(ROOT/'backend/app/modules/m20_general_cognitive_worker')];sys.modules[pkg.__name__]=pkg
r=importlib.import_module(pkg.__name__+'.s72_paper_routes')

class RouteTests(unittest.TestCase):
    def setUp(self):
        r._reports.clear();r.bind_paper_tenant('a');r.bind_paper_tenant('b')
        self.app=FastAPI();self.app.include_router(r.router)
        self.app.dependency_overrides[require_tenant]=lambda:TenantContext('a','owner')
        self.client=TestClient(self.app)
    def test_run_report_isolated(self):
        self.assertEqual(self.client.get('/api/v1/c36/paper/report').status_code,404)
        p=packet();p['strategy_id']='buy_hold'
        response=self.client.post('/api/v1/c36/paper/run',json=p);self.assertEqual(response.status_code,200)
        self.assertAlmostEqual(response.json()['total_return'],.21)
        self.assertEqual(self.client.get('/api/v1/c36/paper/report').json(),response.json())
        self.app.dependency_overrides[require_tenant]=lambda:TenantContext('b','owner')
        self.assertEqual(self.client.get('/api/v1/c36/paper/report').status_code,404)
        self.app.dependency_overrides[require_tenant]=lambda:TenantContext('unknown','owner')
        self.assertEqual(self.client.get('/api/v1/c36/paper/report').status_code,503)
    def test_no_code_execution(self):
        p=packet();p['strategy_id']='__import__("os").system("echo bad")'
        self.assertEqual(self.client.post('/api/v1/c36/paper/run',json=p).status_code,422)
    def test_auth(self):
        import os
        from unittest.mock import patch
        self.app.dependency_overrides.clear()
        with patch.dict(os.environ,{'ATLAS_ENV':'production','ATLAS_DEV_NO_AUTH':'0'}):self.assertEqual(self.client.get('/api/v1/c36/paper/report').status_code,401)
    def test_effects_not_allowed(self):
        for action,code in [('trade','TRADE'),('spend','SPEND')]:
            p=packet();p['action']=action
            self.assertEqual(self.client.post('/api/v1/c36/paper/run',json=p).json()['detail']['code'],'MONEY_REFUSED_'+code)
    def test_moving_average_prefix(self):
        bars=[{'close':v} for v in [1,2,3,4,5]]
        self.assertEqual(r.moving_average(bars[:4]),0)
        self.assertEqual(r.moving_average(bars),1)

if __name__=='__main__':unittest.main()
