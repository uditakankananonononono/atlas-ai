"""Slice 16: the m20 LEGACY DeliberativeLoop binds each EXTERNAL/IRREVERSIBLE step to a real Module 0 approval (tenant, run, step, digest), consumes it once, and never
retries an uncertain effect. Real Module 0 on a file SQLite DB with an injected clock; fake stores only where a test says it proves fail-closed.

SCOPE LIMITS (verbatim): covers ONLY m20/legacy_service.py Service/DeliberativeLoop (what Claire's realize path uses), NOT the newer CognitiveWorkerService. No role or
designation authorization: approved_by != actor is a structural guard on a string and cannot prove who the approver is or which tenant they belong to (m00 decide path
and actor binding stay open). Effect class is still whatever the integrator registered (a send tool registered READ runs ungated; characterized in the audit file).
Outcome-unknown is in-memory run state, not a durable journal. SQLite does not prove Postgres row-lock behaviour: here at-most-one rests on the UNIQUE constraints; under
contention a DB error can surface (such a step is blocked with a fixed code and nothing is dispatched). Approved validity 900s inclusive; pending TTL 24h.
Labels: NEW = failed/absent on base 36f9f3ca. CONVERTED = old behaviour test with changed meaning. PROTECTION = holds on base and now.
"""
import asyncio
import copy
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalRequest, ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalBroadcaster, Service as M00
from app.modules.m20_general_cognitive_worker.legacy_service import APPROVED_VALIDITY_SECONDS, Risk, Service, State, Tool
from app.modules.m21_claire.service import Service as ClaireService

T0 = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
BUDGET = {"seconds": 5, "tokens": 5, "money": 0}


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


class Store:
    def __init__(self, tmp_path, clock):
        eng = create_engine(f"sqlite:///{tmp_path}/m00.db", connect_args={"check_same_thread": False, "timeout": 30})
        Base.metadata.create_all(eng)
        self.m00 = M00(session_factory=sessionmaker(bind=eng, expire_on_commit=False), broadcaster=ApprovalBroadcaster(), clock=clock)

    def put(self, item, *, user_id=None, ttl_seconds=None):
        tenant = user_id or str(item.payload.get("tenant_id") or "default")
        v = self.m00.submit(module_id=item.module_id, action_type=item.action_type, payload=item.payload, user_id=tenant, ttl_seconds=ttl_seconds)
        return ApprovalRequest(id=v["id"], module_id=v["module_id"], action_type=v["action_type"], payload=v["payload"], status=v["status"])

    def list(self):
        return []

    def full_view(self, i):
        return self.m00.get(i)

    def consume_effect(self, i, **kw):
        return self.m00.consume_effect(i, **kw)


class Handler:
    def __init__(self):
        self.calls = []
        self.fail = None
        self.sleep = 0

    async def __call__(self, args, key):
        self.calls.append((copy.deepcopy(args), key))
        if self.sleep:
            await asyncio.sleep(self.sleep)
        if self.fail:
            raise self.fail
        return {"ok": True}


def make(tmp_path, steps=None, tool_risk=Risk.EXTERNAL, timeout=60):
    clock = Clock()
    store = Store(tmp_path, clock)
    steps = steps or [{"id": "s1", "title": "send", "tool": "sender", "arguments": {"to": "a"}, "risk": "external"}]

    async def model(kind, data):
        return {"steps": steps}
    svc = Service(store, model)
    h = Handler()
    svc.tools.register(Tool("sender", "d", tool_risk, set(), h, timeout=timeout))
    return type("E", (), dict(clock=clock, store=store, svc=svc, h=h))


def start(e, tenant="t1", actor="u1"):
    return asyncio.run(e.svc.start("goal", {}, BUDGET, tenant_id=tenant, actor_id=actor))


def again(e, run):
    return asyncio.run(e.svc.loop.execute(run))


def approve(e, run, by="approver-1"):
    e.store.m00.decide(run.plan.steps[0].approval_id, ApprovalStatus.APPROVED, by)


def test_NEW_filing_binds_tenant_run_step_digest_and_pending_ttl_and_never_dispatches(tmp_path):
    e = make(tmp_path)
    run = start(e)
    st = run.plan.steps[0]
    v = e.store.full_view(st.approval_id)
    assert st.state == State.WAITING_APPROVAL and e.h.calls == []
    assert v["user_id"] == "t1" and v["action_type"] == "cognitive:sender" and v["expires_at"] == T0 + timedelta(hours=24)
    p = v["payload"]
    assert p["tenant_id"] == "t1" and p["run_id"] == run.id and p["step_id"] == "s1" and len(p["step_digest"]) == 64


def test_NEW_exact_approval_dispatches_once_and_a_rerun_never_dispatches_again(tmp_path):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    again(e, run)
    again(e, run)
    assert run.plan.steps[0].state == State.SUCCEEDED and len(e.h.calls) == 1 and run.plan.steps[0].error is None


