import random,copy
import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker,Session
from app.modules.m22_tools_hub.query_journal import QueryJournal,QueryJournalError

def make(tmp_path):
 e=create_engine('sqlite:///'+str(tmp_path/'state.sqlite'));sessions=sessionmaker(bind=e);return e,sessions,QueryJournal('alice',session_factory=sessions,db_engine=e)
def test_reference_diff_history_and_capacity(tmp_path):
 e,ss,j=make(tmp_path);rng=random.Random(732);prior={};hist=[]
 for i in range(350):
  q='q'+str(rng.randrange(12));snap={format(k,'064x'):'name'+str(k) for k in rng.sample(range(30),rng.randrange(10))}
  before=prior.get(q);expected={'first_run':before is None,'added':[v for k,v in snap.items() if before is not None and k not in before],'removed':[v for k,v in (before or {}).items() if k not in snap]}
  assert j.record(q,snap,at=str(i))==expected;prior[q]=copy.deepcopy(snap);hist=(hist+[{'query':q,'kinds':None,'at':str(i),'count':len(snap)}])[-200:]
  assert j.history()==hist
  assert QueryJournal('bob',session_factory=ss,db_engine=e).history()==[]
  view=j.read();view['queries'].clear();assert len(j.read()['queries'])==len(prior)
 e.dispose()
def test_real_commit_failure_rolls_back(tmp_path):
 e,ss,j=make(tmp_path);j.record('q',{'a'*64:'old'},at='1');before=j.read()
 class FailSession(Session):pass
 bad=sessionmaker(bind=e,class_=FailSession)
 def fail(session):raise RuntimeError('fault-before-real-commit')
 event.listen(FailSession,'before_commit',fail)
 try:
  broken=QueryJournal('alice',session_factory=bad,db_engine=e)
  with pytest.raises(RuntimeError,match='fault-before-real-commit'):broken.record('q',{'b'*64:'new'},at='2')
 finally:event.remove(FailSession,'before_commit',fail)
 assert j.read()==before;e.dispose()
def test_validation_boundaries_and_capacity_unchanged(tmp_path):
 e,ss,j=make(tmp_path)
 for q in ['',True,'x'*501]:
  with pytest.raises(ValueError):j.record(q,{},at='now')
 for snap in [{'x':'n'},{'a'*64:'x'*301},{'A'*64:'name'}]:
  with pytest.raises(ValueError):j.record('q',snap,at='now')
 assert j.history()==[]
 for i in range(200):j.record(str(i),{},at='now')
 before=j.read()
 with pytest.raises(QueryJournalError):j.record('over',{},at='now')
 assert j.read()==before
 j.record('0',{},at='later');assert len(j.history())==200;e.dispose()
