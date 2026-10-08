# ruff: noqa: F811
"""Slice 12: withdraw an unused approval (and list approval state) with the same audience gate as every other approval act.

Labels: PROTECTION_* (must not change), NEW_*. 'Base' for NEW tests is an unmet capability: no revoke or list path existed, so a live
approval simply stayed consumable until its TTL or a whole-goal cancel; that was not an exploitable-permission bug.
Limits: SQLite only (races use independent connections but this is not a real-PG concurrency proof); revoking one approval does NOT stop
dispatch when another matching live grant exists; a consumed approval is never un-consumed; ids trusted from the authenticated contract.
"""
import os
import sqlite3
import subprocess
import sys
import threading
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.auth.context import TenantContext, require_tenant
from app.main import app
from app.modules.m21_claire.runtime.gates import GateRefused, payload_digest
from app.modules.m21_claire.runtime.goals import ApprovalRow, ApproverNotDesignated, GoalRow, GoalStore, RevokeNotAuthorized
from tests.modules.test_m21_runtime_effects import (CRIT, URL, WORLD, _clear, clk, live, make, reg, run, set_status, store)  # noqa: F401


def setup(store, designated=None, *, name="send_note", money=False, gates=("comms",), args=None):
    args = args or {"target": "a"}
    gid = store.create("t1", "a1", "do work", CRIT, 6, designated_approvers=designated)
    d = payload_digest(gid, name, args)
    aids = {g: store.grant("t1", "a1", gid, name, g, d, "ap1" if designated is None else designated[0]) for g in gates}
    return gid, d, aids


def rev(store, gid, aid, who, role=False, tenant="t1"):
    return store.revoke_approval(tenant, gid, aid, who, approver_role=role)


def arow(store, aid):
    with store._sessions() as s:
        r = s.get(ApprovalRow, aid)
        return r.consumed_at, r.revoked_at, r.revoked_by, r.expires_at


def tool(**kw):
    return make("send_note", person=True, **kw)


def test_NEW_owner_revokes_without_a_role_and_the_gated_call_is_then_refused(store):
    gid, d, aids = setup(store)
    assert rev(store, gid, aids["comms"], "a1") == "revoked"
    c, ra, rb, ex = arow(store, aids["comms"])
    assert c is None and ra is not None and rb == "a1" and ex == ra          # both fields together, expiry pulled to now
    with pytest.raises(GateRefused) as e:
        run(reg(store, tool()).execute(1, "send_note", {"target": "a"}, live(store, gid)))
    assert e.value.reason == "approval_required" and WORLD == {}


def test_NEW_nonowner_needs_the_approver_role_and_designation_before_anything_is_read(store):
    gid, d, aids = setup(store, ["ap1"])
    snap = arow(store, aids["comms"])
    with pytest.raises(RevokeNotAuthorized):
        rev(store, gid, aids["comms"], "ap1", role=False)                 # designated but no role
    with pytest.raises(RevokeNotAuthorized):
        rev(store, gid, "no-such-approval", "ap1", role=False)            # generic 403 even for an unknown approval id
    with pytest.raises(ApproverNotDesignated) as e:
        rev(store, gid, aids["comms"], "outsider", role=True)             # role but not designated
    assert "ap1" not in str(e.value) and "outsider" not in str(e.value)
    with pytest.raises(ApproverNotDesignated):
        rev(store, gid, "no-such-approval", "outsider", role=True)        # designation precedes existence/state classification
    assert arow(store, aids["comms"]) == snap
    assert rev(store, gid, aids["comms"], "ap1", role=True) == "revoked"
    assert arow(store, aids["comms"])[2] == "ap1"


def test_NEW_null_list_lets_any_role_holding_nonowner_revoke(store):
    gid, d, aids = setup(store)
    assert rev(store, gid, aids["comms"], "anyone", role=True) == "revoked"


