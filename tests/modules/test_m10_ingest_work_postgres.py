"""Actual local PG ingestion ownership/migration. No providers."""
import os,sys,subprocess
import pytest

def test_ingest_work_real_pg_migration_claim_race_and_guarded_downgrade(tmp_path):
 pgserver=pytest.importorskip('pgserver');psycopg=pytest.importorskip('psycopg')
 server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');uri=server.get_uri()
 env={**os.environ,'ATLAS_DATABASE_URL':uri.replace('postgresql://','postgresql+psycopg://'),'ATLAS_ENV':'production','PYTHONPATH':'backend'}
 def run(args):return subprocess.run([sys.executable,*args],env=env,capture_output=True,text=True,timeout=90)
 for args in [['upgrade','head'],['downgrade','20261007_m10_draft_work'],['upgrade','head']]:
  result=run(['-m','alembic',*args]);assert result.returncode==0,result.stderr[-2000:]
 result=run(['-c',"""
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
repo=SqlEmailRepository('a');repo.save_account(account_id='account',email_address='fixture@example.invalid',encrypted_refresh_token='fixture',history_id='100',watch_expiration=None)
assert SqlEmailRepository('b').ingest_work('account','g') is None
barrier=Barrier(2)
def claim(_):
 barrier.wait(timeout=5)
 return SqlEmailRepository('a').claim_ingest_work('account','g',{'raw_digest':'fixture'})
with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(claim,[1,2]))==[False,True]
assert not repo.checkpoint_history('account','100','101')
assert not SqlEmailRepository('b').transition_ingest_work('account','g','extraction_inflight','extraction_done',{})
assert repo.transition_ingest_work('account','g','extraction_inflight','extraction_done',{'raw_digest':'fixture','actions':[]})
assert repo.transition_ingest_work('account','g','extraction_done','embedding_inflight',{'raw_digest':'fixture','actions':[]})
data={'raw_digest':'fixture','actions':[],'embedding':[]}
assert repo.transition_ingest_work('account','g','embedding_inflight','effects_done',data)
params=dict(message_id='m',account_id='account',gmail_id='g',thread_id=None,history_id=None,subject='fixture',sender='s',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='personal',category_confidence=1,embedding=None,unsubscribe_url=None)
assert not repo.save_message(**params,ingest_work_data={**data,'embedding':[99]})
assert repo.ingest_work('account','g')['phase']=='effects_done' and repo.list_messages()==[]
assert repo.save_message(**params,ingest_work_data=data)
assert repo.ingest_work('account','g')['phase']=='complete' and len(repo.list_messages())==1
assert repo.checkpoint_history('account','100','101')
"""]);assert result.returncode==0,result.stderr[-2000:]
 result=run(['-m','alembic','downgrade','20261007_m10_draft_work'])
 assert result.returncode!=0 and 'Cannot remove ingestion ownership' in result.stderr
 with psycopg.connect(uri) as conn:
  assert conn.execute('SELECT phase FROM m10_ingest_work').fetchone()[0]=='complete'
  assert conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='20261007_m10_ingest_work'
