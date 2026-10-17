"""M19 decide/outcome transactional repair v2 (CAS guards inside the transaction, route wired).
REAL imports only from atlas-ai @ 94fe792d..., fetched live 2026-10-17. Real SQLite + memory repo.
Covers: success paths, concurrent finalization races (SQL + memory), rollback under injected
mid-transaction write failure, route-level composition with prevalidation. Builder self-report."""
import os, sys, threading
tree = os.environ["M19_TREE"]
os.environ["ATLAS_DATABASE_URL"] = "sqlite:////tmp/m19/txn2_test.db"
os.environ["ATLAS_AUTO_CREATE_SCHEMA"] = "1"
if os.path.exists("/tmp/m19/txn2_test.db"):
    os.remove("/tmp/m19/txn2_test.db")
sys.path.insert(0, tree)
from sqlalchemy.orm import Session, sessionmaker
from app.core.database import engine
from app.modules.m19_idea_incubator.repository import SqlIdeaRepository, MemoryIdeaRepository, DecisionRow, EvidenceRow
from app.modules.m19_idea_incubator.ledger import LedgerService, ConflictError
from app.modules.m19_idea_incubator.schemas import (IdeaCreate, DecisionCreate, IdeaStage,
    ExperimentCreate, ExperimentUpdate, EvidenceCreate, EvidenceKind, EvidencePolarity)

results = []
def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))

def seed(svc):
    idea = svc.create_idea(IdeaCreate(title="t", problem="p", proposed_solution="s"))
    exp = svc.create_experiment(idea.id, ExperimentCreate(name="e", hypothesis="h", method="m", metric="m", target=100))
    svc.update_experiment(idea.id, exp.id, ExperimentUpdate(status="running"))
    return idea, exp

def ev(claim="learned something real"):
    from datetime import datetime, timezone
    return EvidenceCreate(kind=EvidenceKind.EXPERIMENT, claim=claim, source="src",
                          polarity=EvidencePolarity.CONTRADICTS, strength=0.9, confidence=0.8,
                          observed_at=datetime.now(timezone.utc), metadata={})

def race(fn, n=2):
    outs, errs = [], []
    def w():
        try: outs.append(fn())
        except Exception as e: errs.append(type(e).__name__)
    ts = [threading.Thread(target=w) for _ in range(n)]
    [t.start() for t in ts]; [t.join() for t in ts]
    return outs, errs

def suite(label, make_svc):
    svc = make_svc()
    idea, exp = seed(svc)
    d = svc.decide(idea.id, DecisionCreate(to_stage=IdeaStage.PARKED, rationale="r"))
    check(f"{label} decide success", svc._idea(idea.id).stage == IdeaStage.PARKED and len(svc.repository.list_decisions(idea.id)) == 1)
    i2, e2 = seed(svc)
    svc.record_outcome(i2.id, e2.id, ExperimentUpdate(status="failed", observed_value=1), ev())
    check(f"{label} record_outcome success",
          svc.repository.list_experiments(i2.id)[0].status.value == "failed" and len(svc.repository.list_evidence(i2.id)) == 1)
    # race: two concurrent finalizations of one running experiment
    i3, e3 = seed(svc)
    outs, errs = race(lambda: svc.record_outcome(i3.id, e3.id, ExperimentUpdate(status="failed", observed_value=1), ev()))
    check(f"{label} outcome race: exactly one commits", len(outs) == 1 and errs == ["ConflictError"], f"outs={len(outs)} errs={errs}")
    check(f"{label} outcome race: final state terminal with exactly 1 evidence",
          svc.repository.list_experiments(i3.id)[0].status.value == "failed" and len(svc.repository.list_evidence(i3.id)) == 1)
    # race: two concurrent decides on one idea
    i4, _ = seed(svc)
    outs, errs = race(lambda: svc.decide(i4.id, DecisionCreate(to_stage=IdeaStage.PARKED, rationale="r")))
    # loser refuses either by CAS version conflict (read before winner committed) or by
    # invalid-transition validation (read after); both are correct refusals of the second write.
    check(f"{label} decide race: exactly one commits", len(outs) == 1 and len(errs) == 1 and errs[0] in ("ConflictError", "ValidationError"), f"outs={len(outs)} errs={errs}")
    check(f"{label} decide race: version bumped once, exactly 1 decision",
          svc._idea(i4.id).version == 2 and len(svc.repository.list_decisions(i4.id)) == 1)
    # replay after terminal -> 409-class conflict from validation
    try:
        svc.record_outcome(i3.id, e3.id, ExperimentUpdate(status="succeeded", observed_value=200), ev())
        replay = "no-error"
    except Exception as e:
        replay = type(e).__name__
    check(f"{label} terminal replay refused (ConflictError)", replay == "ConflictError", replay)

