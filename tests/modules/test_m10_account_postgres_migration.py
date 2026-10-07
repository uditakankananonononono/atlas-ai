"""Real PG historical account-ID migration, no mailbox/provider effects."""
import os
import subprocess
import sys
import pytest


def test_m10_account_key_real_pg_upgrade_downgrade(tmp_path):
    pgserver=pytest.importorskip('pgserver');psycopg=pytest.importorskip('psycopg')
    server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');uri=server.get_uri()
    env={**os.environ,'ATLAS_DATABASE_URL':uri.replace('postgresql://','postgresql+psycopg://'),'ATLAS_ENV':'production','PYTHONPATH':'backend'}
    def migrate(*args):
        result=subprocess.run([sys.executable,'-m','alembic',*args],env=env,capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stderr[-1800:]
    migrate('upgrade','head')
    migrate('downgrade','20261007_m05_delivery_claims')
    with psycopg.connect(uri) as conn:
        constraints=conn.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='m10_email_messages'::regclass AND contype='u'").fetchall()
        assert constraints==[('UNIQUE (tenant_id, gmail_id)',)]
    migrate('upgrade','head')
    with psycopg.connect(uri) as conn:
        constraints=conn.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='m10_email_messages'::regclass AND contype='u'").fetchall()
        assert constraints==[('UNIQUE (tenant_id, account_id, gmail_id)',)]

    run=subprocess.run([sys.executable,'-c',"""
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository
repo=SqlEmailRepository('tenant-a')
def save(account,mid):
 repo.save_message(message_id=mid,account_id=account,gmail_id='same-provider-id',thread_id='same-thread',history_id=None,subject='fixture',sender='sender@example.com',recipients=[],snippet=account,body_text=account,received_at=None,labels=[],headers={},category='personal',category_confidence=1,embedding=None,unsubscribe_url=None)
save('account-a','message-a');save('account-b','message-b');save('account-b','message-b-retry')
assert len(repo.list_messages())==2
assert [m.id for m in repo.thread_messages('same-thread',account_id='account-b')]==['message-b']
assert not repo.has_message('same-provider-id',account_id='account-c')
assert not SqlEmailRepository('tenant-b').has_message('same-provider-id',account_id='account-b')
from concurrent.futures import ThreadPoolExecutor
import threading
barrier=threading.Barrier(2)
def race(i):
 barrier.wait(timeout=5)
 return SqlEmailRepository('tenant-race').save_message(message_id='race-'+str(i),account_id='a',gmail_id='same',thread_id='t',history_id=None,subject='fixture',sender='s',recipients=[],snippet='',body_text='',received_at=None,labels=[],headers={},category='personal',category_confidence=1,embedding=None,unsubscribe_url=None)
with ThreadPoolExecutor(max_workers=2) as pool:
 outcomes=list(pool.map(race,[1,2]))
assert sorted(outcomes)==[False,True],outcomes
assert len(SqlEmailRepository('tenant-race').list_messages())==1

"""],env=env,capture_output=True,text=True,timeout=120)
    assert run.returncode==0,run.stderr[-1800:]
    with psycopg.connect(uri) as conn:
        assert conn.execute("SELECT account_id,gmail_id FROM m10_email_messages WHERE tenant_id='tenant-a' ORDER BY account_id").fetchall()==[('account-a','same-provider-id'),('account-b','same-provider-id')]

    blocked=subprocess.run([sys.executable,'-m','alembic','downgrade','20261007_m05_delivery_claims'],env=env,capture_output=True,text=True,timeout=120)
    assert blocked.returncode!=0
    assert 'losing account data' in blocked.stderr
    with psycopg.connect(uri) as conn:
        assert conn.execute('SELECT count(*) FROM m10_email_messages').fetchone()[0]==3
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='20261007_m10_account_messages'