@pytest.mark.parametrize("raw", ["[]", "not json", '["ap1", ""]', '["ap1", "ap1"]', '["ap1", " x"]', '["ap1", 1]'])
def test_NEW_corrupt_list_gives_a_nonowner_a_generic_denial_even_for_a_consumed_approval_and_owner_still_works(store, raw):
    gid, d, aids = setup(store, ["ap1"])
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(designated_approvers=raw))
        s.execute(update(ApprovalRow).where(ApprovalRow.id == aids["comms"]).values(consumed_at="2026-10-08T00:00:00+00:00"))
    with pytest.raises(ApproverNotDesignated):
        rev(store, gid, aids["comms"], "ap1", role=True)
    assert rev(store, gid, aids["comms"], "a1") == "already_consumed"      # owner authority is independent of the list
    assert store.list_approvals("t1", gid, "a1")[0]["state"] == "consumed"
    with pytest.raises(ApproverNotDesignated):
        store.list_approvals("t1", gid, "ap1", approver_role=True)


def test_NEW_classification_precedence_not_found_consumed_revoked_expired(store, clk):
    gid, d, aids = setup(store, gates=("comms", "payment"), name="pay_msg", money=True)
    c, p = aids["comms"], aids["payment"]
    assert rev(store, gid, "nope", "a1") == "not_found"
    with store._sessions.begin() as s:
        s.execute(update(ApprovalRow).where(ApprovalRow.id == p).values(consumed_at="2026-10-08T00:00:01+00:00"))
    assert rev(store, gid, p, "a1") == "already_consumed" and arow(store, p)[1] is None and arow(store, p)[2] is None   # no new audit fields
    assert rev(store, gid, c, "a1") == "revoked"
    first = arow(store, c)
    clk[0] += timedelta(days=2)                                              # now far past the original TTL
    assert rev(store, gid, c, "a1") == "already_revoked"                     # revoked beats expired
    assert arow(store, c) == first
    gid2, d2, aids2 = setup(store)
    clk[0] += timedelta(days=2)
    assert rev(store, gid2, aids2["comms"], "a1") == "expired" and arow(store, aids2["comms"])[1:3] == (None, None)


def test_PROTECTION_expiry_boundary_now_equal_to_expires_at_is_expired_not_revocable(store, clk):
    gid, d, aids = setup(store)
    with store._sessions() as s:
        exp = s.get(ApprovalRow, aids["comms"]).expires_at
    from datetime import datetime
    clk[0] = datetime.fromisoformat(exp)
    assert rev(store, gid, aids["comms"], "a1") == "expired"
    clk[0] -= timedelta(seconds=1)
    assert rev(store, gid, aids["comms"], "a1") == "revoked"


def test_NEW_wrong_tenant_goal_or_approval_of_another_goal_is_not_found_and_changes_nothing(store):
    gid, d, aids = setup(store)
    gid2, d2, aids2 = setup(store)
    snap = (arow(store, aids["comms"]), arow(store, aids2["comms"]))
    assert rev(store, gid, aids["comms"], "a1", tenant="t2") == "not_found"
    assert rev(store, "no-goal", aids["comms"], "a1") == "not_found"
    assert rev(store, gid, aids2["comms"], "a1") == "not_found"              # approval belongs to a different goal
    assert store.list_approvals("t2", gid, "a1") is None and store.list_approvals("t1", "no-goal", "a1") is None
    assert (arow(store, aids["comms"]), arow(store, aids2["comms"])) == snap


def test_NEW_revocation_works_on_terminal_goals_and_survives_cancel_and_expiry(store, clk):
    gid, d, aids = setup(store, gates=("comms", "payment"), name="pay_msg", money=True)
    assert rev(store, gid, aids["comms"], "a1") == "revoked"
    before = arow(store, aids["comms"])
    clk[0] += timedelta(minutes=5)
    set_status(store, gid, "awaiting_review")
    assert store.cancel("t1", "a1", gid) == "cancelled"                      # _expire_unused kills the other approval, not the tombstone
    assert arow(store, aids["comms"]) == before
    assert arow(store, aids["payment"])[1] is None                           # expired by cancel, never mislabelled revoked
    states = {a["id"]: a["state"] for a in store.list_approvals("t1", gid, "a1")}
    assert states == {aids["comms"]: "revoked", aids["payment"]: "expired"}
    gid2, d2, aids2 = setup(store)
    set_status(store, gid2, "failed")
    assert rev(store, gid2, aids2["comms"], "a1") == "revoked"


