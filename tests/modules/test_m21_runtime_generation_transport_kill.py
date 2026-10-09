"""Generation/real synthetic HTTP transport kill barriers, not learned-model proof."""
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

import pytest
from sqlalchemy import text
from app.modules.m21_claire.runtime.goals import GoalStore
from tests.modules.test_m21_runtime_postgres_seam import migrated_pg
from tests.modules.test_m21_runtime_external_kill import KILL_PROCESS,replace_once

MODEL_PROCESS=replace_once(KILL_PROCESS,'store=GoalStore(url,lease_seconds=4)','store=GoalStore(url,lease_seconds=8)')
MODEL_PROCESS=replace_once(MODEL_PROCESS,'model_timeout_seconds=1','model_timeout_seconds=5')
MODEL_PROCESS=replace_once(MODEL_PROCESS,"if len(messages)==2:return AgentDecision(tool_call=ToolCall(name='record_artifact',arguments={'label':'committed'}))", """
        if len(messages)==2:
            if phase=='crash' and point=='generation':barrier()
            if point=='transport':
                from app.modules.m21_claire.runtime.model_adapter import LocalSharedModel
                return await LocalSharedModel.select('hermes',os.environ['SCRATCH_MODEL_URL'],'synthetic-kill-model').decide(messages)
            return AgentDecision(tool_call=ToolCall(name='record_artifact',arguments={'label':'committed'}))
""")


@pytest.mark.parametrize('point',['generation','transport'])
def test_external_kill_during_model_then_fresh_process_recovers(migrated_pg,tmp_path,point):
    url,_=migrated_pg
    arrived,release=threading.Event(),threading.Event()
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(body)
            if len(requests)==1:arrived.set();release.wait(20)
            response=json.dumps({'choices':[{'message':{'content':json.dumps({'tool_call':{'name':'record_artifact','arguments':{'label':'committed'}}})}}]}).encode()
            try:
                self.send_response(200);self.send_header('Content-Length',str(len(response)));self.end_headers();self.wfile.write(response)
            except (BrokenPipeError,ConnectionResetError):pass  # killed request client, expected
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever);thread.start()
    (tmp_path/'key').write_bytes(secrets.token_bytes(32));os.chmod(tmp_path/'key',0o600)
    store=GoalStore(url,lease_seconds=8)
    gid=store.create('model-kill-tenant','actor','scratch artifact',[{'kind':'tool_receipt','tool':'record_artifact','min_count':1}],3)
    env={**os.environ,'PYTHONPATH':'backend','SCRATCH_MODEL_URL':f'http://127.0.0.1:{server.server_port}/v1'}
    child=subprocess.Popen([sys.executable,'-c',MODEL_PROCESS,url,str(tmp_path),'crash',point],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+20
        while not (arrived.is_set() if point=='transport' else (tmp_path/'ready').exists()):
            assert child.poll() is None,'child exited before model barrier'
            assert time.monotonic()<deadline
            time.sleep(.01)
        assert store.get('model-kill-tenant','actor',gid)['status']=='running'
        assert not (tmp_path/'artifact').exists()
        with store.engine.connect() as conn:
            assert conn.scalar(text('SELECT count(*) FROM claire_runtime_effects WHERE goal_id=:id'),{'id':gid})==0
        os.kill(child.pid,signal.SIGKILL)
        stdout,stderr=child.communicate(timeout=10)
        assert child.returncode==-signal.SIGKILL,stdout+stderr
        release.set()
        deadline=time.monotonic()+12
        while True:
            with store.engine.connect() as conn:
                expires=conn.scalar(text('SELECT lease_expires_at FROM claire_runtime_goals WHERE id=:id'),{'id':gid})
            if datetime.now(timezone.utc)>datetime.fromisoformat(expires):break
            assert time.monotonic()<deadline
            time.sleep(.05)
        resumed=subprocess.run([sys.executable,'-c',MODEL_PROCESS,url,str(tmp_path),'resume',point],env=env,capture_output=True,text=True,timeout=30)
        assert resumed.returncode==0,resumed.stderr
        receipt=json.loads((tmp_path/'resumed.json').read_text())
        assert receipt['pid'] not in (child.pid,os.getpid()) and receipt['goal']==gid
        got=store.get('model-kill-tenant','actor',gid)
        assert got['status']=='completed' and got['attempts']==2
        assert got['report']['receipts'][0]['replayed'] is False
        assert (tmp_path/'dispatch-count').read_text()=='effect\n'
        if point=='transport':
            assert len(requests)==2 and all(r['model']=='synthetic-kill-model' for r in requests)
    finally:
        release.set()
        if child.poll() is None:child.kill();child.communicate(timeout=10)
        store.close();server.shutdown();thread.join();server.server_close()
