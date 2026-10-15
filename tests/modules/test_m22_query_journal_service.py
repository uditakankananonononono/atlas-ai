"""Actual Service integration; requires real application dependencies, no shims."""
import asyncio,tempfile,unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m22_tools_hub.query_journal import QueryJournal,QueryJournalError
from app.modules.m22_tools_hub.service import Service

class Collector:
 name='fixture-blog';kind='blog'
 def __init__(self,rows):self.rows=rows;self.calls=0
 async def collect(self,query):
  self.calls+=1
  for row in self.rows:yield row

class ServiceJournalTest(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.engine=create_engine('sqlite:///'+str(Path(self.tmp.name)/'db.sqlite'))
  self.sessions=sessionmaker(bind=self.engine)
 def tearDown(self):self.engine.dispose();self.tmp.cleanup()
 def store(self,tenant='alice'):return QueryJournal(tenant,session_factory=self.sessions,db_engine=self.engine)
 async def test_actual_discovery_restart_and_tenant_isolation(self):
  c=Collector([{'name':'Old','url':'https://example.org/old'}])
  first=Service(None,[c],query_journal=self.store())
  await first.discover('search',kinds=['blog'])
  second=Service(None,[Collector([{'name':'New','url':'https://example.org/new'}])],query_journal=self.store())
  self.assertEqual(second.query_history[0]['query'],'search')
  await second.discover('search',kinds=['blog'])
  self.assertEqual(second.discovery_report('search')['diff'],{'first_run':False,'added':['New'],'removed':['Old']})
  self.assertEqual(Service(None,[],query_journal=self.store('bob')).query_history,[])
 async def test_failed_commit_does_not_expose_new_candidates_or_success(self):
  store=self.store()
  def fail(*args,**kw):raise QueryJournalError('injected commit refusal')
  store.record=fail
  service=Service(None,[Collector([{'name':'A','url':'https://example.org/a'}])],query_journal=store)
  with self.assertRaises(QueryJournalError):await service.discover('search')
  self.assertEqual(service.candidates,{})
  self.assertEqual(service.query_history,[])
 async def test_capacity_preflight_before_collectors(self):
  store=self.store()
  for i in range(200):store.record(str(i),{},at='now')
  collector=Collector([]);service=Service(None,[collector],query_journal=store)
  with self.assertRaises(QueryJournalError):await service.discover('new query')
  self.assertEqual(collector.calls,0)
 async def test_legacy_no_store_behavior_retained(self):
  service=Service(None,[Collector([{'name':'A','url':'https://example.org/a'}])])
  await service.discover('q')
  self.assertEqual(service.query_history[0]['query'],'q')
  self.assertEqual(service.last_diffs['q'],{'first_run':True,'added':[],'removed':[]})

if __name__=='__main__':unittest.main()
