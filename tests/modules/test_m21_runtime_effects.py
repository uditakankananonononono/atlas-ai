"""Slice 3b: effect journal, idempotency, reconciliation, owner resolve route.

Tests are named PROTECTION_* (a hole that must stay closed) or NEW_* (new capability).
Limits: SQLite only; fake tools against an in-memory "external world"; a timed-out sync tool body keeps running in its thread;
exactly-once holds only for tools that honour the key or implement reconcile; no real-concurrency stress beyond two store handles
on one SQLite file; identical calls (same goal, tool and arguments) are one effect by design.
"""
import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import update

from app.auth.context import TenantContext, require_tenant
from app.main import app
from app.modules.m21_claire.runtime import routes as rroutes
from app.modules.m21_claire.runtime.engine import Engine
from app.modules.m21_claire.runtime.gates import GateEnforcer, GateRefused, Principal, payload_digest
from app.modules.m21_claire.runtime.goals import EffectRow, GoalRow, GoalStore
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry, Tool
from app.modules.m21_claire.runtime.types import AgentDecision, ToolCall, ToolRisk
from app.modules.m21_claire.runtime.worker import Worker

URL = "/api/v1/claire/runtime/goals"
CRIT = [{"kind": "tool_receipt", "tool": "write_row", "min_count": 1}]
WORLD: dict[str, int] = {}   # the fake external system: effect label -> times it happened
KEYS: list[Any] = []         # idempotency keys the tools actually received


class A(BaseModel):
    target: str = "x"


class Boom(RuntimeError):
    """Not an allowlisted failure class: simulates a process crash mid-call (propagates, nothing is recorded)."""


def make(name="write_row", *, idempotent=False, accepts=False, risk=ToolRisk.WRITE, money=False, person=False,
         mode="ok", reconcile=None, delay=0.0):
    class T(Tool):
        arguments_model = A
        def run(self, a, idempotency_key=None):
            KEYS.append(idempotency_key)
            label = f"{self.name}:{a.target}"
            if self.accepts_idempotency_key and idempotency_key is not None and f"k:{idempotency_key}" in WORLD:
                return {"deduped": True}
            WORLD[label] = WORLD.get(label, 0) + 1
            if self.accepts_idempotency_key and idempotency_key is not None:
                WORLD[f"k:{idempotency_key}"] = 1
            if delay: time.sleep(delay)
            if mode == "crash_after": raise Boom()
            if mode == "oserror_after": raise OSError("x")
            return {"done": a.target}
    T.name, T.risk, T.spends_money, T.sends_to_person = name, risk, money, person
    T.idempotent, T.accepts_idempotency_key = idempotent, accepts
    if reconcile is not None:
        T.reconcile = lambda self, key: reconcile(key)
    return T()


@pytest.fixture(autouse=True)
def _clear():
    WORLD.clear(); KEYS.clear()


@pytest.fixture
def clk():
    return [datetime(2026, 10, 8, tzinfo=timezone.utc)]


@pytest.fixture
def store(tmp_path, clk, monkeypatch):
    s = GoalStore(f"sqlite:///{tmp_path}/e.db", clock=lambda: clk[0], create_schema=True)
    monkeypatch.setattr(rroutes, "_store", s)
    yield s
    s.close()


def reg(store, *tools, timeout=30.0):
    r = ReadOnlyToolRegistry(enforcer=GateEnforcer(store), journal=store, call_timeout=timeout)
    for t in tools: r.register(t)
    return r


def run(c): return asyncio.run(c)
def goal(store, tenant="t1", actor="a1"): return store.create(tenant, actor, "do work", CRIT, 6)


def live(store, gid, tenant="t1", actor="a1"):
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(status="running", lease_token="tok-" + gid,
                                                                  lease_expires_at="9999-01-01T00:00:00+00:00"))
    return Principal(tenant, actor, gid, "tok-" + gid)


def set_status(store, gid, status):
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(status=status, lease_token=None))


