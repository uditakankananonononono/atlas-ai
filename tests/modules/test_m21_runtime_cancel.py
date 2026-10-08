# ruff: noqa: F811
"""Slice 6: owner cancel of a RUNNING goal, delivered through the worker, plus advisory replan evidence.

Labels: PROTECTION_* (a hole that must stay closed), NEW_* (new capability).
Limits: SQLite only; scripted stub model only; cancel is polled (cancel_poll_seconds), not pushed; a sync tool thread cannot be
killed, so an interrupted non-read effect is left unknown by design (cancelled + blocker effect_unknown), never abandoned;
cancel is owner-only (no separation of duties); awaiting_review goals still cannot be cancelled.
"""
import asyncio
import time

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.pool import StaticPool

from app.modules.m21_claire.runtime.engine import Engine
from app.modules.m21_claire.runtime.types import AgentDecision, ToolRisk
from app.modules.m21_claire.runtime.worker import Worker
from tests.modules.test_m21_runtime_effects import (  # noqa: F401  (fixtures + helpers)
    CRIT, WORLD, _clear, call, clk, final, goal, live, make, reg, run, states, store, Script,
)

POLL = 0.02


def worker(store, model, tools, wid="w1"):
    return Worker(store, lambda c: Engine(model, tools, max_steps=c.max_steps, cancel_poll_seconds=POLL), wid)


class Slow:
    """Model whose decide blocks (cancellable) until released."""
    def __init__(self, then=None): self.then = then or []
    async def decide(self, m):
        await asyncio.sleep(30)
        return self.then.pop(0)


async def run_and_cancel(store, w, gid, delay=0.15, tenant="t1", actor="a1"):
    task = asyncio.ensure_future(w.run_once())
    await asyncio.sleep(delay)
    out = store.cancel(tenant, actor, gid)
    t0 = time.monotonic()
    await asyncio.wait_for(task, 5)
    return out, time.monotonic() - t0


# ---- PROTECTION -----------------------------------------------------------------------------------

def test_PROTECTION_cancel_during_model_call_stops_it_and_dispatches_nothing(store):
    t = make(); r = reg(store, t); gid = goal(store)
    w = worker(store, Slow([call("write_row", target="a")]), r)
    out, took = run(run_and_cancel(store, w, gid))
    got = store.get("t1", "a1", gid)
    assert out == "cancel_requested" and took < 2
    assert got["status"] == "cancelled" and got["blocker"] is None and got["report"]["stop_reason"] == "cancelled"
    assert WORLD == {} and states(store, gid) == []


def test_PROTECTION_cancel_during_read_tool_stops_waiting_for_it(store):
    t = make("slow_read", risk=ToolRisk.READ, delay=1.5)
    r = reg(store, t); gid = goal(store)
    w = worker(store, Script(call("slow_read")), r)
    out, took = run(run_and_cancel(store, w, gid))
    got = store.get("t1", "a1", gid)
    assert out == "cancel_requested" and took < 1.2
    assert got["status"] == "cancelled" and got["report"]["receipts"] == []


def test_PROTECTION_cancel_during_write_leaves_the_effect_unknown_never_abandoned(store):
    t = make(delay=1.0); r = reg(store, t); gid = goal(store)
    w = worker(store, Script(call("write_row", target="a")), r)
    out, took = run(run_and_cancel(store, w, gid, delay=0.3))
    got = store.get("t1", "a1", gid)
    assert out == "cancel_requested" and took < 0.9
    assert got["status"] == "cancelled" and got["blocker"] == "effect_unknown"   # never looks cleanly cancelled
    assert states(store, gid) == ["intent"]                                      # not failed/abandoned, so never retried
    effs = store.list_effects("t1", "a1", gid)
    assert store.resolve_effect(gid, effs[0]["id"], "committed", tenant_id="t1", resolver_id="ap1") == "resolved"
    time.sleep(1.0)  # let the orphan thread finish so it cannot leak into later tests


def test_PROTECTION_cancel_with_lost_lease_settles_nothing(store, clk):
    from datetime import timedelta
    r = reg(store, make()); gid = goal(store)
    w = worker(store, Slow(), r)

    async def go():
        task = asyncio.ensure_future(w.run_once())
        await asyncio.sleep(0.1)
        clk[0] += timedelta(seconds=500)           # lease expires while the model is blocked
        store.cancel("t1", "a1", gid)
        await asyncio.wait_for(task, 5)
    run(go())
    assert w.last_outcome == "lease_lost"
    assert store.get("t1", "a1", gid)["status"] == "running"


