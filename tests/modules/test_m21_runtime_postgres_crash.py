"""Actual worker subprocess death after a scratch effect; ephemeral PG only."""
import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel
from app.modules.m21_claire.runtime.engine import Engine
from app.modules.m21_claire.runtime.gates import GateEnforcer
from app.modules.m21_claire.runtime.goals import GoalStore
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry, Tool
from app.modules.m21_claire.runtime.types import AgentDecision, ToolCall, ToolRisk
from app.modules.m21_claire.runtime.worker import Worker
from tests.modules.test_m21_runtime_postgres_seam import migrated_pg

CHILD = r'''
import asyncio, os, sys
from datetime import datetime, timezone
from pydantic import BaseModel
from app.modules.m21_claire.runtime.engine import Engine
from app.modules.m21_claire.runtime.gates import GateEnforcer
from app.modules.m21_claire.runtime.goals import GoalStore
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry, Tool
from app.modules.m21_claire.runtime.types import AgentDecision, ToolCall, ToolRisk
from app.modules.m21_claire.runtime.worker import Worker
url, path = sys.argv[1:]
class Args(BaseModel): label: str
class Effect(Tool):
    name, arguments_model, risk = "record_artifact", Args, ToolRisk.WRITE
    spends_money, sends_to_person, idempotent = False, False, False
    def run(self, args):
        with open(path, "a") as file:
            file.write(args.label+"\n"); file.flush(); os.fsync(file.fileno())
        os._exit(73)  # before execute can mark_effect or return its receipt
class Script:
    async def decide(self, messages):
        return AgentDecision(tool_call=ToolCall(name="record_artifact",arguments={"label":"committed"}))
store = GoalStore(url, clock=lambda:datetime(2026,10,9,tzinfo=timezone.utc))
registry = ReadOnlyToolRegistry(GateEnforcer(store), journal=store)
registry.register(Effect())
asyncio.run(Worker(store,lambda claim:Engine(Script(),registry),"crashing-child").run_once())
raise AssertionError("crash point not reached")
'''


@pytest.mark.parametrize("reconcile", [False, True])
def test_postgres_crash_after_effect_before_receipt_no_duplicate(migrated_pg, tmp_path, reconcile):
    url, _ = migrated_pg
    artifact = tmp_path / "scratch-effect.txt"
    now = datetime(2026,10,9,tzinfo=timezone.utc)
    producer = GoalStore(url, clock=lambda:now)
    gid = producer.create("crash-tenant", "actor", "write scratch artifact",
                          [{"kind":"tool_receipt","tool":"record_artifact","min_count":1}], 3)
    try:
        child = subprocess.run([sys.executable,"-c",CHILD,url,str(artifact)],
                               env={**os.environ,"PYTHONPATH":"backend"},capture_output=True,text=True,timeout=40)
        assert child.returncode == 73, child.stdout + child.stderr
        assert artifact.read_text() == "committed\n"
        before = producer.get("crash-tenant","actor",gid)
        assert before["status"] == "running" and before["report"] is None
        assert len(producer.pending_effects(gid)) == 1
    finally: producer.close()
    # Real process death, but lease expiry uses an explicit advanced test clock.
    resumed = GoalStore(url, clock=lambda:now+timedelta(seconds=121))
    class Args(BaseModel): label: str
    dispatches = []
    class Effect(Tool):
        name, arguments_model, risk = "record_artifact", Args, ToolRisk.WRITE
        spends_money, sends_to_person, idempotent = False, False, False
        def run(self,args):
            dispatches.append(True)
            raise AssertionError("must never dispatch a duplicate effect")
    class Reconciled(Effect):
        def reconcile(self,key):
            # Artifact is owned by this one test goal. Production tools must bind
            # receipts to exact effect keys; this is scratch evidence only.
            return "committed" if artifact.read_text() == "committed\n" else "unknown"
    class Script:
        async def decide(self,messages):
            if len(messages) == 2:
                return AgentDecision(tool_call=ToolCall(name="record_artifact",arguments={"label":"committed"}))
            return AgentDecision(final="script only")
    registry = ReadOnlyToolRegistry(GateEnforcer(resumed), journal=resumed)
    registry.register(Reconciled() if reconcile else Effect())
    try:
        assert asyncio.run(Worker(resumed,lambda claim:Engine(Script(),registry),"restarted").run_once()) == gid
        got = resumed.get("crash-tenant","actor",gid)
        assert got["attempts"] == 2 and not dispatches
        assert artifact.read_text() == "committed\n"
        if reconcile:
            assert got["status"] == "completed" and got["verdict"]["accepted"] is True
            assert got["report"]["receipts"][0]["replayed"] is True
            assert got["report"]["receipts"][0]["content"] == {"reconciled":True}
            assert resumed.pending_effects(gid) == []
        else:
            assert got["status"] == "awaiting_review" and got["blocker"] == "effect_unknown"
            assert len(resumed.pending_effects(gid)) == 1
    finally: resumed.close()
