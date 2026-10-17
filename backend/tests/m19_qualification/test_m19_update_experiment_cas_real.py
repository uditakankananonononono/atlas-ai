"""M19 PATCH update_experiment CAS repair qualification. REAL imports only from the frozen
composition (94fe792d + preview 3ea67c8d + intake v3 61eb6e47 + v4 9cd76657 + txn v2 8e2b874e)
+ descendant CAS repair. Real SQLite + memory + HTTP. No model/network calls.
Select tree with M19_TREE (final = frozen composition = RED, fixed = repaired = GREEN)."""
import os, sys, threading
from datetime import datetime, timezone
tree = os.environ["M19_TREE"]
os.environ["ATLAS_DATABASE_URL"] = "sqlite:////tmp/m19/cas_repair.db"
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
if os.path.exists("/tmp/m19/cas_repair.db"): os.remove("/tmp/m19/cas_repair.db")
sys.path.insert(0, tree)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from app.modules.m19_idea_incubator import routes as m19_routes
from app.modules.m19_idea_incubator.repository import SqlIdeaRepository, MemoryIdeaRepository
from app.modules.m19_idea_incubator.ledger import LedgerService
from app.modules.m19_idea_incubator.schemas import (IdeaCreate, ExperimentCreate, ExperimentUpdate,
    EvidenceCreate, EvidenceKind, EvidencePolarity)

results = []
def check(name, ok, detail=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))

def seed(svc):
    idea = svc.create_idea(IdeaCreate(title="t", problem="p", proposed_solution="s"))
    exp = svc.create_experiment(idea.id, ExperimentCreate(name="e", hypothesis="h", method="m", metric="m", target=100))
    svc.update_experiment(idea.id, exp.id, ExperimentUpdate(status="running"))
    return idea, exp

def ev():
    return EvidenceCreate(kind=EvidenceKind.EXPERIMENT, claim="missed segment", source="src",
                          polarity=EvidencePolarity.CONTRADICTS, strength=.9, confidence=.8,
                          observed_at=datetime.now(timezone.utc), metadata={})

def suite(label, repo_cls):
    svc = LedgerService(repo_cls, "tester")
    idea, exp = seed(svc)  # PATCH happy path planned->running already exercised in seed
    svc.update_experiment(idea.id, exp.id, ExperimentUpdate(status="cancelled"))
    check(f"{label} PATCH happy path running->cancelled preserved",
          svc.repository.list_experiments(idea.id)[0].status.value == "cancelled")
    try:
        svc.update_experiment(idea.id, exp.id, ExperimentUpdate(status="succeeded", observed_value=1))
        replay = "no-error"
    except Exception as e: replay = type(e).__name__
    check(f"{label} PATCH terminal replay refused (ConflictError)", replay == "ConflictError", replay)
    i2, e2 = seed(svc)
    try:
        svc.update_experiment(i2.id, e2.id, ExperimentUpdate(status="running"))
        same = "no-error"
    except Exception as e: same = type(e).__name__
    check(f"{label} same-status update still invalid (ValidationError)", same == "ValidationError", same)
    i3, e3 = seed(svc)
    svc.record_outcome(i3.id, e3.id, ExperimentUpdate(status="failed", observed_value=1), ev())
    check(f"{label} outcome success still atomic", len(svc.repository.list_evidence(i3.id)) == 1)

def race_patch_loses(repo_cls, block_method):
    entered = threading.Event(); release = threading.Event()
    class SlowRepo(repo_cls):
        pass
    repo = SlowRepo("tenant-a") if repo_cls is SqlIdeaRepository else SlowRepo()
    orig = getattr(repo, block_method)
    def wrapped(x, *a, **k):
        if getattr(x, "status", None) and x.status.value == "cancelled":
            entered.set(); release.wait(10)
        return orig(x, *a, **k)
    setattr(repo, block_method, wrapped)
    svc = LedgerService(repo, "tester")
    idea, exp = seed(svc)
    err = [None]
    def patch_cancel():
        try: svc.update_experiment(idea.id, exp.id, ExperimentUpdate(status="cancelled"))
        except Exception as e: err[0] = type(e).__name__
    t = threading.Thread(target=patch_cancel); t.start()
    assert entered.wait(10), "PATCH write never entered"
    svc.record_outcome(idea.id, exp.id, ExperimentUpdate(status="failed", observed_value=1), ev())
    release.set(); t.join(10)
    final = svc.repository.list_experiments(idea.id)[0]
    evs = svc.repository.list_evidence(idea.id)
    return err[0], final, evs

