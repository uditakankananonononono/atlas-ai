"""Phase 2 slice 2: payment/comms gates enforced at dispatch. Fake tools only; no real effects exist.

Owner ruling: only spending money and reaching a person are gated; delete/install/execute/deploy are autonomous.
Limits: test-only fake tools; SQLite; no effect reconciliation or idempotency for writes (required before any real
write tool); Claire's older ActionPolicy/orchestrator verb gate is unchanged and not consulted by this runtime.
"""
import asyncio
from typing import Any
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.auth.context import TenantContext, require_tenant
from app.main import app
from app.modules.m21_claire.runtime import routes as rroutes
from app.modules.m21_claire.runtime.engine import Engine
from app.modules.m21_claire.runtime.gates import GateEnforcer, GateRefused, Principal, classify, payload_digest
from app.modules.m21_claire.runtime.goals import GoalStore, SelfApprovalRefused
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry, Tool
from app.modules.m21_claire.runtime.types import AgentDecision, ToolCall, ToolRisk
from app.modules.m21_claire.runtime.worker import Worker

URL = "/api/v1/claire/runtime/goals"
RAN: list[tuple] = []


class Args(BaseModel):
    target: Any = ""
    policy_tags: list[str] = []


def make(name, risk=ToolRisk.EXECUTE, money=False, person=False):
    class T(Tool):
        arguments_model = Args
        def run(self, a):
            RAN.append((self.name, a.target)); return {"done": a.target}
    T.name, T.risk, T.spends_money, T.sends_to_person = name, risk, money, person
    T.idempotent = False
    return T()


class Script:
    def __init__(self, *d): self.d = list(d)
    async def decide(self, m): return self.d.pop(0)


def call(name, **a): return AgentDecision(tool_call=ToolCall(name=name, arguments=a))
def final(): return AgentDecision(final="done")
def run(c): return asyncio.run(c)


@pytest.fixture(autouse=True)
def reset():
    RAN.clear()


@pytest.fixture
def t0():
    return [datetime(2026, 10, 8, tzinfo=timezone.utc)]


@pytest.fixture
def store(tmp_path, t0, monkeypatch):
    s = GoalStore(f"sqlite:///{tmp_path}/g.db", clock=lambda: t0[0], create_schema=True)
    monkeypatch.setattr(rroutes, "_store", s)
    yield s
    s.close()


def registry(store, *tools):
    r = ReadOnlyToolRegistry(enforcer=GateEnforcer(store), journal=store)
    for t in tools: r.register(t)
    return r


def work(store, model, tools, wid="w"):
    return Worker(store, lambda c: Engine(model, tools, max_steps=c.max_steps), wid)


CRIT = [{"kind": "tool_receipt", "tool": "write_note", "min_count": 1}]


def live(store, gid, tenant="t1", actor="a1"):
    """Principal for a goal forced into a running state with a live lease (unit tests of the registry, no worker)."""
    from sqlalchemy import update
    from app.modules.m21_claire.runtime.goals import GoalRow
    with store._sessions.begin() as s:
        s.execute(update(GoalRow).where(GoalRow.id == gid).values(status="running", lease_token="tok-" + gid, lease_expires_at="9999-01-01T00:00:00+00:00"))
    return Principal(tenant, actor, gid, "tok-" + gid)


def goal(store, tenant="t1", actor="a1"):
    return store.create(tenant, actor, "do work", CRIT, 6)


def test_destructive_verbs_are_autonomous_but_money_and_people_are_not(store):
    r = registry(store, make("delete_file"), make("install_package"), make("execute_command"), make("deploy_site"),
                 make("change_permissions"), make("pay_invoice", money=True), make("notify_person", person=True))
    p = live(store, goal(store), "t1", "a1")
    for n in ("delete_file", "install_package", "execute_command", "deploy_site", "change_permissions"):
        assert classify(r.get(n), {}).gates == ()
        assert run(r.execute(1, n, {"target": "x"}, p)).ok
    assert classify(r.get("pay_invoice"), {}).gates == ("payment",)
    assert classify(r.get("notify_person"), {}).gates == ("comms",)
    for n in ("pay_invoice", "notify_person"):
        with pytest.raises(GateRefused) as e:
            run(r.execute(1, n, {"target": "x"}, p))
        assert e.value.reason == "approval_required"
    assert [x[0] for x in RAN] == ["delete_file", "install_package", "execute_command", "deploy_site", "change_permissions"]