@pytest.mark.parametrize("tenant,actor", [(None, "u1"), ("t1", None), ("", "u1"), ("t1", "   "), (None, None)])
def test_NEW_missing_or_blank_identity_blocks_and_files_nothing_under_default(tmp_path, tenant, actor):
    e = make(tmp_path)
    run = start(e, tenant, actor)
    assert run.plan.steps[0].state == State.BLOCKED and run.plan.steps[0].error == "binding_unavailable"
    assert e.store.m00.list() == [] and e.h.calls == []


def test_NEW_store_without_the_binding_methods_fails_closed(tmp_path):
    e = make(tmp_path)

    class Bare:
        def put(self, item, **kw):
            raise AssertionError("must not file")
    e.svc.loop.approvals = Bare()
    del Bare.put
    run = start(e)
    assert run.plan.steps[0].error == "binding_unavailable" and e.h.calls == []


def test_NEW_pending_waits_and_denied_expired_block_with_distinct_codes(tmp_path):
    e = make(tmp_path)
    run = start(e)
    again(e, run)
    assert run.plan.steps[0].state == State.WAITING_APPROVAL                  # pending approvals WAIT
    e.store.m00.decide(run.plan.steps[0].approval_id, ApprovalStatus.DENIED, "approver-1")
    again(e, run)
    assert run.plan.steps[0].error == "approval_denied"
    e2 = make(tmp_path / "x") if (tmp_path / "x").mkdir() is None else None
    run2 = start(e2)
    e2.clock.now = T0 + timedelta(hours=24, seconds=1)
    again(e2, run2)
    assert run2.plan.steps[0].error == "approval_expired" and e.h.calls == [] and e2.h.calls == []


@pytest.mark.parametrize("by", ["u1", "  u1 ", "   ", ""])
def test_NEW_self_approved_and_blank_approver_are_refused_without_dispatch(tmp_path, by):
    e = make(tmp_path)
    run = start(e)
    approve(e, run, by=by)
    again(e, run)
    assert run.plan.steps[0].error == "approval_mismatch" and e.h.calls == []


def test_NEW_mutated_arguments_or_tool_or_risk_after_approval_is_refused_and_does_not_consume(tmp_path):
    e = make(tmp_path)
    read_h = Handler()
    e.svc.tools.register(Tool("reader2", "d", Risk.READ, set(), read_h))
    run = start(e)
    approve(e, run)
    st = run.plan.steps[0]
    st.arguments = {"to": "attacker"}
    again(e, run)
    assert st.error == "approval_mismatch" and e.h.calls == []
    st.arguments = {"to": "a"}
    st.state = State.WAITING_APPROVAL
    st.tool, st.risk = "reader2", Risk.READ                                 # approved EXTERNAL -> READ with a newly registered matching READ tool
    again(e, run)
    assert st.error == "approval_mismatch" and read_h.calls == [] and e.h.calls == []
    st.tool, st.risk, st.state = "sender", Risk.EXTERNAL, State.WAITING_APPROVAL
    again(e, run)                                                           # none of the refusals consumed the approval
    assert st.state == State.SUCCEEDED and len(e.h.calls) == 1 and read_h.calls == []


def test_NEW_a_step_once_filed_stays_gated_even_when_its_risk_is_mutated_to_read(tmp_path):
    e = make(tmp_path)
    run = start(e)
    st = run.plan.steps[0]
    st.risk = Risk.READ                                                     # no approval yet decided: must NOT run as a plain READ step
    again(e, run)
    assert e.h.calls == [] and st.state in (State.BLOCKED, State.WAITING_APPROVAL, State.PENDING, State.FAILED)


def test_NEW_stale_boundary_future_and_fresh_clock_inside_the_consume(tmp_path):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    st = run.plan.steps[0]
    e.clock.now = T0 + timedelta(seconds=APPROVED_VALIDITY_SECONDS, microseconds=1)
    again(e, run)
    assert st.error == "approval_stale" and e.h.calls == []
    e.clock.now = T0 - timedelta(seconds=1)                                 # decided_at in the future
    st.state = State.WAITING_APPROVAL
    again(e, run)
    assert st.error == "approval_stale" and e.h.calls == []
    readings = iter([T0, T0 + timedelta(seconds=APPROVED_VALIDITY_SECONDS + 5)])
    last = [T0]

    def clock():
        last[0] = next(readings, last[0])
        return last[0]
    e.store.m00._clock = clock                                              # first (cached) reading in time, in-transaction reading stale
    st.state = State.WAITING_APPROVAL
    again(e, run)
    assert st.error == "approval_stale" and e.h.calls == []
    e.store.m00._clock = e.clock
    e.clock.now = T0 + timedelta(seconds=APPROVED_VALIDITY_SECONDS)         # exactly at the boundary is valid
    st.state = State.WAITING_APPROVAL
    again(e, run)
    assert st.state == State.SUCCEEDED and len(e.h.calls) == 1


