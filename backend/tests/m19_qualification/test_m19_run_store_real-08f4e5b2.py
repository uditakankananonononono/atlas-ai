"""M19 durable run-store regression. REAL imports from the COMPOSED tree: 94fe792d + txn v2 +
preview tenant + idempotency v3+v4 + this unit (run_store.py, service.py wiring, migration).
Real SQLite; real HTTP router. Seams: require_tenant override + generate constructor arg (no LLM).
Covers: durable intake/GET, restart survival (fresh Service + same DB), cross-tenant 404, budget
CAS under a concurrent race (exactly one reserve when only one fits), cap refusal, append-only
events with monotonic versions, idempotent replay valid after restart (durable run), migration
upgrade/downgrade on a scratch sqlite via Alembic ops, explicit in-memory injection only.
Builder self-report."""
import os, json, sys, asyncio, threading, importlib.util
tree = os.environ["M19_TREE"]
os.environ["ATLAS_DATABASE_URL"] = os.environ.get("M19_DB", "sqlite:////tmp/m19/runstore_test.db")
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
for f in ("/tmp/m19/runstore_test.db", "/tmp/m19/migration_scratch.db"):
    if os.path.exists(f):
        os.remove(f)
sys.path.insert(0, tree)
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from app.modules.m19_idea_incubator import routes as m19_routes
from app.modules.m19_idea_incubator.service import Service
from app.modules.m19_idea_incubator.run_store import SqlRunStore, InMemoryRunStore
from app.core.approvals import approvals

CANVAS = {"problem": ["p"], "customer_segments": ["c"], "unique_value_proposition": "u",
          "solution": ["s"], "channels": ["ch"], "revenue_streams": ["r"], "cost_structure": ["c"],
          "key_metrics": ["k"], "unfair_advantage": None, "riskiest_assumptions": ["a"]}
PACKAGE = {"executive_summary": "sum", "recommendation": "go", "recommendation_confidence": 0.8,
           "market_claims": [{"claim": "c"}], "technical_feasibility": ["t"], "prototype_artifacts": ["a"],
           "prototype_preview": None, "unresolved_risks": ["r"], "next_experiments": ["e"]}
async def fake_generate(prompt, provider, model):
    return ("", json.dumps(PACKAGE if "viability package" in prompt else CANVAS))
async def header_tenant(x_tenant: str = Header(default="tenant-a")):
    return TenantContext(tenant_id=x_tenant, actor_id=x_tenant)

results = []
def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))

from app.modules.m19_idea_incubator.idempotency import IntakeIdempotencyStore
svc = Service(generate=fake_generate, approval_store=approvals, idempotency_store=IntakeIdempotencyStore())
check("production default store is SqlRunStore", isinstance(svc._store, SqlRunStore), type(svc._store).__name__)
app = FastAPI(); app.include_router(m19_routes.router)
app.dependency_overrides[require_tenant] = header_tenant
app.dependency_overrides[m19_routes.get_service] = lambda: svc
c = TestClient(app)
A, B = {"x-tenant": "tenant-a"}, {"x-tenant": "tenant-b"}

r = c.post("/idea-incubator/ideas", json={"one_liner": "durable idea", "budget_cap": 25, "idempotency_key": "rs-1"}, headers=A)
check("intake 201", r.status_code == 201, r.text[:120])
run_id = r.json()["id"]
check("get 200 owning tenant", c.get(f"/idea-incubator/ideas/{run_id}", headers=A).status_code == 200)
check("get 404 foreign tenant", c.get(f"/idea-incubator/ideas/{run_id}", headers=B).status_code == 404)

# restart survival: brand-new Service over the same DB, empty process state
svc2 = Service(generate=fake_generate, approval_store=approvals, idempotency_store=IntakeIdempotencyStore())
app2 = FastAPI(); app2.include_router(m19_routes.router)
app2.dependency_overrides[require_tenant] = header_tenant
app2.dependency_overrides[m19_routes.get_service] = lambda: svc2
c2 = TestClient(app2)
check("after restart: GET still 200 (durable run)", c2.get(f"/idea-incubator/ideas/{run_id}", headers=A).status_code == 200)
r = c2.post("/idea-incubator/ideas", json={"one_liner": "durable idea", "budget_cap": 25, "idempotency_key": "rs-1"}, headers=A)
check("after restart: idempotent replay returns SAME run id (run is durable, no 410)",
      r.status_code == 201 and r.json()["id"] == run_id, f"{r.status_code} {r.json().get('id','?')[:8]} vs {run_id[:8]}")

