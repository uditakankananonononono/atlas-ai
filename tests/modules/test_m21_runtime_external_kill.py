"""External SIGKILL at explicit barriers; no outbox exists in this runtime."""
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
from tests.modules.test_m21_runtime_subprocess_recovery import PROCESS

# Reuse the reviewed scratch tool/receipt protocol, extending test-process barriers.
KILL_PROCESS = PROCESS.replace('import asyncio, hashlib, hmac, json, os, sys','import asyncio, hashlib, hmac, json, os, sys, time')
KILL_PROCESS = KILL_PROCESS.replace("if phase=='crash':os._exit(73)", "if phase=='crash' and point in ('before','after'):os._exit(73)")
KILL_PROCESS = KILL_PROCESS.replace('store=GoalStore(url,lease_seconds=2)', '''
store=GoalStore(url,lease_seconds=4)
def barrier():
    with open(root/'ready','w') as f:
        f.write('ready');f.flush();os.fsync(f.fileno())
    while True:time.sleep(.1)
if phase=='crash' and point=='before-claim':barrier()
if phase=='crash' and point=='journal-committed':
    original=store.mark_effect
    def marked(effect_id,state,receipt=None):
        result=original(effect_id,state,receipt)
        if result and state=='committed':barrier()
        return result
    store.mark_effect=marked
''')
KILL_PROCESS = KILL_PROCESS.replace('call_timeout=.5','call_timeout=1').replace('model_timeout_seconds=.5','model_timeout_seconds=1')


@pytest.mark.parametrize('point',['before-claim','journal-committed'])
def test_external_sigkill_then_new_subprocess_resume(migrated_pg,tmp_path,point):
    url,_=migrated_pg
    (tmp_path/'key').write_bytes(secrets.token_bytes(32));os.chmod(tmp_path/'key',0o600)
    store=GoalStore(url,lease_seconds=4)
    gid=store.create('kill-tenant','actor','scratch artifact',[{'kind':'tool_receipt','tool':'record_artifact','min_count':1}],3)
    env={**os.environ,'PYTHONPATH':'backend'}
    child=subprocess.Popen([sys.executable,'-c',KILL_PROCESS,url,str(tmp_path),'crash',point],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+20
        while not (tmp_path/'ready').exists():
            assert child.poll() is None,'child exited before barrier'
            assert time.monotonic()<deadline,'barrier deadline exceeded'
            time.sleep(.02)
        before=store.get('kill-tenant','actor',gid)
        assert before['status']==('queued' if point=='before-claim' else 'running')
        if point=='journal-committed':
            with store.engine.connect() as conn:
                assert conn.scalar(text('SELECT state FROM claire_runtime_effects WHERE goal_id=:id'),{'id':gid})=='committed'
            assert before['report'] is None
        os.kill(child.pid,signal.SIGKILL)
        stdout,stderr=child.communicate(timeout=10)
        assert child.returncode==-signal.SIGKILL,stdout+stderr
        if point=='journal-committed':
            deadline=time.monotonic()+7
            while True:
                with store.engine.connect() as conn:
                    expires=conn.scalar(text('SELECT lease_expires_at FROM claire_runtime_goals WHERE id=:id'),{'id':gid})
                if datetime.now(timezone.utc)>datetime.fromisoformat(expires):break
                assert time.monotonic()<deadline
                time.sleep(.05)
        resumed=subprocess.run([sys.executable,'-c',KILL_PROCESS,url,str(tmp_path),'resume',point],env=env,capture_output=True,text=True,timeout=30)
        assert resumed.returncode==0,resumed.stderr
        receipt=json.loads((tmp_path/'resumed.json').read_text())
        assert receipt['pid'] not in (os.getpid(),child.pid) and receipt['goal']==gid
        got=store.get('kill-tenant','actor',gid)
        assert got['status']=='completed' and got['verdict']['accepted'] is True
        assert got['attempts']==(1 if point=='before-claim' else 2)
        assert got['report']['receipts'][0]['replayed'] is (point=='journal-committed')
        assert (tmp_path/'dispatch-count').read_text()=='effect\n'
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=10)
        store.close()