def states(store, gid): return [e["state"] for e in store.list_effects("t1", "a1", gid)]
def call(name, **a): return AgentDecision(tool_call=ToolCall(name=name, arguments=a))
def final(): return AgentDecision(final="done")


class Script:
    def __init__(self, *d): self.d = list(d)
    async def decide(self, m): return self.d.pop(0)


def worker(store, model, tools, wid="w1"):
    return Worker(store, lambda c: Engine(model, tools, max_steps=c.max_steps), wid)


# ---- PROTECTION ---------------------------------------------------------------------------------

def test_PROTECTION_crash_after_effect_then_retry_never_runs_it_twice(store, clk):
    t = make(mode="crash_after")
    r = reg(store, t)
    gid = goal(store); w1 = worker(store, Script(call("write_row", target="a")), r, "w1")
    with pytest.raises(Boom):
        run(w1.run_once())                      # the effect happened, the process "died": no receipt, row stays intent
    assert WORLD["write_row:a"] == 1 and states(store, gid) == ["intent"]
    clk[0] += timedelta(seconds=200)            # lease expires; another worker claims
    w2 = worker(store, Script(call("write_row", target="a"), final()), r, "w2")
    run(w2.run_once())
    got = store.get("t1", "a1", gid)
    assert WORLD["write_row:a"] == 1            # never executed a second time
    assert got["status"] == "awaiting_review" and got["blocker"] == "effect_unknown"


def test_PROTECTION_direct_redispatch_of_an_unknown_effect_is_refused(store):
    gid = goal(store); p = live(store, gid)
    r = reg(store, make(mode="oserror_after"))
    assert run(r.execute(1, "write_row", {"target": "a"}, p)).error == "OSError"
    assert states(store, gid) == ["unknown"]
    with pytest.raises(GateRefused) as e:
        run(r.execute(2, "write_row", {"target": "a"}, p))
    assert e.value.reason == "effect_unknown" and WORLD["write_row:a"] == 1


def test_PROTECTION_two_store_handles_racing_on_one_call_get_one_intent(tmp_path, clk):
    url = f"sqlite:///{tmp_path}/race.db"
    a = GoalStore(url, clock=lambda: clk[0], create_schema=True); b = GoalStore(url, clock=lambda: clk[0])
    gid = goal(a); p = live(a, gid)
    key = payload_digest(gid, "write_row", {"target": "a"})
    first = a.begin_effect(p, "write_row", key, takeover_pending=False)
    second = b.begin_effect(p, "write_row", key, takeover_pending=False)
    assert first[0] == "new" and second[0] == "pending"
    with a._sessions.begin() as s:
        assert len(s.query(EffectRow).all()) == 1
    a.close(); b.close()


def test_PROTECTION_stale_worker_cannot_write_intent_or_run(store, clk):
    gid = goal(store); p = live(store, gid)
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(lease_expires_at="2026-10-07T00:00:00+00:00"))  # expired
    r = reg(store, make())
    with pytest.raises(GateRefused) as e:
        run(r.execute(1, "write_row", {"target": "a"}, p))
    assert e.value.reason == "lease_lost" and WORLD == {} and states(store, gid) == []


def test_PROTECTION_replaced_lease_token_cannot_write_intent(store):
    gid = goal(store); live(store, gid)
    stale = Principal("t1", "a1", gid, "some-old-token")
    with pytest.raises(GateRefused) as e:
        run(reg(store, make()).execute(1, "write_row", {"target": "a"}, stale))
    assert e.value.reason == "lease_lost" and WORLD == {}


def test_PROTECTION_committed_call_replays_stored_receipt_and_runs_nothing(store):
    gid = goal(store); p = live(store, gid)
    r = reg(store, make())
    first = run(r.execute(1, "write_row", {"target": "a"}, p))
    again = run(r.execute(2, "write_row", {"target": "a"}, p))
    assert first.ok and not first.replayed and again.ok and again.replayed and again.content == first.content
    assert WORLD["write_row:a"] == 1 and states(store, gid) == ["committed"]