# race: PATCH pre-reads RUNNING, outcome commits first -> PATCH must LOSE, no clobber
for label, cls, method in (("sql", SqlIdeaRepository, "save_experiment_cas"), ("memory", MemoryIdeaRepository, "save_experiment_cas")):
    if cls is MemoryIdeaRepository and not hasattr(cls, "save_experiment_cas"): method = "save_experiment"
    if cls is SqlIdeaRepository and not hasattr(cls, "save_experiment_cas"): method = "save_experiment"
    err, final, evs = race_patch_loses(cls, method)
    repaired = hasattr(cls, "save_experiment_cas")
    if repaired:
        check(f"{label} race: PATCH loses with ConflictError after outcome commits", err == "ConflictError", err)
        check(f"{label} race: terminal outcome NOT clobbered (failed + 1 evidence)",
              final.status.value == "failed" and final.observed_value == 1 and len(evs) == 1,
              f"status={final.status.value} ev={len(evs)}")
    else:
        clobbered = final.status.value == "cancelled" and len(evs) == 1
        check(f"{label} race: RED - PATCH clobbers committed outcome (pre-repair defect)", clobbered,
              f"status={final.status.value} ev={len(evs)}")

def race_outcome_loses(repo_cls):
    entered = threading.Event(); release = threading.Event()
    repo = repo_cls("tenant-a") if repo_cls is SqlIdeaRepository else repo_cls()
    orig = repo.save_experiment_with_evidence
    def wrapped(x, *a, **k):
        entered.set(); release.wait(10)
        return orig(x, *a, **k)
    repo.save_experiment_with_evidence = wrapped
    svc = LedgerService(repo, "tester")
    idea, exp = seed(svc)
    err = [None]
    def outcome():
        try: svc.record_outcome(idea.id, exp.id, ExperimentUpdate(status="failed", observed_value=1), ev())
        except Exception as e: err[0] = type(e).__name__
    t = threading.Thread(target=outcome); t.start()
    assert entered.wait(10), "outcome write never entered"
    svc.update_experiment(idea.id, exp.id, ExperimentUpdate(status="cancelled"))  # cancel WINS
    release.set(); t.join(10)
    final = svc.repository.list_experiments(idea.id)[0]
    return err[0], final, svc.repository.list_evidence(idea.id)

for label, cls in (("sql", SqlIdeaRepository), ("memory", MemoryIdeaRepository)):
    err, final, evs = race_outcome_loses(cls)
    check(f"{label} winning cancel: outcome loses (ConflictError), no orphaned evidence",
          err == "ConflictError" and final.status.value == "cancelled" and len(evs) == 0,
          f"err={err} status={final.status.value} ev={len(evs)}")

# HTTP level: PATCH success, terminal replay 409, race over HTTP one-winner
app = FastAPI(); app.include_router(m19_routes.router)
app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="tenant-a", actor_id="tester")
c = TestClient(app)
idea = c.post("/idea-incubator/portfolio/ideas", json={"title": "I", "problem": "p", "proposed_solution": "s"}).json()
exp = c.post(f"/idea-incubator/portfolio/ideas/{idea['id']}/experiments",
             json={"name": "e", "hypothesis": "h", "method": "m", "metric": "m", "target": 100}).json()
r = c.patch(f"/idea-incubator/portfolio/ideas/{idea['id']}/experiments/{exp['id']}", json={"status": "running"})
check("http PATCH running 200", r.status_code == 200, f"{r.status_code}")
body = {"outcome": {"status": "failed", "observed_value": 1, "target": 100, "learnings": "missed the target segment", "source_refs": ["s"]},
        "evidence_kind": "experiment"}
codes, resps = [], []
def http_outcome(): resps.append(c.post(f"/idea-incubator/luxury-venture-studio/portfolio/{idea['id']}/experiments/{exp['id']}/outcome", json=body).status_code)
def http_patch(): codes.append(c.patch(f"/idea-incubator/portfolio/ideas/{idea['id']}/experiments/{exp['id']}", json={"status": "cancelled"}).status_code)
import random
ts = [threading.Thread(target=http_outcome), threading.Thread(target=http_patch)]
[t.start() for t in ts]; [t.join() for t in ts]
d = c.get(f"/idea-incubator/portfolio/ideas/{idea['id']}").json()
x = d["experiments"][0]
check("http race: exactly one winner", sorted(codes + resps) == [200, 409], f"patch={codes} outcome={resps}")
check("http race: state consistent with the winner, no orphan evidence",
      (x["status"] == "failed" and len(d["evidence"]) == 1) or (x["status"] == "cancelled" and len(d["evidence"]) == 0),
      f"status={x['status']} ev={len(d['evidence'])}")

failed = [n for n, ok in results if not ok]
print(f"TREE={tree} TOTAL={len(results)} FAILED={len(failed)}")
sys.exit(1 if failed else 0)
