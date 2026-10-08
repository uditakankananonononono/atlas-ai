# ruff: noqa: F811
"""Slice 11: the goal's designated approvers also bind owner attestations (resolve_effect with a tenant).

Labels: PROTECTION_* (answers and paths that must not change), NEW_*, CONVERTED_* (slice 10 pinned the opposite).
CONVERTED: the slice 10 pin 'an outsider can still resolve_effect' is replaced by NEW_outsider_is_refused_* below.
Limits: SQLite only; list immutable; the runtime's own reconcile path (tenant_id=None, tool-proven outcome) is deliberately
not bound; ids trusted from the authenticated contract.
"""
import json
import threading
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.auth.context import TenantContext, require_tenant
from app.main import app
from app.modules.m21_claire.runtime.goals import ApproverNotDesignated, EffectRow, GoalRow, SelfApprovalRefused
from tests.modules.test_m21_runtime_effects import (CRIT, URL, WORLD, Boom, Script, _clear, call, clk, final, live, make, reg, run,  # noqa: F401
                                                    set_status, states, store, worker)


def unknown(store, designated, *, name="write_row"):
    gid = store.create("t1", "a1", "do work", CRIT, 6, designated_approvers=designated)
    p = live(store, gid)
    assert run(reg(store, make(name, mode="oserror_after")).execute(1, name, {"target": "a"}, p)).error == "OSError"
    eid = store.list_effects("t1", "a1", gid)[0]["id"]
    set_status(store, gid, "awaiting_review")
    return gid, eid


def row(store, eid):
    with store._sessions() as s:
        r = s.get(EffectRow, eid)
        return r.state, r.resolved_by, r.receipt_json, r.attempts, r.updated_at


def res(store, gid, eid, who, outcome="absent", **kw):
    return store.resolve_effect(gid, eid, outcome, tenant_id="t1", resolver_id=who, **kw)


@pytest.mark.parametrize("outcome", ["committed", "absent"])
def test_NEW_outsider_is_refused_and_nothing_changes_both_outcomes(store, outcome):
    gid, eid = unknown(store, ["ap1"])
    before = row(store, eid)
    with pytest.raises(ApproverNotDesignated) as e:
        res(store, gid, eid, "outsider", outcome, receipt={"content": {"x": 1}})
    assert "ap1" not in str(e.value) and "outsider" not in str(e.value)
    assert row(store, eid) == before and row(store, eid)[0] == "unknown" and row(store, eid)[1] is None


@pytest.mark.parametrize("outcome", ["committed", "absent"])
def test_NEW_designated_resolver_succeeds_and_is_recorded(store, outcome):
    gid, eid = unknown(store, ["ap1", "ap2"])
    assert res(store, gid, eid, "ap2", outcome) == "resolved"
    assert row(store, eid)[:2] == (outcome, "ap2")


def test_PROTECTION_null_list_is_exactly_the_old_behaviour(store):
    gid, eid = unknown(store, None)
    with pytest.raises(SelfApprovalRefused):
        res(store, gid, eid, "a1")
    assert res(store, gid, eid, "anyone") == "resolved"


@pytest.mark.parametrize("raw", ["[]", "not json", '"ap"', "null", '["ap", ""]', '["ap", " x"]', '["ap", "x "]', '["ap", "ap"]',
                                 json.dumps(["ap"] + ["a%d" % i for i in range(20)]), json.dumps(["ap", "y" * 201]), '["ap", 1]', '[["ap"]]'])
def test_NEW_empty_corrupt_or_schema_invalid_stored_list_denies_everyone_including_a_listed_member(store, raw):
    gid, eid = unknown(store, ["ap"])
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(designated_approvers=raw))
    before = row(store, eid)
    for who in ("ap", "other"):
        with pytest.raises(ApproverNotDesignated):
            res(store, gid, eid, who)
    assert row(store, eid) == before


def test_PROTECTION_existing_answers_survive_for_an_outsider_and_designation_is_checked_last(store):
    gid, eid = unknown(store, ["ap1"])
    assert res(store, gid, eid, "ap1") == "resolved"
    before = row(store, eid)
    assert res(store, gid, eid, "outsider") == "not_pending"                    # already resolved: same answer as before slice 11
    assert row(store, eid) == before
    gid2, eid2 = unknown(store, ["ap1"])
    set_status(store, gid2, "running")
    assert res(store, gid2, eid2, "outsider", require_not_running=True) == "goal_running"   # running: same answer
    assert row(store, eid2)[0] == "unknown"
    assert res(store, gid2, "no-such-effect", "outsider") == "not_found"
    assert res(store, "no-such-goal", eid2, "outsider") == "not_found"
    with pytest.raises(SelfApprovalRefused):
        res(store, gid2, eid2, "a1")                                           # actor, not in list: self-approval answer, not designation