def test_PROTECTION_timed_out_write_is_unknown_not_failed_and_goal_is_not_completed(store):
    gid = goal(store)
    r = reg(store, make(delay=0.4), timeout=0.05)
    w = worker(store, Script(call("write_row", target="a"), final()), r, "w1")
    run(w.run_once())
    got = store.get("t1", "a1", gid)
    assert states(store, gid) == ["unknown"]
    assert got["status"] == "awaiting_review" and got["blocker"] == "effect_unknown" and got["verdict"] is None
    time.sleep(0.5)  # let the orphan thread finish so it cannot leak into later tests


def test_PROTECTION_consumed_approval_is_not_refunded_after_unknown(store):
    gid = goal(store); p = live(store, gid)
    r = reg(store, make("send_note", person=True, mode="oserror_after"))
    d = payload_digest(gid, "send_note", {"target": "a"})
    store.grant("t1", "a1", gid, "send_note", "comms", d, "ap1")
    assert run(r.execute(1, "send_note", {"target": "a"}, p)).error == "OSError"      # approval consumed, outcome unknown
    with pytest.raises(GateRefused) as e:
        run(r.execute(2, "send_note", {"target": "a"}, p))
    assert e.value.reason == "effect_unknown"
    store.grant("t1", "a1", gid, "send_note", "comms", d, "ap1")                         # a fresh approval alone does not unblock
    with pytest.raises(GateRefused) as e:
        run(r.execute(3, "send_note", {"target": "a"}, p))
    assert e.value.reason == "effect_unknown" and WORLD["send_note:a"] == 1
    eid = store.list_effects("t1", "a1", gid)[0]["id"]
    set_status(store, gid, "awaiting_review"); p = live(store, gid)
    assert store.resolve_effect(gid, eid, "absent", tenant_id="t1", resolver_id="ap1") == "resolved"
    assert run(r.execute(4, "send_note", {"target": "a"}, p)).error == "OSError"        # absent + a spare approval -> the retry really ran
    assert WORLD["send_note:a"] == 2


def test_PROTECTION_mutating_idempotency_declarations_after_registration_is_refused(store):
    gid = goal(store); p = live(store, gid)
    t = make(); r = reg(store, t)
    for attr, val in (("idempotent", True), ("idempotent", 1), ("idempotent", None), ("accepts_idempotency_key", True),
                      ("accepts_idempotency_key", 1)):
        t = make(); r = reg(store, t); setattr(t, attr, val)
        assert r.risk_intact("write_row") is False
        with pytest.raises(PermissionError):
            run(r.execute(1, "write_row", {"target": "a"}, p))
    assert WORLD == {}


def test_PROTECTION_non_read_tool_without_declared_idempotency_or_journal_cannot_run(store):
    with pytest.raises(ValueError):
        reg(store, make(idempotent=None))
    r = ReadOnlyToolRegistry(enforcer=GateEnforcer(store))     # no journal
    r.register(make())
    gid = goal(store)
    with pytest.raises(PermissionError):
        run(r.execute(1, "write_row", {"target": "a"}, live(store, gid)))
    with pytest.raises(PermissionError):                         # a principal without a lease token is not fenced
        run(reg(store, make()).execute(1, "write_row", {"target": "a"}, Principal("t1", "a1", gid)))
    assert WORLD == {}


@pytest.mark.parametrize("bad", [1, 0, "true", [], 1.0])
def test_PROTECTION_idempotency_declarations_must_be_exact_bool(store, bad):
    with pytest.raises(ValueError):
        reg(store, make(idempotent=bad))
    t = make(); t.accepts_idempotency_key = bad
    with pytest.raises(ValueError):
        reg(store, t)


def test_PROTECTION_validation_failure_never_reached_the_tool_and_is_retriable(store):
    class Strict(BaseModel):
        n: int
    t = make(); t.arguments_model = Strict
    gid = goal(store); p = live(store, gid)
    r = reg(store, t)
    assert run(r.execute(1, "write_row", {"n": "nope"}, p)).error == "ValidationError"
    assert states(store, gid) == ["failed"] and WORLD == {}
    assert run(r.execute(2, "write_row", {"n": "nope"}, p)).error == "ValidationError"   # failed rows may be retried
    assert [e["attempts"] for e in store.list_effects("t1", "a1", gid)] == [2]


