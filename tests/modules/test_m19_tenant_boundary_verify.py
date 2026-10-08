"""Independent tenant-boundary probe for Module 19 over the real OIDC verifier and a real SQLite database.

Run with ATLAS_ENV=production ATLAS_DATABASE_URL=sqlite:////tmp/x.db (see run_m19_tenant_verify.sh).
Each test names what it counts. Tests that expose real gaps are NOT xfail: they fail loudly.
"""
from __future__ import annotations
import os
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not os.environ.get("ATLAS_DATABASE_URL","").startswith("sqlite:///") or "atlas.db" in os.environ.get("ATLAS_DATABASE_URL",""), reason="needs isolated ATLAS_DATABASE_URL")

@pytest.fixture
def prod(monkeypatch):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    monkeypatch.setenv("ATLAS_ENV", "production")

@pytest.fixture
def c(prod, oidc_auth_headers):
    from app.modules.m19_idea_incubator.routes import router
    from app.auth.context import require_tenant
    app = FastAPI(); app.include_router(router, prefix='/api/v1', dependencies=[Depends(require_tenant)])  # same mount as app/main.py
    cl = TestClient(app); cl.h = oidc_auth_headers
    return cl

P = "/api/v1/idea-incubator/portfolio/ideas"
def mk(c, tenant):
    r = c.post(P, json={"title": "Idea", "problem": "P", "proposed_solution": "S"}, headers=c.h(tenant)); assert r.status_code == 201, r.text
    return r.json()["id"]

def test_portfolio_routes_reject_missing_and_forged_credentials(c):
    n = 0
    for rpath, ops in c.app.openapi()["paths"].items():
        if not rpath.startswith(P): continue
        for m in (k.upper() for k in ops):
            path = rpath.replace("{idea_id}", "x").replace("{experiment_id}", "y")
            r = c.request(m, path, json={})
            assert r.status_code in (401, 403), (m, path, r.status_code); n += 1
            r = c.request(m, path, json={}, headers={"Authorization": "Bearer a.b.c", "X-Atlas-Tenant": "tenant-a"})
            assert r.status_code in (401, 403), (m, path, r.status_code)
    assert n >= 7

def test_cross_tenant_reads_and_writes_all_404_and_leave_no_rows(c):
    i = mk(c, "tenant-a")
    ev = {"kind": "market_data", "claim": "c", "source": "s", "polarity": "supports", "strength": .8, "confidence": .7, "observed_at": "2026-10-01T00:00:00+00:00"}
    dim = {"score": 80, "confidence": .8, "notes": "n"}
    exp = {"name": "n", "hypothesis": "h", "method": "m", "metric": "x", "target": 10}
    b = c.h("tenant-b")
    assert c.get(f"{P}/{i}", headers=b).status_code == 404
    assert c.post(f"{P}/{i}/evidence", json=ev, headers=b).status_code == 404
    assert c.post(f"{P}/{i}/feasibility-tests", json={k: dim for k in ("desirability","technical","viability","strategic_fit","compliance")}, headers=b).status_code == 404
    assert c.post(f"{P}/{i}/experiments", json=exp, headers=b).status_code == 404
    assert c.post(f"{P}/{i}/decisions", json={"to_stage": "discovery", "rationale": "x"}, headers=b).status_code == 404
    assert c.get(P, headers=b).json() == []
    d = c.get(f"{P}/{i}", headers=c.h("tenant-a")).json()
    assert d["idea"]["stage"] == "captured" and d["idea"]["version"] == 1, d

