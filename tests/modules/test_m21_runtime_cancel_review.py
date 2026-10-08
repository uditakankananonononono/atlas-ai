# ruff: noqa: F811
"""Slice 7: owner cancel of awaiting_review goals; approvals cannot be granted on terminal goals.

Labels: PROTECTION_* (must stay closed), NEW_* (new capability). Limits: SQLite only; owner-only (no separation of duties);
no new migration; a cancelled goal that has an unresolved effect keeps blocker effect_unknown and stays resolvable.
"""
import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.modules.m21_claire.runtime.goals import ApprovalRow, GoalNotGrantable, GoalRow
from tests.modules.test_m21_runtime_effects import (  # noqa: F401
    CRIT, _clear, clk, goal, live, make, reg, run, set_status, states, store,
)

DIG = hashlib.sha256(b"x").hexdigest()


def awaiting(store, gid, blocker="approval_required"):
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(status="awaiting_review", blocker=blocker, lease_token=None))


def test_NEW_awaiting_review_goal_can_be_cancelled_by_its_owner_cleanly(store):
    gid = goal(store); awaiting(store, gid)
    assert store.cancel("t1", "a1", gid) == "cancelled"
    got = store.get("t1", "a1", gid)
    assert got["status"] == "cancelled" and got["blocker"] is None


@pytest.mark.parametrize("kw", [{}, dict(idempotent=True, accepts=True)])
def test_PROTECTION_cancel_with_a_pending_effect_keeps_effect_unknown_and_resolvable(store, kw):
    gid = goal(store); p = live(store, gid)
    r = reg(store, make(mode="oserror_after", **kw))
    run(r.execute(1, "write_row", {"target": "a"}, p))
    assert states(store, gid) == ["unknown"]
    awaiting(store, gid, "effect_unknown")
    assert store.cancel("t1", "a1", gid) == "cancelled"
    got = store.get("t1", "a1", gid)
    assert got["status"] == "cancelled" and got["blocker"] == "effect_unknown" and states(store, gid) == ["unknown"]
    eid = store.list_effects("t1", "a1", gid)[0]["id"]
    assert store.resolve_effect(gid, eid, "absent", tenant_id="t1", resolver_id="ap1") == "resolved"


def test_PROTECTION_cancel_expires_unused_approvals_and_leaves_consumed_ones(store, clk):
    gid = goal(store)
    a1 = store.grant("t1", "a1", gid, "send_mail", "comms", DIG, approver="ap1")
    a2 = store.grant("t1", "a1", gid, "wire", "payment", DIG, approver="ap1")
    with store._sessions.begin() as s:
        s.execute(update(ApprovalRow).where(ApprovalRow.id == a2).values(consumed_at="2026-10-08T00:00:00+00:00"))
    awaiting(store, gid)
    assert store.cancel("t1", "a1", gid) == "cancelled"
    with store._sessions.begin() as s:
        rows = {r.id: r for r in s.scalars(select(ApprovalRow)).all()}
    assert rows[a1].expires_at <= clk[0].isoformat()          # expired now, not live for its remaining ttl
    assert rows[a1].expires_at < (clk[0] + timedelta(seconds=60)).isoformat()
    assert rows[a2].consumed_at == "2026-10-08T00:00:00+00:00"


def test_PROTECTION_cancel_is_scoped_and_other_terminal_states_stay_409(store):
    gid = goal(store); awaiting(store, gid)
    assert store.cancel("t2", "a1", gid) == "not_found" and store.cancel("t1", "a2", gid) == "not_found"
    assert store.get("t1", "a1", gid)["status"] == "awaiting_review"
    for st in ("completed", "failed", "exhausted", "not_accepted", "blocked", "cancelled"):
        g = goal(store); set_status(store, g, st)
        assert store.cancel("t1", "a1", g) == "not_cancellable", st


def test_PROTECTION_cancelled_goal_cannot_be_requeued_or_claimed(store):
    gid = goal(store); awaiting(store, gid); store.cancel("t1", "a1", gid)
    assert store.requeue("t1", "a1", gid) == "not_requeueable"
    assert store.claim("w1") is None


@pytest.mark.parametrize("st", ["completed", "blocked", "failed", "exhausted", "not_accepted", "cancelled"])
def test_NEW_grant_on_a_terminal_goal_is_refused(store, st):
    gid = goal(store); set_status(store, gid, st)
    with pytest.raises(GoalNotGrantable):
        store.grant("t1", "a1", gid, "send_mail", "comms", DIG, approver="ap1")
    with store._sessions.begin() as s:
        assert s.scalars(select(ApprovalRow)).first() is None


@pytest.mark.parametrize("st", ["queued", "awaiting_review"])
def test_PROTECTION_grant_still_works_on_open_goals(store, st):
    gid = goal(store)
    if st == "awaiting_review":
        awaiting(store, gid)
    assert store.grant("t1", "a1", gid, "send_mail", "comms", DIG, approver="ap1")


