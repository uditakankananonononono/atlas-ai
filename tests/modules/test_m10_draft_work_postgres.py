"""Durable M10 work ownership/finalization on real temporary PG, no provider."""
import os,subprocess,sys
import pytest

def test_draft_work_migration_ownership_and_lossy_downgrade_guard(tmp_path):
 pgserver=pytest.importorskip('pgserver');psycopg=pytest.importorskip('psycopg')
 server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');uri=server.get_uri()
 env={**os.environ,'ATLAS_DATABASE_URL':uri.replace('postgresql://','postgresql+psycopg://'),'ATLAS_ENV':'production','PYTHONPATH':'backend'}
 def run(args):return subprocess.run([sys.executable,*args],env=env,capture_output=True,text=True,timeout=120)
 result=run(['-m','alembic','upgrade','head']);assert result.returncode==0,result.stderr[-1800:]
 result=run(['-m','alembic','downgrade','20261007_m10_account_messages']);assert result.returncode==0,result.stderr[-1800:]
 result=run(['-m','alembic','upgrade','head']);assert result.returncode==0,result.stderr[-1800:]
 result=run(['-c',"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository
repo=SqlEmailRepository('a')
assert repo.save_message(message_id='m',account_id='account',gmail_id='g',thread_id='t',history_id=None,subject='fixture',sender='sender@example.invalid',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='action_required',category_confidence=1,embedding=None,unsubscribe_url=None,draft_work={'actions':[]})
assert not repo.transition_draft_work('m','other','ready','model_inflight',{})
assert not SqlEmailRepository('b').transition_draft_work('m','account','ready','model_inflight',{})
barrier=Barrier(2)
def claim(_):
 barrier.wait(timeout=5)
 return SqlEmailRepository('a').transition_draft_work('m','account','ready','model_inflight',{'actions':[]})
with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(claim,[1,2]))==[False,True]
assert repo.recoverable_draft_work('account')==[]
data={'draft_id':'d','approval_id':'ap','subject':'fixture','body':'fixture','to':'sender@example.invalid','model':'fake'}
assert repo.transition_draft_work('m','account','model_inflight','model_done',data)
assert repo.transition_draft_work('m','account','model_done','approval_inflight',data)
assert repo.transition_draft_work('m','account','approval_inflight','approval_done',data)
assert repo.finalize_draft_work('m','account',data)
assert not repo.finalize_draft_work('m','account',data)
assert len(repo.list_drafts())==1 and repo.draft_work('m','account')['phase']=='complete'
"""]);assert result.returncode==0,result.stderr[-1800:]
 result=run(['-m','alembic','downgrade','20261007_m10_account_messages'])
 assert result.returncode!=0 and 'Cannot remove durable draft ownership' in result.stderr
 with psycopg.connect(uri) as conn:
  assert conn.execute('SELECT phase FROM m10_draft_work').fetchall()==[('complete',)]
  assert conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='20261007_m10_draft_work'