def test_undeclared_write_tool_and_name_tokens_fail_closed_to_the_stricter_gate(store):
    class Undeclared(Tool):
        name, risk, arguments_model = "frobnicate", ToolRisk.WRITE, Args
        def run(self, a): RAN.append(1)
    u = Undeclared()
    assert classify(u, {}).gates == ("comms", "payment")
    assert classify(make("purchase_item"), {}).gates == ("payment",)   # declared False, name raises
    assert classify(make("book_table"), {}).gates == ("comms", "payment")
    assert classify(make("update_row"), {"policy_tags": ["send"]}).gates == ("comms",)  # tags raise
    assert classify(make("update_row"), {"policy_tags": ["safe", "autonomous", "read"]}).gates == ()  # tags never lower
    spend_declared = make("update_row", money=True)
    assert classify(spend_declared, {"policy_tags": ["safe"]}).gates == ("payment",)
    read = make("lookup", risk=ToolRisk.READ)
    read.spends_money = read.sends_to_person = None
    assert classify(read, {}).gates == ()  # undeclared READ tool has no effects


def test_blocked_standing_no_is_refused_even_with_an_approval(store):
    r = registry(store, make("impersonate_user", person=True))
    gid = goal(store); p = live(store, gid, "t1", "a1")
    d = payload_digest(gid, "impersonate_user", {"target": "x"})
    store.grant("t1", "a1", gid, "impersonate_user", "comms", d, "ap1")
    with pytest.raises(GateRefused) as e:
        run(r.execute(1, "impersonate_user", {"target": "x"}, p))
    assert e.value.reason == "blocked" and RAN == []


def test_direct_dispatch_without_principal_or_approval_never_runs(store):
    r = registry(store, make("send_email", person=True))
    for p in (None, live(store, goal(store), "t1", "a1")):
        with pytest.raises(GateRefused):
            run(r.execute(1, "send_email", {"target": "bob"}, p))
    assert RAN == []