def test_NEW_real_concurrent_duplicate_dispatch_runs_the_effect_at_most_once(tmp_path):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    runs, barrier = [copy.deepcopy(run) for _ in range(8)], threading.Barrier(8)

    def worker(r):
        # a Service per thread (own event loop, own scheduler primitives) sharing the SAME real m00 store and the same handler
        async def model(kind, data):
            return {"steps": []}
        svc = Service(e.store, model)
        svc.tools.register(Tool("sender", "d", Risk.EXTERNAL, set(), e.h, timeout=60))
        barrier.wait()
        asyncio.run(svc.loop.execute(r))
    ts = [threading.Thread(target=worker, args=(r,)) for r in runs]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(e.h.calls) == 1 and sum(r.plan.steps[0].state == State.SUCCEEDED for r in runs) == 1


def test_NEW_real_contention_across_expiry_dispatches_nothing(tmp_path):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    e.clock.now = T0 + timedelta(seconds=APPROVED_VALIDITY_SECONDS, microseconds=1)
    runs, barrier = [copy.deepcopy(run) for _ in range(8)], threading.Barrier(8)

    def worker(r):
        # a Service per thread (own event loop, own scheduler primitives) sharing the SAME real m00 store and the same handler
        async def model(kind, data):
            return {"steps": []}
        svc = Service(e.store, model)
        svc.tools.register(Tool("sender", "d", Risk.EXTERNAL, set(), e.h, timeout=60))
        barrier.wait()
        asyncio.run(svc.loop.execute(r))
    ts = [threading.Thread(target=worker, args=(r,)) for r in runs]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert e.h.calls == []


def test_NEW_database_operational_failure_blocks_before_any_handler(tmp_path):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    real = e.store.consume_effect

    def boom(i, **kw):
        raise OperationalError("stmt", {}, Exception("database is locked secret"))
    e.store.consume_effect = boom
    again(e, run)
    st = run.plan.steps[0]
    assert st.error == "approval_store_unavailable" and e.h.calls == [] and "secret" not in str(st.error)
    e.store.consume_effect = real


@pytest.mark.parametrize("tamper", ["payload_none", "module_bool", "user", "digest", "no_decided_at", "wrong_action"])
def test_NEW_malformed_or_mismatched_view_fails_closed(tmp_path, tamper):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    real = e.store.full_view

    def fv(i):
        v = dict(real(i))
        p = dict(v["payload"])
        if tamper == "payload_none":
            v["payload"] = None
        elif tamper == "module_bool":
            v["module_id"] = True
        elif tamper == "user":
            v["user_id"] = "t2"
        elif tamper == "digest":
            v["payload"] = {**p, "step_digest": "0" * 64}
        elif tamper == "no_decided_at":
            v["decided_at"] = None
        else:
            v["action_type"] = "cognitive:other"
        return v
    e.store.full_view = fv
    again(e, run)
    assert run.plan.steps[0].error == "approval_mismatch" and e.h.calls == []


def test_NEW_a_permit_that_is_not_allowed_true_for_this_effect_is_refused(tmp_path):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    real = e.store.consume_effect
    e.store.consume_effect = lambda i, **kw: {**real(i, **kw), "allowed": 1}
    again(e, run)
    assert run.plan.steps[0].error == "approval_refused" and e.h.calls == []


def test_CONVERTED_failed_external_step_is_blocked_unknown_and_never_dispatched_twice(tmp_path):
    # base: a failed approved external step went back to PENDING and dispatched again (different key) under one approval.
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    e.h.fail = RuntimeError("boom token=SECRET")
    again(e, run)
    st = run.plan.steps[0]
    assert st.state == State.BLOCKED and st.error == "outcome_unknown" and st.outcome_unknown and st.attempts == 1
    assert "SECRET" not in repr(st) and all("SECRET" not in repr(t) for t in run.traces)
    e.h.fail = None
    again(e, run)
    assert len(e.h.calls) == 1 and st.state == State.BLOCKED


def test_NEW_timeout_and_scheduler_level_exceptions_keep_the_fixed_unknown_state(tmp_path):
    e = make(tmp_path, timeout=1)
    run = start(e)
    approve(e, run)
    e.h.sleep = 3
    again(e, run)
    st = run.plan.steps[0]
    assert st.error == "outcome_unknown" and st.state == State.BLOCKED and len(e.h.calls) == 1

    class Boom(BaseException):
        pass
    e2 = make(tmp_path / "b") if (tmp_path / "b").mkdir() is None else None
    run2 = start(e2)
    approve(e2, run2)
    e2.h.fail = Boom("raw detail")
    again(e2, run2)                                                         # BaseException surfaces via the scheduler, which must not overwrite the marker
    s2 = run2.plan.steps[0]
    assert s2.error == "outcome_unknown" and s2.outcome_unknown and "raw detail" not in repr(s2)


