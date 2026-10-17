"""M19 preview-approval tenant scoping regression. REAL imports only: routes.py, service.py,
schemas, app.core.approvals facade, m00_approval_center Service, app.auth.context, app.core.database
from atlas-ai @ 94fe792d7eed01c37091bb87a18989d1c0f2d61a, fetched live 2026-10-17.
HTTP through the real router on a real SQLite database (ATLAS_DATABASE_URL temp file,
ATLAS_AUTO_CREATE_SCHEMA=1). Only two seams are substituted, both the app's own injection points:
require_tenant (FastAPI dependency_overrides, header-selected tenant) and the Service `generate`
constructor arg (deterministic lean-canvas JSON; no LLM network call is made or authorized here).
Select tree with M19_TREE. Builder self-report."""
import os, json, sys
tree = os.environ["M19_TREE"]
os.environ["ATLAS_DATABASE_URL"] = "sqlite:////tmp/m19/approvals_test.db"
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
if os.path.exists("/tmp/m19/approvals_test.db"):
    os.remove("/tmp/m19/approvals_test.db")
sys.path.insert(0, tree)
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from app.core.approvals import approvals
from app.modules.m19_idea_incubator import routes as m19_routes
from app.modules.m19_idea_incubator.service import Service

CANVAS = {"problem": ["p"], "customer_segments": ["c"], "unique_value_proposition": "u",
          "solution": ["s"], "channels": ["ch"], "revenue_streams": ["r"], "cost_structure": ["c"],
          "key_metrics": ["k"], "unfair_advantage": None, "riskiest_assumptions": ["a"]}

async def fake_generate(prompt, provider, model):
    return ("", json.dumps(CANVAS))

async def header_tenant(x_tenant: str = Header(default="tenant-a")):
    return TenantContext(tenant_id=x_tenant, actor_id=x_tenant)

def make_client():
    app = FastAPI()
    app.include_router(m19_routes.router)
    app.dependency_overrides[require_tenant] = header_tenant
    svc = Service(generate=fake_generate, approval_store=approvals)
    app.dependency_overrides[m19_routes.get_service] = lambda: svc
    return TestClient(app)

def intake_and_preview(c, tenant, cost=5):
    r = c.post("/idea-incubator/ideas", json={"one_liner": "test idea", "budget_cap": 25},
               headers={"x-tenant": tenant})
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]
    p = c.post(f"/idea-incubator/ideas/{run_id}/preview",
               json={"artifacts": ["a1"], "estimated_cost": cost}, headers={"x-tenant": tenant})
    assert p.status_code == 201, p.text
    return run_id, p.json()

results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))

c = make_client()
run_id, item = intake_and_preview(c, "tenant-a")
item_id = item["id"]

check("response payload carries tenant_id",
      item["payload"].get("tenant_id") == "tenant-a",
      f"payload keys: {sorted(item['payload'].keys())}")
check("approval filed in owning tenant queue",
      any(x.id == item_id for x in approvals.list(user_id="tenant-a")))
check("approval NOT filed under default queue",
      not any(x.id == item_id for x in approvals.list(user_id="default")))
check("cross-tenant get denied",
      approvals.get(item_id, user_id="tenant-b") is None)
check("owning tenant get returns item",
      approvals.get(item_id, user_id="tenant-a") is not None)

r = c.post(f"/idea-incubator/ideas/{run_id}/preview",
           json={"artifacts": ["a2"], "estimated_cost": 3}, headers={"x-tenant": "tenant-b"})
check("foreign-run preview rejected 404", r.status_code == 404, f"got {r.status_code}")

r = c.post(f"/idea-incubator/ideas/{run_id}/preview",
           json={"artifacts": ["a3"], "estimated_cost": 21}, headers={"x-tenant": "tenant-a"})
check("budget cap still enforced (409)", r.status_code == 409, f"got {r.status_code}")

failed = [n for n, ok, _ in results if not ok]
print(f"TREE={tree} TOTAL={len(results)} FAILED={len(failed)}")
sys.exit(1 if failed else 0)