def test_end_to_end_gate_awaiting_review_approve_requeue_single_use(store, t0):
    c = TestClient(app)
    who = {"ctx": TenantContext("t1", "a1")}  # CONVERTED (slice 5): the goal's actor reads/requeues; a distinct approver approves
    app.dependency_overrides[require_tenant] = lambda: who["ctx"]
    try:
        gid = goal(store)
        tools = registry(store, make("write_note"), make("send_email", person=True))
        run(work(store, Script(call("write_note", target="n"), call("send_email", target="bob"), final()), tools).run_once())
        g = c.get(f"{URL}/{gid}").json()
        # criteria are met by write_note, the model said final, yet the goal must not complete
        assert g["status"] == "awaiting_review" and g["verdict"] is None and RAN == [("write_note", "n")]
        ref = g["report"]["refusals"][0]
        assert ref["reason"] == "approval_required" and ref["gates"] == ["comms"] and ref["tool"] == "send_email"
        bad = {"capability": "send_email", "gate": "comms", "digest": "0" * 64}
        who["ctx"] = TenantContext("t1", "ap1", frozenset({"claire-approver"}))
        assert c.post(f"{URL}/{gid}/approvals", json=bad).status_code == 422          # cannot pre-sign a cheque
        ok = {"capability": "send_email", "gate": "comms", "digest": ref["digest"]}
        assert c.post(f"{URL}/{gid}/approvals", json=ok).status_code == 201
        who["ctx"] = TenantContext("t1", "a1")
        assert c.post(f"{URL}/{gid}/requeue").json()["status"] == "queued"
        run(work(store, Script(call("send_email", target="bob"), final()), tools).run_once())
        assert ("send_email", "bob") in RAN
        n = len([x for x in RAN if x[0] == "send_email"])
        assert n == 1
        # replay: the approval is consumed
        assert c.post(f"{URL}/{gid}/requeue").status_code == 409  # not awaiting review any more or attempts used
        again = run(tools.execute(9, "send_email", {"target": "bob"}, live(store, gid, "t1", "a1")))
        assert again.replayed is True  # slice 3b: an identical committed call is a replay of the stored receipt, never a second send
        assert len([x for x in RAN if x[0] == "send_email"]) == 1
        with pytest.raises(GateRefused):  # a DIFFERENT call (new recipient) still needs its own approval; the old one is spent
            run(tools.execute(9, "send_email", {"target": "carol"}, live(store, gid, "t1", "a1")))
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def test_approval_binding_changed_payload_goal_actor_expiry_and_all_or_nothing(store, t0):
    r = registry(store, make("send_email", person=True), make("book_table"))
    gid = goal(store); other = goal(store)
    p = live(store, gid, "t1", "a1")
    d = payload_digest(gid, "send_email", {"target": "bob"})
    store.grant("t1", "a1", gid, "send_email", "comms", d, "ap1", ttl_seconds=60)
    with pytest.raises(GateRefused):  # changed recipient
        run(r.execute(1, "send_email", {"target": "mallory"}, p))
    with pytest.raises(GateRefused):  # same call under another goal
        run(r.execute(1, "send_email", {"target": "bob"}, live(store, other, "t1", "a1")))
    with pytest.raises(GateRefused):  # another actor/tenant claiming the goal
        run(r.execute(1, "send_email", {"target": "bob"}, live(store, gid, "t1", "a2")))
    with pytest.raises(GateRefused):
        run(r.execute(1, "send_email", {"target": "bob"}, live(store, gid, "t2", "a1")))
    t0[0] += timedelta(seconds=61)  # expired
    with pytest.raises(GateRefused):
        run(r.execute(1, "send_email", {"target": "bob"}, p))
    assert RAN == []
    # book needs BOTH gates; one approval is not enough and is not consumed by the failed attempt
    bd = payload_digest(gid, "book_table", {"target": "x"})
    store.grant("t1", "a1", gid, "book_table", "comms", bd, "ap1")
    with pytest.raises(GateRefused):
        run(r.execute(1, "book_table", {"target": "x"}, p))
    store.grant("t1", "a1", gid, "book_table", "payment", bd, "ap1")
    assert run(r.execute(1, "book_table", {"target": "x"}, p)).ok and RAN == [("book_table", "x")]
    assert run(r.execute(1, "book_table", {"target": "x"}, p)).replayed is True and RAN == [("book_table", "x")]  # replay, not a re-run
    with pytest.raises(GateRefused):  # a different payload needs its own approvals
        run(r.execute(1, "book_table", {"target": "y"}, p))


def test_grant_is_scoped_to_the_owners_goal_and_known_gates(store):
    gid = goal(store)
    with pytest.raises(KeyError):
        store.grant("t2", "a1", gid, "x", "comms", "0" * 64, "ap1")
    with pytest.raises(KeyError):
        store.grant("t1", "a2", gid, "x", "comms", "0" * 64, "ap1")
    with pytest.raises(ValueError):
        store.grant("t1", "a1", gid, "x", "review", "0" * 64, "ap1")


