"""M19 luxury_venture_outcome atomicity regression. REAL imports only: routes.py, schemas,
ledger, luxury_venture, repository (MemoryIdeaRepository), app.auth.context, app.core.*
from atlas-ai @ 94fe792d7eed01c37091bb87a18989d1c0f2d61a, fetched live 2026-10-17.
Select tree with M19_TREE env (original vs patched). Builder self-report."""
import os, sys
sys.path.insert(0, os.environ["M19_TREE"])
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from app.modules.m19_idea_incubator import routes as m19_routes
from app.modules.m19_idea_incubator.ledger import LedgerService
from app.modules.m19_idea_incubator.repository import MemoryIdeaRepository

def make_client():
    repo = MemoryIdeaRepository()
    app = FastAPI()
    app.include_router(m19_routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="tenant-a", actor_id="tester")
    app.dependency_overrides[m19_routes.get_ledger] = lambda: LedgerService(repo, "tester")
    return TestClient(app)

def seed_running_experiment(c):
    idea = c.post("/idea-incubator/portfolio/ideas", json={"title": "Idea", "problem": "p", "proposed_solution": "s"})
    assert idea.status_code == 201, idea.text
    idea_id = idea.json()["id"]
    exp = c.post(f"/idea-incubator/portfolio/ideas/{idea_id}/experiments",
                 json={"name": "e", "hypothesis": "h", "method": "m", "metric": "m", "target": 100})
    assert exp.status_code == 201, exp.text
    exp_id = exp.json()["id"]
    r = c.patch(f"/idea-incubator/portfolio/ideas/{idea_id}/experiments/{exp_id}", json={"status": "running"})
    assert r.status_code == 200, r.text
    return idea_id, exp_id

def outcome_payload(ref_len):
    return {"outcome": {"status": "failed", "observed_value": 1, "target": 100,
                        "learnings": "distribution missed the target segment",
                        "source_refs": ["https://example.com/" + "x" * ref_len]},
            "evidence_kind": "experiment"}

def outcome_url(idea_id, exp_id):
    return f"/idea-incubator/luxury-venture-studio/portfolio/{idea_id}/experiments/{exp_id}/outcome"

def state(c, idea_id, exp_id):
    d = c.get(f"/idea-incubator/portfolio/ideas/{idea_id}").json()
    return next(x["status"] for x in d["experiments"] if x["id"] == exp_id), len(d["evidence"])

def test_valid_outcome_control():
    c = make_client()
    idea_id, exp_id = seed_running_experiment(c)
    r = c.post(outcome_url(idea_id, exp_id), json=outcome_payload(10))
    assert r.status_code == 200, r.text
    status, ev_count = state(c, idea_id, exp_id)
    assert status == "failed" and ev_count == 1, (status, ev_count)
    assert r.json()["evidence"]["polarity"] == "contradicts"

def test_oversized_source_refs_must_not_strand_terminal_experiment():
    """joined source_refs of 2103 chars passes VentureOutcome (refs uncapped, max 50 items)
    but violates EvidenceCreate.source max_length=2000. The evidence write must fail BEFORE
    the experiment update commits, leaving the experiment mutable and retryable."""
    c = make_client()
    idea_id, exp_id = seed_running_experiment(c)
    r = c.post(outcome_url(idea_id, exp_id), json=outcome_payload(2100))
    assert r.status_code == 422, (r.status_code, r.text)
    status, ev_count = state(c, idea_id, exp_id)
    assert status == "running", f"partial write: experiment stranded at {status!r} with no evidence"
    assert ev_count == 0, f"unexpected evidence rows: {ev_count}"
    retry = c.post(outcome_url(idea_id, exp_id), json=outcome_payload(10))
    assert retry.status_code == 200, f"retry blocked: {retry.status_code} {retry.text}"
    status, ev_count = state(c, idea_id, exp_id)
    assert status == "failed" and ev_count == 1, (status, ev_count)

if __name__ == "__main__":
    tree = os.environ["M19_TREE"]
    test_valid_outcome_control()
    print(f"[{tree}] control valid-outcome PASS")
    test_oversized_source_refs_must_not_strand_terminal_experiment()
    print(f"[{tree}] atomicity regression PASS")
