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
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry,Tool
from app.modules.m21_claire.runtime.types import AgentDecision,ToolCall,ToolRisk
from app.modules.m21_claire.runtime.worker import Worker
from tests.modules.test_m21_runtime_postgres_seam import migrated_pg


def test_terminated_reservation_connection_propagates_then_retry_is_clean(migrated_pg):
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
            with admin.connect() as killer:
                assert killer.scalar(text('SELECT pg_terminate_backend(:pid)'),{'pid':pid}) is True
            terminated.append(pid)
    event.listen(store.engine,'after_cursor_execute',cut)
    try:
        with pytest.raises(OperationalError):asyncio.run(worker(store).run_once())
        assert len(terminated)==1 and dispatch==[]
        with admin.connect() as conn:
            assert conn.scalar(text('SELECT count(*) FROM claire_runtime_effects WHERE goal_id=:id'),{'id':gid})==0
            assert conn.scalar(text('SELECT status FROM claire_runtime_goals WHERE id=:id'),{'id':gid})=='running'
            assert conn.scalar(text('SELECT report FROM claire_runtime_goals WHERE id=:id'),{'id':gid}) is None
        event.remove(store.engine,'after_cursor_execute',cut)
        store.close()
        deadline=time.monotonic()+6
        while True:
            with admin.connect() as conn:
                expires=conn.scalar(text('SELECT lease_expires_at FROM claire_runtime_goals WHERE id=:id'),{'id':gid})
            if datetime.now(timezone.utc)>datetime.fromisoformat(expires):break
            assert time.monotonic()<deadline
            time.sleep(.05)
        fresh=GoalStore(url,lease_seconds=3)
        try:
            assert asyncio.run(worker(fresh).run_once())==gid
            got=fresh.get('loss-tenant','actor',gid)
            assert got['status']=='completed' and got['attempts']==2
            assert got['report']['receipts'][0]['replayed'] is False
            assert dispatch==['once']
        finally:fresh.close()
    finally:
        if event.contains(store.engine,'after_cursor_execute',cut):event.remove(store.engine,'after_cursor_execute',cut)
        store.close()