def test_approve_route_is_owner_scoped(store):
    c = TestClient(app)
    gid = goal(store)
    # CONVERTED (slice 5): approvals are tenant+role scoped now; the owner-only routes (requeue) stay actor scoped.
    app.dependency_overrides[require_tenant] = lambda: TenantContext("t2", "approver-x", frozenset({"claire-approver"}))
    try:
        body = {"capability": "send_email", "gate": "comms", "digest": "0" * 64}
        assert c.post(f"{URL}/{gid}/approvals", json=body).status_code == 404            # other tenant's approver
        app.dependency_overrides[require_tenant] = lambda: TenantContext("t1", "intruder")
        assert c.post(f"{URL}/{gid}/approvals", json=body).status_code == 403            # no approver role
        assert c.post(f"{URL}/{gid}/requeue").status_code == 404
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def test_registry_without_enforcer_still_read_only_and_non_read_dispatch_is_refused(store):
    with pytest.raises(ValueError):
        ReadOnlyToolRegistry().register(make("delete_file"))
    r = registry(store, make("delete_file"))
    r.enforcer = None  # configuration mutation after registration
    with pytest.raises(PermissionError):
        run(r.execute(1, "delete_file", {}, None))
    assert RAN == []


def test_approvals_table_matches_migration_and_refuses_wrong_shape(tmp_path):
    import os, subprocess, sys
    from sqlalchemy import create_engine, inspect
    from app.modules.m21_claire.runtime.goals import Base
    def alembic(db, *a):
        return subprocess.run([sys.executable, "-m", "alembic", *a], env={**os.environ, "ATLAS_DATABASE_URL": f"sqlite:///{db}"},
                              text=True, capture_output=True, timeout=110)
    db = tmp_path / "a.sqlite"
    assert alembic(db, "upgrade", "head").returncode == 0
    insp = inspect(create_engine(f"sqlite:///{db}"))
    t = Base.metadata.tables["claire_runtime_approvals"]
    assert {c["name"]: c["nullable"] for c in insp.get_columns(t.name)} == {c.name: c.nullable for c in t.columns}
    assert {i["name"] for i in insp.get_indexes(t.name)} >= {i.name for i in t.indexes}
    bad = tmp_path / "b.sqlite"
    assert alembic(bad, "upgrade", "20261008_m21_runtime_goals").returncode == 0
    con = sqlite3.connect(bad); con.execute("CREATE TABLE claire_runtime_approvals (id TEXT PRIMARY KEY)"); con.commit(); con.close()
    r = alembic(bad, "upgrade", "head")
    assert r.returncode != 0 and "incompatible shape" in r.stderr


def test_standing_no_names_are_blocked_on_word_boundaries_not_substrings():
    for n in ("impersonate_user", "self_bot_poster", "do-ban-evasion", "fabricate_evidence", "login_scraping_tool"):
        assert classify(make(n), {}).blocked is True, n
    assert classify(make("update_row"), {}).blocked is False
    assert classify(make("pirated_name_checker_unrelated"), {}).blocked is False  # 'pirated' != 'piracy'


@pytest.mark.parametrize("attr,value", [("sends_to_person", False), ("spends_money", False), ("risk", ToolRisk.READ), ("name", "other")])
def test_mutating_any_gated_attribute_after_registration_is_refused_at_dispatch(store, attr, value):
    """Reviewer reproduction: gated tool correctly refused, then the SAME object is mutated to look ungated."""
    t = make("notify_person", risk=ToolRisk.WRITE, money=True, person=True)
    r = registry(store, t)
    p = live(store, goal(store), "t1", "a1")
    with pytest.raises(GateRefused):
        run(r.execute(1, "notify_person", {"target": "bob"}, p))
    setattr(t, attr, value)
    assert r.risk_intact("notify_person") is False
    with pytest.raises(PermissionError):
        run(r.execute(1, "notify_person", {"target": "bob"}))          # no principal, no approval
    rep = run(Engine(Script(call("notify_person", target="bob"), final()), r).run("g", principal=p))
    assert rep.receipts == [] and rep.refusals[0].reason == "risk_changed"
    assert RAN == []


def test_effect_metadata_mutation_on_a_never_refused_tool_is_also_refused(store):
    t = make("update_row")  # autonomous at registration
    r = registry(store, t)
    t.sends_to_person = True  # upgrading is also a change from what was reviewed at registration
    assert r.risk_intact("update_row") is False


