"""Priority boundary probe: unbounded Python int vs SQL Integer column. HTTP-level."""
import os, sys, json
tree = os.environ["M19_TREE"]
os.environ["ATLAS_DATABASE_URL"] = os.environ.get("M19_DB", "sqlite:////tmp/m19/prio.db")
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
if "sqlite" in os.environ["ATLAS_DATABASE_URL"] and os.path.exists("/tmp/m19/prio.db"):
    os.remove("/tmp/m19/prio.db")
sys.path.insert(0, tree)
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from app.modules.m19_idea_incubator import routes as m19_routes
from app.modules.m19_idea_incubator.service import Service
from app.core.approvals import approvals
CANVAS = {"problem": ["p"], "customer_segments": ["c"], "unique_value_proposition": "u",
          "solution": ["s"], "channels": ["ch"], "revenue_streams": ["r"], "cost_structure": ["c"],
          "key_metrics": ["k"], "unfair_advantage": None, "riskiest_assumptions": ["a"]}
async def fake_generate(prompt, provider, model): return ("", json.dumps(CANVAS))
async def header_tenant(x_tenant: str = Header(default="tenant-a")):
    return TenantContext(tenant_id=x_tenant, actor_id=x_tenant)
svc = Service(generate=fake_generate, approval_store=approvals)
app = FastAPI(); app.include_router(m19_routes.router)
app.dependency_overrides[require_tenant] = header_tenant
app.dependency_overrides[m19_routes.get_service] = lambda: svc
c = TestClient(app, raise_server_exceptions=False)
A = {"x-tenant": "tenant-a"}
cases = [("max int4", 2147483647), ("int4+1", 2147483648), ("huge 2^63", 2**63), ("beyond 2^63", 2**70),
         ("negative", -7), ("bool true", True), ("string '5'", "5"), ("float 3.9", 3.9)]
for label, val in cases:
    r = c.post("/idea-incubator/ideas", json={"one_liner": f"prio {label}", "priority": val}, headers=A)
    print(f"{label}: HTTP {r.status_code} {r.text[:100] if r.status_code != 201 else 'id=' + r.json()['id'][:8]}")
print("DB", os.environ["ATLAS_DATABASE_URL"][:40])
