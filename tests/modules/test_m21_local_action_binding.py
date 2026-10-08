"""Slice 15 (Step 2B): Service.local_action only executes a high-risk action under a real, exact, fresh, single-use Module 0 approval.

Everything here runs against a REAL Module 0 Service on a file SQLite database with an injected clock (not a fake approval store), except where a test
says it substitutes a store to prove fail-closed. SCOPE LIMITS (verbatim): no role/designation check (m00 decide path untraced); approved_by != actor is a
structural guard only, never role closure; no actor binding at m00; the daemon is NOT claimed to validate the token; the unknown-outcome marker lives in
in-memory goal state, not a durable journal; lexical high-risk classification is unchanged (an effectful kind with external_effect omitted stays ungated);
no production wiring exists for a local client. Approved validity is 900s inclusive: valid iff 0 <= now - decided_at <= 900s. Pending review TTL is 24h.
Labels: NEW = failed/absent on base 5e1001dd. CONVERTED = old test whose meaning changed. PROTECTION = must hold on base and now.
"""
import asyncio
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalRequest, ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalBroadcaster, ApprovalConflictError, Service as M00
from app.modules.m21_claire.service import APPROVED_VALIDITY_SECONDS, LocalActionOutcomeUnknown, Service

T0 = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
REFUSED = "local action approval refused"


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


class Store:
    """Facade over a REAL m00 Service (file SQLite, injected clock), shaped like core.approvals.ApprovalStore."""
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


class Client:
    def __init__(self):
        self.executed, self.audits, self.cap_calls, self.preview_calls = [], [], 0, 0
        self.fail_execute = None
        self.fail_audit = False
        self.preview_extra = {}
        self.hang = False
        self.preview_hook = None

    async def capabilities(self):
        self.cap_calls += 1
        return {"send_message", "delete_file", "read_file"}

    async def preview(self, action):
        self.preview_calls += 1
        if self.preview_hook:
            self.preview_hook(action)
        return {"kind": action["kind"], "to": action.get("to"), **self.preview_extra}

    async def execute(self, action, token):
        if self.hang:
            await asyncio.sleep(3600)
        if self.fail_execute:
            raise self.fail_execute
        self.executed.append((action, token))
        return {"ok": True}

    async def audit(self, event):
        if self.fail_audit:
            raise RuntimeError("audit down password=hunter2")
        self.audits.append(event)


class _Cog:
    pass


@pytest.fixture
def env(tmp_path):
    clock = Clock()
    store = Store(tmp_path, clock)
    client = Client()
    svc = Service(_Cog(), store, client)
    gid = svc.intake("tidy files", [], {}, tenant_id="t1", actor_id="u1").id
    return type("E", (), dict(clock=clock, store=store, client=client, svc=svc, gid=gid))


def run(coro):
    return asyncio.run(coro)


def call(e, action, token=None, gid=None, tenant="t1", actor="u1"):
    return run(e.svc.local_action(gid or e.gid, action, token, tenant_id=tenant, actor_id=actor))


ACTION = {"kind": "delete_file", "path": "/tmp/x"}


def approved(e, action=ACTION, by="approver-1", gid=None):
    req = call(e, action, gid=gid)                                       # high-risk without token files the request
    e.store.m00.decide(req.id, ApprovalStatus.APPROVED, by)
    return req.id


def test_NEW_filed_request_binds_the_exact_action_and_has_a_pending_ttl(env):
    req = call(env, ACTION)
    v = env.store.full_view(req.id)
    assert v["payload"]["goal_id"] == env.gid and len(v["payload"]["action_digest"]) == 64
    assert v["expires_at"] == T0 + timedelta(hours=24) and env.client.executed == []


def test_NEW_exact_approved_approval_executes_once_and_cannot_be_reused(env):
    aid = approved(env)
    assert call(env, ACTION, aid) == {"ok": True}
    assert env.client.executed == [(ACTION, aid)]
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, aid)
    assert len(env.client.executed) == 1


@pytest.mark.parametrize("token", ["tok", "", "not-an-id", "x" * 300])
def test_CONVERTED_an_arbitrary_token_no_longer_executes_a_high_risk_action(env, token):
    # base: any non-empty token executed (audit CHARACTERIZATION / superset test). Empty token = files a request, never executes.
    if token == "":
        call(env, ACTION, token)
    else:
        with pytest.raises(ValueError, match=REFUSED):
            call(env, ACTION, token)
    assert env.client.executed == []


def test_NEW_pending_and_denied_approvals_are_refused(env):
    req = call(env, ACTION)
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, req.id)
    env.store.m00.decide(req.id, ApprovalStatus.DENIED, "approver-1")
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, req.id)
    assert env.client.executed == []


