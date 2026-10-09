"""Server immediate stop while reservation is uncommitted: no intent survives."""
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

import pgserver
import pytest
from sqlalchemy import create_engine,text
from app.modules.m21_claire.runtime.goals import GoalStore
from tests.modules.test_m21_runtime_transaction_kill import TRANSACTION_PROCESS as KILL_PROCESS


def test_pg_immediate_stop_uncommitted_reservation_rolls_back(tmp_path):
    point='in-transaction'
    data=tmp_path/'pgdata'
    server=pgserver.get_server(data,cleanup_mode='stop')
    url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
    env={**os.environ,'ATLAS_DATABASE_URL':url,'PYTHONPATH':'backend'}
    migration=subprocess.run([sys.executable,'-m','alembic','upgrade','20261008_m21_runtime_revoke'],env=env,capture_output=True,text=True,timeout=90)
    assert migration.returncode==0,migration.stderr
    engine=create_engine(url)
    with engine.connect() as conn:
        old_start=conn.scalar(text('SELECT pg_postmaster_start_time()'))
        print('ACTUAL_PG_VERSION:',conn.scalar(text('SELECT version()')))
    old_pid=server.get_pid()
    (tmp_path/'key').write_bytes(secrets.token_bytes(32));os.chmod(tmp_path/'key',0o600)
    store=GoalStore(url,lease_seconds=4)
    gid=store.create('pg-restart-tenant','actor','scratch artifact',[{'kind':'tool_receipt','tool':'record_artifact','min_count':1}],3)
    child=subprocess.Popen([sys.executable,'-c',KILL_PROCESS,url,str(tmp_path),'crash',point],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+20
        while not (tmp_path/'ready').exists():
            assert child.poll() is None
            assert time.monotonic()<deadline
            time.sleep(.02)
        assert not (tmp_path/'artifact').exists()
        assert store.get('pg-restart-tenant','actor',gid)['status']=='running'
        with engine.connect() as conn:
            assert conn.scalar(text('SELECT count(*) FROM claire_runtime_effects WHERE goal_id=:id'),{'id':gid})==0
        store.close();engine.dispose()
        pg_ctl=Path(pgserver.__file__).parent/'pginstall'/'bin'/'pg_ctl'
        stop=subprocess.run([str(pg_ctl),'-D',str(data),'-m','immediate','-w','stop'],capture_output=True,text=True,timeout=20)
        assert stop.returncode==0,stop.stderr
        print('PG_IMMEDIATE_STOP:',stop.stdout.strip())
        # Server dies while old client's transaction remains blocked at test barrier.
        assert child.poll() is None
        os.kill(child.pid,signal.SIGKILL)
        stdout,stderr=child.communicate(timeout=10)
        assert child.returncode==-signal.SIGKILL,stdout+stderr
        server.ensure_postgres_running()
        assert server.get_pid()!=old_pid
        engine=create_engine(url)
        with engine.connect() as conn:
            assert conn.scalar(text('SELECT pg_postmaster_start_time()'))>old_start
            assert conn.scalar(text('SELECT version_num FROM alembic_version'))=='20261008_m21_runtime_revoke'
            assert conn.scalar(text('SELECT count(*) FROM claire_runtime_effects WHERE goal_id=:id'),{'id':gid})==0
        print('PG_RESTART_PID_CHANGED:',old_pid,server.get_pid())
        log=server.log.read_text()
        assert 'database system was interrupted' in log and 'redo' in log
        print('WAL_RECOVERY_MARKERS: database system was interrupted; redo')
        store=GoalStore(url)
        deadline=time.monotonic()+7
        while True:
            with engine.connect() as conn:
                expires=conn.scalar(text('SELECT lease_expires_at FROM claire_runtime_goals WHERE id=:id'),{'id':gid})
            if datetime.now(timezone.utc)>datetime.fromisoformat(expires):break
            assert time.monotonic()<deadline
            time.sleep(.05)
        resumed=subprocess.run([sys.executable,'-c',KILL_PROCESS,url,str(tmp_path),'resume',point],env=env,capture_output=True,text=True,timeout=30)
        assert resumed.returncode==0,resumed.stderr
        receipt=json.loads((tmp_path/'resumed.json').read_text())
        assert receipt['pid'] not in (child.pid,os.getpid())
        got=store.get('pg-restart-tenant','actor',gid)
        assert got['status']=='completed' and got['attempts']==2
        assert got['report']['receipts'][0]['replayed'] is False
        assert (tmp_path/'dispatch-count').read_text()=='effect\n'
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=10)
        store.close();engine.dispose();server.cleanup()
