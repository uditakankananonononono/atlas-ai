import importlib.util,sys,types,pathlib,unittest
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.context import TenantContext,require_tenant
root=pathlib.Path(__file__).parents[2]/'backend/app/modules/m20_general_cognitive_worker'
pkg=types.ModuleType('tunit_routes_fixture');pkg.__path__=[str(root)];sys.modules[pkg.__name__]=pkg
from tunit_routes_fixture.training_data_units import TrainingUnits, SourcePermit
from tunit_routes_fixture.training_data_routes import router,bind_training_units

class RouteTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def production_auth_environment(self,monkeypatch):
        monkeypatch.delenv("ATLAS_DEV_NO_AUTH",raising=False)
    def setUp(self):
        self.app=FastAPI();self.app.include_router(router,prefix='/api/v1');self.client=TestClient(self.app)
        self.permit=SourcePermit('fixture','https://example.org','CC0','https://example.org/terms','2026-10-11',True)
    def tenant(self,name):
        self.app.dependency_overrides[require_tenant]=lambda:TenantContext(tenant_id=name,actor_id='tester',roles=frozenset())
    def test_auth(self):
        self.assertEqual(self.client.get('/api/v1/c32/books/report').status_code,401)
    def test_tenant_isolation(self):
        bind_training_units('a',TrainingUnits({'fixture':self.permit},policy=lambda p:None))
        bind_training_units('b',TrainingUnits({'fixture':self.permit},policy=lambda p:None))
        self.tenant('a')
        payload={'records':[{'source_id':'fixture','url':'https://example.org/book','text':'Always verify.','as_of':'2026-10-11'}]}
        self.assertEqual(self.client.post('/api/v1/c32/books/run',json=payload).status_code,200)
        self.tenant('b');self.assertEqual(self.client.get('/api/v1/c32/books/report').status_code,404)
        self.tenant('a');self.assertEqual(self.client.get('/api/v1/c32/books/report').json()['unit'],'T3')
    def test_unbound_and_no_client_grant(self):
        self.tenant('unbound');self.assertEqual(self.client.post('/api/v1/c35/case-corpus/run',json={}).status_code,503)
        bind_training_units('c',TrainingUnits(policy=lambda p:None));self.tenant('c')
        r=self.client.post('/api/v1/c35/case-corpus/run',json={'records':[{'source_id':'fixture','license':'CC0','url':'https://example.org/case','text':'x','as_of':'2026-10-11'}]})
        self.assertEqual(r.status_code,422)
    def test_route_paths(self):
        paths=set(self.app.openapi()['paths'])
        for p in ['/c35/case-corpus','/c20/m22/search','/c32/books','/c31/advice-first']:
            self.assertIn('/api/v1'+p+'/run',paths);self.assertIn('/api/v1'+p+'/report',paths)
    def test_plain_policy_valueerror_is_422(self):
        def deny(action):raise ValueError('POLICY_REFUSED_SPEND')
        bind_training_units('deny',TrainingUnits({'fixture':self.permit},policy=deny));self.tenant('deny')
        payload={'records':[{'source_id':'fixture','url':'https://example.org/book','text':'Advice','as_of':'2026-10-11'}]}
        self.assertEqual(self.client.post('/api/v1/c32/books/run',json=payload).status_code,422)
if __name__=='__main__':unittest.main()
