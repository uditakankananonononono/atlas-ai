"""Genuine M16 stream/repository checks, no provider/network, no pytest shim."""
import asyncio,threading,time,tempfile,unittest,os
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker,Session
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from app.core.database import Base
from app.modules.m16_executive_dashboard import routes
from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository
from app.modules.m16_executive_dashboard.schemas import Event
from app.modules.m16_executive_dashboard.service import Service
class Req:
 headers={}
 def __init__(self):self.stop=False
 async def is_disconnected(self):return self.stop
class Reviewer(unittest.IsolatedAsyncioTestCase):
 async def test_actual_sql_service_read_in_worker_session_closed_tenant_scope(self):
  with tempfile.TemporaryDirectory() as tmp:
   engine=create_engine('sqlite:///'+str(Path(tmp)/'db.sqlite'),connect_args={'check_same_thread':False})
   self.addCleanup(engine.dispose);Base.metadata.create_all(engine)
   created=[];closed=[];threads=[]
   class TrackedSession(Session):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);created.append(id(self));threads.append(threading.get_ident())
    def close(self):closed.append(id(self));super().close()
   sessions=sessionmaker(bind=engine,class_=TrackedSession)
   repo=SqlDashboardRepository('alice','actor',session_factory=sessions)
   repo.append_event(Event(id='e1',sequence=0,topic='t',aggregate_type='a',aggregate_id='x',payload={},occurred_at=datetime.now(timezone.utc)))
   repo_b=SqlDashboardRepository('bob','actor',session_factory=sessions)
   repo_b.append_event(Event(id='other',sequence=0,topic='t',aggregate_type='a',aggregate_id='y',payload={},occurred_at=datetime.now(timezone.utc)))
   created.clear();closed.clear();threads.clear()
   req=Req();response=await routes.live(req,cursor=0,service=Service(repo));iterator=response.body_iterator
   first=await anext(iterator);req.stop=True;await iterator.aclose()
   self.assertIn('e1',first);self.assertNotIn('other',first)
   self.assertEqual(created,closed);self.assertTrue(threads);self.assertNotIn(threading.get_ident(),threads)
 async def test_slow_read_does_not_stall_loop(self):
  req=Req();worker=[]
  class Slow:
   def events_after(self,cursor):worker.append(threading.get_ident());time.sleep(0.25);return []
  response=await routes.live(req,0,Slow());iterator=response.body_iterator
  start=time.monotonic();read=asyncio.create_task(anext(iterator));await asyncio.sleep(0.03)
  self.assertLess(time.monotonic()-start,0.15);self.assertFalse(read.done())
  self.assertEqual(await read,': heartbeat\n\n');req.stop=True;await iterator.aclose()
  self.assertNotIn(threading.get_ident(),worker)
 async def test_cancel_during_thread_read_stops_stream_but_thread_finishes(self):
  entered=threading.Event();release=threading.Event();finished=threading.Event()
  class Slow:
   def events_after(self,cursor):entered.set();release.wait(timeout=3);finished.set();return []
  req=Req();response=await routes.live(req,0,Slow());iterator=response.body_iterator
  read=asyncio.create_task(anext(iterator))
  while not entered.is_set():await asyncio.sleep(0.001)
  read.cancel()
  with self.assertRaises(asyncio.CancelledError):await read
  self.assertFalse(finished.is_set())
  release.set()
  while not finished.is_set():await asyncio.sleep(0.001)
  await iterator.aclose()
 async def test_disconnected_before_first_read_does_no_db_work(self):
  class NoneExpected:
   def events_after(self,cursor):raise AssertionError('unexpected query')
  req=Req();req.stop=True;response=await routes.live(req,0,NoneExpected())
  self.assertEqual([x async for x in response.body_iterator],[])
 async def test_cursor_above_int64_refused_before_stream(self):
  with self.assertRaises(HTTPException) as caught:await routes.live(Req(),2**63,object())
  self.assertEqual(caught.exception.status_code,422)
 def test_live_unauthenticated_route_refused(self):
  app=FastAPI();app.include_router(routes.router)
  with patch.dict(os.environ,{'ATLAS_ENV':'production','ATLAS_DEV_NO_AUTH':'0'}),TestClient(app) as c:
   self.assertEqual(c.get('/executive-dashboard/live').status_code,401)
"""Genuine M16 stream/repository checks, no provider/network, no pytest shim."""
import asyncio,threading,time,tempfile,unittest,os
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker,Session
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from app.core.database import Base
from app.modules.m16_executive_dashboard import routes
from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository
from app.modules.m16_executive_dashboard.schemas import Event
from app.modules.m16_executive_dashboard.service import Service
class Req:
 headers={}
 def __init__(self):self.stop=False
 async def is_disconnected(self):return self.stop
