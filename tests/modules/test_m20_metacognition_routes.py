"""Mounted-route evidence for rows 10-34: one HTTP path per row."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m20_general_cognitive_worker.metacognition import PromptTemplate
from app.modules.m20_general_cognitive_worker.routes import bind_service, router
from app.modules.m20_general_cognitive_worker.schemas import (
    ActionRecord, EpisodeOutcome, Risk, ToolSpec,
)
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService


@pytest.fixture()
def client():
    service = CognitiveWorkerService()
    service.prompt_registry.register(PromptTemplate(name="orient_prompt", content="analyze"))

    async def search(args):
        return {"r": 1}

    service.tools.register(ToolSpec(name="web_search", description="s", risk=Risk.READ), search)
    service.episodic.log_execution(
        task_id="t1", goal="research professors and draft email outreach",
        actions=[ActionRecord(tool="web_search"), ActionRecord(tool="draft_email"),
                 ActionRecord(tool="send_email")],
        outcome=EpisodeOutcome.SUCCEEDED, reflection="gather transform deliver",
    )
    app = FastAPI()
    app.include_router(router)
    bind_service(service)
    return TestClient(app), service


def test_row10_routes(client):
    c, service = client
    created = c.post("/api/modules/20/meta/improvement/proposals",
                     json={"target_name": "orient_prompt", "proposed_content": "analyze then list gaps"})
    assert created.status_code == 201
    pid = created.json()["proposal_id"]
    rejected = c.post(f"/api/modules/20/meta/improvement/proposals/{pid}/apply", json={"approved": False})
    assert rejected.status_code == 403
    created2 = c.post("/api/modules/20/meta/improvement/proposals",
                      json={"target_name": "orient_prompt", "proposed_content": "v2 content"})
    applied = c.post(f"/api/modules/20/meta/improvement/proposals/{created2.json()['proposal_id']}/apply",
                     json={"approved": True, "approval_id": "appr-9"})
    assert applied.json()["version"] == 2
    assert c.post("/api/modules/20/meta/improvement/proposals",
                  json={"target_name": "ghost", "proposed_content": "x"}).status_code == 404


def test_row11_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/meta-learning/transfer",
               json={"goal": "study coral reefs and publish findings"})
    assert r.status_code == 200
    assert r.json()["transfers"][0]["role_sequence"] == ["gather", "transform", "deliver"]


def test_row12_route(client):
    c, _ = client
    assert c.post("/api/modules/20/meta/load-allocation").status_code == 200


def test_row13_routes(client):
    c, _ = client
    claim = c.post("/api/modules/20/meta/calibration/claims",
                   json={"text": "deadline is friday", "confidence": 0.95, "evidence_count": 0})
    assert claim.status_code == 201 and claim.json()["flagged"] is True
    cid = claim.json()["claim_id"]
    assert c.post(f"/api/modules/20/meta/calibration/claims/{cid}/resolve",
                  json={"correct": False}).json()["resolved"] is True
    assert c.get("/api/modules/20/meta/calibration/curve").status_code == 200
    assert c.post("/api/modules/20/meta/calibration/claims/nope/resolve",
                  json={"correct": True}).status_code == 404


def test_row14_route(client):
    c, service = client
    episode_id = list(service.episodic._episodes.keys())[0]
    r = c.post("/api/modules/20/meta/counterfactuals",
               json={"episode_id": episode_id,
                     "alternatives": [{"replaces_step": 0, "action": "dry run", "risk": "read"}]})
    assert r.json()["best_alternative"]["alternative_action"] == "dry run"
    assert c.post("/api/modules/20/meta/counterfactuals",
                  json={"episode_id": "nope", "alternatives": []}).status_code == 404


def test_row15_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/temporal/compare",
               json={"immediate_value": 50, "delayed_value": 100, "delay_days": 365})
    assert r.json()["choice"] in ("immediate", "delayed")


def test_row16_route(client):
    c, service = client
    from app.modules.m20_general_cognitive_worker.schemas import ChunkType, MemoryChunk
    service.working_memory.put(MemoryChunk(type=ChunkType.GOAL, content="x",
                                           salience=0.99, confidence=1.0),
                               active_goal="x", partition="ctx-a")
    r = c.post("/api/modules/20/meta/context-switch",
               json={"from_partition": "ctx-a", "to_partition": "ctx-b", "active_goal": "y"})
    assert r.json()["cleared_count"] == 1


def test_row17_routes(client):
    c, _ = client
    assert c.post("/api/modules/20/meta/flow/assess",
                  json={"challenge": 0.5, "skill": 0.52}).json()["zone"] == "flow"
    structured = c.post("/api/modules/20/meta/flow/structure",
                        json={"tasks": [{"title": "t", "difficulty": 0.5}], "skill": 0.5})
    assert structured.json()["structured"][0]["zone"] == "flow"


def test_row18_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/reframe", json={"setback": "the test failed with an error"})
    assert r.json()["category"] == "technical"


def test_row19_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/bias-scan", json={"text": "we've already invested too much to quit"})
    assert any(f["bias"] == "sunk_cost" for f in r.json()["findings"])


def test_row20_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/intuition", json={"question": "stress test my conclusion"})
    assert r.json()["latency_class"] == "fast"
    assert "devils-advocate" in r.json()["answer"]


def test_row21_routes(client):
    c, _ = client
    assert c.post("/api/modules/20/meta/world-models",
                  json={"name": "growth", "assumptions": {"m": "up"}}).status_code == 201
    assert c.post("/api/modules/20/meta/world-models/growth/evidence",
                  json={"supported": True, "weight": 2.0}).json()["posterior"] > 0.5
    assert c.post("/api/modules/20/meta/world-models/growth/revise",
                  json={"assumptions": {"m": "up", "moat": "brand"}}).json()["version"] == 2
    listing = c.get("/api/modules/20/meta/world-models").json()
    assert listing["current_best"] == "growth"
    assert c.post("/api/modules/20/meta/world-models/ghost/evidence",
                  json={"supported": True}).status_code == 404


def test_row22_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/goals/check-conflicts",
               json={"plan": [{"title": "create fake reviews"}, {"title": "research competitors"}],
                     "terminal_values": ["honesty"]})
    assert r.json()["restructured"] is True
    assert "create fake reviews" in r.json()["cancelled"]


def test_row23_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/decisions/routine",
               json={"decision_type": "calendar_color", "options": ["blue", "red"]})
    assert r.json()["automated"] is True
    high = c.post("/api/modules/20/meta/decisions/routine",
                  json={"decision_type": "hire", "options": ["a"], "stakes": "high"})
    assert high.json()["automated"] is False


def test_row24_25_26_routes(client):
    c, _ = client
    regret = c.post("/api/modules/20/meta/decisions/regret",
                    json={"options": {"safe": {"g": 50, "b": 50}, "risky": {"g": 200, "b": 0}}})
    assert regret.json()["minimax_choice"] == "risky"
    sac = c.post("/api/modules/20/meta/decisions/opportunity-cost",
                 json={"chosen": {"name": "a", "value": 80}, "alternatives": [{"name": "b", "value": 120}]})
    assert sac.json()["opportunity_cost"] == 40.0
    sunk = c.post("/api/modules/20/meta/decisions/sunk-cost",
                  json={"options": [{"name": "x", "past_investment": 900, "forward_value": 10},
                                     {"name": "y", "past_investment": 0, "forward_value": 50}]})
    assert sunk.json()["recommended"] == "y" and sunk.json()["sunk_cost_influenced"] is True


def test_row27_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/planning-horizon",
               json={"uncertainty": 0.9, "time_available_minutes": 30})
    assert r.json()["max_depth"] <= 2


def test_row28_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/abstraction/rollup",
               json={"goal": "launch", "plan": [{"title": "research"}, {"title": "build"}], "level": "streams"})
    assert len(r.json()["streams"]) == 2
    bad = c.post("/api/modules/20/meta/abstraction/rollup",
                 json={"goal": "g", "plan": [], "level": "quantum"})
    assert bad.status_code == 422


def test_row29_route(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/perspectives",
               json={"proposal": {"summary": "ship", "evidence_count": 4, "risk": "reversible",
                                   "upside": 8, "timeline_days": 21, "externally_visible": False}})
    assert len(r.json()["perspectives"]) == 5


def test_row30_31_routes(client):
    c, _ = client
    r = c.post("/api/modules/20/meta/devils-advocate",
               json={"claim": "we will win", "assumptions": ["users want this"], "evidence": []})
    assert r.json()["assumption_attacks"] and r.json()["residual_confidence"] < 0.9
    s = c.post("/api/modules/20/meta/steelman",
               json={"opposing_position": "remote work hurts cohesion",
                      "known_facts": ["remote teams report lower cohesion"]})
    assert s.json()["supporting_points"]


def test_row32_route(client):
    from datetime import datetime, timedelta, timezone
    c, service = client
    b = c.post("/api/modules/20/meta/epistemic-calendar/beliefs",
               json={"content": "competitor is not building this", "review_interval_days": 90})
    assert b.status_code == 201 and "next_review" in b.json()
    old = datetime.now(timezone.utc) - timedelta(days=120)
    service.epistemic_calendar.register("stale belief", formed_at=old, review_interval_days=90)
    due = c.get("/api/modules/20/meta/epistemic-calendar/due").json()["due"]
    assert due and due[0]["content"] == "stale belief"
    assert due[0]["overdue_days"] > 0


def test_row33_route(client):
    c, service = client
    from datetime import datetime, timedelta, timezone
    fact = service.semantic.remember("competitor price is $10", kind="price")
    fact.last_confirmed_at = datetime.now(timezone.utc) - timedelta(days=90)
    r = c.get("/api/modules/20/meta/knowledge-decay/forecast", params={"days_ahead": 60})
    assert any(f["fact_id"] == fact.id for f in r.json()["forecast"])


def test_row34_routes(client):
    c, _ = client
    gaps = c.post("/api/modules/20/meta/curiosity/gaps", json={"text": "explore quantum computing"})
    assert "quantum" in gaps.json()["gaps"]
    explore = c.post("/api/modules/20/meta/curiosity/explore", json={"idle_budget": 5.0})
    assert explore.json()["exploration"]
