"""Delivered contract pins for the M19 repair delta (bedd1c9f -> e5d8cd11). REAL imports from the
COMPOSED tree; real SQLite. No model calls (generate constructor seam; recording stub).
C1 SqlRunStore() construction performs NO engine work: no create_all, no engine connect.
C2 create_all is deferred to first store use and runs exactly once across later calls (flag guard).
C3 IntegrityError mapping: duplicate run id -> RuntimeError('run id unavailable');
   NOT NULL violation -> raw IntegrityError propagates unmasked (not RuntimeError).
   (m19_runs/m19_run_events declare no ForeignKey constraints; unique + NOT NULL paths pinned.)
C4 Cross-mode isolation: tenantless runs unreachable via tenant get/preview and vice versa; same
   run id existing in both modes does not bleed; tenantless intake keeps the legacy generate call
   shape generate(prompt, provider, model) and process-local dict storage; idempotency_key without
   a tenant is refused (ValueError) as before.
Builder self-report."""
import os, json, sys, asyncio
tree = os.environ["M19_TREE"]
os.environ["ATLAS_DATABASE_URL"] = os.environ.get("M19_DB", "sqlite:////tmp/m19/repair_contracts.db")
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
for f in ("/tmp/m19/repair_contracts.db",):
    if os.path.exists(f):
        os.remove(f)
sys.path.insert(0, tree)
from sqlalchemy.exc import IntegrityError
from app.modules.m19_idea_incubator import run_store as rs
from app.modules.m19_idea_incubator.run_store import SqlRunStore
from app.modules.m19_idea_incubator.service import Service
from app.modules.m19_idea_incubator.schemas import RunOut, Stage, GateOut, LeanCanvasOut, PreviewIn, IntakeIn
from app.core.approvals import approvals

CANVAS = {"problem": ["p"], "customer_segments": ["c"], "unique_value_proposition": "u",
          "solution": ["s"], "channels": ["ch"], "revenue_streams": ["r"], "cost_structure": ["c"],
          "key_metrics": ["k"], "unfair_advantage": None, "riskiest_assumptions": ["a"]}

results = []
def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))

def mk_run(rid, cap=25.0):
    return RunOut(id=rid, state="queued", stage=Stage.LANDSCAPE,
                  canvas=LeanCanvasOut.model_validate(CANVAS),
                  gates=[GateOut(stage=Stage.INTAKE, proceed=True, reasons=["intake normalized"],
                                 missing_evidence=["a"], expected_cost=0)], budget_cap=cap)

# ---- C1: construction performs no engine work
calls = {"create_all": 0, "connect": 0}
real_create_all = rs.Base.metadata.create_all
real_connect = rs.engine.connect
class _ConnectSpy:
    def __call__(self, *a, **k):
        calls["connect"] += 1
        return real_connect(*a, **k)
rs.Base.metadata.create_all = lambda *a, **k: calls.__setitem__("create_all", calls["create_all"] + 1)
rs.engine.connect = _ConnectSpy()
try:
    st = SqlRunStore()
finally:
    rs.Base.metadata.create_all = real_create_all
    rs.engine.connect = real_connect
check("C1 construction: no create_all at construction", calls["create_all"] == 0, f"create_all calls={calls['create_all']}")
check("C1 construction: no engine connect at construction", calls["connect"] == 0, f"connect calls={calls['connect']}")

# ---- C2: create_all deferred to first use, exactly once across calls
rs.Base.metadata.create_all = lambda *a, **k: (calls.__setitem__("create_all", calls["create_all"] + 1), real_create_all(*a, **k))[1]
try:
    st.create("t-c2", mk_run("run-c2"))
    after_first = calls["create_all"]
    st.get("t-c2", "run-c2"); st.list_events("t-c2", "run-c2"); st.next_queued("t-c2")
    after_many = calls["create_all"]
finally:
    rs.Base.metadata.create_all = real_create_all
check("C2 deferred create_all fires on first store use", after_first == 1, f"after first use={after_first}")
check("C2 create_all exactly once across later calls", after_many == 1, f"after 4 uses={after_many}")

# ---- C3: narrowed IntegrityError mapping
st2 = SqlRunStore()
st2.create("t-c3", mk_run("run-dup"))
try:
    st2.create("t-c3", mk_run("run-dup"))
    dup = "NO ERROR (BAD)"
except RuntimeError as e:
    dup = f"RuntimeError: {e}"
except IntegrityError as e:
    dup = f"IntegrityError leaked: {str(e.orig)[:80]}"
check("C3 duplicate run id -> RuntimeError('run id unavailable')", dup == "RuntimeError: run id unavailable", dup)
try:
    st2.create(None, mk_run("run-null-tenant"))  # NOT NULL tenant_id violation
    nn = "NO ERROR (BAD)"
except RuntimeError as e:
    nn = f"MASKED as RuntimeError: {e} (BAD)"
except IntegrityError as e:
    nn = f"raw IntegrityError: {str(e.orig)[:70]}"
