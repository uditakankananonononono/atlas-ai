"""Atomic account/work/checkpoint boundaries. Actual SQLite/temporary PG."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository,GmailAccountRow,DraftWorkRow,EmailEventRow,EmailMessageRow,ActionItemRow,EmailDraftRow

@pytest.fixture(params=['sqlite','postgres'])
def repo(request,tmp_path):
 if request.param=='postgres':
  pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/checkpoint.db'
 engine=create_engine(url)
 for model in (GmailAccountRow,DraftWorkRow,EmailEventRow,EmailMessageRow,ActionItemRow,EmailDraftRow):model.__table__.create(engine)
 sessions=sessionmaker(bind=engine);repo=SqlEmailRepository('a',sessions)
 repo.save_account(account_id='account',email_address='fixture@example.invalid',encrypted_refresh_token='fixture',history_id='100',watch_expiration=None)
 yield repo
 engine.dispose()


def test_checkpoint_refuses_all_unfinished_phases_and_stale_decreasing_ids(repo):
 with repo.sessions.begin() as db:db.add(DraftWorkRow(tenant_id='a',message_id='m',account_id='account',phase='ready',data={}))
 for phase in ['ready','model_inflight','model_done','approval_inflight','approval_done']:
  with repo.sessions.begin() as db:
   row=db.get(DraftWorkRow,('a','m'));row.phase=phase
  assert not repo.checkpoint_history('account','100','101')
  assert repo.get_account('account').history_id=='100'
 with repo.sessions.begin() as db:db.get(DraftWorkRow,('a','m')).phase='complete'
 assert not SqlEmailRepository('other',repo.sessions).checkpoint_history('account','100','101')
 assert not repo.checkpoint_history('account','100','99')
 assert not repo.checkpoint_history('account','99','101')
 assert repo.checkpoint_history('account','100','101')
 assert repo.checkpoint_history('account','100','101') # idempotent only exact target
 assert not repo.checkpoint_history('account','100','102')
 assert repo.get_account('account').history_id=='101'


def test_two_stale_checkpoint_writers_one_winner(repo):
 barrier=Barrier(2)
 def checkpoint(target):
  barrier.wait(timeout=5)
  return SqlEmailRepository('a',repo.sessions).checkpoint_history('account','100',target)
 with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(checkpoint,['101','102']))
 assert sorted(outcomes)==[False,True]
 assert repo.get_account('account').history_id in ['101','102']


def test_checkpoint_audit_failure_rolls_back_history(repo):
 def fail(mapper,conn,target):
  if target.event=='history_checkpoint':raise RuntimeError('fixture checkpoint log fail')
 event.listen(EmailEventRow,'before_insert',fail)
 try:
  with pytest.raises(RuntimeError,match='checkpoint log fail'):repo.checkpoint_history('account','100','101')
 finally:event.remove(EmailEventRow,'before_insert',fail)
 assert repo.get_account('account').history_id=='100'
 assert repo.checkpoint_history('account','100','101')


def test_message_work_action_transaction_failure_rolls_back_all(repo):
 def fail(mapper,conn,target):raise RuntimeError('fixture work insert failure')
 event.listen(DraftWorkRow,'before_insert',fail)
 try:
  with pytest.raises(RuntimeError,match='work insert failure'):
   repo.save_message(message_id='m',account_id='account',gmail_id='g',thread_id='t',history_id=None,subject='fixture',sender='sender@example.invalid',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='action_required',category_confidence=1,embedding=None,unsubscribe_url=None,draft_work={'actions':[{'action':'reply','deadline':None,'related_entity':None}]})
 finally:event.remove(DraftWorkRow,'before_insert',fail)
 assert repo.list_messages()==[] and repo.list_action_items()==[] and repo.draft_work('m','account') is None


def test_finalize_failure_rolls_back_draft_and_complete(repo):
 with repo.sessions.begin() as db:db.add(DraftWorkRow(tenant_id='a',message_id='m',account_id='account',phase='approval_done',data={'draft_id':'d','approval_id':'ap','to':'fixture@example.invalid','subject':'fixture','body':'fixture','model':'fake'}))
 data=repo.draft_work('m','account')['data']
 def fail(mapper,conn,target):raise RuntimeError('fixture draft insert failure')
 event.listen(EmailDraftRow,'before_insert',fail)
 try:
  with pytest.raises(RuntimeError,match='draft insert failure'):repo.finalize_draft_work('m','account',data)
 finally:event.remove(EmailDraftRow,'before_insert',fail)
 assert repo.draft_work('m','account')['phase']=='approval_done' and repo.list_drafts()==[]
 assert repo.finalize_draft_work('m','account',data)


def test_work_mutation_and_checkpoint_share_account_lock(repo,monkeypatch):
 from threading import Event
 from concurrent.futures import ThreadPoolExecutor
 from sqlalchemy import select
 acquired=Event();release=Event();original=repo._lock_account
 def lock(db,aid):
  result=original(db,aid);acquired.set();assert release.wait(timeout=5);return result
 monkeypatch.setattr(repo,'_lock_account',lock)
 def insert():
  return repo.save_message(message_id='locked',account_id='account',gmail_id='g',thread_id=None,history_id=None,subject='fixture',sender='s',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='action_required',category_confidence=1,embedding=None,unsubscribe_url=None,draft_work={'actions':[]})
 with ThreadPoolExecutor(max_workers=2) as pool:
  work=pool.submit(insert);assert acquired.wait(timeout=5)
  other=SqlEmailRepository('a',repo.sessions)
  checkpoint=pool.submit(other.checkpoint_history,'account','100','101')
  # release only after competing transaction started, completion follows commit.
  release.set();assert work.result(timeout=5)
  assert checkpoint.result(timeout=5) is False
 assert repo.get_account('account').history_id=='100'
 assert repo.draft_work('locked','account')['phase']=='ready'