def test_PROTECTION_identical_read_calls_are_not_journaled(store):
    class R(Tool):
        name, risk, arguments_model = "lookup", ToolRisk.READ, A
        def run(self, a): return {"v": 1}
    r = reg(store, R()); gid = goal(store); p = live(store, gid)
    assert run(r.execute(1, "lookup", {}, p)).ok and run(r.execute(2, "lookup", {}, p)).replayed is False
    assert states(store, gid) == []


# ---- NEW CAPABILITY -----------------------------------------------------------------------------

def test_NEW_idempotent_tool_is_redispatched_with_the_same_key_and_the_world_dedupes(store):
    gid = goal(store); p = live(store, gid)
    r = reg(store, make(idempotent=True, accepts=True, mode="oserror_after"))
    assert run(r.execute(1, "write_row", {"target": "a"}, p)).error == "OSError"      # unknown
    second = run(r.execute(2, "write_row", {"target": "a"}, p))                       # same key re-sent, not refused
    assert second.ok and second.content == {"deduped": True} and states(store, gid) == ["committed"]
    assert len(set(KEYS)) == 1 and KEYS[0] is not None
    assert WORLD["write_row:a"] == 1                                                    # the external system deduped on the key


@pytest.mark.parametrize("answer,state,reran", [("committed", "committed", 0), ("absent", "absent", 0), ("unknown", "intent", 0)])
def test_NEW_reconcile_resolves_unknown_effects_at_the_next_claim(store, clk, answer, state, reran):
    t = make(mode="crash_after", reconcile=lambda key: answer)
    r = reg(store, t)
    gid = goal(store)
    with pytest.raises(Boom):
        run(worker(store, Script(call("write_row", target="a")), r, "w1").run_once())
    clk[0] += timedelta(seconds=200)
    w2 = worker(store, Script(final()), r, "w2")
    run(w2.run_once())
    assert states(store, gid) == [state]
    got = store.get("t1", "a1", gid)
    if answer == "unknown":
        assert got["status"] == "awaiting_review" and got["blocker"] == "effect_unknown"
    else:
        assert got["blocker"] != "effect_unknown"        # resolved; the goal proceeded (acceptance may or may not be met)
    assert WORLD["write_row:a"] == 1


def test_NEW_reconcile_exceptions_are_contained_to_named_classes_and_leave_the_effect_blocking(store, clk):
    def bad(key): raise OSError("x")
    r = reg(store, make(mode="crash_after", reconcile=bad))
    gid = goal(store)
    with pytest.raises(Boom):
        run(worker(store, Script(call("write_row", target="a")), r, "w1").run_once())
    clk[0] += timedelta(seconds=200)
    run(worker(store, Script(final()), r, "w2").run_once())
    assert states(store, gid) == ["intent"] and store.get("t1", "a1", gid)["blocker"] == "effect_unknown"


@pytest.fixture
def client(store):
    c = TestClient(app)
    def as_(tenant, actor, roles=frozenset()): app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant, actor, frozenset(roles))
    c.as_ = as_; as_("t1", "a1")
    yield c
    app.dependency_overrides.pop(require_tenant, None)


APPROVER = ("claire-approver",)


def resolve_as(client, gid, eid, body, tenant="t1", actor="ap1", roles=APPROVER):
    """Slice 5: resolving is an approver act by a principal other than the goal's actor (a1). Restores the owner view after."""
    client.as_(tenant, actor, roles)
    try:
        return client.post(f"{URL}/{gid}/effects/{eid}/resolve", json=body)
    finally:
        client.as_("t1", "a1")


