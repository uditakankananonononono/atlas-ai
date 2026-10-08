"""Milestone 1 of the Meemee->Claire merge: read-only runtime slice, via the mounted Atlas app.

Limits: the model here is a scripted stub, not a real selected model; no real PostgreSQL (SQLite file
only); no Alembic migration (create_all); only READ tools exist; running goals cannot be cancelled.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.auth.context import TenantContext, require_tenant
from app.main import app
from app.modules.m21_claire.runtime import acceptance
from app.modules.m21_claire.runtime import routes as rroutes
from app.modules.m21_claire.runtime.engine import Engine
from app.modules.m21_claire.runtime.goals import GoalStore
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry, Tool
from app.modules.m21_claire.runtime.types import AgentDecision, ToolCall, ToolRisk
from app.modules.m21_claire.runtime.worker import Worker

URL = "/api/v1/claire/runtime/goals"
CRIT = [{"kind": "tool_receipt", "tool": "lookup", "min_count": 1}]


class LookupArgs(BaseModel):
    key: str


class Lookup(Tool):
    name, risk, arguments_model = "lookup", ToolRisk.READ, LookupArgs
    def run(self, a): return {"value": f"v-{a.key}"}


class Boom(Tool):
    name, risk, arguments_model = "boom", ToolRisk.READ, LookupArgs
    def run(self, a): raise ZeroDivisionError("bug")


class Leaky(Tool):
    name, risk, arguments_model = "leaky", ToolRisk.READ, LookupArgs
    def run(self, a): raise OSError("https://secret.example/x?token=abc123456789")


class Script:
    def __init__(self, *decisions): self.d = list(decisions)
    async def decide(self, messages): return self.d.pop(0)


def call(name, **a): return AgentDecision(tool_call=ToolCall(name=name, arguments=a))
def final(t="done"): return AgentDecision(final=t)


def registry(*tools):
    r = ReadOnlyToolRegistry()
    for t in tools: r.register(t)
    return r


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = GoalStore(f"sqlite:///{tmp_path}/g.db")
    monkeypatch.setattr(rroutes, "_store", s)
    yield s
    s.close()


@pytest.fixture
def client(store):
    c = TestClient(app)
    def as_(tenant, actor): app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant, actor)
    c.as_ = as_
    as_("t1", "a1")
    yield c
    app.dependency_overrides.pop(require_tenant, None)


def worker(store, model, tools, wid="w1"):
    return Worker(store, lambda claim: Engine(model, tools, max_steps=claim.max_steps), wid)


def run(coro): return asyncio.run(coro)


def create(client, **kw):
    body = {"purpose": "look up k", "acceptance_criteria": CRIT, **kw}
    r = client.post(URL, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_mounted_goal_to_receipt_to_acceptance_survives_restart(client, store, tmp_path):
    gid = create(client)
    assert client.get(f"{URL}/{gid}").json()["status"] == "queued"
    run(worker(store, Script(call("lookup", key="k"), final()), registry(Lookup())).run_once())
    store.close()
    fresh = GoalStore(f"sqlite:///{tmp_path}/g.db")  # simulated API/worker restart
    rroutes._store = fresh
    got = client.get(f"{URL}/{gid}").json()
    fresh.close()
    assert got["status"] == "completed" and got["verdict"]["accepted"] is True
    assert got["report"]["receipts"][0]["content"] == {"value": "v-k"}


def test_missing_model_is_a_blocker_not_pretend_execution(client, store):
    gid = create(client)
    run(worker(store, None, registry(Lookup())).run_once())
    g = client.get(f"{URL}/{gid}").json()
    assert g["status"] == "blocked" and g["blocker"] == "model_unavailable" and g["report"]["receipts"] == []


def test_model_final_text_alone_cannot_complete(client, store):
    gid = create(client)
    run(worker(store, Script(final("I did it, trust me")), registry(Lookup())).run_once())
    g = client.get(f"{URL}/{gid}").json()
    assert g["status"] == "not_accepted" and g["verdict"]["accepted"] is False


def test_step_limit_is_exhausted_not_complete(client, store):
    gid = create(client, max_steps=2)
    run(worker(store, Script(call("nope"), call("nope")), registry(Lookup())).run_once())
    assert client.get(f"{URL}/{gid}").json()["status"] == "exhausted"


def test_unknown_or_aliased_tool_is_refused_and_registry_rejects_non_read():
    r = registry(Lookup())
    rep = run(Engine(Script(call("shell_command", cmd="rm -rf /"), final()), r).run("g"))
    assert rep.refusals[0].reason == "unknown_tool" and rep.receipts == []
    class W(Lookup):
        name, risk = "w", ToolRisk.WRITE
    with pytest.raises(ValueError):
        ReadOnlyToolRegistry().register(W())


def test_tool_error_text_has_class_name_only_and_arguments_are_redacted():
    r = registry(Leaky())
    rep = run(Engine(Script(call("leaky", key="k", api_key="supersecretvalue1"), final()), r).run("g"))
    rc = rep.receipts[0]
    assert rc.ok is False and rc.error == "OSError"
    assert "secret.example" not in rep.model_dump_json() and "supersecretvalue1" not in rep.model_dump_json()


def test_unlisted_tool_bug_is_not_swallowed(client, store):
    create(client)
    with pytest.raises(ZeroDivisionError):
        run(worker(store, Script(call("boom", key="k")), registry(Boom())).run_once())


def test_bug_leases_expire_and_attempts_are_bounded(tmp_path):
    t = [datetime(2026, 10, 8, tzinfo=timezone.utc)]
    s = GoalStore(f"sqlite:///{tmp_path}/b.db", clock=lambda: t[0], max_attempts=2, lease_seconds=10)
    gid = s.create("t1", "a1", "p", CRIT, 3)
    for _ in range(2):
        assert s.claim("w") is not None
        t[0] += timedelta(seconds=11)
    assert s.claim("w") is None
    assert s.get("t1", "a1", gid)["status"] == "failed" and s.get("t1", "a1", gid)["blocker"] == "attempts_exhausted"
    s.close()


def test_two_workers_cannot_settle_one_lease(tmp_path):
    t = [datetime(2026, 10, 8, tzinfo=timezone.utc)]
    s = GoalStore(f"sqlite:///{tmp_path}/l.db", clock=lambda: t[0], lease_seconds=10)
    s.create("t1", "a1", "p", CRIT, 3)
    c1 = s.claim("w1")
    assert s.claim("w2") is None  # live lease
    t[0] += timedelta(seconds=11)
    c2 = s.claim("w2")
    assert c2 and c2.lease_token != c1.lease_token
    assert s.settle(c1, "completed", blocker=None, report={}, verdict=None) is False  # fenced
    assert s.settle(c2, "blocked", blocker="x", report={}, verdict=None) is True
    assert s.settle(c2, "completed", blocker=None, report={}, verdict=None) is False
    s.close()


def test_tenant_and_actor_isolation_and_auth(client, store, monkeypatch):
    gid = create(client)
    for tenant, actor in (("t2", "a1"), ("t1", "a2")):
        client.as_(tenant, actor)
        assert client.get(f"{URL}/{gid}").status_code == 404
        assert client.post(f"{URL}/{gid}/cancel").status_code == 404
    client.as_("t1", "a1")
    assert client.get(f"{URL}/{gid}").status_code == 200
    app.dependency_overrides.pop(require_tenant)
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)  # production mode: spoofed headers must fail
    assert TestClient(app).get(f"{URL}/{gid}", headers={"x-atlas-tenant": "t1", "x-atlas-actor": "a1"}).status_code == 401


def test_validation_cancel_and_unconfigured_store(client, store, monkeypatch):
    assert client.post(URL, json={"purpose": "abc", "acceptance_criteria": []}).status_code == 422
    assert client.post(URL, json={"purpose": "abc"}).status_code == 422
    gid = create(client)
    assert client.post(f"{URL}/{gid}/cancel").json()["status"] == "cancelled"
    assert client.post(f"{URL}/{gid}/cancel").status_code == 409
    monkeypatch.setattr(rroutes, "_store", None)
    monkeypatch.delenv("ATLAS_CLAIRE_RUNTIME_DB", raising=False)
    assert client.get(f"{URL}/x").status_code == 503


def test_acceptance_ignores_failed_receipts():
    from app.modules.m21_claire.runtime.types import RunReport, ToolReceipt
    rep = RunReport(final="x", stop_reason="final", steps_used=1,
                    receipts=[ToolReceipt(step=1, tool="lookup", arguments={}, ok=False, error="OSError")])
    assert acceptance.evaluate(CRIT, rep).accepted is False