def test_NEW_cancellation_after_consume_leaves_the_unknown_marker(tmp_path):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    e.h.sleep = 30

    async def go():
        t = asyncio.ensure_future(e.svc.loop.execute(run))
        await asyncio.sleep(0.5)
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
    asyncio.run(go())
    st = run.plan.steps[0]
    assert st.outcome_unknown and st.error == "outcome_unknown" and st.state == State.RUNNING
    e.h.sleep = 0
    again(e, run)
    # cancellation propagates out of execute, so the step stays RUNNING (not BLOCKED) with the unknown marker; a rerun does not
    # pick RUNNING steps up (ready set is PENDING/WAITING only), blocks the run and never dispatches again
    assert len(e.h.calls) == 1 and run.status == State.BLOCKED and st.state == State.RUNNING and st.outcome_unknown


def test_PROTECTION_pre_dispatch_refusals_keep_the_approval_unconsumed(tmp_path):
    e = make(tmp_path, tool_risk=Risk.REVERSIBLE)                            # registered risk differs from the reviewed step risk
    run = start(e)
    approve(e, run)
    again(e, run)
    st = run.plan.steps[0]
    assert e.h.calls == [] and st.error == "ValueError"
    e.svc.tools.register(Tool("sender", "d", Risk.EXTERNAL, set(), e.h))
    st.state, st.attempts = State.PENDING, 0
    again(e, run)
    assert st.state == State.SUCCEEDED and len(e.h.calls) == 1


def test_PROTECTION_read_steps_are_unchanged_and_still_retry(tmp_path):
    steps = [{"id": "r1", "title": "read", "tool": "sender", "arguments": {}, "risk": "read"}]
    e = make(tmp_path, steps=steps, tool_risk=Risk.READ)
    e.h.fail = OSError("flaky")
    run = start(e, tenant=None, actor=None)
    assert run.plan.steps[0].attempts == 3 and run.plan.steps[0].state == State.FAILED and len(e.h.calls) == 3
    assert e.store.m00.list() == []


def test_NEW_non_plain_json_arguments_block_before_filing(tmp_path):
    e = make(tmp_path, steps=[{"id": "s1", "title": "send", "tool": "sender", "arguments": {"to": 1}, "risk": "external"}])
    run = start(e)
    st = run.plan.steps[0]
    assert st.state == State.WAITING_APPROVAL
    st.arguments = {"to": ("a", "b")}
    st.state = State.PENDING
    st.approval_id = None
    again(e, run)
    assert st.error == "arguments_invalid" and len(e.store.m00.list()) == 1


def test_NEW_claire_realize_propagates_the_goal_owner_identity_into_the_run(tmp_path):
    e = make(tmp_path, steps=[])
    claire = ClaireService(e.svc, e.store)
    owned = claire.intake("g", [], {}, tenant_id="t1", actor_id="u1")
    asyncio.run(claire.realize(owned.id))
    run = e.svc.runs[claire.goals[owned.id].run_id]
    assert (run.tenant_id, run.actor_id) == ("t1", "u1")
    legacy = claire.intake("g2", [], {})
    asyncio.run(claire.realize(legacy.id))
    run2 = e.svc.runs[claire.goals[legacy.id].run_id]
    assert (run2.tenant_id, run2.actor_id) == (None, None)


def _wrap_consume(e, after):
    real = e.store.consume_effect

    def wrapped(*a, **kw):
        permit = real(*a, **kw)   # genuine committed consumption and genuine permit
        after()
        return permit
    e.store.consume_effect = wrapped


def test_NEW_post_consume_handler_swap_still_runs_the_pre_consume_handler(tmp_path):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    replacement = Handler()

    def swap():
        e.svc.tools.tools["sender"].handler = replacement
        e.svc.tools.tools["sender"].timeout = 1
    _wrap_consume(e, swap)
    again(e, run)
    assert len(e.h.calls) == 1 and replacement.calls == [] and run.plan.steps[0].state == State.SUCCEEDED


def test_NEW_post_consume_tool_to_none_does_not_fake_success(tmp_path):
    e = make(tmp_path)
    run = start(e)
    approve(e, run)
    _wrap_consume(e, lambda: setattr(run.plan.steps[0], "tool", None))
    again(e, run)
    st = run.plan.steps[0]
    assert len(e.h.calls) == 1 and st.state == State.SUCCEEDED and st.result == {"ok": True}   # the checked handler ran, not the synthetic result