suite("sql", lambda: LedgerService(SqlIdeaRepository("tenant-a"), "tester"))
suite("memory", lambda: LedgerService(MemoryIdeaRepository(), "tester"))

# rollback under injected mid-transaction write failure (SQL)
FAIL = {"on": True}
class FailOnRow(Session):
    def add(self, instance, _warn=True):
        if FAIL["on"] and isinstance(instance, (DecisionRow, EvidenceRow)):
            raise RuntimeError("injected write failure")
        return super().add(instance, _warn=_warn)
svc_fail = LedgerService(SqlIdeaRepository("tenant-a", session_factory=sessionmaker(class_=FailOnRow, bind=engine)), "tester")
fi, fe = seed(svc_fail)
v0 = svc_fail._idea(fi.id).version
try: svc_fail.decide(fi.id, DecisionCreate(to_stage=IdeaStage.PARKED, rationale="r"))
except Exception: pass
a = svc_fail._idea(fi.id)
check("sql decide fault: full rollback", a.stage == IdeaStage.CAPTURED and a.version == v0 and len(svc_fail.repository.list_decisions(fi.id)) == 0,
      f"stage={a.stage} v{a.version}")
fi2, fe2 = seed(svc_fail)
try: svc_fail.record_outcome(fi2.id, fe2.id, ExperimentUpdate(status="failed", observed_value=1), ev())
except Exception: pass
e_after = svc_fail.repository.list_experiments(fi2.id)[0]
check("sql outcome fault: full rollback", e_after.status.value == "running" and len(svc_fail.repository.list_evidence(fi2.id)) == 0)

# route-level composition: real router, real SQL, header tenant
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from app.modules.m19_idea_incubator import routes as m19_routes
async def header_tenant(x_tenant: str = Header(default="tenant-a")):
    return TenantContext(tenant_id=x_tenant, actor_id=x_tenant)
app = FastAPI(); app.include_router(m19_routes.router)
app.dependency_overrides[require_tenant] = header_tenant
c = TestClient(app)
A = {"x-tenant": "tenant-a"}
r = c.post("/idea-incubator/portfolio/ideas", json={"title": "Idea", "problem": "p", "proposed_solution": "s"}, headers=A)
idea_id = r.json()["id"]
r = c.post(f"/idea-incubator/portfolio/ideas/{idea_id}/experiments", json={"name": "e", "hypothesis": "h", "method": "m", "metric": "m", "target": 100}, headers=A)
exp_id = r.json()["id"]
c.patch(f"/idea-incubator/portfolio/ideas/{idea_id}/experiments/{exp_id}", json={"status": "running"}, headers=A)
url = f"/idea-incubator/luxury-venture-studio/portfolio/{idea_id}/experiments/{exp_id}/outcome"
def outcome_payload(ref_len):
    return {"outcome": {"status": "failed", "observed_value": 1, "target": 100,
                        "learnings": "distribution missed the target segment",
                        "source_refs": ["https://example.com/" + "x" * ref_len]}, "evidence_kind": "experiment"}
r = c.post(url, json=outcome_payload(10), headers=A)
check("http valid outcome 200 via atomic record_outcome", r.status_code == 200 and r.json()["experiment"]["status"] == "failed", f"{r.status_code} {r.text[:100]}")
r = c.post(url, json=outcome_payload(10), headers=A)
check("http terminal replay 409", r.status_code == 409, f"got {r.status_code}")
r2 = c.post("/idea-incubator/portfolio/ideas", json={"title": "Idea2", "problem": "p", "proposed_solution": "s"}, headers=A)
i2 = r2.json()["id"]
r2 = c.post(f"/idea-incubator/portfolio/ideas/{i2}/experiments", json={"name": "e", "hypothesis": "h", "method": "m", "metric": "m", "target": 100}, headers=A)
e2 = r2.json()["id"]
c.patch(f"/idea-incubator/portfolio/ideas/{i2}/experiments/{e2}", json={"status": "running"}, headers=A)
r = c.post(f"/idea-incubator/luxury-venture-studio/portfolio/{i2}/experiments/{e2}/outcome", json=outcome_payload(2100), headers=A)
d = c.get(f"/idea-incubator/portfolio/ideas/{i2}", headers=A).json()
st = next(x["status"] for x in d["experiments"] if x["id"] == e2)
check("http oversized refs: 422 AND experiment still running (prevalidation composed)",
      r.status_code == 422 and st == "running", f"{r.status_code} status={st}")

failed = [n for n, ok in results if not ok]
print(f"TREE={tree} TOTAL={len(results)} FAILED={len(failed)}")
sys.exit(1 if failed else 0)