def test_cross_tenant_experiment_patch_and_outcome_404(c):
    i = mk(c, "tenant-a")
    e = c.post(f"{P}/{i}/experiments", json={"name": "n", "hypothesis": "h", "method": "m", "metric": "x", "target": 10}, headers=c.h("tenant-a")).json()["id"]
    b = c.h("tenant-b")
    assert c.patch(f"{P}/{i}/experiments/{e}", json={"status": "running"}, headers=b).status_code == 404
    # tenant B owns its own idea; A's experiment id must not resolve under B's idea either
    j = mk(c, "tenant-b")
    assert c.patch(f"{P}/{j}/experiments/{e}", json={"status": "running"}, headers=b).status_code == 404
    a = c.get(f"{P}/{i}", headers=c.h("tenant-a")).json()
    assert "running" not in str(a)

def test_foreign_idea_id_collision_does_not_500_or_leak(c):
    """SqlIdeaRepository.save_idea with an id owned by another tenant: global unique(id) vs tenant-scoped lookup."""
    from app.modules.m19_idea_incubator.repository import SqlIdeaRepository
    from app.modules.m19_idea_incubator.schemas import Idea, IdeaStage
    from datetime import datetime, timezone
    i = mk(c, "tenant-a"); now = datetime.now(timezone.utc)
    x = Idea(id=i, title="steal", problem="p", proposed_solution="s", tags=[], metadata={}, stage=IdeaStage("captured"), version=1, created_at=now, updated_at=now)
    try:
        SqlIdeaRepository("tenant-b").save_idea(x)
        raised = None
    except Exception as exc:  # report type; any exception is a boundary signal, not a clean refusal
        raised = type(exc).__name__
    a = SqlIdeaRepository("tenant-a").get_idea(i)
    assert a.title == "Idea", "tenant A row was overwritten"
    assert SqlIdeaRepository("tenant-b").get_idea(i) is None, "tenant B now sees A's id"
    assert raised in (None, "RuntimeError", "LookupError", "ConflictError", "ValidationError"), f"foreign-id write raised raw {raised} (existence oracle / 500)"

def test_legacy_run_routes_reject_missing_credentials_at_production_mount(c):
    for m, p in (("POST", "/api/v1/idea-incubator/ideas"), ("GET", "/api/v1/idea-incubator/ideas/z"), ("POST", "/api/v1/idea-incubator/ideas/z/preview"), ("POST", "/api/v1/idea-incubator/packages"), ("POST", "/api/v1/idea-incubator/portfolio/ideas/x/business-analyses")):
        assert c.request(m, p, json={}).status_code in (401, 403), (m, p)

def test_legacy_run_is_not_readable_or_previewable_by_another_tenant(c, monkeypatch):
    """Service._runs is process-global and RunOut carries no tenant: tenant B can read and preview tenant A's run."""
    import json, asyncio
    import app.modules.m19_idea_incubator.routes as R
    from app.modules.m19_idea_incubator.service import Service
    canvas = {"problem": ["p"], "customer_segments": ["c"], "unique_value_proposition": "u", "solution": ["s"], "channels": ["ch"], "revenue_streams": ["r"], "cost_structure": ["k"], "key_metrics": ["m"], "riskiest_assumptions": ["a"]}
    async def gen(prompt, provider, model): return ("x", json.dumps(canvas))
    class Store:
        def put(self, item, **kw): return item
    svc = Service(generate=gen, approval_store=Store())
    c.app.dependency_overrides[R.get_service] = lambda: svc
    a = c.post("/api/v1/idea-incubator/ideas", json={"one_liner": "tenant a secret idea"}, headers=c.h("tenant-a")); assert a.status_code == 201, a.text
    rid = a.json()["id"]
    assert c.get(f"/api/v1/idea-incubator/ideas/{rid}", headers=c.h("tenant-a")).status_code == 200
    assert c.get(f"/api/v1/idea-incubator/ideas/{rid}", headers=c.h("tenant-b")).status_code == 404, "tenant B read tenant A's run"
    r = c.post(f"/api/v1/idea-incubator/ideas/{rid}/preview", json={"artifacts": ["x"], "estimated_cost": 1}, headers=c.h("tenant-b"))
    assert r.status_code == 404, f"tenant B created an approval request against tenant A's run ({r.status_code})"
