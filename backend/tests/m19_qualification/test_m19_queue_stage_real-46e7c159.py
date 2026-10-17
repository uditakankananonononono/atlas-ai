"""M19 queue priority + optimistic expected-stage checks. REAL imports from composed_work
(frozen composition + qualifier CAS + run-store unit + this unit). Real HTTP + real DB
(SQLite or PG via M19_DB). Spec source: INTEGRATION.md @ 94fe792d ("optimistic expected-stage
checks ... queue priority"). Builder self-report."""
import os, json, sys, asyncio
tree = os.environ["M19_TREE"]
os.environ["ATLAS_DATABASE_URL"] = os.environ.get("M19_DB", "sqlite:////tmp/m19/qs_test.db")
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
if "sqlite" in os.environ["ATLAS_DATABASE_URL"] and os.path.exists("/tmp/m19/qs_test.db"):
    os.remove("/tmp/m19/qs_test.db")
sys.path.insert(0, tree)
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from app.modules.m19_idea_incubator import routes as m19_routes
from app.modules.m19_idea_incubator.service import Service
from app.modules.m19_idea_incubator.schemas import IntakeIn, PreviewIn, Stage
from app.core.approvals import approvals

CANVAS = {"problem": ["p"], "customer_segments": ["c"], "unique_value_proposition": "u",
          "solution": ["s"], "channels": ["ch"], "revenue_streams": ["r"], "cost_structure": ["c"],
          "key_metrics": ["k"], "unfair_advantage": None, "riskiest_assumptions": ["a"]}
async def fake_generate(prompt, provider, model): return ("", json.dumps(CANVAS))
async def header_tenant(x_tenant: str = Header(default="tenant-a")):
    return TenantContext(tenant_id=x_tenant, actor_id=x_tenant)

results = []
def check(name, ok, detail=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))

svc = Service(generate=fake_generate, approval_store=approvals)
from fastapi.exceptions import RequestValidationError
from app.core.validation_errors import request_validation_error_handler
app = FastAPI(); app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.include_router(m19_routes.router)
app.dependency_overrides[require_tenant] = header_tenant
app.dependency_overrides[m19_routes.get_service] = lambda: svc
c = TestClient(app); A = {"x-tenant": "tenant-a"}

# priority plumbed from intake request into the stored row
r1 = c.post("/idea-incubator/ideas", json={"one_liner": "low prio", "priority": 1}, headers=A)
r9 = c.post("/idea-incubator/ideas", json={"one_liner": "high prio", "priority": 9}, headers=A)
r5 = c.post("/idea-incubator/ideas", json={"one_liner": "mid prio", "priority": 5}, headers=A)
check("intake 201 x3 with priority field", all(r.status_code == 201 for r in (r1, r9, r5)))
lo, hi, mid = r1.json()["id"], r9.json()["id"], r5.json()["id"]

# queue priority selector: highest priority first, then mid, then low
n1 = svc._store.next_queued("tenant-a")
check("next_queued returns highest priority run", n1 is not None and n1.id == hi, n1.id[:8] if n1 else None)
# cross-tenant isolation of the queue selector
check("next_queued tenant-isolated", svc._store.next_queued("tenant-b") is None)