def _unknown_effect(store):
    gid = goal(store); p = live(store, gid)
    r = reg(store, make(mode="oserror_after"))
    run(r.execute(1, "write_row", {"target": "a"}, p))
    set_status(store, gid, "awaiting_review")
    return gid, store.list_effects("t1", "a1", gid)[0]["id"], r


def test_NEW_resolve_route_committed_means_never_rerun(store, client):
    gid, eid, r = _unknown_effect(store)
    listed = client.get(f"{URL}/{gid}/effects").json()["effects"]
    assert listed[0]["state"] == "unknown" and "arguments" not in listed[0]
    assert resolve_as(client, gid, eid, {"outcome": "committed"}).json()["state"] == "committed"
    p = live(store, gid)
    assert run(r.execute(2, "write_row", {"target": "a"}, p)).replayed is True and WORLD["write_row:a"] == 1


def test_NEW_resolve_route_absent_allows_a_retry(store, client):
    gid, eid, r = _unknown_effect(store)
    assert resolve_as(client, gid, eid, {"outcome": "absent"}).status_code == 200
    p = live(store, gid)
    assert run(r.execute(2, "write_row", {"target": "a"}, p)).error == "OSError" and WORLD["write_row:a"] == 2


def test_NEW_resolve_route_is_owner_scoped_and_state_checked(store, client):
    gid, eid, _ = _unknown_effect(store)
    body = {"outcome": "absent"}
    # CONVERTED (slice 5): was actor-scoped; resolving is now approver-scoped by tenant. Covers: other tenant, no role,
    # and the goal's own actor are all refused; the owner's own read view stays actor-scoped.
    assert resolve_as(client, gid, eid, body, tenant="t2", actor="ap1").status_code == 404
    client.as_("t2", "a1")
    assert client.get(f"{URL}/{gid}/effects").status_code == 404
    client.as_("t1", "a2")
    assert client.get(f"{URL}/{gid}/effects").status_code == 404
    client.as_("t1", "a1")
    assert resolve_as(client, gid, eid, body, actor="ap1", roles=()).status_code == 403             # no approver role
    assert resolve_as(client, gid, eid, body, actor="a1").status_code == 403                         # the goal's own actor
    assert states(store, gid) == ["unknown"]
    assert resolve_as(client, gid, "no-such", body).status_code == 404
    assert resolve_as(client, gid, eid, {"outcome": "maybe"}).status_code == 422
    set_status(store, gid, "running")
    assert resolve_as(client, gid, eid, body).status_code == 409      # goal running
    set_status(store, gid, "awaiting_review")
    assert resolve_as(client, gid, eid, body).status_code == 200
    assert resolve_as(client, gid, eid, body).status_code == 409      # already resolved
    assert states(store, gid) == ["absent"]


def test_NEW_effects_migration_matches_model_refuses_wrong_shape_and_downgrade_guards_data(tmp_path):
    import os, subprocess, sys, sqlite3
    from sqlalchemy import create_engine, inspect
    from app.modules.m21_claire.runtime.goals import Base
    def alembic(db, *a):
        return subprocess.run([sys.executable, "-m", "alembic", *a], env={**os.environ, "ATLAS_DATABASE_URL": f"sqlite:///{db}"},
                              text=True, capture_output=True, timeout=110)
    db = tmp_path / "a.sqlite"
    assert alembic(db, "upgrade", "head").returncode == 0
    insp = inspect(create_engine(f"sqlite:///{db}"))
    t = Base.metadata.tables["claire_runtime_effects"]
    assert {c["name"]: c["nullable"] for c in insp.get_columns(t.name)} == {c.name: c.nullable for c in t.columns}
    assert {i["name"] for i in insp.get_indexes(t.name)} >= {i.name for i in t.indexes}
    assert any(u["column_names"] == ["goal_id", "idempotency_key"] for u in insp.get_unique_constraints(t.name))
    con = sqlite3.connect(db)
    con.execute("INSERT INTO claire_runtime_effects (id,tenant_id,actor_id,goal_id,tool,idempotency_key,state,attempts,receipt_json,created_at,updated_at) VALUES ('e','t','a','g','tool','k','unknown',1,NULL,'x','x')"); con.commit(); con.close()
    r = alembic(db, "downgrade", "20261008_m21_runtime_approvals")
    assert r.returncode != 0 and "holds effect journal records" in r.stderr
    bad = tmp_path / "b.sqlite"
    assert alembic(bad, "upgrade", "20261008_m21_runtime_approvals").returncode == 0
    con = sqlite3.connect(bad); con.execute("CREATE TABLE claire_runtime_effects (id TEXT PRIMARY KEY)"); con.commit(); con.close()
    r = alembic(bad, "upgrade", "head")
    assert r.returncode != 0 and "incompatible shape" in r.stderr