def test_PROTECTION_a_consumed_approval_is_never_refunded_or_unconsumed_and_the_journal_is_untouched(store):
    gid, d, aids = setup(store)
    assert run(reg(store, tool()).execute(1, "send_note", {"target": "a"}, live(store, gid))).ok
    consumed = arow(store, aids["comms"])
    effects = store.list_effects("t1", "a1", gid)
    assert rev(store, gid, aids["comms"], "a1") == "already_consumed"
    assert arow(store, aids["comms"]) == consumed and store.list_effects("t1", "a1", gid) == effects


def test_PROTECTION_revoking_one_id_does_not_stop_dispatch_when_another_matching_live_grant_exists(store):
    gid, d, aids = setup(store)
    second = store.grant("t1", "a1", gid, "send_note", "comms", d, "ap2")
    assert rev(store, gid, aids["comms"], "a1") == "revoked"
    assert run(reg(store, tool()).execute(1, "send_note", {"target": "a"}, live(store, gid))).ok         # the other grant is consumed
    assert arow(store, second)[0] is not None


def test_NEW_multi_gate_dispatch_with_one_revoked_gate_rolls_back_the_other_consumption(store):
    gid, d, aids = setup(store, gates=("comms", "payment"), name="pay_msg", money=True)
    t = make("pay_msg", money=True, person=True)
    assert rev(store, gid, aids["comms"], "a1") == "revoked"
    with pytest.raises(GateRefused):
        run(reg(store, t).execute(1, "pay_msg", {"target": "a"}, live(store, gid)))
    assert arow(store, aids["payment"])[0] is None                            # all-or-nothing: the payment approval was not spent
    assert arow(store, aids["comms"])[1] is not None and WORLD == {} and store.list_effects("t1", "a1", gid) == []


def test_NEW_revoke_then_consume_and_consume_then_revoke_each_have_exactly_one_winner(store):
    gid, d, aids = setup(store)
    from app.modules.m21_claire.runtime.gates import Principal
    p = Principal("t1", "a1", gid, "x")
    assert rev(store, gid, aids["comms"], "a1") == "revoked"
    assert store.consume_all(p, "send_note", d, ("comms",)) is False
    gid2, d2, aids2 = setup(store)
    p2 = Principal("t1", "a1", gid2, "x")
    assert store.consume_all(p2, "send_note", d2, ("comms",)) is True
    assert rev(store, gid2, aids2["comms"], "a1") == "already_consumed"


def test_NEW_consume_refuses_a_revoked_row_even_if_its_expiry_is_still_in_the_future(store):
    # defence in depth: revocation also pulls expires_at to now, but both consume predicates (subquery AND outer UPDATE) check revoked_at
    from app.modules.m21_claire.runtime.gates import Principal
    gid, d, aids = setup(store)
    with store._sessions.begin() as s:
        s.execute(update(ApprovalRow).where(ApprovalRow.id == aids["comms"]).values(revoked_at="2026-10-08T00:00:00+00:00", revoked_by="x"))
    assert store.consume_all(Principal("t1", "a1", gid, "x"), "send_note", d, ("comms",)) is False
    assert arow(store, aids["comms"])[0] is None
    assert store.list_approvals("t1", gid, "a1")[0]["state"] == "revoked"
    live2 = store.grant("t1", "a1", gid, "send_note", "comms", d, "ap2")          # a live twin: the revoked row must not shadow it
    assert store.consume_all(Principal("t1", "a1", gid, "x"), "send_note", d, ("comms",)) is True
    assert arow(store, live2)[0] is not None and arow(store, aids["comms"])[0] is None


