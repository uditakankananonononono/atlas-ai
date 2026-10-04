"""Chunk 4 tests: FastAPI surface for the GCW."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m20_general_cognitive_worker.routes import bind_service, router
from app.modules.m20_general_cognitive_worker.safety import (
    ApprovalGateDecision, InMemoryApprovalGate,
)
from app.modules.m20_general_cognitive_worker.schemas import (
    HTNMethod, PlanNode, Risk, ToolSpec,
)
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService


@pytest.fixture()
def client():
    gate = InMemoryApprovalGate()
    service = CognitiveWorkerService(approval_gate=gate)

    async def search(args):
        return {"results": ["x"]}

    async def send(args):
        return {"sent": True}

    service.tools.register(ToolSpec(name="web_search", description="search", risk=Risk.READ), search)
    service.tools.register(ToolSpec(name="send_email", description="send", risk=Risk.EXTERNAL), send)
    service.planner.register_method(HTNMethod(
        name="research-report", goal_pattern="research topic and send summary",
        subtasks=[
            PlanNode(title="research", tool="web_search", risk=Risk.READ),
            PlanNode(title="send summary", tool="send_email", risk=Risk.EXTERNAL,
                     depends_on=["research"]),
        ],
    ))
    app = FastAPI()
    app.include_router(router)
    bind_service(service)
    return TestClient(app), service, gate


def test_goal_lifecycle_over_http(client):
    c, service, gate = client
    created = c.post("/api/modules/20/goals", json={"goal": "research topic and send summary"})
    assert created.status_code == 201
    body = created.json()
    assert body["state"] == "waiting_approval"
    task_id = body["task_id"]

    task = c.get(f"/api/modules/20/tasks/{task_id}")
    assert task.status_code == 200
    waiting = [n for n in task.json()["plan"] if n["state"] == "waiting_approval"]
    assert len(waiting) == 1
    gate.decide(waiting[0]["approval_id"], ApprovalGateDecision.APPROVED)

    resumed = c.post(f"/api/modules/20/tasks/{task_id}/resume",
                     json={"node_id": waiting[0]["id"], "approved": True})
    assert resumed.json()["state"] == "succeeded"

    listing = c.get("/api/modules/20/tasks").json()
    assert any(t["id"] == task_id and t["steps_done"] == 2 for t in listing)

    traces = c.get("/api/modules/20/traces", params={"task_id": task_id}).json()
    assert any(t["phase"] == "decide" for t in traces)


def test_ingest_memory_skills_tools_over_http(client):
    c, service, _ = client
    ingested = c.post("/api/modules/20/ingest/text",
                      json={"text": "competitor raised prices", "source": "api"})
    assert ingested.status_code == 201 and ingested.json()["ingested"] is True
    dupe = c.post("/api/modules/20/ingest/text",
                  json={"text": "competitor raised prices", "source": "api"})
    assert dupe.json()["ingested"] is False

    email = c.post("/api/modules/20/ingest/email",
                   json={"subject": "Grant", "body": "Deadline Friday", "sender": "a@b.c"})
    assert email.status_code == 201

    fact = c.post("/api/modules/20/memory/facts", json={"content": "grants need budgets"})
    assert fact.status_code == 201
    hits = c.get("/api/modules/20/memory/facts", params={"query": "what do grants need"}).json()
    assert hits and "budgets" in hits[0]["content"]
    assert c.get("/api/modules/20/memory/facts").status_code == 400

    skills = c.get("/api/modules/20/skills").json()
    assert any(s["name"] == "premortem" for s in skills)
    tools = c.get("/api/modules/20/tools").json()
    assert {t["name"] for t in tools} == {"web_search", "send_email"}


def test_standup_health_ruminate_and_404s(client):
    c, service, _ = client
    c.post("/api/modules/20/goals",
           json={"goal": "research topic and send summary", "run_immediately": False})
    standup = c.get("/api/modules/20/standup").json()["standup"]
    assert "research topic" in standup
    health = c.get("/api/modules/20/health").json()
    assert health["module"] == "m20_general_cognitive_worker"
    assert health["healthy"] is True

    task_id = c.get("/api/modules/20/tasks").json()[0]["id"]
    rum = c.post(f"/api/modules/20/tasks/{task_id}/ruminate").json()
    assert "simulations" in rum

    retro = c.post(f"/api/modules/20/tasks/{task_id}/retrospective",
                   json={"went_well": ["a"], "went_poorly": [], "lessons": ["l"]})
    assert retro.status_code == 200

    missing = "00000000-0000-0000-0000-000000000000"
    assert c.get(f"/api/modules/20/tasks/{missing}").status_code == 404
    assert c.post(f"/api/modules/20/tasks/{missing}/ruminate").status_code == 404
    assert c.post(f"/api/modules/20/tasks/{missing}/resume",
                  json={"node_id": "x", "approved": True}).status_code == 404
    assert c.post(f"/api/modules/20/tasks/{missing}/retrospective", json={}).status_code == 404


def test_booted_app_m20_routes_are_not_permanently_503_when_no_service_bound():
    """Regression: app.main never bound a GCW service, so /tasks, /standup, /tools... were 503 forever.
    The lazily-created default is in-memory with no models; this asserts reachability only, not model quality."""
    import app.modules.m20_general_cognitive_worker.routes as r
    saved = r._service
    r._service = None
    r._default_services.clear()
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        c = TestClient(app, raise_server_exceptions=False)
        assert c.get("/api/v1/api/modules/20/tasks").status_code == 200
        h = c.get("/api/v1/api/modules/20/health").json()
        assert h["healthy"] is True and "not a model" in h["healthy_meaning"]
        assert h["capabilities"]["executive_model_configured"] is False
        assert h["capabilities"]["embedder_configured"] is False
        assert h["capabilities"]["persistence"].startswith("none")
    finally:
        r._service = saved


def test_unbound_default_services_are_separate_per_tenant_in_dev_mode():
    """Dev-mode (tenant header trusted = TEST MODE) check that default services are not shared across tenants."""
    import app.modules.m20_general_cognitive_worker.routes as r
    saved = r._service
    r._service = None
    r._default_services.clear()
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        c = TestClient(app, raise_server_exceptions=False)
        a = {"x-atlas-tenant": "tenant-a"}
        b = {"x-atlas-tenant": "tenant-b"}
        made = c.post("/api/v1/api/modules/20/goals", json={"goal": "research topic and send summary"}, headers=a)
        assert made.status_code in (200, 201), made.text
        assert len(c.get("/api/v1/api/modules/20/tasks", headers=a).json()) == 1
        assert c.get("/api/v1/api/modules/20/tasks", headers=b).json() == []
        assert set(r._default_services) == {"tenant-a", "tenant-b"}
    finally:
        r._service = saved
        r._default_services.clear()


def _fresh_unbound():
    import app.modules.m20_general_cognitive_worker.routes as r
    saved = (r._service, dict(r._bound_by_tenant))
    r._service = None
    r._default_services.clear()
    r._bound_by_tenant.clear()
    return r, saved


def test_shared_bound_service_is_refused_in_production_unless_single_tenant(monkeypatch):
    r, saved = _fresh_unbound()
    try:
        from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
        from fastapi import HTTPException
        r.bind_service(CognitiveWorkerService())
        tok = r._tenant_var.set("tenant-a")
        try:
            assert r.get_service() is r._service  # dev/test mode: shared serves everyone
            monkeypatch.setenv("ATLAS_ENV", "production")
            monkeypatch.delenv("ATLAS_GCW_SINGLE_TENANT", raising=False)
            with pytest.raises(HTTPException) as e:
                r.get_service()
            assert e.value.status_code == 503
            monkeypatch.setenv("ATLAS_GCW_SINGLE_TENANT", "tenant-b")
            with pytest.raises(HTTPException):
                r.get_service()
            monkeypatch.setenv("ATLAS_GCW_SINGLE_TENANT", "tenant-a")
            assert r.get_service() is r._service
        finally:
            r._tenant_var.reset(tok)
    finally:
        r._service, bound = saved
        r._bound_by_tenant.clear(); r._bound_by_tenant.update(bound)


def test_per_tenant_binding_serves_only_that_tenant_and_missing_tenant_fails_closed():
    r, saved = _fresh_unbound()
    try:
        from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
        from fastapi import HTTPException
        svc_a = CognitiveWorkerService()
        r.bind_service(svc_a, tenant_id="tenant-a")
        tok = r._tenant_var.set("tenant-a")
        assert r.get_service() is svc_a
        r._tenant_var.reset(tok)
        tok = r._tenant_var.set("tenant-b")
        assert r.get_service() is not svc_a  # b gets its own default, never a's
        r._tenant_var.reset(tok)
        with pytest.raises(HTTPException):  # no request-scoped tenant: no shared bucket
            r.get_service()
    finally:
        r._service, bound = saved
        r._bound_by_tenant.clear(); r._bound_by_tenant.update(bound)


def test_default_service_cap_fails_closed_without_evicting(monkeypatch):
    r, saved = _fresh_unbound()
    try:
        from fastapi import HTTPException
        monkeypatch.setattr(r, "MAX_DEFAULT_TENANT_SERVICES", 2)
        made = {}
        for t in ("t1", "t2"):
            tok = r._tenant_var.set(t); made[t] = r.get_service(); r._tenant_var.reset(tok)
        tok = r._tenant_var.set("t3")
        with pytest.raises(HTTPException) as e:
            r.get_service()
        r._tenant_var.reset(tok)
        assert e.value.status_code == 503 and set(r._default_services) == {"t1", "t2"}
        tok = r._tenant_var.set("t1"); assert r.get_service() is made["t1"]; r._tenant_var.reset(tok)
    finally:
        r._service, bound = saved
        r._bound_by_tenant.clear(); r._bound_by_tenant.update(bound)


def test_concurrent_requests_for_two_tenants_do_not_cross():
    import threading
    r, saved = _fresh_unbound()
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        errors = []

        def work(tenant, n):
            c = TestClient(app, raise_server_exceptions=False)
            h = {"x-atlas-tenant": tenant}
            for i in range(n):
                if c.post("/api/v1/modules/20/goals", json={"goal": "research topic and send summary"}, headers=h).status_code not in (200, 201):
                    errors.append((tenant, "post"))
            got = c.get("/api/v1/modules/20/tasks", headers=h).json()
            if len(got) != n:
                errors.append((tenant, len(got), n))
        ts = [threading.Thread(target=work, args=("tc-a", 3)), threading.Thread(target=work, args=("tc-b", 5))]
        [t.start() for t in ts]; [t.join() for t in ts]
        assert not errors, errors
    finally:
        r._service, bound = saved
        r._bound_by_tenant.clear(); r._bound_by_tenant.update(bound)
        r._default_services.clear()


def test_clean_m20_alias_matches_legacy_path_and_is_not_a_prefix_match():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app, raise_server_exceptions=False)
    legacy = c.get("/api/v1/api/modules/20/health")
    clean = c.get("/api/v1/modules/20/health")
    assert legacy.status_code == clean.status_code == 200
    assert c.get("/api/v1/modules/2000/health").status_code == 404


def test_tenant_scope_dependency_restores_context_directly():
    """Direct generator-dependency test: the tenant contextvar is set inside and restored after, even on error."""
    import asyncio
    from app.auth.context import TenantContext
    import app.modules.m20_general_cognitive_worker.routes as r

    async def run():
        assert r._tenant_var.get() is None
        gen = r._tenant_scope(TenantContext("tenant-x", "u"))
        await gen.__anext__()
        assert r._tenant_var.get() == "tenant-x"
        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("handler failed"))
        assert r._tenant_var.get() is None
        gen2 = r._tenant_scope(TenantContext("tenant-y", "u"))
        await gen2.__anext__()
        with pytest.raises(StopAsyncIteration):
            await gen2.__anext__()
        assert r._tenant_var.get() is None
    asyncio.run(run())


def test_alias_and_legacy_paths_both_fail_closed_unauthenticated_in_production(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app, raise_server_exceptions=False)
    monkeypatch.setenv("ATLAS_ENV", "production")
    for path in ("/api/v1/api/modules/20/tasks", "/api/v1/modules/20/tasks"):
        r = c.get(path)  # no bearer token
        assert r.status_code == 401, (path, r.status_code, r.text[:100])
        r = c.get(path, headers={"x-atlas-tenant": "tenant-a"})  # header alone must not authenticate in production
        assert r.status_code == 401, (path, r.status_code)


def test_alias_and_legacy_share_one_rate_bucket_no_bypass_by_alternate_path():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.platform.middleware import ProductionBoundaryMiddleware
    c = TestClient(app, raise_server_exceptions=False)
    c.get("/health")  # builds the middleware stack
    m = app.middleware_stack
    mw = None
    while m is not None:
        if isinstance(m, ProductionBoundaryMiddleware):
            mw = m
            break
        m = getattr(m, "app", None)
    assert mw is not None
    old_limit = mw.limiter.limit
    mw.limiter.limit = 3
    mw.limiter._hits.clear()
    try:
        h = {"x-atlas-tenant": "rl-tenant", "x-atlas-actor": "rl-actor"}
        codes = [c.get("/api/v1/api/modules/20/health", headers=h).status_code,
                 c.get("/api/v1/modules/20/health", headers=h).status_code,
                 c.get("/api/v1/api/modules/20/health", headers=h).status_code]
        assert codes == [200, 200, 200]
        assert c.get("/api/v1/modules/20/health", headers=h).status_code == 429  # 4th, via the alias, same bucket
        assert c.get("/api/v1/api/modules/20/health", headers=h).status_code == 429
    finally:
        mw.limiter.limit = old_limit
        mw.limiter._hits.clear()
