"""Chunk 4 tests: FastAPI surface for the GCW."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m20_general_cognitive_worker.routes import bind_service, router
from app.modules.m20_general_cognitive_worker.safety import (
    ApprovalGateDecision, InMemoryApprovalGate,
)
from app.modules.m20_general_cognitive_worker.schemas import (
    HTNMethod, PlanNode, Risk, ToolSpec,
)
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService


@pytest.fixture()
def client():
    gate = InMemoryApprovalGate()
    service = CognitiveWorkerService(approval_gate=gate)

    async def search(args):
        return {"results": ["x"]}

    async def send(args):
        return {"sent": True}

    service.tools.register(ToolSpec(name="web_search", description="search", risk=Risk.READ), search)
    service.tools.register(ToolSpec(name="send_email", description="send", risk=Risk.EXTERNAL), send)
    service.planner.register_method(HTNMethod(
        name="research-report", goal_pattern="research topic and send summary",
        subtasks=[
            PlanNode(title="research", tool="web_search", risk=Risk.READ),
            PlanNode(title="send summary", tool="send_email", risk=Risk.EXTERNAL,
                     depends_on=["research"]),
        ],
    ))
    app = FastAPI()
    app.include_router(router)
    bind_service(service)
    return TestClient(app), service, gate


def test_goal_lifecycle_over_http(client):
    c, service, gate = client
    created = c.post("/api/modules/20/goals", json={"goal": "research topic and send summary"})
    assert created.status_code == 201
    body = created.json()
    assert body["state"] == "waiting_approval"
    task_id = body["task_id"]

    task = c.get(f"/api/modules/20/tasks/{task_id}")
    assert task.status_code == 200
    waiting = [n for n in task.json()["plan"] if n["state"] == "waiting_approval"]
    assert len(waiting) == 1
    gate.decide(waiting[0]["approval_id"], ApprovalGateDecision.APPROVED)

    resumed = c.post(f"/api/modules/20/tasks/{task_id}/resume",
                     json={"node_id": waiting[0]["id"], "approved": True})
    assert resumed.json()["state"] == "succeeded"

    listing = c.get("/api/modules/20/tasks").json()
    assert any(t["id"] == task_id and t["steps_done"] == 2 for t in listing)

    traces = c.get("/api/modules/20/traces", params={"task_id": task_id}).json()
    assert any(t["phase"] == "decide" for t in traces)


def test_ingest_memory_skills_tools_over_http(client):
    c, service, _ = client
    ingested = c.post("/api/modules/20/ingest/text",
                      json={"text": "competitor raised prices", "source": "api"})
    assert ingested.status_code == 201 and ingested.json()["ingested"] is True
    dupe = c.post("/api/modules/20/ingest/text",
                  json={"text": "competitor raised prices", "source": "api"})
    assert dupe.json()["ingested"] is False

    email = c.post("/api/modules/20/ingest/email",
                   json={"subject": "Grant", "body": "Deadline Friday", "sender": "a@b.c"})
    assert email.status_code == 201

    fact = c.post("/api/modules/20/memory/facts", json={"content": "grants need budgets"})
    assert fact.status_code == 201
    hits = c.get("/api/modules/20/memory/facts", params={"query": "what do grants need"}).json()
    assert hits and "budgets" in hits[0]["content"]
    assert c.get("/api/modules/20/memory/facts").status_code == 400

    skills = c.get("/api/modules/20/skills").json()
    assert any(s["name"] == "premortem" for s in skills)
    tools = c.get("/api/modules/20/tools").json()
    assert {t["name"] for t in tools} == {"web_search", "send_email"}


def test_standup_health_ruminate_and_404s(client):
    c, service, _ = client
    c.post("/api/modules/20/goals",
           json={"goal": "research topic and send summary", "run_immediately": False})
    standup = c.get("/api/modules/20/standup").json()["standup"]
    assert "research topic" in standup
    health = c.get("/api/modules/20/health").json()
    assert health["module"] == "m20_general_cognitive_worker"
    assert health["healthy"] is True

    task_id = c.get("/api/modules/20/tasks").json()[0]["id"]
    rum = c.post(f"/api/modules/20/tasks/{task_id}/ruminate").json()
    assert "simulations" in rum

    retro = c.post(f"/api/modules/20/tasks/{task_id}/retrospective",
                   json={"went_well": ["a"], "went_poorly": [], "lessons": ["l"]})
    assert retro.status_code == 200

    missing = "00000000-0000-0000-0000-000000000000"
    assert c.get(f"/api/modules/20/tasks/{missing}").status_code == 404
    assert c.post(f"/api/modules/20/tasks/{missing}/ruminate").status_code == 404
    assert c.post(f"/api/modules/20/tasks/{missing}/resume",
                  json={"node_id": "x", "approved": True}).status_code == 404
    assert c.post(f"/api/modules/20/tasks/{missing}/retrospective", json={}).status_code == 404