# ---- reviewer repair: the lease fence must be atomic with the journal write ---------------------

@pytest.mark.parametrize("path", ["insert", "takeover_update"])
def test_PROTECTION_replacement_between_fence_and_journal_write_cannot_write_intent(tmp_path, clk, path):
    """Interleaving: just before the journal INSERT/UPDATE statement executes, the old lease expires and a second store claims a
    replacement token. The old principal must get lease_lost and the journal must not gain/revive an intent for it."""
    from sqlalchemy import event
    url = f"sqlite:///{tmp_path}/r.db"
    a = GoalStore(url, clock=lambda: clk[0], lease_seconds=10, create_schema=True)
    b = GoalStore(url, clock=lambda: clk[0], lease_seconds=10)
    gid = goal(a); c1 = a.claim("one"); p = Principal("t1", "a1", gid, c1.lease_token)
    key = payload_digest(gid, "write_row", {})
    if path == "takeover_update":
        eid = a.begin_effect(p, "write_row", key, takeover_pending=False)[1]
        assert a.mark_effect(eid, "failed")
    seen: dict[str, Any] = {}
    def hook(conn, cursor, statement, params, context, many):
        if not seen and statement.lstrip().upper().startswith(("INSERT INTO CLAIRE_RUNTIME_EFFECTS", "UPDATE CLAIRE_RUNTIME_EFFECTS")):
            seen["c2"] = "pending"
            clk[0] += timedelta(seconds=11)
            seen["c2"] = b.claim("two")
    event.listen(a.engine, "before_cursor_execute", hook)
    status = a.begin_effect(p, "write_row", key, takeover_pending=False)[0]
    event.remove(a.engine, "before_cursor_execute", hook)
    assert seen.get("c2") not in (None, "pending")               # the replacement really happened mid-call
    assert status == "lease_lost"
    effects = b.list_effects("t1", "a1", gid)
    assert [e["state"] for e in effects] == ([] if path == "insert" else ["failed"])
    a.close(); b.close()


# ---- reviewer repair 2: reservation and approval consumption are one atomic step ----------------

def _consumed(store, gid):
    from app.modules.m21_claire.runtime.goals import ApprovalRow
    with store._sessions() as s:
        return [r.consumed_at is not None for r in s.query(ApprovalRow).filter(ApprovalRow.goal_id == gid).all()]


def test_PROTECTION_concurrent_commit_between_classification_and_reservation_replays_without_consuming(store):
    gid = goal(store); p = live(store, gid)
    r = reg(store, make("send_note", person=True))
    key = payload_digest(gid, "send_note", {"target": "a"})
    store.grant("t1", "a1", gid, "send_note", "comms", key, "ap1")
    real = store.begin_effect
    def racing(principal, tool, k, **kw):  # another caller reserves and commits the same effect right before ours
        st, eid, _ = real(principal, tool, k, takeover_pending=False)
        assert st == "new" and store.mark_effect(eid, "committed", {"content": {"by": "other caller"}})
        return real(principal, tool, k, **kw)
    store.begin_effect = racing
    got = run(r.execute(1, "send_note", {"target": "a"}, p))
    assert got.replayed is True and got.content == {"by": "other caller"}
    assert WORLD == {} and _consumed(store, gid) == [False]          # replay ran nothing and spent nothing


