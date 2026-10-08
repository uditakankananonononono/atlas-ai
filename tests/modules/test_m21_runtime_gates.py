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
from app.modules.m21_claire.runtime.goals import GoalStore
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
    r = ReadOnlyToolRegistry(enforcer=GateEnforcer(store))
    for t in tools: r.register(t)
    return r


def work(store, model, tools, wid="w"):
    return Worker(store, lambda c: Engine(model, tools, max_steps=c.max_steps), wid)


CRIT = [{"kind": "tool_receipt", "tool": "write_note", "min_count": 1}]


def goal(store, tenant="t1", actor="a1"):
    return store.create(tenant, actor, "do work", CRIT, 6)


def test_destructive_verbs_are_autonomous_but_money_and_people_are_not(store):
    r = registry(store, make("delete_file"), make("install_package"), make("execute_command"), make("deploy_site"),
                 make("change_permissions"), make("pay_invoice", money=True), make("notify_person", person=True))
    p = Principal("t1", "a1", goal(store))
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
    gid = goal(store); p = Principal("t1", "a1", gid)
    d = payload_digest(gid, "impersonate_user", {"target": "x"})
    store.grant("t1", "a1", gid, "impersonate_user", "comms", d, "a1")
    with pytest.raises(GateRefused) as e:
        run(r.execute(1, "impersonate_user", {"target": "x"}, p))
    assert e.value.reason == "blocked" and RAN == []


def test_direct_dispatch_without_principal_or_approval_never_runs(store):
    r = registry(store, make("send_email", person=True))
    for p in (None, Principal("t1", "a1", goal(store))):
        with pytest.raises(GateRefused):
            run(r.execute(1, "send_email", {"target": "bob"}, p))
    assert RAN == []


def test_end_to_end_gate_awaiting_review_approve_requeue_single_use(store, t0):
    c = TestClient(app)
    app.dependency_overrides[require_tenant] = lambda: TenantContext("t1", "a1")
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
        assert c.post(f"{URL}/{gid}/approvals", json=bad).status_code == 422          # cannot pre-sign a cheque
        ok = {"capability": "send_email", "gate": "comms", "digest": ref["digest"]}
        assert c.post(f"{URL}/{gid}/approvals", json=ok).status_code == 201
        assert c.post(f"{URL}/{gid}/requeue").json()["status"] == "queued"
        run(work(store, Script(call("send_email", target="bob"), final()), tools).run_once())
        assert ("send_email", "bob") in RAN
        n = len([x for x in RAN if x[0] == "send_email"])
        assert n == 1
        # replay: the approval is consumed
        assert c.post(f"{URL}/{gid}/requeue").status_code == 409  # not awaiting review any more or attempts used
        with pytest.raises(GateRefused):
            run(tools.execute(9, "send_email", {"target": "bob"}, Principal("t1", "a1", gid)))
        assert len([x for x in RAN if x[0] == "send_email"]) == 1
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def test_approval_binding_changed_payload_goal_actor_expiry_and_all_or_nothing(store, t0):
    r = registry(store, make("send_email", person=True), make("book_table"))
    gid = goal(store); other = goal(store)
    p = Principal("t1", "a1", gid)
    d = payload_digest(gid, "send_email", {"target": "bob"})
    store.grant("t1", "a1", gid, "send_email", "comms", d, "a1", ttl_seconds=60)
    with pytest.raises(GateRefused):  # changed recipient
        run(r.execute(1, "send_email", {"target": "mallory"}, p))
    with pytest.raises(GateRefused):  # same call under another goal
        run(r.execute(1, "send_email", {"target": "bob"}, Principal("t1", "a1", other)))
    with pytest.raises(GateRefused):  # another actor/tenant claiming the goal
        run(r.execute(1, "send_email", {"target": "bob"}, Principal("t1", "a2", gid)))
    with pytest.raises(GateRefused):
        run(r.execute(1, "send_email", {"target": "bob"}, Principal("t2", "a1", gid)))
    t0[0] += timedelta(seconds=61)  # expired
    with pytest.raises(GateRefused):
        run(r.execute(1, "send_email", {"target": "bob"}, p))
    assert RAN == []
    # book needs BOTH gates; one approval is not enough and is not consumed by the failed attempt
    bd = payload_digest(gid, "book_table", {"target": "x"})
    store.grant("t1", "a1", gid, "book_table", "comms", bd, "a1")
    with pytest.raises(GateRefused):
        run(r.execute(1, "book_table", {"target": "x"}, p))
    store.grant("t1", "a1", gid, "book_table", "payment", bd, "a1")
    assert run(r.execute(1, "book_table", {"target": "x"}, p)).ok and RAN == [("book_table", "x")]
    with pytest.raises(GateRefused):
        run(r.execute(1, "book_table", {"target": "x"}, p))


def test_grant_is_scoped_to_the_owners_goal_and_known_gates(store):
    gid = goal(store)
    with pytest.raises(KeyError):
        store.grant("t2", "a1", gid, "x", "comms", "0" * 64, "a1")
    with pytest.raises(KeyError):
        store.grant("t1", "a2", gid, "x", "comms", "0" * 64, "a1")
    with pytest.raises(ValueError):
        store.grant("t1", "a1", gid, "x", "review", "0" * 64, "a1")


def test_approve_route_is_owner_scoped(store):
    c = TestClient(app)
    gid = goal(store)
    app.dependency_overrides[require_tenant] = lambda: TenantContext("t1", "intruder")
    try:
        body = {"capability": "send_email", "gate": "comms", "digest": "0" * 64}
        assert c.post(f"{URL}/{gid}/approvals", json=body).status_code == 404
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
    p = Principal("t1", "a1", goal(store))
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
    gid = goal(store); p = Principal("t1", "a1", gid)
    d = payload_digest(gid, "send_email", {"target": ["a", "b"]})
    store.grant("t1", "a1", gid, "send_email", "comms", d, "a1")
    for args in ({"target": ("a", "b")}, {"target": {"a"}}, {"target": b"a"}, {1: "x"}, {"target": float("nan")}):
        with pytest.raises(GateRefused) as e:
            run(r.execute(1, "send_email", args, p))
        assert e.value.reason == "invalid_arguments"
    assert RAN == []
    assert run(r.execute(1, "send_email", {"target": ["a", "b"]}, p)).ok  # the exact approved plain-JSON call still works
