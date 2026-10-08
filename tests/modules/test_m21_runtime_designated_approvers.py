# ruff: noqa: F811
"""Slice 10: a goal may name the principals allowed to approve its gated calls.

Labels: PROTECTION_* (must stay closed / unchanged), NEW_*.
Limits: SQLite only; the list is immutable after creation (no edit API); principal ids are trusted as supplied by Claire's
authenticated contract; resolve_effect (unknown-effect resolution) is NOT bound to the list in this slice; the self-approve
flag stays default OFF and the list does not widen it.
"""
import json
import sqlite3
import subprocess
import sys
import threading

import pytest
from sqlalchemy import update

from app.auth.context import TenantContext, require_tenant
from app.main import app
from app.modules.m21_claire.runtime.goals import (GoalNotGrantable, GoalRow, GoalStore, ApproverNotDesignated,
                                                  SelfApprovalRefused, normalize_designated)
from tests.modules.test_m21_runtime_gates import (CRIT, URL, Script, _client, call, final, make, registry, run, work,  # noqa: F401
                                                  reset, store, t0)


def refused(store, designated):
    gid = store.create("t1", "a1", "do work", CRIT, 6, designated_approvers=designated)
    run(work(store, Script(call("send_email", target="bob"), final()), registry(store, make("send_email", person=True))).run_once())
    return gid, store.get("t1", "a1", gid)["report"]["refusals"][0]


def g(store, gid, ref, who):
    return store.grant("t1", "a1", gid, "send_email", "comms", ref["digest"], who)


# PROTECTION: no list, or an empty one, is exactly today's behaviour
@pytest.mark.parametrize("d", [None, [], ()])
def test_PROTECTION_no_list_means_any_distinct_approver_as_before(store, d):
    gid, ref = refused(store, d)
    assert g(store, gid, ref, "anyone")
    with pytest.raises(SelfApprovalRefused):
        g(store, gid, ref, "a1")
    assert store.get("t1", "a1", gid)["approver_restricted"] is False


def test_NEW_only_designated_principals_may_grant_others_are_refused_and_no_row_is_written(store):
    gid, ref = refused(store, ["ap1", "ap2"])
    with pytest.raises(ApproverNotDesignated) as e:
        g(store, gid, ref, "ap9")
    assert "ap9" not in str(e.value) and "ap1" not in str(e.value)
    with store._sessions() as s:
        from app.modules.m21_claire.runtime.goals import ApprovalRow
        assert s.query(ApprovalRow).count() == 0
    assert g(store, gid, ref, "ap1") and g(store, gid, ref, "ap2")
    assert store.get("t1", "a1", gid)["approver_restricted"] is True


def test_NEW_ids_match_exactly_not_by_case_or_whitespace_or_prefix(store):
    gid, ref = refused(store, ["ap1"])
    for who in ("AP1", "ap1 ", " ap1", "ap", "ap10", "ap1\u200b"):
        with pytest.raises(ApproverNotDesignated):
            g(store, gid, ref, who)


def test_NEW_actor_in_the_list_is_still_a_self_approval_and_the_flag_does_not_waive_the_list(store, tmp_path, t0):
    gid, ref = refused(store, ["a1", "ap1"])
    with pytest.raises(SelfApprovalRefused):
        g(store, gid, ref, "a1")
    s2 = GoalStore(f"sqlite:///{tmp_path}/o.db", clock=lambda: t0[0], create_schema=True, owner_may_self_approve=True)
    try:
        gid2 = s2.create("t1", "a1", "p", CRIT, 2, designated_approvers=["ap1"])
        with s2._sessions.begin() as s:
            s.execute(update(GoalRow).where(GoalRow.id == gid2).values(status="awaiting_review"))
        with pytest.raises(ApproverNotDesignated):
            s2.grant("t1", "a1", gid2, "send_email", "comms", "d" * 64, "a1")  # flag on, but a1 is not in the list
        gid3 = s2.create("t1", "a1", "p", CRIT, 2, designated_approvers=["a1"])
        with s2._sessions.begin() as s:
            s.execute(update(GoalRow).where(GoalRow.id == gid3).values(status="awaiting_review"))
        assert s2.grant("t1", "a1", gid3, "send_email", "comms", "d" * 64, "a1")
    finally:
        s2.close()


@pytest.mark.parametrize("bad", ["ap1", {"ap1"}, [1], [True], [None], [""], ["  "], [" ap1"], ["ap1 "], ["x" * 201],
                                 ["a%d" % i for i in range(21)], [["ap1"]], b"ap1", 5, True])
def test_NEW_validation_is_strict(store, bad):
    with pytest.raises(ValueError):
        store.create("t1", "a1", "p", CRIT, 2, designated_approvers=bad)


def test_NEW_dedup_keeps_order_and_twenty_is_allowed():
    assert normalize_designated(["b", "a", "b"]) == ["b", "a"]
    assert len(normalize_designated(["a%d" % i for i in range(20)])) == 20
    assert normalize_designated([]) is None and normalize_designated(None) is None


