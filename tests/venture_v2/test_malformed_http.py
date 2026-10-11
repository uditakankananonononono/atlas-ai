import unittest,tempfile
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.context import require_tenant,TenantContext
from app.modules.m20_general_cognitive_worker.venture_v2_routes import router,get_store
from app.modules.m20_general_cognitive_worker.venture_v2.store import ReportStore
from test_engines import request
class MalformedHTTP(unittest.TestCase):
    def test_malformed_actions_and_source_ids_are_422(self):
        with tempfile.TemporaryDirectory() as temp:
            app=FastAPI();app.include_router(router,prefix='/api/v1')
            store=ReportStore(temp+'/db');app.dependency_overrides[get_store]=lambda:store
            app.dependency_overrides[require_tenant]=lambda:TenantContext('t','owner')
            client=TestClient(app)
            for action in [[],{}]:
                r=client.post('/api/v1/c32/problems/run',json=request(action=action))
                self.assertEqual(r.status_code,422);self.assertEqual(r.json()['detail']['code'],'POLICY_REFUSED_ACTION')
            for sid in [[],{}]:
                r=client.post('/api/v1/c32/problems/run',json=request(sources=[{'id':sid,'url':'https://example.org'}]))
                self.assertEqual(r.status_code,422);self.assertEqual(r.json()['detail']['code'],'PLAN_REFUSED_SOURCE')

    def test_malformed_urls_are_422(self):
        with tempfile.TemporaryDirectory() as temp:
            app=FastAPI();app.include_router(router,prefix='/api/v1')
            store=ReportStore(temp+'/db');app.dependency_overrides[get_store]=lambda:store
            app.dependency_overrides[require_tenant]=lambda:TenantContext('t','owner')
            client=TestClient(app)
            for url in ['http://[::1','http://exa\u2100mple.com/','https://example.com:abc/','https://[::1]:99999/']:
                r=client.post('/api/v1/c32/problems/run',json=request(sources=[{'id':'s1','url':url}]))
                self.assertEqual(r.status_code,422);self.assertEqual(r.json()['detail']['code'],'PLAN_REFUSED_SOURCE')
