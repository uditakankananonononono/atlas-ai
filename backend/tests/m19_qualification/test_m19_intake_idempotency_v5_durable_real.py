"""M19 intake idempotency (claim-first) regression. REAL imports only: routes.py, service.py,
schemas, idempotency.py, app.core.database, app.auth.context from atlas-ai @ 94fe792d..., fetched
live 2026-10-17. Real SQLite store. Substituted seams (app-owned injection points): require_tenant
via dependency_overrides, Service `generate` constructor arg (deterministic canvas; no LLM call).
Semantics under test: pre-effect durable claim, payload binding, tenant authority, concurrency
(exactly one generate), pending/in-progress with NO automatic reclaim (lease cannot prove worker or
effect died) and NO abandon on unknown-outcome failure, explicit grounded reconciliation only,
restart replay durable 201 via run store (same run, no second effect), receipt preserved; 410 kept only for
(resubmission could repeat a completed, possibly charged generation). Select tree with M19_TREE.
Builder self-report."""
import os, json, sys, asyncio, threading
from datetime import datetime, timedelta, timezone
tree = os.environ["M19_TREE"]
os.environ["ATLAS_DATABASE_URL"] = "sqlite:////tmp/m19/idempotency_test.db"
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
if os.path.exists("/tmp/m19/idempotency_test.db"):
    os.remove("/tmp/m19/idempotency_test.db")
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
CALLS = {"n": 0}
async def fake_generate(prompt, provider, model):
    CALLS["n"] += 1
    await asyncio.sleep(0.05)
    return ("", json.dumps(CANVAS))
async def header_tenant(x_tenant: str = Header(default="tenant-a")):
    return TenantContext(tenant_id=x_tenant, actor_id=x_tenant)

IDEM = os.path.exists(tree + "/app/modules/m19_idea_incubator/idempotency.py")
results = []
def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))

BODY = {"one_liner": "test idea", "budget_cap": 25, "idempotency_key": "k-1"}

if IDEM:
    from app.modules.m19_idea_incubator.idempotency import IntakeIdempotencyStore
    store = IntakeIdempotencyStore()
    svc = Service(generate=fake_generate, approval_store=approvals, idempotency_store=store)
else:
    svc = Service(generate=fake_generate, approval_store=approvals)

app = FastAPI()
app.include_router(m19_routes.router)
app.dependency_overrides[require_tenant] = header_tenant
app.dependency_overrides[m19_routes.get_service] = lambda: svc
c = TestClient(app)

r1 = c.post("/idea-incubator/ideas", json=BODY, headers={"x-tenant": "tenant-a"})
r2 = c.post("/idea-incubator/ideas", json=BODY, headers={"x-tenant": "tenant-a"})
check("replay same key+payload returns same run id",
      r1.status_code == 201 and r2.status_code == 201 and r1.json()["id"] == r2.json()["id"],
      f"{r1.status_code}/{r2.status_code}")
r3 = c.post("/idea-incubator/ideas", json={**BODY, "one_liner": "different idea"}, headers={"x-tenant": "tenant-a"})
check("same key + different payload rejected 409", r3.status_code == 409, f"got {r3.status_code}")
r4 = c.post("/idea-incubator/ideas", json=BODY, headers={"x-tenant": "tenant-b"})
check("same key other tenant is independent",
      r4.status_code == 201 and r4.json()["id"] != r1.json()["id"], f"got {r4.status_code}")
r5 = c.post("/idea-incubator/ideas", json={"one_liner": "no key", "budget_cap": 5}, headers={"x-tenant": "tenant-a"})
r6 = c.post("/idea-incubator/ideas", json={"one_liner": "no key", "budget_cap": 5}, headers={"x-tenant": "tenant-a"})
check("no key still creates distinct runs", r5.json()["id"] != r6.json()["id"])