# caller-supplied optimistic expected_stage; default preserves original re-preview semantics
ok = c.post(f"/idea-incubator/ideas/{hi}/preview", json={"artifacts": ["a"], "estimated_cost": 1, "expected_stage": "landscape"}, headers=A)
check("preview with correct expected_stage allowed (201)", ok.status_code == 201, f"got {ok.status_code}")
wrong = c.post(f"/idea-incubator/ideas/{hi}/preview", json={"artifacts": ["a"], "estimated_cost": 1, "expected_stage": "landscape"}, headers=A)
check("wrong expected_stage rejected 409 with stage reason", wrong.status_code == 409 and "expected stage" in wrong.text, f"got {wrong.status_code} {wrong.text[:90]}")
run = svc.get(hi, "tenant-a")
check("rejected preview left reservation unchanged", run.reserved == 1, f"reserved={run.reserved}")
right = c.post(f"/idea-incubator/ideas/{hi}/preview", json={"artifacts": ["a"], "estimated_cost": 1, "expected_stage": "preview"}, headers=A)
check("re-preview allowed when caller asserts current stage (original semantics)", right.status_code == 201, f"got {right.status_code}")
bare = c.post(f"/idea-incubator/ideas/{mid}/preview", json={"artifacts": ["a"], "estimated_cost": 1}, headers=A)
check("no expected_stage supplied: preview allowed (original default)", bare.status_code == 201, f"got {bare.status_code}")
# raw NaN/+inf estimated_cost: typed 422 must RENDER (not 500 in error serialization)
for label, raw in (("NaN", "NaN"), ("+inf", "Infinity")):
    rr = c.post(f"/idea-incubator/ideas/{lo}/preview", data='{"artifacts": ["a"], "estimated_cost": %s}' % raw,
                headers={"x-tenant": "tenant-a", "content-type": "application/json"})
    check(f"raw {label} estimated_cost renders 422 (no serialization 500)", rr.status_code == 422, f"got {rr.status_code} {rr.text[:70]}")
run_after = svc.get(lo, "tenant-a")
check("reservation unaffected by refused raw probes", run_after.reserved == 0, f"reserved={run_after.reserved}")
# dedicated budget oracle unmasked by stage reason: LANDSCAPE run, over-cap -> 409 'budget cap exceeded'
over = c.post(f"/idea-incubator/ideas/{lo}/preview", json={"artifacts": ["a"], "estimated_cost": 999}, headers=A)
check("budget oracle: over-cap 409 says 'budget cap exceeded'", over.status_code == 409 and "budget cap exceeded" in over.text, over.text[:90])
# typed 422 contracts: int4 priority bounds, finite cost
for label, body, want in [("int4 max ok", {"one_liner": "prio max", "priority": 2147483647}, 201),
                          ("int4 min ok", {"one_liner": "prio min", "priority": -2147483648}, 201),
                          ("int4 overflow +", {"one_liner": "prio hi", "priority": 2147483648}, 422),
                          ("int4 overflow -", {"one_liner": "prio lo", "priority": -2147483649}, 422)]:
    r = c.post("/idea-incubator/ideas", json=body, headers=A)
    check(f"priority {label} -> {want}", r.status_code == want, f"got {r.status_code}")
import math
from app.modules.m19_idea_incubator.run_store import SqlRunStore, InMemoryRunStore
from app.modules.m19_idea_incubator.schemas import Stage as _S
from app.modules.m19_idea_incubator.schemas import RunOut, LeanCanvasOut
runobj = svc.get(lo, "tenant-a")
for store, nm in ((SqlRunStore(), "sql"), (InMemoryRunStore(), "memory")):
    if nm == "memory": store.create("tenant-a", runobj)
    for meth in ("reserve_budget", "release_budget"):
        try:
            getattr(store, meth)("tenant-a", lo, -5, "pending_approval", _S.PREVIEW) if meth == "reserve_budget" else getattr(store, meth)("tenant-a", lo, -5, 1, "queued", _S.LANDSCAPE)
            bad = "ACCEPTED (BAD)"
        except ValueError: bad = "refused"
        check(f"store-level negative {meth} refused ({nm})", bad == "refused", bad)

# priority does not leak into RunOut response shape (storage-only contract)
body = c.get(f"/idea-incubator/ideas/{lo}", headers=A).json()
check("RunOut response unchanged (no priority leak)", "priority" not in body)

failed = [n for n, ok in results if not ok]
print(f"TREE={tree} TOTAL={len(results)} FAILED={len(failed)}")
sys.exit(1 if failed else 0)
