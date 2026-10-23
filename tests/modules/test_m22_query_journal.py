import tempfile,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m22_tools_hub.query_journal import QueryJournal,QueryJournalError

A='a'*64
B='b'*64
class JournalTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.url='sqlite:///'+str(Path(self.tmp.name)/'state.db')
  self.engine=create_engine(self.url)
  self.sessions=sessionmaker(bind=self.engine)
 def tearDown(self):
  self.engine.dispose();self.tmp.cleanup()
 def store(self,tenant='alice'):
  return QueryJournal(tenant,session_factory=self.sessions,db_engine=self.engine)
 def test_restart_diff_history_and_isolation(self):
  a=self.store()
  self.assertEqual(a.record('query',{A:'Old'},at='2026-10-15T00:00:00Z'),{'first_run':True,'added':[],'removed':[]})
  # Re-open real DB/service object; no in-memory snapshot provided.
  b=self.store()
  self.assertEqual(b.record('query',{B:'New'},at='2026-10-15T00:01:00Z'),{'first_run':False,'added':['New'],'removed':['Old']})
  self.assertEqual(len(self.store().history()),2)
  self.assertEqual(self.store('bob').history(),[])
  self.assertIsNone(self.store('bob').diff('query'))
 def test_empty_snapshot_is_prior_run(self):
  s=self.store();s.record('q',{},at='now')
  self.assertEqual(self.store().record('q',{A:'A'},at='later'),{'first_run':False,'added':['A'],'removed':[]})
 def test_stale_instances_read_current_database(self):
  a,b=self.store(),self.store()
  a.record('q',{A:'A'},at='1');b.record('q',{B:'B'},at='2')
  self.assertEqual(a.diff('q'),{'first_run':False,'added':['B'],'removed':['A']})
 def test_capacity_and_bounded_history(self):
  s=self.store()
  for i in range(200):s.record(str(i),{},at='now')
  with self.assertRaises(QueryJournalError):s.record('overflow',{},at='now')
  self.assertEqual(len(s.history()),200)
  s.record('0',{A:'A'},at='later')
  self.assertEqual(len(s.history()),200)
  self.assertEqual(s.history()[-1]['query'],'0')
 def test_validation_does_not_mutate_committed_state(self):
  s=self.store();s.record('q',{A:'A'},at='now')
  with self.assertRaises(ValueError):s.record('q',{'bad':'name'},at='later')
  self.assertEqual(len(s.history()),1)
  result=s.history();result.clear();self.assertEqual(len(s.history()),1)

 def test_concurrent_instances_do_not_lose_history(self):
  self.store().record('seed',{},at='0')
  def run(i):return self.store().record('q'+str(i),{},at=str(i))
  with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run,range(16)))
  self.assertEqual(len(self.store().history()),17)
  self.assertEqual(len(self.store().read()['queries']),17)
 def test_real_engine_restart(self):
  self.store().record('q',{A:'Saved'},at='now')
  self.engine.dispose()
  other=create_engine(self.url)
  try:
   restarted=QueryJournal('alice',session_factory=sessionmaker(bind=other),db_engine=other)
   self.assertEqual(restarted.history()[0]['query'],'q')
   self.assertEqual(restarted.diff('q'),{'first_run':True,'added':[],'removed':[]})
  finally:other.dispose()
 def test_contention_losses_retried_with_bounded_backoff(self):
  from app.modules.m22_tools_hub import query_journal as qj
  self.store().record('seed',{},at='0')
  uniform_calls=[]
  class FakeRandom:
   def uniform(self,a,b):uniform_calls.append((a,b));return 0.0
  sleeps=[]
  class FakeTime:
   def sleep(self,x):sleeps.append(x)
  old_r,old_t=qj.random,qj.time
  qj.random,qj.time=FakeRandom(),FakeTime()
  try:
   wrapper=_LoseFirstUpdates(self.sessions(),9)
   losing=QueryJournal('alice',session_factory=lambda:wrapper,db_engine=self.engine)
   self.assertEqual(losing.record('q',{A:'Saved'},at='1'),{'first_run':True,'added':[],'removed':[]})
  finally:qj.random,qj.time=old_r,old_t
  self.assertEqual(uniform_calls,[(0,0.0005),(0,0.001),(0,0.002),(0,0.004)]+[(0,0.008)]*5)
  self.assertEqual(len(sleeps),9)
  self.assertEqual(len(self.store().history()),2)
 def test_contention_budget_exhaustion_still_raises(self):
  from app.modules.m22_tools_hub import query_journal as qj
  self.store().record('seed',{},at='0')
  wrapper=_LoseFirstUpdates(self.sessions(),10**9)
  class FakeTime:
   def sleep(self,x):pass
  old_t=qj.time;qj.time=FakeTime()
  try:
   losing=QueryJournal('alice',session_factory=lambda:wrapper,db_engine=self.engine)
   with self.assertRaises(QueryJournalError) as ctx:losing.record('q',{},at='1')
  finally:qj.time=old_t
  self.assertEqual(str(ctx.exception),'query journal concurrent update conflict')
  self.assertEqual(wrapper.executes,64)
 def test_permanent_errors_raise_without_retry(self):
  from app.modules.m22_tools_hub import query_journal as qj
  s=self.store()
  for i in range(200):s.record(str(i),{},at='now')
  wrapper=_LoseFirstUpdates(self.sessions(),10**9)
  class FakeTime:
   def sleep(self,x):raise AssertionError('permanent errors must not be retried')
  old_t=qj.time;qj.time=FakeTime()
  try:
   losing=QueryJournal('alice',session_factory=lambda:wrapper,db_engine=self.engine)
   with self.assertRaises(QueryJournalError) as ctx:losing.record('overflow',{},at='now')
  finally:qj.time=old_t
  self.assertEqual(str(ctx.exception),'query journal capacity exceeded')
  self.assertEqual(wrapper.executes,0)

class _LoseFirstUpdates:
 def __init__(self,real,losses):self._r=real;self._left=losses;self.executes=0
 def __enter__(self):return self
 def __exit__(self,*a):return self._r.__exit__(*a)
 def __getattr__(self,k):return getattr(self._r,k)
 def execute(self,*a,**k):
  self.executes+=1
  if self._left>0:
   self._left-=1
   class _R:rowcount=0
   return _R()
  return self._r.execute(*a,**k)