if IDEM:
    from app.modules.m19_idea_incubator.schemas import IntakeIn
    # MIGRATED for the durable run store (run_store v1): a fresh Service over the SAME database
    # now finds the run durable, so restart replay returns the SAME run (201), not 410.
    # Receipt dedup safety assertions preserved: no second effect, receipt row unmutated.
    fresh = Service(generate=fake_generate, approval_store=approvals, idempotency_store=IntakeIdempotencyStore())
    calls_before_replay = CALLS["n"]
    try:
        out = asyncio.run(fresh.intake(IntakeIn.model_validate(BODY), "tenant-a", idempotency_key="k-1"))
        replayed, replay_msg = "201-durable", ""
    except Exception as e:
        out, replayed, replay_msg = None, type(e).__name__, str(e)
    check("restart replay returns SAME run via durable store (201, no 410, run present)",
          replayed == "201-durable" and out is not None and out.id == r1.json()["id"],
          f"got {replayed} id={out.id if out else None}")
    check("restart replay ran NO second effect (generate call count unchanged)",
          CALLS["n"] == calls_before_replay, f"calls {calls_before_replay} -> {CALLS['n']}")
    with IntakeIdempotencyStore().sessions() as db:
        from app.modules.m19_idea_incubator.idempotency import IntakeIdempotencyRow as _R
        kept = db.get(_R, ("tenant-a", "k-1"))
    check("completed receipt row preserved after durable replay (not mutated/deleted)",
          kept is not None and kept.status == "completed" and kept.run_id == r1.json()["id"]
          and kept.response_json is not None)
    # 410 path kept for a receipt whose run is genuinely absent from the store:
    # wording must still never instruct a new-key resubmission of a possibly-charged generation.
    st3 = IntakeIdempotencyStore()
    import hashlib as _h
    req_gone = IntakeIn.model_validate({**BODY, "idempotency_key": "k-gone"})
    digest_gone = _h.sha256(json.dumps({"tenant_id": "tenant-a", "request": req_gone.model_dump(mode="json", exclude={"idempotency_key"})}, sort_keys=True).encode()).hexdigest()
    st3.claim("tenant-a", "k-gone", digest_gone)
    st3.complete("tenant-a", "k-gone", "00000000-0000-0000-0000-000000000000", {"id": "00000000-0000-0000-0000-000000000000"})
    try:
        asyncio.run(svc.intake(req_gone, "tenant-a", idempotency_key="k-gone"))
        gone, gone_msg = "no-error", ""
    except Exception as e:
        gone, gone_msg = type(e).__name__, str(e)
    check("receipt with absent run still qualified 410-class, message never instructs new-key resubmission",
          gone == "IdempotencyUnavailableError" and "submit a new request" not in gone_msg
          and ("reconciliation" in gone_msg or "restoration" in gone_msg), f"{gone} | {gone_msg[:120]}")

    before = CALLS["n"]
    ids, codes = set(), []
    def worker():
        try:
            out = asyncio.run(svc.intake(IntakeIn.model_validate({**BODY, "idempotency_key": "k-race"}), "tenant-a", idempotency_key="k-race"))
            ids.add(out.id); codes.append(201)
        except Exception as e:
            codes.append(type(e).__name__)
    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    check("8-way race: exactly one run id", len(ids) == 1, f"distinct={len(ids)} codes={codes}")
    check("8-way race: exactly one generate call", CALLS["n"] - before == 1, f"calls={CALLS['n'] - before}")
    check("8-way race: losers get in-progress or replay, none error",
          all(x in (201, "IdempotencyInProgressError") for x in codes), f"codes={codes}")

    req = IntakeIn.model_validate({**BODY, "idempotency_key": "k-pend"})
    digest = __import__("hashlib").sha256(json.dumps({"tenant_id": "tenant-a", "request": req.model_dump(mode="json", exclude={"idempotency_key"})}, sort_keys=True).encode()).hexdigest()
    st = IntakeIdempotencyStore()
    outcome, _ = st.claim("tenant-a", "k-pend", digest)
    check("manual claim succeeds", outcome == "claimed", outcome)
    try:
        asyncio.run(svc.intake(req, "tenant-a", idempotency_key="k-pend"))
        pend = "no-error"
    except Exception as e:
        pend = type(e).__name__
    check("fresh pending claim -> in-progress, no second effect", pend == "IdempotencyInProgressError", pend)
    from app.modules.m19_idea_incubator.idempotency import IntakeIdempotencyRow
    from sqlalchemy import update as sa_update
    with st.sessions.begin() as db:
        db.execute(sa_update(IntakeIdempotencyRow).where(IntakeIdempotencyRow.key == "k-pend")
                   .values(updated_at=datetime.now(timezone.utc) - timedelta(hours=1)))
    try:
        asyncio.run(svc.intake(req, "tenant-a", idempotency_key="k-pend"))
        stale = "no-error"
    except Exception as e:
        stale = type(e).__name__
    check("STALE pending claim is NOT auto-reclaimed (lease cannot prove worker/effect died)",
          stale == "IdempotencyInProgressError", stale)

    flops = {"n": 0}
    async def flaky(prompt, provider, model):
        flops["n"] += 1
        if flops["n"] == 1:
            raise RuntimeError("outcome unknown: remote effect may have run")
        return ("", json.dumps(CANVAS))
    svc2 = Service(generate=flaky, approval_store=approvals, idempotency_store=IntakeIdempotencyStore())
    req2 = IntakeIn.model_validate({**BODY, "idempotency_key": "k-flop"})
    try:
        asyncio.run(svc2.intake(req2, "tenant-a", idempotency_key="k-flop"))
    except RuntimeError:
        pass
    try:
        asyncio.run(svc2.intake(req2, "tenant-a", idempotency_key="k-flop"))
        after_fail = "no-error"
    except Exception as e:
        after_fail = type(e).__name__
    check("unknown-outcome failure keeps claim pending; retry does NOT re-run effect",
          after_fail == "IdempotencyInProgressError" and flops["n"] == 1, f"{after_fail} calls={flops['n']}")
    st2 = IntakeIdempotencyStore()
    check("explicit grounded reconciliation clears the pending claim",
          st2.reconcile_abandon("tenant-a", "k-flop") is True)
    out2 = asyncio.run(svc2.intake(req2, "tenant-a", idempotency_key="k-flop"))
    check("after explicit reconciliation a retry succeeds", bool(out2.id), f"calls={flops['n']}")

failed = [n for n, ok in results if not ok]
print(f"TREE={tree} TOTAL={len(results)} FAILED={len(failed)}")
sys.exit(1 if failed else 0)