def test_PROTECTION_pending_effect_refusal_consumes_no_approval(store):
    gid = goal(store); p = live(store, gid)
    r = reg(store, make("send_note", person=True, mode="oserror_after"))
    key = payload_digest(gid, "send_note", {"target": "a"})
    store.grant("t1", "a1", gid, "send_note", "comms", key, "ap1")
    assert run(r.execute(1, "send_note", {"target": "a"}, p)).error == "OSError"      # spends the first approval
    store.grant("t1", "a1", gid, "send_note", "comms", key, "ap1")
    with pytest.raises(GateRefused) as e:
        run(r.execute(2, "send_note", {"target": "a"}, p))
    assert e.value.reason == "effect_unknown" and sorted(_consumed(store, gid)) == [False, True]


def test_PROTECTION_missing_approval_leaves_no_intent_and_consumes_nothing_partial(store):
    gid = goal(store); p = live(store, gid)
    r = reg(store, make("book_slot", money=True, person=True))
    key = payload_digest(gid, "book_slot", {"target": "a"})
    store.grant("t1", "a1", gid, "book_slot", "comms", key, "ap1")          # the payment gate has no approval
    with pytest.raises(GateRefused) as e:
        run(r.execute(1, "book_slot", {"target": "a"}, p))
    assert e.value.reason == "approval_required" and states(store, gid) == [] and _consumed(store, gid) == [False] and WORLD == {}


@pytest.mark.parametrize("path", ["insert", "takeover_update"])
def test_PROTECTION_lease_replaced_before_the_reservation_write_consumes_no_approval(tmp_path, clk, path):
    from sqlalchemy import event
    url = f"sqlite:///{tmp_path}/r2.db"
    a = GoalStore(url, clock=lambda: clk[0], lease_seconds=10, create_schema=True)
    b = GoalStore(url, clock=lambda: clk[0], lease_seconds=10)
    gid = goal(a); c1 = a.claim("one"); p = Principal("t1", "a1", gid, c1.lease_token)
    key = payload_digest(gid, "send_note", {})
    if path == "takeover_update":
        eid = a.begin_effect(p, "send_note", key, takeover_pending=False)[1]; a.mark_effect(eid, "failed")
    a.grant("t1", "a1", gid, "send_note", "comms", key, "ap1")
    seen: dict[str, Any] = {}
    def hook(conn, cursor, statement, params, context, many):
        if not seen and statement.lstrip().upper().startswith(("INSERT INTO CLAIRE_RUNTIME_EFFECTS", "UPDATE CLAIRE_RUNTIME_EFFECTS")):
            seen["x"] = "pending"; clk[0] += timedelta(seconds=11); seen["x"] = b.claim("two")
    event.listen(a.engine, "before_cursor_execute", hook)
    status = a.begin_effect(p, "send_note", key, takeover_pending=False, gates=("comms",))[0]
    event.remove(a.engine, "before_cursor_execute", hook)
    assert seen["x"] not in (None, "pending") and status == "lease_lost"
    assert _consumed(a, gid) == [False]
    assert [e["state"] for e in b.list_effects("t1", "a1", gid)] == ([] if path == "insert" else ["failed"])
    a.close(); b.close()


def test_PROTECTION_concurrent_transition_before_takeover_update_neither_reserves_nor_consumes(tmp_path, clk):
    from sqlalchemy import event
    url = f"sqlite:///{tmp_path}/r3.db"
    a = GoalStore(url, clock=lambda: clk[0], create_schema=True); b = GoalStore(url, clock=lambda: clk[0])
    gid = goal(a); c1 = a.claim("one"); p = Principal("t1", "a1", gid, c1.lease_token)
    key = payload_digest(gid, "send_note", {})
    eid = a.begin_effect(p, "send_note", key, takeover_pending=False)[1]; a.mark_effect(eid, "failed")
    a.grant("t1", "a1", gid, "send_note", "comms", key, "ap1")
    done: list[Any] = []
    def hook(conn, cursor, statement, params, context, many):
        if not done and statement.lstrip().upper().startswith("UPDATE CLAIRE_RUNTIME_EFFECTS"):
            done.append(1)   # the other handle retries and commits the same effect first
            st, e2, _ = b.begin_effect(p, "send_note", key, takeover_pending=False)
            assert st == "new" and b.mark_effect(e2, "committed", {"content": {}})
    event.listen(a.engine, "before_cursor_execute", hook)
    status = a.begin_effect(p, "send_note", key, takeover_pending=False, gates=("comms",))[0]
    event.remove(a.engine, "before_cursor_execute", hook)
    assert done and status == "pending" and _consumed(a, gid) == [False]
    a.close(); b.close()