def test_NEW_threaded_race_on_independent_connections_never_double_wins(tmp_path, clk):
    from app.modules.m21_claire.runtime.gates import Principal
    url = f"sqlite:///{tmp_path}/race.db"
    a = GoalStore(url, clock=lambda: clk[0], create_schema=True)
    b = GoalStore(url, clock=lambda: clk[0])
    try:
        tally = {"revoked": 0, "consumed": 0}
        for _ in range(20):
            gid, d, aids = setup(a)
            out = {}
            barrier = threading.Barrier(2)

            def do_rev(gid=gid, aid=aids["comms"], out=out, barrier=barrier):
                barrier.wait()
                out["r"] = rev(a, gid, aid, "a1")

            def do_con(gid=gid, d=d, out=out, barrier=barrier):
                barrier.wait()
                out["c"] = b.consume_all(Principal("t1", "a1", gid, "x"), "send_note", d, ("comms",))
            ts = [threading.Thread(target=do_rev), threading.Thread(target=do_con)]
            [t.start() for t in ts]; [t.join() for t in ts]
            c, ra, rb, ex = arow(a, aids["comms"])
            assert (out["r"] == "revoked") != (out["c"] is True)              # exactly one winner
            assert out["r"] in ("revoked", "already_consumed")
            assert not (c and ra)                                             # never both consumed and revoked
            tally["revoked" if out["r"] == "revoked" else "consumed"] += 1
        assert sum(tally.values()) == 20
    finally:
        a.close(); b.close()


def test_NEW_list_state_precedence_audience_and_no_digest(store, clk):
    gid, d, aids = setup(store, ["ap1"], gates=("comms", "payment"), name="pay_msg", money=True)
    third = store.grant("t1", "a1", gid, "pay_msg", "comms", d, "ap1")
    with store._sessions.begin() as s:
        s.execute(update(ApprovalRow).where(ApprovalRow.id == aids["payment"]).values(consumed_at="2026-10-08T00:00:02+00:00", revoked_at="2026-10-08T00:00:03+00:00", revoked_by="x"))
    assert rev(store, gid, aids["comms"], "ap1", role=True) == "revoked"
    got = {x["id"]: x for x in store.list_approvals("t1", gid, "a1")}
    assert got[aids["payment"]]["state"] == "consumed"                       # consumed beats revoked
    assert got[aids["comms"]]["state"] == "revoked" and got[third]["state"] == "live"
    assert all("digest" not in x and "payload_digest" not in x for x in got.values())
    clk[0] += timedelta(days=2)
    assert {x["state"] for x in store.list_approvals("t1", gid, "a1")} == {"consumed", "revoked", "expired"}
    with pytest.raises(RevokeNotAuthorized):
        store.list_approvals("t1", gid, "ap1")
    with pytest.raises(ApproverNotDesignated):
        store.list_approvals("t1", gid, "outsider", approver_role=True)


def test_NEW_routes_derive_the_revoker_from_the_context_and_never_the_body(store):
    from tests.modules.test_m21_runtime_gates import _client
    gid, d, aids = setup(store, ["ap1"])
    who = {"ctx": TenantContext("t1", "outsider", frozenset({"claire-approver"}))}
    c = _client(who)
    u = f"{URL}/{gid}/approvals/{aids['comms']}/revoke"
    try:
        r = c.post(u, json={"revoked_by": "ap1", "revoker_id": "a1", "tenant_id": "t1"})
        assert r.status_code == 403 and r.json()["detail"] == "approver_not_designated" and "ap1" not in r.text
        assert c.get(f"{URL}/{gid}/approvals").status_code == 403
        who["ctx"] = TenantContext("t1", "ap1")                              # designated but no role
        assert c.post(u).status_code == 403 and c.get(f"{URL}/{gid}/approvals").status_code == 403
        who["ctx"] = TenantContext("t1", "a1")                               # owner, no role
        listing = c.get(f"{URL}/{gid}/approvals")
        assert listing.status_code == 200 and "digest" not in listing.text and listing.json()["approvals"][0]["state"] == "live"
        ok = c.post(u, json={"revoked_by": "somebody-else"})
        assert ok.status_code == 200 and arow(store, aids["comms"])[2] == "a1"
        assert c.post(u).status_code == 409 and c.post(u).json()["detail"] == "already_revoked"
        assert c.post(f"{URL}/{gid}/approvals/nope/revoke").status_code == 404
        who["ctx"] = TenantContext("t2", "a1")
        assert c.post(u).status_code == 404 and c.get(f"{URL}/{gid}/approvals").status_code == 404
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def _alembic(db, *args):
    return subprocess.run([sys.executable, "-m", "alembic", *args], env={**os.environ, "ATLAS_DATABASE_URL": f"sqlite:///{db}"},
                          text=True, capture_output=True, timeout=110)


