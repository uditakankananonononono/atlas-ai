# Corrected fixture (TenantContext(tenant_id, actor) per peer 701 evidence). Still UNRUN by me: needs fastapi + real app.auth.
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.providers import ProviderOutcomeUnknown
from app.modules.m12_ai_research_lab import routes
from app.modules.m12_ai_research_lab.workflow import DagEngine

def _client(runner):
    app = FastAPI(); app.include_router(routes.router)
    from app.auth.context import TenantContext, require_tenant
    app.dependency_overrides[require_tenant] = lambda: TenantContext('t1', 'actor')
    app.dependency_overrides[routes.get_dag_engine] = lambda: DagEngine(runner)
    return TestClient(app)

def test_workflow_unknown_outcome_is_409_not_retryable_and_leaks_nothing():
    async def runner(task, cfg, ctx):
        if ctx["parents"]: raise ProviderOutcomeUnknown("api_key=abc123 PRIVATE-BODY")
        return {"text": "SECRET-OUTPUT"}
    y = "nodes:\n- {id: a, task: research}\n- {id: b, task: draft, depends_on: [a]}\n"
    r = _client(runner).post("/ai-research-lab/workflows/run", json={"yaml": y, "inputs": {}})
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["state"] == "unknown" and d["retry_allowed"] is False
    assert "abc123" not in r.text and "PRIVATE-BODY" not in r.text and "SECRET-OUTPUT" not in r.text