def test_NEW_corrupt_stored_list_fails_closed(store):
    gid, ref = refused(store, ["ap1"])
    for raw in ("not json", '"ap1"', "[1]", '{"a":1}', "null"):
        with store._sessions.begin() as s:
            s.execute(update(GoalRow).where(GoalRow.id == gid).values(designated_approvers=raw))
        with pytest.raises(ApproverNotDesignated):
            g(store, gid, ref, "ap1")


def test_PROTECTION_terminal_goal_is_still_not_grantable_and_unknown_goal_still_keyerror(store):
    gid, ref = refused(store, ["ap1"])
    store.cancel("t1", "a1", gid)
    with pytest.raises(GoalNotGrantable):
        g(store, gid, ref, "ap1")
    with pytest.raises(GoalNotGrantable):
        g(store, gid, ref, "ap9")  # terminal wins over designation: no information about the list leaks
    with pytest.raises(KeyError):
        store.grant("t1", "a1", "nope", "send_email", "comms", "d" * 64, "ap1")


def test_NEW_grant_vs_cancel_race_still_leaves_no_live_approval_on_a_cancelled_goal(store):
    for _ in range(5):
        gid, ref = refused(store, ["ap1"])
        t = threading.Thread(target=_try, args=(lambda gid=gid, ref=ref: g(store, gid, ref, "ap1"),))
        t.start(); store.cancel("t1", "a1", gid); t.join()
        from app.modules.m21_claire.runtime.goals import ApprovalRow
        with store._sessions() as s:
            live = [a for a in s.query(ApprovalRow).filter_by(goal_id=gid) if a.consumed_at is None and a.expires_at > store.clock().isoformat()]
        assert store.get("t1", "a1", gid)["status"] == "cancelled" and live == []


def _try(f):
    try:
        return f()
    except (GoalNotGrantable, ApproverNotDesignated):
        return None


def test_NEW_route_create_validation_and_restricted_flag_only(store):
    who = {"ctx": TenantContext("t1", "a1")}
    c = _client(who)
    body = {"purpose": "do the work", "acceptance_criteria": CRIT, "designated_approvers": ["ap1", "ap2"]}
    try:
        r = c.post(URL, json=body)
        assert r.status_code == 201 and r.json()["approver_restricted"] is True
        assert "ap1" not in json.dumps(r.json()) and "designated_approvers" not in r.json()
        for bad in ([""], [" x"], [5], "ap1", ["a%d" % i for i in range(21)], [" bad"]):
            assert c.post(URL, json={**body, "designated_approvers": bad}).status_code == 422
        assert c.post(URL, json={k: v for k, v in body.items() if k != "designated_approvers"}).json()["approver_restricted"] is False
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def test_NEW_route_approve_designated_vs_not_and_view_never_lists_ids(store):
    gid, ref = refused(store, ["ap1"])
    b = {"capability": "send_email", "gate": "comms", "digest": ref["digest"]}
    who = {"ctx": TenantContext("t1", "ap9", frozenset({"claire-approver"}))}
    c = _client(who)
    try:
        r = c.post(f"{URL}/{gid}/approvals", json=b)
        assert r.status_code == 403 and r.json()["detail"] == "approver_not_designated" and "ap1" not in r.text
        v = c.get(f"{URL}/{gid}/approver-view")
        assert v.status_code == 200 and v.json()["approver_restricted"] is True and "ap1" not in v.text
        who["ctx"] = TenantContext("t1", "ap1")  # designated but no approver role: the role check still applies
        assert c.post(f"{URL}/{gid}/approvals", json=b).status_code == 403
        who["ctx"] = TenantContext("t1", "ap1", frozenset({"claire-approver"}))
        assert c.post(f"{URL}/{gid}/approvals", json=b).status_code == 201
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def _alembic(db, *args):
    import os
    env = {**os.environ, "ATLAS_DATABASE_URL": f"sqlite:///{db}"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], env=env, text=True, capture_output=True, timeout=110)


def test_NEW_migration_is_additive_idempotent_and_refuses_to_drop_data(tmp_path):
    db = tmp_path / "m.sqlite"
    assert _alembic(db, "upgrade", "20261008_m21_runtime_cancel").returncode == 0
    con = sqlite3.connect(db)
    con.execute("insert into claire_runtime_goals (id,tenant_id,actor_id,purpose,criteria,max_steps,status,attempts,created_at,updated_at) "
                "values ('g1','t','a','p','[]',1,'queued',0,'x','x')")
    con.commit(); con.close()
    assert _alembic(db, "upgrade", "20261008_m21_runtime_designated").returncode == 0
    con = sqlite3.connect(db)
    assert con.execute("select designated_approvers from claire_runtime_goals where id='g1'").fetchone() == (None,)  # existing goals unrestricted
    con.execute("update claire_runtime_goals set designated_approvers='[\"ap1\"]'"); con.commit(); con.close()
    r = _alembic(db, "downgrade", "20261008_m21_runtime_cancel")
    assert r.returncode != 0 and "approver restrictions" in r.stderr
    con = sqlite3.connect(db); con.execute("update claire_runtime_goals set designated_approvers=NULL"); con.commit(); con.close()
    assert _alembic(db, "downgrade", "20261008_m21_runtime_cancel").returncode == 0
    assert _alembic(db, "upgrade", "20261008_m21_runtime_designated").returncode == 0
