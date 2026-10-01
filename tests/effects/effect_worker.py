"""Subprocess worker for the crash tests. Uses the real GCWRuntime, real
SQLAlchemy engine on a file database and a real file-backed fake counter.

usage: effect_worker.py <db> <counter> <tenant> <cmd> [task_id]
cmd: submit | run <task_id> | resume-reconcile ...
Crash point via env EFFECT_CRASH (SIGKILLs this process):
  before_reserve, after_reserve, before_effect, after_effect,
  before_receipt, before_final_state
"""
import json, os, signal, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from sqlalchemy import create_engine
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.safety import InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.schemas import Risk, TaskState, ToolSpec
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.tools import ToolDispatcher
import app.modules.m20_general_cognitive_worker.runtime as rt

db, counter, tenant, cmd = sys.argv[1:5]
CRASH = os.environ.get("EFFECT_CRASH", "")
HOLD = float(os.environ.get("EFFECT_HOLD", "0"))


def die():
    os.kill(os.getpid(), signal.SIGKILL)


def crash_if(point):
    if CRASH == point:
        die()


class Planner:
    def decompose(self, goal, *, context=""):
        return [{"title": "bump the counter", "tool": "bump", "risk": "reversible",
                 "arguments": {"by": 1}}]


async def bump(args):
    if HOLD:
        time.sleep(HOLD)
    with open(counter, "a+") as f:
        f.seek(0)
        value = int(f.read() or 0) + args["by"]
        f.seek(0); f.truncate(); f.write(str(value)); f.flush(); os.fsync(f.fileno())
    crash_if("after_effect")
    return {"counter": value}


engine = create_engine(f"sqlite:///{db}", connect_args={"timeout": 30})
repo = GCWRepository(engine, tenant_id=tenant)
repo.create_schema()
runtime = GCWRuntime(repo, planner_model=Planner(), approval_gate=InMemoryApprovalGate(), _hydrate=True)
runtime.tools.register(ToolSpec(name="bump", description="increment the fake counter",
                                risk=Risk.REVERSIBLE), bump)

orig_dispatch = ToolDispatcher.dispatch
async def dispatch(self, *a, **k):
    crash_if("before_reserve")
    return await orig_dispatch(self, *a, **k)
ToolDispatcher.dispatch = dispatch

ledger = getattr(runtime.dispatcher, "ledger", None)
if ledger is not None:
    for name, point, before in (("reserve", "after_reserve", False), ("mark_invoking", "before_effect", False),
                                ("complete", "before_receipt", True)):
        original = getattr(ledger, name)
        def wrap(original=original, point=point, before=before):
            def inner(*a, **k):
                if before: crash_if(point)
                out = original(*a, **k)
                if not before: crash_if(point)
                return out
            return inner
        setattr(ledger, name, wrap())

orig_persist = runtime._persist_context
state = {"n": 0}
def persist(context):
    done = [n for n in context.plan if n.state == TaskState.SUCCEEDED]
    if done and CRASH == "before_final_state":
        die()
    return orig_persist(context)
runtime._persist_context = persist

if cmd == "submit":
    ctx = runtime.submit_goal("bump the counter exactly once", run_immediately=False)
    print(json.dumps({"task_id": ctx.id}))
elif cmd == "run":
    ctx = runtime.run_task(sys.argv[5])
    print(json.dumps({"state": ctx.state.value,
                      "nodes": [[n.state.value, n.result_summary] for n in ctx.plan]}))
elif cmd == "reconcile":
    ctx = runtime.reconcile_effect(sys.argv[5], sys.argv[6], outcome=sys.argv[7], actor="op@test", note="checked provider")
    print(json.dumps({"state": ctx.state.value, "nodes": [[n.state.value, n.result_summary] for n in ctx.plan]}))
elif cmd == "inspect":
    ctx = runtime.get_task(sys.argv[5])
    print(json.dumps({"state": ctx.state.value, "node_id": ctx.plan[0].id,
                      "nodes": [[n.state.value, n.result_summary] for n in ctx.plan],
                      "ledger": [[r["state"], r["attempt"]] for r in runtime.ledger.list()] if hasattr(runtime, "ledger") else None}))
