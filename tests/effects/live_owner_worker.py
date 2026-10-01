"""Subprocess worker for the live-owner lease-expiry regression test.

Reserves and marks a non-idempotent effect INVOKING with a SHORT lease, then
the handler blocks the event loop synchronously (time.sleep) well past that
lease, then performs the external effect. asyncio.wait_for cannot cancel a
loop-blocking handler, so the invocation outlives its lease while the owner
process is alive. A correct ledger must never reconcile or retake it.

usage: live_owner_worker.py <db> <counter> <tenant> <entered_marker>
env: EFFECT_LEASE (seconds, default 0.3), EFFECT_HOLD (seconds, default 2.5)
"""
import asyncio, json, os, sys, time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

import sqlalchemy as sa

from app.modules.m20_general_cognitive_worker.effect_ledger import EffectLedger
from app.modules.m20_general_cognitive_worker.safety import SafetyGate
from app.modules.m20_general_cognitive_worker.schemas import Risk, ToolSpec
from app.modules.m20_general_cognitive_worker.tools import ToolDispatcher, ToolRegistry

db, counter, tenant, entered = sys.argv[1:5]
LEASE = float(os.environ.get("EFFECT_LEASE", "0.3"))
HOLD = float(os.environ.get("EFFECT_HOLD", "2.5"))

engine = sa.create_engine(f"sqlite:///{db}", connect_args={"timeout": 30})
ledger = EffectLedger(engine, tenant)


async def handler(args):
    Path(entered).write_text(str(os.getpid()))
    # Synchronous block: the event loop is stuck, so asyncio.wait_for CANNOT
    # cancel this handler at timeout. It outlives its lease while still live.
    time.sleep(HOLD)
    with open(counter, "a+") as f:
        f.seek(0)
        value = int(f.read() or 0) + 1
        f.seek(0)
        f.truncate()
        f.write(str(value))
        f.flush()
        os.fsync(f.fileno())
    return {"counter": value}


orig_reserve = ledger.reserve


def reserve_short_lease(**kw):
    kw["lease_seconds"] = LEASE
    return orig_reserve(**kw)


ledger.reserve = reserve_short_lease

registry = ToolRegistry()
registry.register(
    ToolSpec(name="act", description="external write", risk=Risk.REVERSIBLE,
             timeout_seconds=30, max_retries=5),
    handler,
)


async def main():
    try:
        record = await ToolDispatcher(registry, SafetyGate(), ledger).dispatch(
            "act", {}, task_id="T", node_id="N")
        print(json.dumps({"success": record.succeeded}))
    except BaseException as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}))
        sys.exit(2)


asyncio.run(main())