def _two_handles(tmp_path, clk):
    from app.modules.m21_claire.runtime.goals import GoalStore
    url = f"sqlite:///{tmp_path}/race.db"
    a = GoalStore(url, clock=lambda: clk[0], create_schema=True); b = GoalStore(url, clock=lambda: clk[0])
    return a, b


def _live_approvals(store, gid):
    with store._sessions.begin() as s:
        return [r for r in s.scalars(select(ApprovalRow).where(ApprovalRow.goal_id == gid)).all() if r.expires_at > store.clock().isoformat()
                and r.consumed_at is None]


def test_PROTECTION_race_cancel_waits_for_an_in_flight_grant_then_expires_it(tmp_path, clk):
    """The reviewer's interleaving (cancel lands while grant is between its status check and its INSERT) must never leave a
    cancelled goal holding a live approval. grant() takes the goal write lock first, so the cancel waits and then expires it."""
    import threading, time
    from sqlalchemy import event
    a, b = _two_handles(tmp_path, clk)
    gid = goal(a); awaiting(a, gid)
    started, out = [], {}

    def do_cancel():
        out["r"] = b.cancel("t1", "a1", gid)

    @event.listens_for(a.engine, "before_cursor_execute")
    def hook(conn, cur, stmt, params, ctx, many):
        if stmt.startswith("INSERT INTO claire_runtime_approvals") and not started:
            started.append(1)
            t = threading.Thread(target=do_cancel); t.start(); out["t"] = t
            time.sleep(0.4)                     # the cancel is now blocked on the goal's write lock
            assert "r" not in out
    aid = a.grant("t1", "a1", gid, "x", "comms", DIG, approver="ap1")
    out["t"].join(10)
    assert out["r"] == "cancelled" and a.get("t1", "a1", gid)["status"] == "cancelled"
    assert _live_approvals(a, gid) == [] and aid
    a.close(); b.close()


def test_PROTECTION_race_grant_after_a_committed_cancel_is_refused_not_inserted(tmp_path, clk):
    from sqlalchemy import event
    a, b = _two_handles(tmp_path, clk)
    gid = goal(a); awaiting(a, gid)
    fired = []

    @event.listens_for(a.engine, "before_cursor_execute")
    def hook(conn, cur, stmt, params, ctx, many):
        if not fired and stmt.startswith("UPDATE claire_runtime_goals"):
            fired.append(1)  # nothing of this grant has run yet: a cancel commits first
            assert b.cancel("t1", "a1", gid) == "cancelled"
    with pytest.raises(GoalNotGrantable):
        a.grant("t1", "a1", gid, "x", "comms", DIG, approver="ap1")
    assert _live_approvals(a, gid) == []
    a.close(); b.close()


def test_NEW_approval_route_201_while_awaiting_then_409_after_cancel(store):
    import json
    from fastapi.testclient import TestClient
    from app.auth.context import TenantContext, require_tenant
    from app.main import app
    gid = goal(store); awaiting(store, gid)
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(report=json.dumps(
            {"refusals": [{"reason": "approval_required", "tool": "send_mail", "gates": ["comms"], "digest": DIG}]})))
    who = {"ctx": TenantContext("t1", "ap1", frozenset({"claire-approver"}))}
    app.dependency_overrides[require_tenant] = lambda: who["ctx"]
    try:
        c = TestClient(app); U = "/api/v1/claire/runtime/goals"
        body = {"capability": "send_mail", "gate": "comms", "digest": DIG}
        assert c.post(f"{U}/{gid}/approvals", json=body).status_code == 201
        who["ctx"] = TenantContext("t1", "a1")
        assert c.post(f"{U}/{gid}/cancel").status_code == 200
        who["ctx"] = TenantContext("t1", "ap1", frozenset({"claire-approver"}))
        res = c.post(f"{U}/{gid}/approvals", json=body)
        assert res.status_code == 409 and "goal_not_grantable" in res.text
        assert _live_approvals(store, gid) == []
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def test_NEW_route_cancel_awaiting_review_is_200_and_grant_on_cancelled_is_409(store):
    from fastapi.testclient import TestClient
    from app.auth.context import TenantContext, require_tenant
    from app.main import app
    who = {"a": "a1", "roles": ()}
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t1", actor_id=who["a"], roles=who["roles"])
    try:
        c = TestClient(app); U = "/api/v1/claire/runtime/goals"
        gid = goal(store); awaiting(store, gid)
        res = c.post(f"{U}/{gid}/cancel")
        assert res.status_code == 200 and res.json()["status"] == "cancelled"
        assert c.post(f"{U}/{gid}/cancel").status_code == 409
    finally:
        app.dependency_overrides.pop(require_tenant, None)
