"""Real mounted-route checks for dependency-equipped application review."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from httpx import AsyncClient,ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext,require_tenant
from app.modules.m22_tools_hub import routes
from app.modules.m22_tools_hub.query_journal import QueryJournal

class FixtureCollector:
 name='fixture-blog';kind='blog'
 async def collect(self,query):
  yield {'name':query,'url':'https://example.org/'+query}

class RoutesTest(unittest.IsolatedAsyncioTestCase):
 async def test_authenticated_route_restart_and_tenant_boundary(self):
  with tempfile.TemporaryDirectory() as tmp:
   engine=create_engine('sqlite:///'+str(Path(tmp)/'db.sqlite'))
   sessions=sessionmaker(bind=engine)
   def journal(tenant):return QueryJournal(tenant,session_factory=sessions,db_engine=engine)
   app=FastAPI();app.include_router(routes.router)
   identity=['alice']
   app.dependency_overrides[require_tenant]=lambda:TenantContext(identity[0],'fixture-user')
   with patch.object(routes,'_services',{}),patch.object(routes,'QueryJournal',side_effect=journal),patch.object(routes,'default_collectors',return_value=[FixtureCollector()]):
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
     response=await client.post('/tools-hub/discoveries',json={'query':'original'})
     self.assertEqual(response.status_code,200,response.text)
     routes._services.clear() # simulated app-service restart, same real DB
     history=await client.get('/tools-hub/queries')
     self.assertEqual(history.json()['queries'][0]['query'],'original')
     report=await client.get('/tools-hub/discoveries/original/report')
     self.assertEqual(report.json()['diff'],{'first_run':True,'added':[],'removed':[]})
     identity[0]='bob'
     self.assertEqual((await client.get('/tools-hub/queries')).json(),{'queries':[]})
     self.assertIsNone((await client.get('/tools-hub/discoveries/original/report')).json()['diff'])
   engine.dispose()
