# ruff: noqa: F811
"""Slice 8: the model call is bounded below the lease (no heartbeat on purpose).

A background heartbeat is deliberately NOT built: it would keep a hung model's lease alive for ever and turn a hang into a
stuck-running goal. Instead every single await is bounded below the lease and the lease is renewed at each step boundary.
Labels: PROTECTION_* (must stay closed), NEW_*. Limits: SQLite, scripted stub model, real-time sleeps, cooperative cancellation.
"""
import asyncio
import time

import pytest

from app.modules.m21_claire.runtime.engine import Engine, ModelUnavailable
from app.modules.m21_claire.runtime.goals import GoalStore
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry
from app.modules.m21_claire.runtime.types import ToolRisk
from app.modules.m21_claire.runtime.worker import Worker
from tests.modules.test_m21_runtime_effects import CRIT, Script, _clear, call, final, make, run  # noqa: F401

READ_CRIT = [{"kind": "tool_receipt", "tool": "slow_read", "min_count": 1}]


def mk(tmp_path, lease=1):
    return GoalStore(f"sqlite:///{tmp_path}/m.db", lease_seconds=lease, create_schema=True)


def rd(): return make("slow_read", risk=ToolRisk.READ)


def tools(*t, timeout=0.5):
    r = ReadOnlyToolRegistry(call_timeout=timeout)
    for x in t:
        r.register(x)
    return r


class Hung:
    async def decide(self, m):
        await asyncio.sleep(30)


def test_PROTECTION_hung_model_becomes_blocked_model_unavailable_within_the_timeout(tmp_path):
    s = mk(tmp_path, lease=10); gid = s.create("t", "a", "p", READ_CRIT, 3)
    w = Worker(s, lambda c: Engine(Hung(), tools(rd(), timeout=1), max_steps=3, model_timeout_seconds=0.3), "w1")
    t0 = time.monotonic(); run(w.run_once())
    got = s.get("t", "a", gid)
    assert time.monotonic() - t0 < 2 and got["status"] == "blocked" and got["blocker"] == "model_unavailable"
    assert got["report"]["receipts"] == []


def test_PROTECTION_default_model_timeout_is_derived_from_the_lease(tmp_path):
    s = mk(tmp_path, lease=1); gid = s.create("t", "a", "p", READ_CRIT, 3)    # derived: min(60, lease/2) = 0.5s
    w = Worker(s, lambda c: Engine(Hung(), tools(rd()), max_steps=3), "w1")
    t0 = time.monotonic(); run(w.run_once())
    assert time.monotonic() - t0 < 2.5 and s.get("t", "a", gid)["blocker"] == "model_unavailable"


def test_PROTECTION_model_timeout_not_below_lease_refuses_to_run(tmp_path):
    s = mk(tmp_path, lease=2); gid = s.create("t", "a", "p", READ_CRIT, 3)
    w = Worker(s, lambda c: Engine(Hung(), tools(rd()), max_steps=3, model_timeout_seconds=2), "w1")
    run(w.run_once())
    got = s.get("t", "a", gid)
    assert got["status"] == "blocked" and got["blocker"] == "timeout_not_below_lease"


@pytest.mark.parametrize("bad", [0, -1, 0.01, float("nan"), float("inf"), True, "5", 99999])
def test_PROTECTION_model_timeout_config_is_strict(bad):
    with pytest.raises(ValueError):
        Engine(None, None, model_timeout_seconds=bad)


def test_PROTECTION_cancel_still_wins_during_a_model_call(tmp_path):
    s = mk(tmp_path, lease=10); gid = s.create("t", "a", "p", READ_CRIT, 3)
    w = Worker(s, lambda c: Engine(Hung(), tools(rd(), timeout=1), max_steps=3, model_timeout_seconds=8, cancel_poll_seconds=0.02), "w1")

    async def go():
        task = asyncio.ensure_future(w.run_once()); await asyncio.sleep(0.2)
        s.cancel("t", "a", gid)
        await asyncio.wait_for(task, 3)
    run(go())
    assert s.get("t", "a", gid)["status"] == "cancelled"


def test_PROTECTION_model_unavailable_still_blocks_regression(tmp_path):
    class Down:
        async def decide(self, m): raise ModelUnavailable()
    s = mk(tmp_path, lease=10); gid = s.create("t", "a", "p", READ_CRIT, 3)
    run(Worker(s, lambda c: Engine(Down(), tools(rd(), timeout=1), max_steps=3), "w1").run_once())
    assert s.get("t", "a", gid)["blocker"] == "model_unavailable"


def test_NEW_step_longer_than_the_lease_survives_and_is_never_double_claimed(tmp_path):
    """lease 1s; model 0.4s + read tool 0.4s + model 0.4s = 1.2s total. Every await is under the lease and the lease is renewed
    at each boundary, so a second worker never claims the goal and the first one completes it."""
    s = mk(tmp_path, lease=1)
    slow = make("slow_read", risk=ToolRisk.READ, delay=0.4)

    class Model:
        n = 0
        async def decide(self, m):
            await asyncio.sleep(0.4); self.n += 1
            return call("slow_read", target="a") if self.n == 1 else final()
    gid = s.create("t", "a", "p", READ_CRIT, 4)
    w1 = Worker(s, lambda c: Engine(Model(), tools(slow, timeout=0.9), max_steps=4, model_timeout_seconds=0.6), "w1")
    w2 = Worker(s, lambda c: Engine(Model(), tools(slow, timeout=0.9), max_steps=4, model_timeout_seconds=0.6), "w2")

    async def go():
        t1 = asyncio.ensure_future(w1.run_once()); await asyncio.sleep(1.1)
        second = await w2.run_once()                    # the lease would have expired at 1.0s without boundary renewals
        await t1
        return second
    assert run(go()) is None
    assert s.get("t", "a", gid)["status"] == "completed" and w1.last_outcome == "completed"
