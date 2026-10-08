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
