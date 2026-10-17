import os, sys, json
sys.path.insert(0, os.environ["M19_TREE"])
os.environ["ATLAS_DATABASE_URL"] = "sqlite:////tmp/m19/mainapp2.db"
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
os.environ["ATLAS_DEV_NO_AUTH"] = "1"
os.environ["ATLAS_ENV"] = "development"
for f in ("/tmp/m19/mainapp2.db",):
    if os.path.exists(f): os.remove(f)
from app.main import app
from app.auth.context import TenantContext, require_tenant
from app.modules.m19_idea_incubator import routes as m19_routes
from app.modules.m19_idea_incubator.service import Service
from app.core.approvals import approvals
from fastapi.testclient import TestClient
CANVAS = {"problem": ["p"], "customer_segments": ["c"], "unique_value_proposition": "u", "solution": ["s"], "channels": ["ch"], "revenue_streams": ["r"], "cost_structure": ["c"], "key_metrics": ["k"], "unfair_advantage": None, "riskiest_assumptions": ["a"]}
async def fg(p, pr, m): return ("", json.dumps(CANVAS))
H={"x-atlas-tenant":"tenant-a","x-atlas-actor":"tester"}
app.dependency_overrides[m19_routes.get_service] = lambda: Service(generate=fg, approval_store=approvals)
c = TestClient(app, raise_server_exceptions=False, headers=H)
r = c.post("/api/v1/idea-incubator/ideas", json={"one_liner": "main app idea", "budget_cap": 25})
print("intake:", r.status_code, r.text[:60])
rid = r.json()["id"] if r.status_code == 201 else None
if rid:
    url = f"/api/v1/idea-incubator/ideas/{rid}/preview"
    print("nan:", c.post(url, data='{"artifacts":["a"],"estimated_cost":NaN}', headers={"content-type": "application/json"}).status_code)
    print("inf:", c.post(url, data='{"artifacts":["a"],"estimated_cost":Infinity}', headers={"content-type": "application/json"}).status_code)
    print("detail-sample:", c.post(url, data='{"artifacts":["a"],"estimated_cost":NaN}', headers={"content-type": "application/json"}).text[:160])
# global regression: another module's typed-body route with a normal validation error
r2 = c.post("/api/v1/goals/plan", json={})
print("goals/plan missing-field 422 shape:", r2.status_code, r2.text[:100])
r3 = c.post("/api/v1/idea-incubator/ideas", json={"one_liner": "overflow idea", "priority": 2147483648})
print("priority overflow on main app:", r3.status_code, r3.text[:100])
