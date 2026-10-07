"""Atomic account/work/checkpoint boundaries. Actual SQLite/temporary PG."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository,GmailAccountRow,DraftWorkRow,EmailEventRow,EmailMessageRow,ActionItemRow,EmailDraftRow,IngestWorkRow

@pytest.fixture(params=['sqlite','postgres'])
def repo(request,tmp_path):
 if request.param=='postgres':
  pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/checkpoint.db'
 engine=create_engine(url)
 for model in (GmailAccountRow,DraftWorkRow,EmailEventRow,EmailMessageRow,ActionItemRow,EmailDraftRow,IngestWorkRow):model.__table__.create(engine)
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
 acquired=Event();release=Event();checkpoint_started=Event();original=repo._lock_account
 def lock(db,aid):
  result=original(db,aid);acquired.set();assert release.wait(timeout=5);return result
 monkeypatch.setattr(repo,'_lock_account',lock)
 def insert():
  return repo.save_message(message_id='locked',account_id='account',gmail_id='g',thread_id=None,history_id=None,subject='fixture',sender='s',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='action_required',category_confidence=1,embedding=None,unsubscribe_url=None,draft_work={'actions':[]})
 with ThreadPoolExecutor(max_workers=2) as pool:
  work=pool.submit(insert);assert acquired.wait(timeout=5)
  other=SqlEmailRepository('a',repo.sessions)
  other_lock=other._lock_account
  def checkpoint_lock(db,aid):
   checkpoint_started.set();return other_lock(db,aid)
  monkeypatch.setattr(other,'_lock_account',checkpoint_lock)
  checkpoint=pool.submit(other.checkpoint_history,'account','100','101')
  assert checkpoint_started.wait(timeout=5)
  # release only after competing transaction started, completion follows commit.
  release.set();assert work.result(timeout=5)
  assert checkpoint.result(timeout=5) is False
 assert repo.get_account('account').history_id=='100'
 assert repo.draft_work('locked','account')['phase']=='ready'


def test_orphan_account_work_mutations_fail_closed(repo):
 with pytest.raises(ValueError,match='account'):
  repo.save_message(message_id='orphan',account_id='missing',gmail_id='g',thread_id=None,history_id=None,subject='fixture',sender='s',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='action_required',category_confidence=1,embedding=None,unsubscribe_url=None,draft_work={'actions':[]})
 assert repo.list_messages()==[] and repo.draft_work('orphan','missing') is None
 # Historical corrupted work cannot bypass the owning-account lock either.
 with repo.sessions.begin() as db:db.add(DraftWorkRow(tenant_id='a',message_id='orphan',account_id='missing',phase='ready',data={}))
 assert not repo.transition_draft_work('orphan','missing','ready','model_inflight',{})
 assert not repo.finalize_draft_work('orphan','missing',{})
 assert repo.draft_work('orphan','missing')['phase']=='ready'
 data={'draft_id':'d','approval_id':'ap','to':'fixture@example.invalid','subject':'fixture','body':'fixture','model':'fake'}
 with repo.sessions.begin() as db:
  row=db.get(DraftWorkRow,('a','orphan'));row.phase='approval_done';row.data=data
 assert not repo.finalize_draft_work('orphan','missing',data)
 assert repo.draft_work('orphan','missing')['phase']=='approval_done' and repo.list_drafts()==[]



def test_watch_and_reconnect_do_not_skip_or_rewind_ingestion_checkpoint(repo):
 from datetime import datetime,timezone
 repo.update_watch_expiration('account',datetime.now(timezone.utc),'200')
 assert repo.get_account('account').history_id=='100'
 repo.save_account(account_id='new-provisional',email_address='fixture@example.invalid',encrypted_refresh_token='new-fixture',history_id='250',watch_expiration=None)
 assert repo.get_account('account').history_id=='100'
 assert repo.get_account('account').encrypted_refresh_token=='new-fixture'
 assert repo.get_account('new-provisional') is None
 repo.update_history_id('account','99')
 assert repo.get_account('account').history_id=='100'


def test_null_watch_baseline_requires_decimal_and_no_unfinished_work_and_correct_audit_id(repo):
 from datetime import datetime,timezone
 from sqlalchemy import select
 with repo.sessions.begin() as db:db.get(GmailAccountRow,repo.get_account('account').pk).history_id=None
 repo.update_watch_expiration('account',datetime.now(timezone.utc),'invalid')
 assert repo.get_account('account').history_id is None
 with repo.sessions.begin() as db:db.add(DraftWorkRow(tenant_id='a',message_id='m',account_id='account',phase='approval_done',data={}))
 repo.update_watch_expiration('account',datetime.now(timezone.utc),'200')
 assert repo.get_account('account').history_id is None
 with repo.sessions.begin() as db:db.get(DraftWorkRow,('a','m')).phase='complete'
 repo.update_watch_expiration('account',datetime.now(timezone.utc),'200')
 assert repo.get_account('account').history_id=='200'
 repo.save_account(account_id='provisional',email_address='fixture@example.invalid',encrypted_refresh_token='new',history_id='300',watch_expiration=None)
 with repo.sessions() as db:
  rows=list(db.scalars(select(EmailEventRow).where(EmailEventRow.event=='account_saved').order_by(EmailEventRow.pk)))
  assert rows[-1].entity_id=='account' and all(r.entity_id!='provisional' for r in rows)


def test_concurrent_watch_reconnect_and_checkpoint_never_overwrite_processed_history(repo):
 from datetime import datetime,timezone
 from concurrent.futures import ThreadPoolExecutor
 from threading import Barrier
 barrier=Barrier(3)
 def watch():
  barrier.wait(timeout=5)
  SqlEmailRepository('a',repo.sessions).update_watch_expiration('account',datetime.now(timezone.utc),'999')
 def reconnect():
  barrier.wait(timeout=5)
  SqlEmailRepository('a',repo.sessions).save_account(account_id='provisional',email_address='fixture@example.invalid',encrypted_refresh_token='new',history_id='888',watch_expiration=None)
 def checkpoint():
  barrier.wait(timeout=5)
  return SqlEmailRepository('a',repo.sessions).checkpoint_history('account','100','101')
 with ThreadPoolExecutor(max_workers=3) as pool:
  futures=[pool.submit(watch),pool.submit(reconnect),pool.submit(checkpoint)]
  assert [f.result(timeout=10) for f in futures]==[None,None,True]
 final=repo.get_account('account')
 assert final.history_id=='101' and final.encrypted_refresh_token=='new'
 assert final.watch_expiration is not None and repo.get_account('provisional') is None


def test_work_claim_blocks_concurrent_null_watch_initialization(repo,monkeypatch):
 from datetime import datetime,timezone
 from threading import Event
 from concurrent.futures import ThreadPoolExecutor
 with repo.sessions.begin() as db:db.get(GmailAccountRow,repo.get_account('account').pk).history_id=None
 locked=Event();release=Event();attempt=Event();original=repo._lock_account
 def hold(db,aid):
  row=original(db,aid);locked.set();assert release.wait(timeout=5);return row
 monkeypatch.setattr(repo,'_lock_account',hold)
 def work():return repo.save_message(message_id='m',account_id='account',gmail_id='g',thread_id=None,history_id=None,subject='fixture',sender='s',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='action_required',category_confidence=1,embedding=None,unsubscribe_url=None,draft_work={'actions':[]})
 other=SqlEmailRepository('a',repo.sessions);otherlock=other._lock_account
 def watching_lock(db,aid):attempt.set();return otherlock(db,aid)
 monkeypatch.setattr(other,'_lock_account',watching_lock)
 with ThreadPoolExecutor(max_workers=2) as pool:
  insertion=pool.submit(work);assert locked.wait(timeout=5)
  watch=pool.submit(other.update_watch_expiration,'account',datetime.now(timezone.utc),'999')
  assert attempt.wait(timeout=5);release.set()
  assert insertion.result(timeout=10);watch.result(timeout=10)
 assert repo.get_account('account').history_id is None
 assert repo.draft_work('m','account')['phase']=='ready'


def test_preinsert_completion_rolls_back_if_message_insert_fails(repo):
 data={'raw_digest':'fixture','actions':[],'embedding':[]}
 assert repo.claim_ingest_work('account','g',data)
 for expected,target in [('extraction_inflight','extraction_done'),('extraction_done','embedding_inflight'),('embedding_inflight','effects_done')]:assert repo.transition_ingest_work('account','g',expected,target,data)
 def fail(mapper,conn,target):raise RuntimeError('fixture message row failure')
 event.listen(EmailMessageRow,'before_insert',fail)
 # Core insert uses SQL directly. Inject failure at database execution boundary.
 def fail_sql(conn,cursor,statement,params,context,many):
  if statement.lstrip().upper().startswith('INSERT INTO M10_EMAIL_MESSAGES'):raise RuntimeError('fixture message row failure')
 engine=repo.sessions.kw['bind'];event.listen(engine,'before_cursor_execute',fail_sql)
 try:
  with pytest.raises(RuntimeError,match='message row failure'):
   repo.save_message(message_id='m',account_id='account',gmail_id='g',thread_id=None,history_id=None,subject='fixture',sender='s',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='personal',category_confidence=1,embedding=None,unsubscribe_url=None,ingest_work_data=data)
 finally:
  event.remove(engine,'before_cursor_execute',fail_sql);event.remove(EmailMessageRow,'before_insert',fail)
 assert repo.ingest_work('account','g')['phase']=='effects_done' and repo.list_messages()==[]