def test_NEW_approval_for_other_args_other_goal_or_foreign_tenant_is_refused(env):
    aid = approved(env)
    with pytest.raises(ValueError, match=REFUSED):
        call(env, {**ACTION, "path": "/tmp/y"}, aid)                    # same kind, different args
    gid2 = env.svc.intake("g2", [], {}, tenant_id="t1", actor_id="u1").id
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, aid, gid=gid2)                                 # same action, different goal
    with pytest.raises(KeyError):
        call(env, ACTION, aid, tenant="t2", actor="u1")                  # foreign tenant cannot even resolve the goal
    assert env.client.executed == []


def test_NEW_self_approved_and_blank_approver_are_refused(env):
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, approved(env, by="u1"))
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, approved(env, by="   "))
    assert env.client.executed == []


def test_NEW_a_route_filed_request_without_a_digest_cannot_authorize_local_action(env):
    req = env.svc.request_environment_change(env.gid, "delete_file", {"kind": "delete_file", "to": None}, tenant_id="t1")
    env.store.m00.decide(req.id, ApprovalStatus.APPROVED, "approver-1")
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, req.id)
    assert env.client.executed == []


def test_NEW_approved_permit_expires_inclusive_boundary_and_future_decided_at_is_refused(env):
    aid = approved(env)
    env.clock.now = T0 + timedelta(seconds=APPROVED_VALIDITY_SECONDS, microseconds=1)
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, aid)
    env.clock.now = T0 - timedelta(seconds=1)                           # decided_at in the future relative to the clock
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, aid)
    env.clock.now = T0 + timedelta(seconds=APPROVED_VALIDITY_SECONDS)  # exactly at the boundary: still valid
    assert call(env, ACTION, aid) == {"ok": True}


def test_NEW_age_is_read_with_a_fresh_clock_inside_the_consuming_transaction(env):
    aid = approved(env)
    readings = iter([T0, T0 + timedelta(seconds=APPROVED_VALIDITY_SECONDS + 5)])   # a cached first reading would pass; the in-txn reading is stale
    last = [T0]

    def clock():
        last[0] = next(readings, last[0])
        return last[0]
    env.store.m00._clock = clock
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, aid)
    assert env.client.executed == []


def test_NEW_real_concurrent_consumption_runs_the_effect_at_most_once(env):
    aid = approved(env)
    results, barrier = [], threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            call(env, ACTION, aid)
            results.append("ok")
        except Exception as e:                                           # ValueError refusal or a DB lock error: either way no second effect
            results.append(type(e).__name__)
    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results.count("ok") == 1 and len(env.client.executed) == 1


def test_NEW_execute_failure_surfaces_unknown_outcome_never_refunds_and_hides_client_text(env):
    aid = approved(env)
    env.client.fail_execute = RuntimeError("boom token=SECRET")
    with pytest.raises(LocalActionOutcomeUnknown) as ei:
        call(env, ACTION, aid)
    assert "SECRET" not in str(ei.value) and isinstance(ei.value.__cause__, RuntimeError)
    assert env.svc.goals[env.gid].evidence[-1]["outcome"] == "unknown"
    env.client.fail_execute = None
    with pytest.raises(ValueError, match=REFUSED):                       # consumed: a retry needs a new approval AND reconciliation
        call(env, ACTION, aid)
    assert env.client.executed == []


def test_NEW_cancellation_leaves_the_unknown_marker(env):
    aid = approved(env)
    env.client.hang = True

    async def go():
        t = asyncio.ensure_future(env.svc.local_action(env.gid, ACTION, aid, tenant_id="t1", actor_id="u1"))
        await asyncio.sleep(0.3)
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
    run(go())
    assert env.svc.goals[env.gid].evidence[-1]["outcome"] == "unknown"
    env.client.hang = False
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, aid)


def test_NEW_audit_failure_keeps_the_confirmed_result_and_marks_audit_failed(env):
    aid = approved(env)
    env.client.fail_audit = True
    assert call(env, ACTION, aid) == {"ok": True}
    ev = env.svc.goals[env.gid].evidence[-1]
    assert ev["result"] == {"ok": True} and ev["audit"] == "audit_failed" and "hunter2" not in str(ev)


def test_NEW_store_without_full_view_or_consume_fails_closed():
    class Bare:
        def put(self, item, **kw):
            return item
    client = Client()
    svc = Service(_Cog(), Bare(), client)
    gid = svc.intake("g", [], {}, tenant_id="t1", actor_id="u1").id
    with pytest.raises(ValueError, match=REFUSED):
        run(svc.local_action(gid, ACTION, "some-id", tenant_id="t1", actor_id="u1"))
    assert client.executed == []


def test_NEW_a_permit_that_is_not_allowed_true_for_this_effect_is_refused(env):
    aid = approved(env)
    real = env.store.consume_effect
    env.store.consume_effect = lambda i, **kw: {**real(i, **kw), "allowed": 1}      # truthy but not True
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, aid)
    assert env.client.executed == []