@pytest.mark.parametrize("attr", ["sends_to_person", "spends_money"])
@pytest.mark.parametrize("value", [1, 0, 1.0, "true", "", [], 2])
def test_type_equal_but_not_bool_mutation_is_refused_and_tool_never_runs(store, attr, value):
    """Reviewer reproduction: True == 1 so a tuple == comparison passed; fingerprint is now type-preserving."""
    t = make("update_row", risk=ToolRisk.WRITE)
    setattr(t, attr, True)
    r = registry(store, t)
    setattr(t, attr, value)
    assert r.risk_intact("update_row") is False
    with pytest.raises(PermissionError):
        run(r.execute(1, "update_row", {"target": "bob"}))
    with pytest.raises(PermissionError):
        run(r.execute(1, "update_row", {"target": "bob"}, live(store, goal(store), "t1", "a1")))
    assert RAN == []


@pytest.mark.parametrize("bad", [0, 1, "false", "", {}, [], "True"])
def test_declared_effects_must_be_exactly_bool_or_none(store, bad):
    for attr in ("spends_money", "sends_to_person"):
        t = make("update_row"); setattr(t, attr, bad)
        with pytest.raises(ValueError):
            registry(store, t)


@pytest.mark.parametrize("name", ["send email", "send/email", "sendEmail", "Pay_Invoice", "pay-invoice", "x" * 65, "", "1abc", "pay.invoice"])
def test_tool_names_outside_the_grammar_cannot_register(store, name):
    t = make("update_row"); t.name = name
    with pytest.raises(ValueError):
        registry(store, t)


def test_word_splitting_in_policy_tags_and_underscore_names_escalates_even_when_declared_ungated():
    t = make("update_row")
    for tag in ("send email", "send/email", "sendEmail", "pay invoice", "pay-invoice", "payInvoice"):
        assert classify(t, {"policy_tags": [tag]}).gates, tag
    assert classify(make("send_email_now"), {}).gates == ("comms",)
    assert classify(make("pay_invoice_now"), {}).gates == ("payment",)


def test_gated_arguments_must_be_plain_json_so_digests_cannot_collide(store):
    r = registry(store, make("send_email", person=True))
    gid = goal(store); p = live(store, gid, "t1", "a1")
    d = payload_digest(gid, "send_email", {"target": ["a", "b"]})
    store.grant("t1", "a1", gid, "send_email", "comms", d, "ap1")
    for args in ({"target": ("a", "b")}, {"target": {"a"}}, {"target": b"a"}, {1: "x"}, {"target": float("nan")}):
        with pytest.raises(GateRefused) as e:
            run(r.execute(1, "send_email", args, p))
        assert e.value.reason == "invalid_arguments"
    assert RAN == []
    assert run(r.execute(1, "send_email", {"target": ["a", "b"]}, p)).ok  # the exact approved plain-JSON call still works


# ---- slice 5: separation of duties (the goal's actor proposes; a different principal with the approver role decides) ----

def _client(who):
    c = TestClient(app)
    app.dependency_overrides[require_tenant] = lambda: who["ctx"]
    return c


def _refused_goal(store):
    gid = goal(store)
    tools = registry(store, make("send_email", person=True))
    run(work(store, Script(call("send_email", target="bob"), final()), tools).run_once())
    return gid, store.get("t1", "a1", gid)["report"]["refusals"][0]


# PROTECTION
def test_store_refuses_the_goals_own_actor_as_approver_and_blank_approvers(store):
    gid, ref = _refused_goal(store)
    with pytest.raises(SelfApprovalRefused):
        store.grant("t1", "a1", gid, "send_email", "comms", ref["digest"], "a1")
    for bad in ("", "  ", None, 5):
        with pytest.raises(ValueError):
            store.grant("t1", "a1", gid, "send_email", "comms", ref["digest"], bad)
    assert store.grant("t1", "a1", gid, "send_email", "comms", ref["digest"], "ap1")


