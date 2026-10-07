"""Actual M00 ApprovalStore + M10 killed restart. Local DB, no model/mail network."""
import os,subprocess,sys
import pytest

@pytest.mark.parametrize('kind',['sqlite','postgres'])
@pytest.mark.parametrize('kill_phase',['approval_done','approval_inflight_receipt'])
def test_actual_m00_durable_approval_is_read_after_killed_m10_restart(tmp_path,kind,kill_phase):
 if kind=='postgres':
  pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/durable.db'
 script="""
import asyncio,os
from sqlalchemy import select,func
from app.core.database import Base,engine,SessionLocal
from app.core.approvals import ApprovalStore
from app.modules.m00_approval_center.service import ApprovalRequestRow,ApprovalEventRow
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository
from app.modules.m10_email_assistant.service import Service
from app.core.token_crypto import TokenCipher
from app.modules.m10_email_assistant.gmail import GmailRawMessage
import httpx
Base.metadata.create_all(engine)
repo=SqlEmailRepository('tenant-fixture');sink=ApprovalStore()
async def no_network(prompt,provider,model):
 if os.environ['MODE']=='restart':raise AssertionError('saved model must not rerun')
 return 'fixture','[]' if prompt.startswith('Extract action items') else 'Subject: Re: fixture\\nFixture draft only'
client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req:(_ for _ in ()).throw(AssertionError('no HTTP expected'))))
svc=Service(repo,sink,object(),client,cipher=TokenCipher('tenant-fixture',master_secret='fixture'),google_client_id='fixture',google_client_secret='fixture',pubsub_verification_token='fixture',llm_generate=no_network)
if os.environ['MODE']=='kill':
 repo.save_account(account_id='account',email_address='fixture@example.invalid',encrypted_refresh_token='fixture',history_id='100',watch_expiration=None)
 if os.environ['KILL_PHASE']=='approval_inflight_receipt':
  original_put=sink.put
  def put(item,*,user_id=None):
   original_put(item,user_id=user_id);os._exit(77)
  sink.put=put
 original=repo.transition_draft_work
 def transition(mid,aid,expected,target,data):
  won=original(mid,aid,expected,target,data)
  if target=='approval_done' and won:os._exit(77)
  return won
 repo.transition_draft_work=transition
 raw=GmailRawMessage(gmail_id='g',thread_id='t',history_id='101',subject='Please reply',sender='sender@example.invalid',recipients=['fixture@example.invalid'],snippet='please reply',body_text='fixture',labels=['INBOX'],headers={},received_at=None)
 asyncio.run(svc._ingest_message('account',raw))
 raise AssertionError('kill missed')
else:
 row=repo.list_messages()[0];work=repo.draft_work(row.id,'account')
 if os.environ['KILL_PHASE']=='approval_inflight_receipt':
  assert work['phase']=='approval_inflight'
  assert not svc.reconcile_approval_claim(row.id,'wrong-account')
  assert svc.reconcile_approval_claim(row.id,'account')
  work=repo.draft_work(row.id,'account')
 assert work['phase']=='approval_done'
 aid=work['data']['approval_id']
 observed=sink.get(aid,user_id='tenant-fixture')
 assert observed is not None and observed.id==aid
 assert sink.get(aid,user_id='other') is None
 with SessionLocal() as db:
  assert db.scalar(select(func.count()).select_from(ApprovalRequestRow))==1
  assert db.scalar(select(func.count()).select_from(ApprovalEventRow))==1
 assert asyncio.run(svc.recover_draft_pipeline('account'))==1
 assert repo.draft_work(row.id,'account')['phase']=='complete'
 assert len(repo.list_drafts())==1 and repo.list_drafts()[0].approval_id==aid
 assert asyncio.run(svc.recover_draft_pipeline('account'))==0
 with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(ApprovalRequestRow))==1
"""
 env={**os.environ,'PYTHONPATH':'backend','ATLAS_DATABASE_URL':url,'ATLAS_ENV':'production','MODE':'kill','KILL_PHASE':kill_phase}
 killed=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=35)
 assert killed.returncode==77,killed.stderr
 restarted=subprocess.run([sys.executable,'-c',script],env={**env,'MODE':'restart'},capture_output=True,text=True,timeout=35)
 assert restarted.returncode==0,restarted.stderr