# budget CAS race at service level: cap 10, two previews of 6 -> exactly one reserves
from app.modules.m19_idea_incubator.schemas import IntakeIn, PreviewIn, Stage
idea = asyncio.run(svc.intake(IntakeIn(one_liner="race idea", budget_cap=10), "tenant-a"))
outs, errs = [], []
def preview():
    try: outs.append(svc.request_preview(idea.id, PreviewIn(artifacts=["a"], estimated_cost=6), "tenant-a"))
    except Exception as e: errs.append(type(e).__name__)
ts = [threading.Thread(target=preview) for _ in range(2)]
[t.start() for t in ts]; [t.join() for t in ts]
final = svc.get(idea.id, "tenant-a")
check("budget CAS race: exactly one preview reserves", len(outs) == 1 and errs == ["ValueError"], f"outs={len(outs)} errs={errs}")
check("budget CAS race: reserved never exceeds cap", final.reserved == 6 and final.spent == 0, f"reserved={final.reserved}")
r = c.post(f"/idea-incubator/ideas/{run_id}/preview", json={"artifacts": ["x"], "estimated_cost": 100}, headers=A)
check("over-cap preview refused 409", r.status_code == 409, f"got {r.status_code}")

# append-only events with monotonic versions
evs = svc._store.list_events("tenant-a", idea.id)
check("append-only events: created then budget_reserved, versions 1,2",
      [e.kind for e in evs] == ["created", "budget_reserved"] and [e.version for e in evs] == [1, 2],
      str([(e.kind, e.version) for e in evs]))

# explicit in-memory injection works and is not the default
mem = Service(generate=fake_generate, approval_store=approvals, run_store=InMemoryRunStore())
m = asyncio.run(mem.intake(IntakeIn(one_liner="mem", budget_cap=5), "tenant-a"))
check("explicit InMemoryRunStore injection works", mem.get(m.id, "tenant-a").id == m.id)

# migration through the REAL Alembic config: actual alembic.ini script_location (toplevel
# migrations/), discovery of the delivered revision, linear-head chain, and a real
# stamp -> upgrade -> downgrade -> (PG: restore upgrade) via alembic.command on a scratch DB.
import alembic.config, alembic.command, alembic.script
_reporoot = os.path.dirname(tree) if os.path.basename(tree) == "backend" else tree
_ini = os.path.join(_reporoot, "alembic.ini")
_mig_path = os.path.join(_reporoot, "migrations", "versions", "20261017_m19_runs.py")
assert os.path.isfile(_ini) and os.path.isfile(_mig_path), (
    f"alembic.ini/migration not found under repo root {_reporoot} - M19_TREE must point at the "
    "composed backend dir (or repo root) delivered by the canonical patch")
_db_url = os.environ["ATLAS_DATABASE_URL"]
if _reporoot not in sys.path:
    sys.path.insert(0, _reporoot)  # revision modules import migrations.*, as when alembic runs from repo root
def _cfg(url):
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = alembic.config.Config(_ini)
    cfg.set_main_option("script_location", os.path.join(_reporoot, "migrations"))
    return cfg
sd = alembic.script.ScriptDirectory.from_config(_cfg(_db_url))
_revs = {r.revision for r in sd.walk_revisions()}
check("migration discovered by REAL alembic script_location (toplevel migrations/)",
      "20261017_m19_runs" in _revs, f"{len(_revs)} revisions visible")
_rev = sd.get_revision("20261017_m19_runs")
check("migration down_revision chains on actual linear head 20261011_m20_meta_state",
      _rev.down_revision == "20261011_m20_meta_state" and "20261011_m20_meta_state" in _revs,
      str(_rev.down_revision))
from sqlalchemy import create_engine, inspect, text
_is_sqlite = "sqlite" in _db_url
_scratch_db = "m19_migration_scratch"
if _is_sqlite:
    _mig_url = "sqlite:////tmp/m19/migration_scratch.db"
    if os.path.exists("/tmp/m19/migration_scratch.db"):
        os.remove("/tmp/m19/migration_scratch.db")
else:
    # isolated scratch DATABASE on the same server: never drop/wipe the shared suite DB
    import psycopg
    _base_q, _qsep, _query = _db_url.partition("?")
    _base, _sep, _dbname = _base_q.rpartition("/")
    assert _sep and _dbname, f"cannot derive scratch database from {_db_url!r}"
    _mig_url = _base + "/" + _scratch_db + (_qsep + _query if _qsep else "")
    with psycopg.connect(_db_url, autocommit=True) as _adm:
        _adm.execute(f'DROP DATABASE IF EXISTS {_scratch_db} WITH (FORCE)')
        _adm.execute(f'CREATE DATABASE {_scratch_db}')