# PROTECTION: the invariant lives in the store, not only the route
def test_route_refuses_self_approval_and_missing_role_and_records_approver(store):
    gid, ref = _refused_goal(store)
    body = {"capability": "send_email", "gate": "comms", "digest": ref["digest"]}
    who = {"ctx": TenantContext("t1", "a1", frozenset({"claire-approver"}))}
    c = _client(who)
    try:
        assert c.post(f"{URL}/{gid}/approvals", json=body).status_code == 403          # own actor, even with the role
        who["ctx"] = TenantContext("t1", "ap1")
        assert c.post(f"{URL}/{gid}/approvals", json=body).status_code == 403          # distinct but no role
        who["ctx"] = TenantContext("t1", "ap1", frozenset({"atlas-reviewer"}))
        assert c.post(f"{URL}/{gid}/approvals", json=body).status_code == 403          # reviewer role is not an approver role
        who["ctx"] = TenantContext("t1", "ap1", frozenset({"claire-approver"}))
        ok = c.post(f"{URL}/{gid}/approvals", json=body)
        assert ok.status_code == 201 and ok.json()["approver"] == "ap1" and ok.json()["self_approved"] is False
        who["ctx"] = TenantContext("t1", "ap2", frozenset({"atlas-admin"}))
        assert c.post(f"{URL}/{gid}/approvals", json=body).status_code == 201          # atlas-admin also decides
    finally:
        app.dependency_overrides.pop(require_tenant, None)


# NEW: an approver who did not create the goal can read exactly what they approve, and nothing more
def test_approver_view_shows_refusal_digest_and_bounded_preview_without_purpose(store):
    # CONVERTED (slice 9): used to pin 'no arguments'. Now covers: the approver reads a bounded redacted preview of the stored
    # arguments (from the same refusal as the digest), labelled untrusted; the goal purpose is still withheld.
    gid, ref = _refused_goal(store)
    who = {"ctx": TenantContext("t1", "ap1", frozenset({"claire-approver"}))}
    c = _client(who)
    try:
        v = c.get(f"{URL}/{gid}/approver-view")
        assert v.status_code == 200
        j = v.json()
        r0 = j["refusals"][0]
        assert j["actor_id"] == "a1" and len(j["refusals"]) == 1 and j["untrusted_model_content"] is True
        assert (r0["tool"], r0["gates"], r0["digest"], r0["reason"]) == ("send_email", ["comms"], ref["digest"], "approval_required")
        assert r0["preview"]["value"]["target"] == "bob" and r0["preview"]["untrusted_model_content"] is True and r0["preview"]["truncated"] is False
        assert "purpose" not in j and "do work" not in repr(j)
        who["ctx"] = TenantContext("t1", "ap1")
        assert c.get(f"{URL}/{gid}/approver-view").status_code == 403
        who["ctx"] = TenantContext("t2", "ap1", frozenset({"claire-approver"}))
        assert c.get(f"{URL}/{gid}/approver-view").status_code == 404
    finally:
        app.dependency_overrides.pop(require_tenant, None)


# NEW: the escape hatch is explicit, default OFF, strict bool, and visible in the record
def test_self_approval_escape_hatch_is_default_off_and_visible(tmp_path):
    with pytest.raises(ValueError):
        GoalStore(f"sqlite:///{tmp_path}/x.db", create_schema=True, owner_may_self_approve="yes")
    assert GoalStore(f"sqlite:///{tmp_path}/y.db", create_schema=True).owner_may_self_approve is False
    solo = GoalStore(f"sqlite:///{tmp_path}/z.db", create_schema=True, owner_may_self_approve=True)
    gid, ref = _refused_goal(solo)
    who = {"ctx": TenantContext("t1", "a1", frozenset({"claire-approver"}))}
    from app.modules.m21_claire.runtime import routes as _r
    app.dependency_overrides[_r.get_store] = lambda: solo
    c = _client(who)
    try:
        ok = c.post(f"{URL}/{gid}/approvals", json={"capability": "send_email", "gate": "comms", "digest": ref["digest"]})
        assert ok.status_code == 201 and ok.json()["self_approved"] is True
    finally:
        app.dependency_overrides.pop(require_tenant, None)
        app.dependency_overrides.pop(_r.get_store, None)
