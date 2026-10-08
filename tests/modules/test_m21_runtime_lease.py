"""Slice 3a: lease renewal at step boundaries, settle fenced on expiry, per-call timeout.

Protection tests are marked PROTECTION; new-capability tests are marked NEW.
Limits: step-boundary renewal only (no background heartbeat); SQLite only; injected clock, no real
concurrency stress; a timed-out SYNC tool body keeps running in its thread; no effect reconciliation (3b).
"""
import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel

from app.modules.m21_claire.runtime.engine import Engine
from app.modules.m21_claire.runtime.goals import GoalStore
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry, Tool
from app.modules.m21_claire.runtime.types import AgentDecision, ToolCall, ToolRisk
from app.modules.m21_claire.runtime.worker import Worker

CRIT = [{"kind": "tool_receipt", "tool": "lookup", "min_count": 1}]
RAN: list[str] = []


class A(BaseModel):
    key: str = "k"


class Lookup(Tool):
    name, risk, arguments_model = "lookup", ToolRisk.READ, A
    def run(self, a):
        RAN.append("lookup"); return {"v": 1}


class SlowSync(Tool):
    name, risk, arguments_model = "slow_sync", ToolRisk.READ, A
    def run(self, a):
        time.sleep(0.4); return {"v": 1}


class SlowAsync(Tool):
    name, risk, arguments_model = "slow_async", ToolRisk.READ, A
    async def run(self, a):
        await asyncio.sleep(0.4); return {"v": 1}


def call(name): return AgentDecision(tool_call=ToolCall(name=name, arguments={}))
def final(): return AgentDecision(final="done")
def run(c): return asyncio.run(c)


@pytest.fixture(autouse=True)
def _clear():
    RAN.clear()


@pytest.fixture
def clk():
    return [datetime(2026, 10, 8, tzinfo=timezone.utc)]


def mkstore(tmp_path, clk, lease=10):
    return GoalStore(f"sqlite:///{tmp_path}/l.db", clock=lambda: clk[0], lease_seconds=lease, create_schema=True)


def reg(*tools, timeout=5.0):
    r = ReadOnlyToolRegistry(call_timeout=timeout)
    for t in tools: r.register(t)
    return r


class Ticking:
    """Scripted model that advances the injected clock by `dt` each time it is asked, then runs `hook`."""
    def __init__(self, clk, dt, decisions, hook=None):
        self.clk, self.dt, self.d, self.hook, self.n = clk, dt, list(decisions), hook, 0
    async def decide(self, messages):
        self.n += 1
        self.clk[0] += timedelta(seconds=self.dt)
        if self.hook: self.hook(self.n)
        return self.d.pop(0)


def worker(store, model, tools, wid="w1"):
    return Worker(store, lambda c: Engine(model, tools, max_steps=c.max_steps), wid)


# ---- PROTECTION ---------------------------------------------------------------------------------

def test_PROTECTION_a_without_renewal_a_second_worker_takes_over_and_first_cannot_settle(tmp_path, clk):
    s = mkstore(tmp_path, clk); s.create("t1", "a1", "p", CRIT, 3)
    c1 = s.claim("w1")
    clk[0] += timedelta(seconds=60)
    c2 = s.claim("w2")
    assert c2 is not None and c2.lease_token != c1.lease_token
    assert s.settle(c1, "completed", blocker=None, report={}, verdict=None) is False
    assert s.renew(c1) is False
    assert s.settle(c2, "blocked", blocker="x", report={}, verdict=None) is True
    s.close()