# ---- slice 5: resolver identity -----------------------------------------------------------------

# NEW: the resolver is recorded on the journal row and shown in the owner view; reconcile is recorded as the system
def test_NEW_resolver_identity_is_recorded_and_visible(store, client):
    gid, eid, _ = _unknown_effect(store)
    assert resolve_as(client, gid, eid, {"outcome": "committed"}, actor="ap7").status_code == 200
    e = client.get(f"{URL}/{gid}/effects").json()["effects"][0]
    assert e["resolved_by"] == "ap7" and e["self_resolved"] is False


# PROTECTION: the store refuses the goal's own actor and a missing resolver, whatever the route does
def test_PROTECTION_store_refuses_self_resolution_and_blank_resolver(store):
    from app.modules.m21_claire.runtime.goals import SelfApprovalRefused
    gid, eid, _ = _unknown_effect(store)
    with pytest.raises(SelfApprovalRefused):
        store.resolve_effect(gid, eid, "absent", tenant_id="t1", resolver_id="a1")
    for bad in (None, "", " "):
        with pytest.raises(ValueError):
            store.resolve_effect(gid, eid, "absent", tenant_id="t1", resolver_id=bad)
    assert states(store, gid) == ["unknown"]


# NEW: with the escape hatch on, self-resolution is allowed and tagged
def test_NEW_self_resolution_with_escape_hatch_is_tagged(tmp_path):
    solo = GoalStore(f"sqlite:///{tmp_path}/s.db", create_schema=True, owner_may_self_approve=True)
    gid, eid, _ = _unknown_effect(solo)
    assert solo.resolve_effect(gid, eid, "absent", tenant_id="t1", resolver_id="a1") == "resolved"
    e = solo.list_effects("t1", "a1", gid)[0]
    assert e["resolved_by"] == "a1" and e["self_resolved"] is True


# NEW: migration adds resolved_by and refuses to drop it when it holds resolver records
def test_NEW_separation_migration_adds_resolved_by_and_downgrade_guards_data(tmp_path):
    import os, subprocess, sys, sqlite3
    def alembic(db, *a):
        return subprocess.run([sys.executable, "-m", "alembic", *a], env={**os.environ, "ATLAS_DATABASE_URL": f"sqlite:///{db}"},
                              text=True, capture_output=True, timeout=110)
    db = tmp_path / "m.sqlite"
    assert alembic(db, "upgrade", "20261008_m21_runtime_effects").returncode == 0
    con = sqlite3.connect(db)
    assert "resolved_by" not in [r[1] for r in con.execute("PRAGMA table_info(claire_runtime_effects)")]
    con.close()
    assert alembic(db, "upgrade", "head").returncode == 0
    con = sqlite3.connect(db)
    assert "resolved_by" in [r[1] for r in con.execute("PRAGMA table_info(claire_runtime_effects)")]
    con.execute("INSERT INTO claire_runtime_effects (id,tenant_id,actor_id,goal_id,tool,idempotency_key,state,attempts,created_at,updated_at,resolved_by) VALUES ('e','t','a','g','x','k','absent',1,'x','x','ap1')")
    con.commit(); con.close()
    r = alembic(db, "downgrade", "20261008_m21_runtime_effects")
    assert r.returncode != 0 and "resolver records" in r.stderr