class Reviewer(unittest.IsolatedAsyncioTestCase):
 async def test_actual_sql_service_read_in_worker_session_closed_tenant_scope(self):
  with tempfile.TemporaryDirectory() as tmp:
   engine=create_engine('sqlite:///'+str(Path(tmp)/'db.sqlite'),connect_args={'check_same_thread':False})
   self.addCleanup(engine.dispose);Base.metadata.create_all(engine)
   created=[];closed=[];threads=[]
   class TrackedSession(Session):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);created.append(id(self));threads.append(threading.get_ident())
    def close(self):closed.append(id(self));super().close()
   sessions=sessionmaker(bind=engine,class_=TrackedSession)
   repo=SqlDashboardRepository('alice','actor',session_factory=sessions)
   repo.append_event(Event(id='e1',sequence=0,topic='t',aggregate_type='a',aggregate_id='x',payload={},occurred_at=datetime.now(timezone.utc)))
   repo_b=SqlDashboardRepository('bob','actor',session_factory=sessions)
   repo_b.append_event(Event(id='other',sequence=0,topic='t',aggregate_type='a',aggregate_id='y',payload={},occurred_at=datetime.now(timezone.utc)))
   created.clear();closed.clear();threads.clear()
   req=Req();response=await routes.live(req,cursor=0,service=Service(repo));iterator=response.body_iterator
   first=await anext(iterator);req.stop=True;await iterator.aclose()
   self.assertIn('e1',first);self.assertNotIn('other',first)
   self.assertEqual(created,closed);self.assertTrue(threads);self.assertNotIn(threading.get_ident(),threads)
 async def test_slow_read_does_not_stall_loop(self):
  req=Req();worker=[]
  class Slow:
   def events_after(self,cursor):worker.append(threading.get_ident());time.sleep(0.25);return []
  response=await routes.live(req,0,Slow());iterator=response.body_iterator
  start=time.monotonic();read=asyncio.create_task(anext(iterator));await asyncio.sleep(0.03)
  self.assertLess(time.monotonic()-start,0.15);self.assertFalse(read.done())
  self.assertEqual(await read,': heartbeat\n\n');req.stop=True;await iterator.aclose()
  self.assertNotIn(threading.get_ident(),worker)
 async def test_cancel_during_thread_read_stops_stream_but_thread_finishes(self):
  entered=threading.Event();release=threading.Event();finished=threading.Event()
  class Slow:
   def events_after(self,cursor):entered.set();release.wait(timeout=3);finished.set();return []
  req=Req();response=await routes.live(req,0,Slow());iterator=response.body_iterator
  read=asyncio.create_task(anext(iterator))
  while not entered.is_set():await asyncio.sleep(0.001)
  read.cancel()
  with self.assertRaises(asyncio.CancelledError):await read
  self.assertFalse(finished.is_set())
  release.set()
  while not finished.is_set():await asyncio.sleep(0.001)
  await iterator.aclose()
 async def test_disconnected_before_first_read_does_no_db_work(self):
  class NoneExpected:
   def events_after(self,cursor):raise AssertionError('unexpected query')
  req=Req();req.stop=True;response=await routes.live(req,0,NoneExpected())
  self.assertEqual([x async for x in response.body_iterator],[])
 async def test_cursor_above_int64_refused_before_stream(self):
  with self.assertRaises(HTTPException) as caught:await routes.live(Req(),2**63,object())
  self.assertEqual(caught.exception.status_code,422)
 def test_live_unauthenticated_route_refused(self):
  app=FastAPI();app.include_router(routes.router)
  with patch.dict(os.environ,{'ATLAS_ENV':'production','ATLAS_DEV_NO_AUTH':'0'}),TestClient(app) as c:
   self.assertEqual(c.get('/executive-dashboard/live').status_code,401)
 async def test_v4_min_and_minus_one_preserve_actual_sql_replay(self):
  with tempfile.TemporaryDirectory() as tmp:
   engine=create_engine('sqlite:///'+str(Path(tmp)/'db.sqlite'),connect_args={'check_same_thread':False});self.addCleanup(engine.dispose)
   Base.metadata.create_all(engine);repo=SqlDashboardRepository('a','u',session_factory=sessionmaker(bind=engine))
   repo.append_event(Event(id='min-replay',sequence=0,topic='t',aggregate_type='a',aggregate_id='x',payload={},occurred_at=datetime.now(timezone.utc)))
   for cursor in (-(2**63),-1):
    req=Req();response=await routes.live(req,cursor,Service(repo));it=response.body_iterator
    self.assertIn('min-replay',await anext(it));req.stop=True;await it.aclose()
 def test_v4_actual_http_signed_bounds_rejected_before_query(self):
  from app.auth.context import require_tenant,TenantContext
  class NoQuery:
   def events_after(self,*args):raise AssertionError('no DB read expected')
  app=FastAPI();app.include_router(routes.router)
  app.dependency_overrides[require_tenant]=lambda:TenantContext('a','u')
  app.dependency_overrides[routes.get_service]=lambda:NoQuery()
  with TestClient(app) as c:
   for cursor in (-(2**63)-1,2**63):self.assertEqual(c.get('/executive-dashboard/live',params={'cursor':cursor}).status_code,422)
