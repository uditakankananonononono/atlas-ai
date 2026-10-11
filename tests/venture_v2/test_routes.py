import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.context import require_tenant, TenantContext
from app.modules.m20_general_cognitive_worker.venture_v2_routes import router,get_store
from app.modules.m20_general_cognitive_worker.venture_v2.store import ReportStore
from test_engines import META

class Routes(unittest.TestCase):
    def setUp(self):
        self.env_patch=patch.dict('os.environ',{'ATLAS_DEV_NO_AUTH':'0'}); self.env_patch.start()
        self.temp=tempfile.TemporaryDirectory(); self.path=self.temp.name+'/reports.db'; self.store=ReportStore(self.path)
        self.app=FastAPI(); self.app.include_router(router,prefix='/api/v1'); self.app.dependency_overrides[get_store]=lambda:self.store
        self.client=TestClient(self.app)
    def tearDown(self): self.temp.cleanup(); self.env_patch.stop()
    def tenant(self,value): self.app.dependency_overrides[require_tenant]=lambda:TenantContext(value,'owner')
    def test_routes_auth_refusal_report_isolation_and_restart(self):
        self.assertEqual(len(self.app.openapi()['paths']),16)
        r=self.client.post('/api/v1/c32/problems/run',json=dict(META,mode='linear',matrix=[[1]],rhs=[2]))
        self.assertEqual(r.status_code,401)
        self.tenant('a')
        r=self.client.post('/api/v1/c32/problems/run',json=dict(META,mode='linear',matrix=[[1]],rhs=[2]))
        self.assertEqual(r.status_code,200); rid=r.json()['run_id']
        self.assertEqual(self.client.get('/api/v1/c32/problems/report',params={'run_id':rid}).json()['solution'],['2'])
        self.assertEqual(ReportStore(self.path).get('a','problems',rid)['solution'],['2'])
        self.tenant('b')
        self.assertEqual(self.client.get('/api/v1/c32/problems/report',params={'run_id':rid}).status_code,404)
        self.assertEqual(self.client.get('/api/v1/c32/problems/report').status_code,404)
        self.assertEqual(self.client.get('/api/v1/c36/hustles/report',params={'run_id':rid}).status_code,404)
        r=self.client.post('/api/v1/c32/problems/run',json=dict(META,action='outreach'))
        self.assertEqual(r.status_code,422); self.assertEqual(r.json()['detail']['code'],'POLICY_REFUSED_OUTREACH')
    def test_unconfigured_store_fails_closed(self):
        self.tenant('a'); del self.app.dependency_overrides[get_store]
        import os
        old=os.environ.pop('ATLAS_VENTURE_REPORT_DB',None)
        try: self.assertEqual(self.client.get('/api/v1/c32/problems/report').status_code,503)
        finally:
            if old is not None: os.environ['ATLAS_VENTURE_REPORT_DB']=old