def test_NEW_migration_additive_idempotent_shape_checked_and_never_drops_provenance(tmp_path):
    db = tmp_path / "m.sqlite"
    assert _alembic(db, "upgrade", "20261008_m21_runtime_designated").returncode == 0
    con = sqlite3.connect(db)
    con.execute("insert into claire_runtime_approvals (id,tenant_id,actor_id,goal_id,capability,gate,payload_digest,approver,expires_at,created_at) "
                "values ('x','t','a','g','c','comms','d','ap','2030','2026')")
    con.commit(); con.close()
    assert _alembic(db, "upgrade", "20261008_m21_runtime_revoke").returncode == 0
    con = sqlite3.connect(db)
    assert con.execute("select revoked_at,revoked_by from claire_runtime_approvals").fetchone() == (None, None)
    con.execute("update claire_runtime_approvals set revoked_by='ap'"); con.commit(); con.close()           # partial tombstone
    r = _alembic(db, "downgrade", "20261008_m21_runtime_designated")
    assert r.returncode != 0 and "revocation provenance" in r.stderr
    con = sqlite3.connect(db); con.execute("update claire_runtime_approvals set revoked_by=NULL, revoked_at='now'"); con.commit(); con.close()
    assert _alembic(db, "downgrade", "20261008_m21_runtime_designated").returncode != 0
    con = sqlite3.connect(db); con.execute("update claire_runtime_approvals set revoked_at=NULL"); con.commit(); con.close()
    assert _alembic(db, "downgrade", "20261008_m21_runtime_designated").returncode == 0
    assert _alembic(db, "upgrade", "20261008_m21_runtime_revoke").returncode == 0


def test_NEW_migration_refuses_partial_or_wrong_shape_existing_columns(tmp_path):
    for ddl, needle in (("alter table claire_runtime_approvals add column revoked_at varchar(40)", "only one"),
                        ("alter table claire_runtime_approvals add column revoked_by varchar(200)", "only one"),
                        ("alter table claire_runtime_approvals add column revoked_at integer; alter table claire_runtime_approvals add column revoked_by varchar(200)", "incompatible"),
                        ("alter table claire_runtime_approvals add column revoked_at varchar(40) not null default ''; alter table claire_runtime_approvals add column revoked_by varchar(200)", "incompatible")):
        db = tmp_path / f"p{abs(hash(ddl))}.sqlite"
        assert _alembic(db, "upgrade", "20261008_m21_runtime_designated").returncode == 0
        con = sqlite3.connect(db); con.executescript(ddl); con.close()
        r = _alembic(db, "upgrade", "20261008_m21_runtime_revoke")
        assert r.returncode != 0 and needle in r.stderr, (ddl, r.stderr[-300:])
    ok = tmp_path / "ok.sqlite"
    assert _alembic(ok, "upgrade", "20261008_m21_runtime_designated").returncode == 0
    con = sqlite3.connect(ok); con.executescript("alter table claire_runtime_approvals add column revoked_at varchar(40); alter table claire_runtime_approvals add column revoked_by varchar(200)"); con.close()
    assert _alembic(ok, "upgrade", "20261008_m21_runtime_revoke").returncode == 0                 # both already present and compatible: stamped