def test_PROTECTION_b_renewal_across_steps_keeps_the_lease_past_the_original_expiry(tmp_path, clk):
    s = mkstore(tmp_path, clk, lease=10); gid = s.create("t1", "a1", "p", CRIT, 8)
    seen = {}
    def hook(n):
        seen[n] = s.claim("w2")  # a competing worker polls at every step; must never win
    m = Ticking(clk, 6, [call("lookup"), call("lookup"), call("lookup"), call("lookup"), final()], hook)
    run(worker(s, m, reg(Lookup()), "w1").run_once())
    assert clk[0] - datetime(2026, 10, 8, tzinfo=timezone.utc) == timedelta(seconds=30)  # 3x the lease elapsed
    assert all(v is None for v in seen.values())
    assert s.get("t1", "a1", gid)["status"] == "completed"
    s.close()


def test_PROTECTION_c_lease_lost_before_dispatch_runs_no_tool_and_settles_nothing(tmp_path, clk):
    s = mkstore(tmp_path, clk, lease=10); gid = s.create("t1", "a1", "p", CRIT, 5)
    # step 1 model call takes longer than the lease; the engine must not dispatch the tool it asked for
    m = Ticking(clk, 60, [call("lookup"), final()])
    w = worker(s, m, reg(Lookup()), "w1")
    run(w.run_once())
    assert RAN == [] and w.last_outcome == "lease_lost"
    assert s.get("t1", "a1", gid)["status"] == "running"  # still the expired claim; not settled by the stale worker
    c2 = s.claim("w2")
    assert c2 is not None  # a new worker can take it over
    s.close()


@pytest.mark.parametrize("how", ["expired", "replaced", "settled"])
def test_PROTECTION_c3_renew_is_false_once_the_lease_is_gone(tmp_path, clk, how):
    s = mkstore(tmp_path, clk); s.create("t1", "a1", "p", CRIT, 3)
    c = s.claim("w1")
    assert s.renew(c) is True
    if how == "expired": clk[0] += timedelta(seconds=11)
    elif how == "replaced": clk[0] += timedelta(seconds=11); assert s.claim("w2") is not None
    else: assert s.settle(c, "blocked", blocker="x", report={}, verdict=None)
    assert s.renew(c) is False
    s.close()


def test_PROTECTION_d_settle_after_expiry_with_matching_token_is_refused(tmp_path, clk):
    s = mkstore(tmp_path, clk); gid = s.create("t1", "a1", "p", CRIT, 3)
    c = s.claim("w1")
    clk[0] += timedelta(seconds=11)  # expired; nobody re-claimed; token still matches
    assert s.settle(c, "completed", blocker=None, report={}, verdict=None) is False
    assert s.get("t1", "a1", gid)["status"] == "running"
    s.close()


# ---- NEW CAPABILITY -----------------------------------------------------------------------------

def test_NEW_renew_extends_the_expiry_from_now(tmp_path, clk):
    s = mkstore(tmp_path, clk, lease=10); s.create("t1", "a1", "p", CRIT, 3)
    c = s.claim("w1")
    clk[0] += timedelta(seconds=8)
    assert s.renew(c) is True
    clk[0] += timedelta(seconds=8)  # 16s after claim, 8s after renew: still ours
    assert s.claim("w2") is None and s.settle(c, "blocked", blocker="x", report={}, verdict=None) is True
    s.close()


@pytest.mark.parametrize("tool", [SlowSync, SlowAsync])
def test_NEW_call_timeout_gives_a_timed_out_receipt_without_retry(tool):
    r = reg(tool(), timeout=0.05)
    rec = run(r.execute(1, tool.name, {}))
    assert rec.ok is False and rec.error == "timed_out"
    rep = run(Engine(Ticking([datetime(2026, 10, 8, tzinfo=timezone.utc)], 0, [call(tool.name), final()]), r).run("g"))
    assert [x.error for x in rep.receipts] == ["timed_out"] and rep.stop_reason == "final"


def test_NEW_timeout_not_below_lease_refuses_to_run(tmp_path, clk):
    s = mkstore(tmp_path, clk, lease=10); gid = s.create("t1", "a1", "p", CRIT, 3)
    w = worker(s, Ticking(clk, 0, [call("lookup"), final()]), reg(Lookup(), timeout=10.0), "w1")
    run(w.run_once())
    got = s.get("t1", "a1", gid)
    assert RAN == [] and got["status"] == "blocked" and got["blocker"] == "timeout_not_below_lease"
    s.close()


