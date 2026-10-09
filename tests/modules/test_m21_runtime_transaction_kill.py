"""Kill after reservation SQL, before transaction commit; PG rollback evidence."""
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from datetime import datetime,timezone

import pytest
from sqlalchemy import text
from app.modules.m21_claire.runtime.goals import GoalStore
from tests.modules.test_m21_runtime_postgres_seam import migrated_pg
from tests.modules.test_m21_runtime_external_kill import KILL_PROCESS, replace_once

TRANSACTION_PROCESS=replace_once(KILL_PROCESS, "if phase=='crash' and point=='before-claim':barrier()", """
if phase=='crash' and point=='before-claim':barrier()
if phase=='crash' and point=='in-transaction':
    from sqlalchemy import event
    def after_insert(conn,cursor,statement,params,context,many):
        if statement.lstrip().startswith('INSERT INTO claire_runtime_effects'):
            barrier()
    event.listen(store.engine,'after_cursor_execute',after_insert)
""")


@pytest.mark.parametrize('script,anchor',[('abc','absent'),('abc abc','abc')])
def test_missing_or_duplicate_barrier_anchor_fails(script,anchor):
    with pytest.raises(AssertionError,match='exactly once'):replace_once(script,anchor,'replacement')


def test_exact_barrier_anchor_changes_only_once():
    assert replace_once('abc def','abc','x')=='x def'


def test_external_sigkill_uncommitted_reservation_rolls_back(migrated_pg,tmp_path):
    url,_=migrated_pg
    (tmp_path/'key').write_bytes(secrets.token_bytes(32));os.chmod(tmp_path/'key',0o600)
    store=GoalStore(url,lease_seconds=4)
    gid=store.create('txn-tenant','actor','scratch artifact',[{'kind':'tool_receipt','tool':'record_artifact','min_count':1}],3)
    env={**os.environ,'PYTHONPATH':'backend'}
    child=subprocess.Popen([sys.executable,'-c',TRANSACTION_PROCESS,url,str(tmp_path),'crash','in-transaction'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+20
        while not (tmp_path/'ready').exists():
            assert child.poll() is None,'child exited before barrier'
            assert time.monotonic()<deadline
            time.sleep(.02)
        assert store.get('txn-tenant','actor',gid)['status']=='running'
        assert not (tmp_path/'artifact').exists()
        # Independent connection cannot see uncommitted INSERT.
        with store.engine.connect() as conn:
            assert conn.scalar(text('SELECT count(*) FROM claire_runtime_effects WHERE goal_id=:id'),{'id':gid})==0
        os.kill(child.pid,signal.SIGKILL)
        stdout,stderr=child.communicate(timeout=10)
        assert child.returncode==-signal.SIGKILL,stdout+stderr
        # Server must release the dead transaction; no committed intent remains.
        deadline=time.monotonic()+7
        while True:
            with store.engine.connect() as conn:
                count=conn.scalar(text('SELECT count(*) FROM claire_runtime_effects WHERE goal_id=:id'),{'id':gid})
                expires=conn.scalar(text('SELECT lease_expires_at FROM claire_runtime_goals WHERE id=:id'),{'id':gid})
            assert count==0
            if datetime.now(timezone.utc)>datetime.fromisoformat(expires):break
            assert time.monotonic()<deadline
            time.sleep(.05)
        resumed=subprocess.run([sys.executable,'-c',TRANSACTION_PROCESS,url,str(tmp_path),'resume','in-transaction'],env=env,capture_output=True,text=True,timeout=30)
        assert resumed.returncode==0,resumed.stderr
        receipt=json.loads((tmp_path/'resumed.json').read_text())
        assert receipt['pid'] not in (os.getpid(),child.pid) and receipt['goal']==gid
        got=store.get('txn-tenant','actor',gid)
        assert got['status']=='completed' and got['attempts']==2
        assert got['report']['receipts'][0]['replayed'] is False
        assert (tmp_path/'dispatch-count').read_text()=='effect\n'
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=10)
        store.close()