def test_NEW_terminal_goal_with_a_pending_effect_is_still_resolvable_by_a_designated_resolver_only(store):
    for terminal in ("cancelled", "failed", "blocked"):
        gid, eid = unknown(store, ["ap1"])
        set_status(store, gid, terminal)
        with pytest.raises(ApproverNotDesignated):
            res(store, gid, eid, "outsider")
        assert res(store, gid, eid, "ap1") == "resolved"          # NOT_GRANTABLE is deliberately not applied here


def test_NEW_wrong_tenant_and_mismatched_goal_never_touch_the_row(store):
    gid, eid = unknown(store, ["ap1"])
    gid2, eid2 = unknown(store, ["ap1"])
    before = (row(store, eid), row(store, eid2))
    assert store.resolve_effect(gid, eid, "absent", tenant_id="t2", resolver_id="ap1") == "not_found"
    assert store.resolve_effect(gid2, eid, "absent", tenant_id="t1", resolver_id="ap1") == "not_found"   # effect belongs to another goal
    assert (row(store, eid), row(store, eid2)) == before


def test_NEW_self_approve_flag_does_not_waive_the_list(store):
    gid, eid = unknown(store, ["ap1"])
    store.owner_may_self_approve = True
    try:
        with pytest.raises(ApproverNotDesignated):
            res(store, gid, eid, "a1")
        gid2, eid2 = unknown(store, ["a1"])
        assert res(store, gid2, eid2, "a1") == "resolved"
    finally:
        store.owner_may_self_approve = False


def test_NEW_resolver_string_system_reconcile_is_not_an_exemption_on_the_owner_path(store):
    gid, eid = unknown(store, ["ap1"])
    with pytest.raises(ApproverNotDesignated):
        res(store, gid, eid, "system:reconcile")
    assert row(store, eid)[0] == "unknown"
    assert store.resolve_effect(gid, eid, "absent") == "resolved"                # only the internal path (no tenant) is unbound
    assert row(store, eid)[:2] == ("absent", "system:reconcile")


@pytest.mark.parametrize("raw", [None, "["+'"ap1"'+"]", "[]", "not json", '["ap1", ""]'])
@pytest.mark.parametrize("answer", ["committed", "absent"])
def test_PROTECTION_runtime_reconcile_still_resolves_for_restricted_and_corrupt_lists(store, clk, raw, answer):
    r = reg(store, make(mode="crash_after", reconcile=lambda key: answer))
    gid = store.create("t1", "a1", "do work", CRIT, 6, designated_approvers=["ap1"])
    with pytest.raises(Boom):
        run(worker(store, Script(call("write_row", target="a")), r, "w1").run_once())
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(designated_approvers=raw))
    clk[0] += timedelta(seconds=200)
    run(worker(store, Script(final()), r, "w2").run_once())
    assert states(store, gid) == [answer]
    with store._sessions() as s:
        assert s.query(EffectRow).filter_by(goal_id=gid).one().resolved_by == "system:reconcile"


def test_NEW_route_403_for_outsider_200_for_designated_and_body_cannot_name_the_resolver(store):
    gid, eid = unknown(store, ["ap1"])
    who = {"ctx": TenantContext("t1", "outsider", frozenset({"claire-approver"}))}
    from tests.modules.test_m21_runtime_gates import _client
    c = _client(who)
    try:
        r = c.post(f"{URL}/{gid}/effects/{eid}/resolve", json={"outcome": "absent", "resolver_id": "ap1", "tenant_id": "t1"})
        assert r.status_code == 403 and r.json()["detail"] == "approver_not_designated" and "ap1" not in r.text
        assert row(store, eid)[0] == "unknown"
        who["ctx"] = TenantContext("t1", "ap1", frozenset({"claire-approver"}))
        ok = c.post(f"{URL}/{gid}/effects/{eid}/resolve", json={"outcome": "absent"})
        assert ok.status_code == 200 and row(store, eid)[:2] == ("absent", "ap1")
        assert c.post(f"{URL}/{gid}/effects/{eid}/resolve", json={"outcome": "absent"}).status_code == 409
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def test_NEW_resolve_races_cancel_without_a_half_written_row(store):
    for _ in range(5):
        gid, eid = unknown(store, ["ap1"])
        set_status(store, gid, "awaiting_review")
        out = []

        def go(gid=gid, eid=eid, out=out):
            out.append(res(store, gid, eid, "ap1"))
        t = threading.Thread(target=go)
        t.start(); store.cancel("t1", "a1", gid); t.join()
        assert out == ["resolved"] and row(store, eid)[:2] == ("absent", "ap1")
        assert store.get("t1", "a1", gid)["status"] == "cancelled"
