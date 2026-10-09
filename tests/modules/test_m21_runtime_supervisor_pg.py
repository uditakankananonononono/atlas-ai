"""Real backend termination: loud DB error and clean retry, not automatic supervisor."""
import asyncio
import time
from datetime import datetime,timezone

import pytest
from pydantic import BaseModel
from sqlalchemy import event,text
from sqlalchemy.exc import OperationalError
from app.modules.m21_claire.runtime.engine import Engine
from app.modules.m21_claire.runtime.gates import GateEnforcer
from app.modules.m21_claire.runtime.goals import GoalStore
from app.modules.m21_claire.runtime.configuration import supervise_read_only
from types import SimpleNamespace
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry,Tool
from app.modules.m21_claire.runtime.types import AgentDecision,ToolCall,ToolRisk
from app.modules.m21_claire.runtime.worker import Worker
from tests.modules.test_m21_runtime_postgres_seam import migrated_pg


@pytest.mark.parametrize("fault",["backend", "server-restart"])
def test_supervisor_handles_real_database_loss_without_caller_retry(migrated_pg,fault):
    url,admin=migrated_pg
    store=GoalStore(url,lease_seconds=3)
    gid=store.create('loss-tenant','actor','scratch effect',[{'kind':'tool_receipt','tool':'record_artifact','min_count':1}],3)
    dispatch=[]
    class Args(BaseModel): label:str
    class Effect(Tool):
        name,arguments_model,risk='record_artifact',Args,ToolRisk.WRITE
        spends_money,sends_to_person,idempotent=False,False,False
        def run(self,args):dispatch.append(args.label);return {'label':args.label}
    class Script:
        async def decide(self,messages):
            if len(messages)==2:return AgentDecision(tool_call=ToolCall(name='record_artifact',arguments={'label':'once'}))
            return AgentDecision(final='scripted')
    def worker(s):
        registry=ReadOnlyToolRegistry(GateEnforcer(s),journal=s,call_timeout=.5);registry.register(Effect())
        return Worker(s,lambda c:Engine(Script(),registry,model_timeout_seconds=.5),'loss-worker')
    terminated=[]
    def cut(conn,cursor,statement,params,context,many):
        if statement.lstrip().startswith('INSERT INTO claire_runtime_effects') and not terminated:
            pid=conn.connection.driver_connection.info.backend_pid
            if fault=="backend":
                with admin.connect() as killer:
                    assert killer.scalar(text('SELECT pg_terminate_backend(:pid)'),{'pid':pid}) is True
            else:
                import pgserver,subprocess
                from pathlib import Path
                from sqlalchemy.engine import make_url
                data=Path(make_url(url).query['host'])
                server=pgserver.get_server(data,cleanup_mode='stop')
                old=server.get_pid()
                ctl=Path(pgserver.__file__).parent/'pginstall'/'bin'/'pg_ctl'
                stopped=subprocess.run([str(ctl),'-D',str(data),'-m','immediate','-w','stop'],capture_output=True,text=True,timeout=20)
                assert stopped.returncode==0,stopped.stderr
                server.ensure_postgres_running()
                assert server.get_pid()!=old
                admin.dispose()
            terminated.append(pid)
    event.listen(store.engine,'after_cursor_execute',cut)
    try:
        result=asyncio.run(supervise_read_only(SimpleNamespace(store=store,worker=worker(store)),max_jobs=1,max_database_failures=2))
        assert result.status=='job_limit' and result.goals==(gid,) and result.database_failures==1
        assert len(terminated)==1 and dispatch==['once']
        got=store.get('loss-tenant','actor',gid)
        assert got['status']=='completed' and got['attempts']==2
        assert got['report']['receipts'][0]['replayed'] is False
        with admin.connect() as conn:
            assert conn.scalar(text('SELECT count(*) FROM claire_runtime_effects WHERE goal_id=:id'),{'id':gid})==1
    finally:
        if event.contains(store.engine,'after_cursor_execute',cut):event.remove(store.engine,'after_cursor_execute',cut)
        store.close()
