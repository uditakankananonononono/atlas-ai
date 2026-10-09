"""Actual supervisor subprocess kill/resume, scripted effect/model only."""
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from datetime import datetime,timezone

from sqlalchemy import text
from app.modules.m21_claire.runtime.goals import GoalStore
from tests.modules.test_m21_runtime_postgres_seam import migrated_pg
from tests.modules.test_m21_runtime_external_kill import KILL_PROCESS,replace_once

SUPERVISOR_PROCESS=replace_once(KILL_PROCESS,"gid=asyncio.run(worker.run_once())", """
from app.modules.m21_claire.runtime.configuration import supervise_read_only
from types import SimpleNamespace
result=asyncio.run(supervise_read_only(SimpleNamespace(store=store,worker=worker),max_jobs=1,max_database_failures=2))
gid=result.goals[0] if result.goals else None
""")


def test_supervisor_sigkill_after_journal_then_fresh_supervisor_replay(migrated_pg,tmp_path):
    url,_=migrated_pg
    (tmp_path/'key').write_bytes(secrets.token_bytes(32));os.chmod(tmp_path/'key',0o600)
    store=GoalStore(url,lease_seconds=4)
    gid=store.create('supervisor-kill-tenant','actor','scratch',[{'kind':'tool_receipt','tool':'record_artifact','min_count':1}],3)
    env={**os.environ,'PYTHONPATH':'backend'}
    child=subprocess.Popen([sys.executable,'-c',SUPERVISOR_PROCESS,url,str(tmp_path),'crash','journal-committed'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+20
        while not (tmp_path/'ready').exists():
            assert child.poll() is None
            assert time.monotonic()<deadline
            time.sleep(.02)
        with store.engine.connect() as conn:
            assert conn.scalar(text('SELECT state FROM claire_runtime_effects WHERE goal_id=:id'),{'id':gid})=='committed'
        assert store.get('supervisor-kill-tenant','actor',gid)['report'] is None
        os.kill(child.pid,signal.SIGKILL);stdout,stderr=child.communicate(timeout=10)
        assert child.returncode==-signal.SIGKILL,stdout+stderr
        deadline=time.monotonic()+7
        while True:
            with store.engine.connect() as conn:
                expires=conn.scalar(text('SELECT lease_expires_at FROM claire_runtime_goals WHERE id=:id'),{'id':gid})
            if datetime.now(timezone.utc)>datetime.fromisoformat(expires):break
            assert time.monotonic()<deadline
            time.sleep(.05)
        resumed=subprocess.run([sys.executable,'-c',SUPERVISOR_PROCESS,url,str(tmp_path),'resume','journal-committed'],env=env,capture_output=True,text=True,timeout=30)
        assert resumed.returncode==0,resumed.stderr
        receipt=json.loads((tmp_path/'resumed.json').read_text())
        assert receipt['pid'] not in (child.pid,os.getpid()) and receipt['goal']==gid
        got=store.get('supervisor-kill-tenant','actor',gid)
        assert got['status']=='completed' and got['attempts']==2
        assert got['report']['receipts'][0]['replayed'] is True
        assert (tmp_path/'dispatch-count').read_text()=='effect\n'
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=10)
        store.close()