_eng = create_engine(_mig_url)
cfg = _cfg(_mig_url)
alembic.command.stamp(cfg, "20261011_m20_meta_state")
alembic.command.upgrade(cfg, "20261017_m19_runs")
with _eng.connect() as conn:
    names = set(inspect(conn).get_table_names())
check("real alembic upgrade creates m19_runs + m19_run_events",
      {"m19_runs", "m19_run_events"} <= names, str(sorted(names)))
alembic.command.downgrade(cfg, "20261011_m20_meta_state")
with _eng.connect() as conn:
    names_after = set(inspect(conn).get_table_names())
check("real alembic downgrade drops them",
      not ({"m19_runs", "m19_run_events"} & names_after), str(sorted(names_after)))
_eng.dispose()
os.environ["ATLAS_DATABASE_URL"] = _db_url
if not _is_sqlite:
    import psycopg
    with psycopg.connect(_db_url, autocommit=True) as _adm:
        _adm.execute(f'DROP DATABASE IF EXISTS {_scratch_db} WITH (FORCE)')

# package body over HTTP with the store-backed read path
r = c.post("/idea-incubator/packages", json={"run_id": run_id, "evidence": [{"kind": "interview"}], "artifacts": ["a"]}, headers=A)
check("package 200 over HTTP (store-backed read)", r.status_code == 200 and r.json()["recommendation"] == "go", f"got {r.status_code} {r.text[:80]}")
r = c.post("/idea-incubator/packages", json={"run_id": run_id, "evidence": [], "artifacts": ["a"]}, headers=B)
check("package 404 foreign tenant", r.status_code == 404, f"got {r.status_code}")

# approval put with after-effect then timeout: reservation must NOT be auto-released (unknown outcome)
class FlakyApprovals:
    def __init__(self): self.stored = []
    def put(self, item): self.stored.append(item); raise TimeoutError("put timed out after effect")
flaky = FlakyApprovals()
svc3 = Service(generate=fake_generate, approval_store=flaky, run_store=SqlRunStore())
idea3 = asyncio.run(svc3.intake(IntakeIn(one_liner="unknown outcome", budget_cap=10), "tenant-a"))
try: svc3.request_preview(idea3.id, PreviewIn(artifacts=["a"], estimated_cost=6), "tenant-a"); after = "no-raise"
except TimeoutError: after = "timeout"
run3 = svc3.get(idea3.id, "tenant-a")
ev3 = [e.kind for e in svc3._store.list_events("tenant-a", idea3.id)]
check("after-effect put + timeout: exception propagates, approval WAS stored", after == "timeout" and len(flaky.stored) == 1, after)
check("unknown outcome: reservation NOT auto-released, no budget_released event",
      run3.reserved == 6 and "budget_released" not in ev3, f"reserved={run3.reserved} events={ev3}")
rel = svc3._store.release_budget("tenant-a", idea3.id, 6, expected_version=svc3.get(idea3.id, "tenant-a") and 2, new_state="queued", new_stage=Stage.LANDSCAPE)
ev3b = [(e.kind, e.version) for e in svc3._store.list_events("tenant-a", idea3.id)]
check("explicit grounded release: atomic version bump + budget_released event",
      rel.reserved == 0 and ev3b == [("created", 1), ("budget_reserved", 2), ("budget_released", 3)], f"{ev3b}")
try:
    svc3._store.release_budget("tenant-a", idea3.id, 6, expected_version=2, new_state="queued", new_stage=Stage.LANDSCAPE); stale = "no-raise"
except RuntimeError: stale = "stale-rejected"
check("stale expected_version release rejected", stale == "stale-rejected", stale)

# concurrent multi-Service race over the SAME database
sA, sB = Service(generate=fake_generate, approval_store=approvals), Service(generate=fake_generate, approval_store=approvals)
ideaM = asyncio.run(sA.intake(IntakeIn(one_liner="multi-svc race", budget_cap=10), "tenant-a"))
outsM, errsM = [], []
def pv(svc):
    try: outsM.append(svc.request_preview(ideaM.id, PreviewIn(artifacts=["a"], estimated_cost=6), "tenant-a"))
    except Exception as e: errsM.append(type(e).__name__)
ts = [threading.Thread(target=pv, args=(sA,)), threading.Thread(target=pv, args=(sB,))]
[t.start() for t in ts]; [t.join() for t in ts]
check("multi-Service concurrent race: exactly one reserves across instances",
      len(outsM) == 1 and errsM == ["ValueError"], f"outs={len(outsM)} errs={errsM}")

failed = [n for n, ok in results if not ok]
print(f"TREE={tree} TOTAL={len(results)} FAILED={len(failed)}")
sys.exit(1 if failed else 0)
