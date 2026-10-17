"""Independent boundary probes for the M19 run-store candidate: budget negative/NaN/inf,
store-level negative cost, cross-tenant reserve denial. Real SQLite, real HTTP, no model calls."""
import os, sys, json, asyncio, math
tree = os.environ["M19_TREE"]
os.environ["ATLAS_DATABASE_URL"] = "sqlite:////tmp/m19/boundary.db"
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
if os.path.exists("/tmp/m19/boundary.db"): os.remove("/tmp/m19/boundary.db")
sys.path.insert(0, tree)
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from app.modules.m19_idea_incubator import routes as m19_routes
from app.modules.m19_idea_incubator.service import Service
from app.modules.m19_idea_incubator.run_store import SqlRunStore
from app.core.approvals import approvals

CANVAS = {"problem": ["p"], "customer_segments": ["c"], "unique_value_proposition": "u",
          "solution": ["s"], "channels": ["ch"], "revenue_streams": ["r"], "cost_structure": ["c"],
          "key_metrics": ["k"], "unfair_advantage": None, "riskiest_assumptions": ["a"]}
async def fake_generate(prompt, provider, model): return ("", json.dumps(CANVAS))
async def header_tenant(x_tenant: str = Header(default="tenant-a")):
    return TenantContext(tenant_id=x_tenant, actor_id=x_tenant)
svc = Service(generate=fake_generate, approval_store=approvals, idempotency_store=None)
app = FastAPI(); app.include_router(m19_routes.router)
app.dependency_overrides[require_tenant] = header_tenant
app.dependency_overrides[m19_routes.get_service] = lambda: svc
c = TestClient(app)
results = []
def check(name, ok, detail=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))

r = c.post("/idea-incubator/ideas", json={"one_liner": "boundary idea", "budget_cap": 25}, headers={"x-tenant": "tenant-a"})
run_id = r.json()["id"]
url = f"/idea-incubator/ideas/{run_id}/preview"
for label, val in (("negative", -5), ("NaN", float("nan")), ("+inf", float("inf")), ("zero", 0)):
    body = {"artifacts": ["a"], "estimated_cost": val}
    try:
        rr = c.post(url, data=json.dumps(body, allow_nan=True), headers={"x-tenant": "tenant-a", "content-type": "application/json"})
        refused, how = (rr.status_code == 422), f"status {rr.status_code}"
    except Exception as e:
        refused, how = ("validation error" in type(e).__name__.lower() or "RequestValidation" in type(e).__name__), f"raised {type(e).__name__} (router re-raises instead of 422 response)"
    if label == "zero":
        check("zero cost preview allowed and reserves 0", refused is False, how)
    else:
        check(f"{label} estimated_cost refused at route", refused, how)
run = svc.get(run_id, "tenant-a")
check("reserved unaffected by refused probes", run.reserved == 0, f"reserved={run.reserved}")

# store-level negative cost (bypasses route schema): does the CAS guard it?
st = SqlRunStore()
try:
    st.reserve_budget("tenant-a", run_id, -5, "pending_approval", __import__("app.modules.m19_idea_incubator.schemas", fromlist=["Stage"]).Stage.PREVIEW)
    neg = f"ACCEPTED reserved={st.get('tenant-a', run_id).reserved}"
except Exception as e:
    neg = f"refused {type(e).__name__}"
check("store-level negative cost handling", "refused" in neg or "ACCEPTED" in neg, neg)  # report either way
# cross-tenant reserve on someone else's run id
try:
    st.reserve_budget("tenant-b", run_id, 1, "pending_approval", __import__("app.modules.m19_idea_incubator.schemas", fromlist=["Stage"]).Stage.PREVIEW)
    xten = "ACCEPTED (BAD)"
except KeyError:
    xten = "KeyError (denied)"
check("cross-tenant reserve denied", "denied" in xten, xten)
# NaN direct at store: CAS condition NULL/false -> ValueError expected, reserved unchanged
before = st.get("tenant-a", run_id).reserved
try:
    st.reserve_budget("tenant-a", run_id, float("nan"), "pending_approval", __import__("app.modules.m19_idea_incubator.schemas", fromlist=["Stage"]).Stage.PREVIEW)
    nan = f"ACCEPTED reserved={st.get('tenant-a', run_id).reserved}"
except ValueError:
    nan = f"ValueError (refused), reserved={st.get('tenant-a', run_id).reserved}"
check("store-level NaN cost refused by CAS falsity", "refused" in nan, nan)
failed = [n for n, ok in results if not ok]
print(f"TOTAL={len(results)} FAILED={len(failed)}")