check("C3 NOT NULL violation -> raw IntegrityError, unmasked", nn.startswith("raw IntegrityError"), nn)
check("C3 no ForeignKey constraints on m19 tables (unique+NOT NULL paths only)",
      all(not t.foreign_keys for t in (rs.RunRow.__table__, rs.RunEventRow.__table__)),
      f"fk counts={len(rs.RunRow.__table__.foreign_keys)},{len(rs.RunEventRow.__table__.foreign_keys)}")

# ---- C4: cross-mode isolation + legacy generate shape
gen_calls = []
async def rec_generate(prompt, provider, model):
    gen_calls.append((prompt, provider, model))
    return ("", json.dumps(CANVAS))
svc = Service(generate=rec_generate, approval_store=approvals, run_store=SqlRunStore())
run_legacy = asyncio.run(svc.intake(IntakeIn(one_liner="legacy tenantless idea"), None))
run_tenant = asyncio.run(svc.intake(IntakeIn(one_liner="tenant scoped idea"), "tenant-x"))
check("C4 tenantless generate keeps legacy (prompt, provider, model) call shape",
      len(gen_calls) >= 1 and all(len(c) == 3 and isinstance(c[0], str) and c[1] == "openai" and c[2] is None for c in gen_calls),
      f"recorded={[(len(c), c[1], c[2]) for c in gen_calls]}")
check("C4 tenantless run stored process-local only", run_legacy.id in svc._runs, run_legacy.id)
r = svc.get(run_legacy.id, None)
check("C4 tenantless get works tenantless", r.id == run_legacy.id, r.id)
try:
    svc.get(run_legacy.id, "tenant-x"); x1 = "ACCESSIBLE (BAD)"
except KeyError:
    x1 = "KeyError (denied)"
check("C4 tenantless run NOT accessible via tenant get", x1.startswith("KeyError"), x1)
r2 = svc.get(run_tenant.id, "tenant-x")
check("C4 tenant run works via tenant get", r2.id == run_tenant.id, r2.id)
try:
    svc.get(run_tenant.id, None); x2 = "ACCESSIBLE (BAD)"
except KeyError:
    x2 = "KeyError (denied)"
check("C4 tenant run NOT accessible tenantless", x2.startswith("KeyError"), x2)
try:
    svc.request_preview(run_legacy.id, PreviewIn(artifacts=["a"], estimated_cost=1), "tenant-x"); x3 = "ACCESSIBLE (BAD)"
except KeyError:
    x3 = "KeyError (denied)"
check("C4 tenantless run NOT previewable via tenant path", x3.startswith("KeyError"), x3)
try:
    svc.request_preview(run_tenant.id, PreviewIn(artifacts=["a"], estimated_cost=1), None); x4 = "ACCESSIBLE (BAD)"
except KeyError:
    x4 = "KeyError (denied)"
check("C4 tenant run NOT previewable tenantless", x4.startswith("KeyError"), x4)
# same run id in both modes: no bleed
svc._runs["shared-id"] = mk_run("shared-id", cap=111.0); svc._owners["shared-id"] = None
svc._store.create("tenant-x", mk_run("shared-id", cap=222.0))
a, b = svc.get("shared-id", None).budget_cap, svc.get("shared-id", "tenant-x").budget_cap
check("C4 same run id in both modes: no bleed", (a, b) == (111.0, 222.0), f"tenantless={a} tenant={b}")
try:
    asyncio.run(svc.intake(IntakeIn(one_liner="keyed but tenantless"), None, idempotency_key="k1")); x5 = "ACCEPTED (BAD)"
except ValueError:
    x5 = "ValueError (refused)"
check("C4 idempotency_key without tenant refused", x5.startswith("ValueError"), x5)

# ---- C5: per-instance isolation of the legacy tenantless dicts (no shared fallback across Service instances)
svcB = Service(generate=rec_generate, approval_store=approvals, run_store=SqlRunStore())
try:
    svcB.get(run_legacy.id, None); xi = "ACCESSIBLE from independent instance (BAD - shared dict mutant)"
except KeyError:
    xi = "KeyError (per-instance)"
check("C5 tenantless run from instance A unreachable on independent instance B", xi.startswith("KeyError"), xi)
try:
    svcB.request_preview(run_legacy.id, PreviewIn(artifacts=["a"], estimated_cost=1), None); xp = "ACCESSIBLE from independent instance (BAD)"
except KeyError:
    xp = "KeyError (per-instance)"
check("C5 tenantless preview from instance A refused on independent instance B", xp.startswith("KeyError"), xp)
check("C5 instance B legacy dicts are empty at construction", svcB._runs == {} and svcB._owners == {},
      f"runs={len(svcB._runs)} owners={len(svcB._owners)}")
check("C5 instance A state intact after B probes", svc.get(run_legacy.id, None).id == run_legacy.id, run_legacy.id)

failed = [n for n, ok in results if not ok]
print(f"TOTAL={len(results)} FAILED={len(failed)}")
sys.exit(1 if failed else 0)