@pytest.mark.parametrize("bad", [0, -1, True, None, "5", 3601, float("nan")])
def test_NEW_call_timeout_must_be_a_positive_bounded_number(bad):
    with pytest.raises(ValueError):
        ReadOnlyToolRegistry(call_timeout=bad)


# ---- reviewer repair: last_outcome must reflect what settle actually did -------------------------

class ModelDownAfterTick:
    def __init__(self, clk, dt): self.clk, self.dt = clk, dt
    async def decide(self, messages):
        from app.modules.m21_claire.runtime.engine import ModelUnavailable
        self.clk[0] += timedelta(seconds=self.dt); raise ModelUnavailable()


def test_PROTECTION_e_final_after_expiry_reports_lease_lost_and_leaves_goal_running(tmp_path, clk):
    s = mkstore(tmp_path, clk, lease=10); gid = s.create("t1", "a1", "p", CRIT, 3)
    w = worker(s, Ticking(clk, 11, [final()]), reg(Lookup(), timeout=1), "w1")
    run(w.run_once())
    assert w.last_outcome == "lease_lost" and s.get("t1", "a1", gid)["status"] == "running"
    s.close()


def test_PROTECTION_e2_model_error_after_expiry_reports_lease_lost(tmp_path, clk):
    s = mkstore(tmp_path, clk, lease=10); gid = s.create("t1", "a1", "p", CRIT, 3)
    w = worker(s, ModelDownAfterTick(clk, 11), reg(Lookup(), timeout=1), "w1")
    run(w.run_once())
    assert w.last_outcome == "lease_lost" and s.get("t1", "a1", gid)["status"] == "running"
    s.close()


def test_PROTECTION_e3_replaced_worker_final_reports_lease_lost_and_does_not_touch_the_new_owner(tmp_path, clk):
    s = mkstore(tmp_path, clk, lease=10); gid = s.create("t1", "a1", "p", CRIT, 3)
    taken = {}
    def hook(n):  # while w1's model call is in flight, the lease runs out and w2 claims the goal
        taken["c2"] = s.claim("w2")
    w = worker(s, Ticking(clk, 11, [final()], hook), reg(Lookup(), timeout=1), "w1")
    run(w.run_once())
    assert taken["c2"] is not None
    assert w.last_outcome == "lease_lost" and s.get("t1", "a1", gid)["status"] == "running"
    assert s.renew(taken["c2"]) is True  # the new owner's lease is intact
    s.close()


def test_PROTECTION_e4_timeout_guard_branch_reports_lease_lost_when_settle_is_refused(tmp_path, clk):
    s = mkstore(tmp_path, clk, lease=10); gid = s.create("t1", "a1", "p", CRIT, 3)
    def factory(c):
        clk[0] += timedelta(seconds=11)  # lease expires before the guard's settle
        return Engine(Ticking(clk, 0, [final()]), reg(Lookup(), timeout=10.0), max_steps=3)
    w = Worker(s, factory, "w1")
    run(w.run_once())
    assert w.last_outcome == "lease_lost" and s.get("t1", "a1", gid)["status"] == "running"
    s.close()


@pytest.mark.parametrize("decisions,status", [([call("lookup"), final()], "completed"), ([final()], "not_accepted")])
def test_PROTECTION_e5_outcome_equals_the_accepted_status_on_the_normal_path(tmp_path, clk, decisions, status):
    s = mkstore(tmp_path, clk, lease=10); gid = s.create("t1", "a1", "p", CRIT, 3)
    w = worker(s, Ticking(clk, 1, decisions), reg(Lookup()), "w1")
    run(w.run_once())
    assert w.last_outcome == status == s.get("t1", "a1", gid)["status"]
    s.close()
