"""Scratch key-bound reconciliation, real clock expiry and separate process resume."""
import json
import os
import subprocess
import sys
import time
import secrets

import pytest
from app.modules.m21_claire.runtime.goals import GoalStore
from tests.modules.test_m21_runtime_postgres_seam import migrated_pg

PROCESS = r'''
import asyncio, hashlib, hmac, json, os, sys
from pathlib import Path
from pydantic import BaseModel
from app.modules.m21_claire.runtime.engine import Engine
from app.modules.m21_claire.runtime.gates import GateEnforcer, payload_digest
from app.modules.m21_claire.runtime.goals import GoalStore
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry, Tool
from app.modules.m21_claire.runtime.types import AgentDecision, ToolCall, ToolRisk
from app.modules.m21_claire.runtime.worker import Worker
url, root, phase, point = sys.argv[1:]
root=Path(root); secret=(root/'key').read_bytes()
class Args(BaseModel): label:str
class Artifact(Tool):
    name,arguments_model,risk='record_artifact',Args,ToolRisk.WRITE
    spends_money,sends_to_person,idempotent=False,False,False
    accepts_idempotency_key=True
    def run(self,args,*,idempotency_key):
        if phase=='crash' and point=='before':os._exit(73)
        data={'effect_key':idempotency_key,'label':args.label}
        encoded=json.dumps(data,sort_keys=True).encode()
        signed={'data':data,'signature':hmac.new(secret,encoded,hashlib.sha256).hexdigest()}
        with open(root/'artifact','w') as f:
            json.dump(signed,f);f.flush();os.fsync(f.fileno())
        with open(root/'dispatch-count','a') as f:
            f.write('effect\n');f.flush();os.fsync(f.fileno())
        if phase=='crash':os._exit(73)
        return {'effect_key':idempotency_key,'label':args.label}
    def reconcile(self,key):
        if not (root/'artifact').exists():return 'absent'
        try:
            signed=json.loads((root/'artifact').read_text());data=signed['data']
            signature=hmac.new(secret,json.dumps(data,sort_keys=True).encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature,signed['signature']):return 'unknown'
            return 'committed' if data['effect_key']==key and data['label']=='committed' else 'unknown'
        except (KeyError,ValueError,TypeError):return 'unknown'
class Script:
    async def decide(self,messages):
        if len(messages)==2:return AgentDecision(tool_call=ToolCall(name='record_artifact',arguments={'label':'committed'}))
        return AgentDecision(final='scripted only')
store=GoalStore(url,lease_seconds=2)
registry=ReadOnlyToolRegistry(GateEnforcer(store),journal=store,call_timeout=.5);registry.register(Artifact())
worker=Worker(store,lambda c:Engine(Script(),registry,model_timeout_seconds=.5),phase)
gid=asyncio.run(worker.run_once())
if phase=='crash':raise AssertionError('crash point not reached')
(root/'resumed.json').write_text(json.dumps({'pid':os.getpid(),'outcome':worker.last_outcome,'goal':gid}))
store.close()
'''


@pytest.mark.parametrize('point',['before','after','tampered','wrong-key'])
def test_separate_process_real_expiry_and_key_bound_scratch_recovery(migrated_pg,tmp_path,point):
    url,_=migrated_pg
    (tmp_path/'key').write_bytes(secrets.token_bytes(32));os.chmod(tmp_path/'key',0o600)
    store=GoalStore(url,lease_seconds=2)
    gid=store.create('subprocess-tenant','actor','scratch artifact',[{'kind':'tool_receipt','tool':'record_artifact','min_count':1}],3)
    env={**os.environ,'PYTHONPATH':'backend'}
    try:
        child=subprocess.Popen([sys.executable,'-c',PROCESS,url,str(tmp_path),'crash',point],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        stdout,stderr=child.communicate(timeout=30)
        assert child.returncode==73,stdout+stderr
        assert store.get('subprocess-tenant','actor',gid)['status']=='running'
        assert len(store.pending_effects(gid))==1
        if point in ('tampered','wrong-key'):
            artifact=json.loads((tmp_path/'artifact').read_text())
            if point=='tampered':artifact['signature']='0'*64
            else:
                # Valid local HMAC but wrong effect binding must still refuse.
                import hashlib,hmac
                artifact['data']['effect_key']='b'*64
                artifact['signature']=hmac.new((tmp_path/'key').read_bytes(),json.dumps(artifact['data'],sort_keys=True).encode(),hashlib.sha256).hexdigest()
            (tmp_path/'artifact').write_text(json.dumps(artifact))
        # Actual elapsed time: no injected clock. Poll for second-worker claim
        # eligibility without consuming the claim itself.
        from datetime import datetime,timezone
        from sqlalchemy import text
        deadline=time.monotonic()+5
        while True:
            with store.engine.connect() as conn:
                expires=conn.scalar(text('SELECT lease_expires_at FROM claire_runtime_goals WHERE id=:id'),{'id':gid})
            if datetime.now(timezone.utc)>datetime.fromisoformat(expires):break
            assert time.monotonic()<deadline
            time.sleep(.05)
        resumed=subprocess.run([sys.executable,'-c',PROCESS,url,str(tmp_path),'resume',point],env=env,capture_output=True,text=True,timeout=30)
        assert resumed.returncode==0,resumed.stderr
        receipt=json.loads((tmp_path/'resumed.json').read_text())
        assert receipt['pid']!=child.pid and receipt['pid']!=os.getpid() and receipt['goal']==gid
        got=store.get('subprocess-tenant','actor',gid)
        assert got['attempts']==2
        if point in ('tampered','wrong-key'):
            assert got['status']=='awaiting_review' and got['blocker']=='effect_unknown'
        else:
            assert got['status']=='completed' and got['verdict']['accepted'] is True
            assert got['report']['receipts'][0]['replayed'] is (point=='after')
        assert (tmp_path/'dispatch-count').read_text()=='effect\n'
    finally:store.close()
