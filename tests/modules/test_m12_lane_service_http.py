"""Tests for the service facade and the FastAPI router (via TestClient)."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger
from app.modules.m12_ai_research_lab.lane_http import build_router
from app.modules.m12_ai_research_lab.lane_models import (
    BudgetPolicy, CAP_CHAT, ModelProfile, usd_to_micro,
)
from app.modules.m12_ai_research_lab.lane_routing import ModelRouter
from app.modules.m12_ai_research_lab.lane_service import AIResearchLabService
from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore
from app.modules.m12_ai_research_lab.lane_workflows import WorkflowEngine


def make_service(tmp_path):
    store = SQLiteLabStore(str(tmp_path / "lab.db"))
    router = ModelRouter()
    ledger = BudgetLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(5)), store=store)

    def echo(params, ctx):
        return params

    def llm(params, ctx):
        ctx.record_usage(10, 5)
        return {"text": "hello " + params.get("prompt", "")}

    engine = WorkflowEngine({"echo": echo, "llm": llm}, router=router,
                            ledger=ledger, state_store=store)
    return AIResearchLabService(router=router, ledger=ledger, engine=engine, store=store)


def make_client(service):
    app = FastAPI()
    app.include_router(build_router(service), prefix="/lab")
    return TestClient(app)


MODEL_BODY = {
    "model_id": "m1", "provider": "test", "display_name": "M1",
    "cost_per_1k_input_micro": 1_000_000, "cost_per_1k_output_micro": 2_000_000,
    "capabilities": ["chat"], "quality_tier": 3,
}


def test_model_register_list_and_route(tmp_path):
    c = make_client(make_service(tmp_path))
    assert c.get("/lab/models").json() == {"models": []}
    r = c.post("/lab/models", json=MODEL_BODY)
    assert r.status_code == 201, r.text
    assert c.get("/lab/models").json()["models"][0]["model_id"] == "m1"

    r = c.post("/lab/route", json={"required_capabilities": ["chat"]})
    assert r.status_code == 200
    body = r.json()
    assert body["chosen"]["model_id"] == "m1"
    assert body["reasons"]

    r = c.post("/lab/route", json={"required_capabilities": ["vision"]})
    assert r.status_code == 422
    assert r.json()["detail"]["verdicts"][0]["reasons"]


def test_duplicate_model_registration_is_422(tmp_path):
    c = make_client(make_service(tmp_path))
    c.post("/lab/models", json=MODEL_BODY)
    assert c.post("/lab/models", json=MODEL_BODY).status_code == 422


def test_workflow_run_persists_manifest_and_budget(tmp_path):
    service = make_service(tmp_path)
    c = make_client(service)
    c.post("/lab/models", json=MODEL_BODY)
    r = c.post("/lab/workflows/run", json={
        "name": "demo",
        "run_id": "run-http-1",
        "steps": [
            {"step_id": "prep", "kind": "echo", "params": {"x": 1}},
            {"step_id": "gen", "kind": "llm", "params": {"prompt": "world"},
             "depends_on": ["prep"],
             "route_requirements": {"required_capabilities": ["chat"]}},
        ],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["run_id"] == "run-http-1"
    assert body["total_cost_micro"] == 20_000  # 10*1000 + 5*2000
    assert len(body["manifest_digest"]) == 64

    r = c.get("/lab/runs/run-http-1")
    assert r.status_code == 200
    payload = r.json()
    assert payload["digest"] == body["manifest_digest"]
    assert payload["manifest"]["total_cost_micro"] == 20_000
    assert "run-http-1" in c.get("/lab/runs").json()["run_ids"]

    budget = c.get("/lab/budget").json()
    assert budget["spent_today_micro"] == 20_000
    assert budget["reserved_micro"] == 0


def test_invalid_workflow_is_422(tmp_path):
    c = make_client(make_service(tmp_path))
    r = c.post("/lab/workflows/run", json={
        "name": "bad",
        "steps": [{"step_id": "a", "kind": "echo", "depends_on": ["a"]}],
    })
    assert r.status_code == 422


def test_unknown_run_is_404(tmp_path):
    c = make_client(make_service(tmp_path))
    assert c.get("/lab/runs/ghost").status_code == 404


def test_eval_run_and_fetch(tmp_path):
    c = make_client(make_service(tmp_path))
    r = c.post("/lab/evals/run", json={
        "eval_id": "eval-1",
        "runner_kind": "echo",
        "cases": [
            {"case_id": "a", "input": {"v": 1},
             "checks": [{"type": "json_equals", "value": {"v": 1}}]},
            {"case_id": "b", "input": {"v": 2},
             "checks": [{"type": "json_equals", "value": {"v": 3}}]},
        ],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2 and body["passed"] == 1 and body["failed"] == 1

    r = c.get("/lab/evals/eval-1")
    assert r.status_code == 200
    assert r.json()["eval_id"] == "eval-1"
    assert c.get("/lab/evals/ghost").status_code == 404


def test_eval_unknown_runner_kind_is_422(tmp_path):
    c = make_client(make_service(tmp_path))
    r = c.post("/lab/evals/run", json={
        "runner_kind": "ghost",
        "cases": [{"case_id": "a", "input": {}, "checks": [{"type": "exact", "value": 1}]}],
    })
    assert r.status_code == 422


def test_run_diff_endpoint(tmp_path):
    c = make_client(make_service(tmp_path))
    c.post("/lab/models", json=MODEL_BODY)
    for run_id, prompt in (("ra", "one"), ("rb", "two")):
        r = c.post("/lab/workflows/run", json={
            "name": "demo", "run_id": run_id,
            "steps": [{"step_id": "gen", "kind": "llm", "params": {"prompt": prompt},
                       "route_requirements": {"required_capabilities": ["chat"]}}],
        })
        assert r.status_code == 200, r.text
    r = c.get("/lab/runs/ra/diff/rb")
    assert r.status_code == 200
    body = r.json()
    assert body["config_changed"] is True  # different params
    assert body["cost_delta_micro"] == 0
    assert body["step_diffs"][0]["change"] == "changed"
    assert "output_hash" in body["step_diffs"][0]["changed_fields"]
    assert c.get("/lab/runs/ra/diff/ghost").status_code == 404
