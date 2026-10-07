"""Source receipt null/presence/ambiguity against real local databases."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service,ApprovalRequestRow,ApprovalEventRow

@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_source_query_excludes_missing_null_keys_before_limit_and_detects_duplicates(tmp_path,kind):
 if kind=='postgres':
  pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/source.db'
 engine=create_engine(url)
 for table in (ApprovalRequestRow.__table__,ApprovalEventRow.__table__):table.create(engine)
 svc=Service(session_factory=sessionmaker(bind=engine,expire_on_commit=False))
 def add(payload,user='a'):return svc.submit(user_id=user,module_id=10,action_type='send_email_reply',payload=payload)
 for _ in range(3):add({'body':'fixture'})
 add({'body':'fixture','thread_id':None},'b')
 valid=add({'body':'fixture','thread_id':None})
 query=lambda:svc.matching_source_approvals(user_id='a',module_id=10,action_type='send_email_reply',payload={'body':'fixture','thread_id':None})
 assert [x['id'] for x in query()]==[valid['id']]
 duplicate=add({'body':'fixture','thread_id':None})
 assert {x['id'] for x in query()}=={valid['id'],duplicate['id']}
 engine.dispose()


@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_m10_atomic_finalize_rechecks_actual_m00_row_after_earlier_read(tmp_path,kind):
 from datetime import datetime,timezone
 from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository,GmailAccountRow,DraftWorkRow,EmailEventRow,EmailMessageRow,EmailDraftRow
 from app.core.approvals import ApprovalStore
 if kind=='postgres':
  pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/atomic-source.db'
 engine=create_engine(url)
 for model in (GmailAccountRow,DraftWorkRow,EmailEventRow,EmailMessageRow,EmailDraftRow,ApprovalRequestRow,ApprovalEventRow):model.__table__.create(engine)
 sessions=sessionmaker(bind=engine,expire_on_commit=False);repo=SqlEmailRepository('a',sessions);m00=Service(session_factory=sessions)
 repo.save_account(account_id='account',email_address='fixture@example.invalid',encrypted_refresh_token='fixture',history_id='100',watch_expiration=None)
 data={'draft_id':'draft','approval_id':'temporary','to':'sender@example.invalid','subject':'Re: fixture','body':'Fixture draft','model':'fake'}
 repo.save_message(message_id='m',account_id='account',gmail_id='g',thread_id='t',history_id=None,subject='fixture',sender='sender@example.invalid',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='action_required',category_confidence=1,embedding=None,unsubscribe_url=None,draft_work={'actions':[]})
 payload={'tenant_id':'a','account_id':'account','draft_id':'draft','message_id':'m','gmail_id':'g','thread_id':'t','to':data['to'],'subject':data['subject'],'body':data['body']}
 receipt=m00.submit(user_id='a',module_id=10,action_type='send_email_reply',payload=payload);data['approval_id']=receipt['id']
 for before,after in [('ready','model_inflight'),('model_inflight','model_done'),('model_done','approval_inflight'),('approval_inflight','approval_done')]:assert repo.transition_draft_work('m','account',before,after,data)
 observed=m00.get(receipt['id']);assert observed['payload']==payload
 with sessions.begin() as db:db.get(ApprovalRequestRow,receipt['id']).payload={**payload,'body':'mutated after source read'}
 sink=ApprovalStore()
 assert not sink.finalize_recovered_m10_draft(repo,'m','account',data)
 assert repo.draft_work('m','account')['phase']=='approval_done' and repo.list_drafts()==[]
 with sessions.begin() as db:db.get(ApprovalRequestRow,receipt['id']).payload=payload
 from concurrent.futures import ThreadPoolExecutor
 from threading import Barrier
 barrier=Barrier(2)
 def finalize(_):
  worker=SqlEmailRepository('a',sessions);barrier.wait(timeout=5)
  return sink.finalize_recovered_m10_draft(worker,'m','account',data)
 with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(finalize,[1,2]))==[False,True]
 assert not sink.finalize_recovered_m10_draft(repo,'m','account',data)
 assert len(repo.list_drafts())==1
 engine.dispose()