def test_PROTECTION_goal_that_finishes_first_keeps_its_real_outcome(store):
    t = make(); r = reg(store, t); gid = goal(store)

    class Model:
        n = 0
        async def decide(self, m):
            self.n += 1
            if self.n == 1: return call("write_row", target="a")
            store.cancel("t1", "a1", gid)           # owner asks just before the model answers
            return final()
    run(worker(store, Model(), r).run_once())
    got = store.get("t1", "a1", gid)
    assert got["status"] == "completed" and got["report"]["cancel_requested"] is True
    assert WORLD["write_row:a"] == 1


def test_PROTECTION_cancel_is_owner_and_tenant_scoped_and_state_checked(store):
    gid = goal(store)
    assert store.cancel("t2", "a1", gid) == "not_found" and store.cancel("t1", "a2", gid) == "not_found"
    p = live(store, gid)
    assert store.cancel("t1", "a2", gid) == "not_found"
    assert store.cancel("t1", "a1", gid) == "cancel_requested"
    assert store.get("t1", "a1", gid)["status"] == "running"       # a request alone never changes the status
    from app.modules.m21_claire.runtime.goals import Claim
    cl = Claim(gid, "t1", "a1", "p", CRIT, 6, p.lease_token)
    assert store.cancel_requested(cl) is True
    assert store.cancel_requested(Claim(gid, "t1", "a1", "p", CRIT, 6, "other")) is False
    assert store.settle(cl, "completed", blocker=None, report={}, verdict=None) is True
    assert store.cancel("t1", "a1", gid) == "not_cancellable"      # terminal
    assert store.cancel_requested(cl) is False                     # flag cleared on settle


@pytest.mark.parametrize("bad", [0, 0.0, -1, float("nan"), True, "1", 99])
def test_PROTECTION_cancel_poll_config_is_strict(bad):
    with pytest.raises(ValueError):
        Engine(None, None, cancel_poll_seconds=bad)


def test_PROTECTION_queued_cancel_and_second_cancel_unchanged(store):
    gid = goal(store)
    assert store.cancel("t1", "a1", gid) == "cancelled" and store.cancel("t1", "a1", gid) == "not_cancellable"


# ---- NEW ----------------------------------------------------------------------------------------

def test_NEW_route_returns_202_for_running_goal_and_409_for_terminal(store):
    from fastapi.testclient import TestClient
    from app.auth.context import TenantContext, require_tenant
    from app.main import app
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t1", actor_id="a1", roles=())
    try:
        c = TestClient(app)
        gid = goal(store); live(store, gid)
        res = c.post(f"/api/v1/claire/runtime/goals/{gid}/cancel")
        assert res.status_code == 202 and res.json()["status"] == "running" and res.json()["cancel_requested"] is True
        gid2 = goal(store); store.cancel("t1", "a1", gid2)
        assert c.post(f"/api/v1/claire/runtime/goals/{gid2}/cancel").status_code == 409
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def test_NEW_replans_are_recorded_as_bounded_advisory_evidence_never_acceptance(store):
    r = reg(store, make()); gid = goal(store)
    long = "x" * 900
    model = Script(AgentDecision(replan={"reason": "r", "steps": [long, "second"]}), final())
    run(worker(store, model, r).run_once())
    got = store.get("t1", "a1", gid)
    rec = got["report"]["replans"]
    assert len(rec) == 1 and rec[0]["revision"] == 1 and rec[0]["advisory"] is True
    assert len(rec[0]["steps"][0]) == 500 and rec[0]["steps"][1] == "second"
    assert got["status"] == "not_accepted"       # a replan never satisfies the tool_receipt criterion


def test_NEW_replan_records_stop_at_the_limit(store):
    r = reg(store, make()); gid = goal(store)
    rp = lambda: AgentDecision(replan={"reason": "r", "steps": ["s"]})  # noqa: E731
    run(worker(store, Script(rp(), rp(), rp(), rp()), r).run_once())
    got = store.get("t1", "a1", gid)
    assert got["status"] == "exhausted" and len(got["report"]["replans"]) == 3


def test_NEW_migration_adds_column_and_is_idempotent():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("mig", pathlib.Path("migrations/versions/20261008_m21_runtime_cancel.py"))
    mig = importlib.util.module_from_spec(spec); spec.loader.exec_module(mig)
    eng = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with eng.begin() as c:
        c.execute(text("CREATE TABLE claire_runtime_goals (id VARCHAR(36) PRIMARY KEY)"))
        with Operations.context(MigrationContext.configure(c)):
            mig.upgrade(); mig.upgrade()
            assert "cancel_requested_at" in [x["name"] for x in sa_inspect(c).get_columns("claire_runtime_goals")]
            c.execute(text("INSERT INTO claire_runtime_goals (id, cancel_requested_at) VALUES ('g','x')"))
            with pytest.raises(RuntimeError):
                mig.downgrade()          # never drops a column that holds cancel requests