def test_NEW_non_plain_json_action_is_refused_before_any_client_call(env):
    for bad in ({"kind": "delete_file", "path": ("a", "b")}, {"kind": "delete_file", "n": float("nan")}, {"kind": "delete_file", 1: "x"}):
        with pytest.raises(ValueError, match="plain JSON"):
            call(env, bad)
    assert env.client.cap_calls == 0


def test_NEW_caller_mutation_during_await_cannot_change_what_executes(env):
    aid = approved(env)
    action = dict(ACTION)
    env.client.preview_hook = lambda a: (action.update(path="/etc/passwd"), a.update(path="/etc/shadow"))
    # the preview hook also mutates the client's own copy; the reviewed preview contains no path so the digest/preview checks pass
    call(env, action, aid)
    assert env.client.executed[0][0] == ACTION


def test_NEW_unknown_goal_and_missing_identity_are_refused_before_capabilities_or_preview(env):
    with pytest.raises(KeyError):
        call(env, ACTION, gid="nope")
    with pytest.raises(KeyError):
        call(env, {"kind": "read_file", "path": "/a"}, tenant=None, actor=None)       # non-high-risk too: owner check applies
    with pytest.raises(KeyError):
        call(env, {"kind": "read_file", "path": "/a"}, tenant="t1", actor="  ")
    assert env.client.cap_calls == 0 and env.client.preview_calls == 0


def test_NEW_legacy_goals_run_non_high_risk_but_never_high_risk(env):
    env.svc.goals["legacy"] = type("G", (), {"evidence": []})()
    assert run(env.svc.local_action("legacy", {"kind": "read_file", "path": "/a"})) == {"ok": True}
    with pytest.raises(ValueError, match=REFUSED):
        run(env.svc.local_action("legacy", ACTION, "some-id"))
    with pytest.raises(KeyError):
        run(env.svc.local_action("legacy", {"kind": "read_file"}, tenant_id="t1", actor_id="u1"))   # legacy namespace is not a wildcard


def test_NEW_a_changed_fresh_preview_requires_fresh_review_and_does_not_consume(env):
    aid = approved(env)
    env.client.preview_extra = {"destination": "other-host"}            # same action JSON, different recipient/destination semantics
    with pytest.raises(ValueError, match=REFUSED):
        call(env, ACTION, aid)
    assert env.client.executed == []
    env.client.preview_extra = {}                                       # approval was NOT consumed by the refusal
    assert call(env, ACTION, aid) == {"ok": True}


def test_PROTECTION_forbidden_actions_still_refuse_and_non_high_risk_executes_without_approval(env):
    with pytest.raises(ValueError, match="boundaries"):
        call(env, {"kind": "delete_file", "path": "/x", "note": "ban evasion"})
    assert call(env, {"kind": "read_file", "path": "/a"}) == {"ok": True}
    assert env.client.executed[-1][0]["kind"] == "read_file"


def test_PROTECTION_unwired_client_is_still_a_runtime_error():
    svc = Service(_Cog(), object())
    with pytest.raises(RuntimeError, match="no signed local client"):
        run(svc.local_action("g", ACTION))


# ---- Module 0 consume_effect(max_age_seconds) ------------------------------------------------------------------------------------------

def _m00_approved(tmp_path, clock):
    st = Store(tmp_path, clock)
    v = st.m00.submit(module_id=21, action_type="claire:x", payload={"a": 1}, user_id="t1")
    st.m00.decide(v["id"], ApprovalStatus.APPROVED, "ap")
    return st, v


@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), -1, 0, "5", None.__class__])
def test_NEW_m00_rejects_malformed_max_age(tmp_path, bad):
    clock = Clock()
    st, v = _m00_approved(tmp_path, clock)
    with pytest.raises(ValueError, match="max_age_seconds"):
        st.m00.consume_effect(v["id"], module_id=21, action_type="claire:x", payload={"a": 1}, user_id="t1", effect_id="e1", actor="a", max_age_seconds=bad)


def test_PROTECTION_m00_consume_without_max_age_is_unchanged_even_when_old(tmp_path):
    clock = Clock()
    st, v = _m00_approved(tmp_path, clock)
    clock.now = T0 + timedelta(days=30)
    assert st.m00.consume_effect(v["id"], module_id=21, action_type="claire:x", payload={"a": 1}, user_id="t1", effect_id="e1", actor="a")["allowed"] is True


def test_NEW_m00_max_age_stale_and_boundary_are_refused_without_writing_an_effect(tmp_path):
    clock = Clock()
    st, v = _m00_approved(tmp_path, clock)
    kw = dict(module_id=21, action_type="claire:x", payload={"a": 1}, user_id="t1", actor="a", max_age_seconds=60)
    clock.now = T0 + timedelta(seconds=60, microseconds=1)
    with pytest.raises(ApprovalConflictError, match="stale"):
        st.m00.consume_effect(v["id"], effect_id="e1", **kw)
    clock.now = T0 + timedelta(seconds=60)
    assert st.m00.consume_effect(v["id"], effect_id="e2", **kw)["allowed"] is True      # the refusal wrote no effect row
