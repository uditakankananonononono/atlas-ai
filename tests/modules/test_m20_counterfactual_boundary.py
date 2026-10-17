"""Row 14 counterfactual API boundary: input validation and honest scope.

The default service has no outcome model, so estimates stay None and the
status honestly reports outcome_model_unavailable; an injected estimator is
labeled supplied_estimator_only. Neither path claims causal proof.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m20_general_cognitive_worker.metacognition import CounterfactualEngine
from app.modules.m20_general_cognitive_worker.routes import bind_service, router
from app.modules.m20_general_cognitive_worker.safety import (
    ApprovalGateDecision, InMemoryApprovalGate,
)
from app.modules.m20_general_cognitive_worker.schemas import (
    Episode, EpisodeOutcome, HTNMethod, PlanNode, Risk, ToolSpec,
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


def produce_episode_over_http(client):
    """Run a real goal to completion through the mounted routes; return its episode."""
    c, service, gate = client
    created = c.post("/api/modules/20/goals", json={"goal": "research topic and send summary"})
    assert created.status_code == 201
    task_id = created.json()["task_id"]
    plan = c.get(f"/api/modules/20/tasks/{task_id}").json()["plan"]
    waiting = [n for n in plan if n["state"] == "waiting_approval"]
    assert len(waiting) == 1
    gate.decide(waiting[0]["approval_id"], ApprovalGateDecision.APPROVED)
    resumed = c.post(f"/api/modules/20/tasks/{task_id}/resume",
                     json={"node_id": waiting[0]["id"], "approved": True})
    assert resumed.json()["state"] == "succeeded"
    episodes = service.episodic.for_task(task_id)
    assert len(episodes) == 1 and episodes[0].outcome == EpisodeOutcome.SUCCEEDED
    return episodes[0]


def test_counterfactual_over_real_episode(client):
    c, _, _ = client
    episode = produce_episode_over_http(client)
    r = c.post("/api/modules/20/meta/counterfactuals",
               json={"episode_id": episode.id,
                     "alternatives": [{"replaces_step": 0, "action": "dry run", "risk": "read"},
                                      {"replaces_step": 1, "action": "skip send"}]})
    assert r.status_code == 200
    body = r.json()
    assert body["episode_id"] == episode.id
    assert body["status"] == "outcome_model_unavailable"
    assert body["capability_executed"] is False
    assert body["best_alternative"] is None
    assert body["actual_outcome"] == "succeeded"
    assert len(body["alternatives"]) == 2
    for alt in body["alternatives"]:
        assert alt["estimated_success_probability"] is None
        assert alt["status"] == "outcome_model_unavailable"
        assert alt["capability_executed"] is False


def test_counterfactual_invalid_risk_maps_to_422(client):
    c, _, _ = client
    episode = produce_episode_over_http(client)
    r = c.post("/api/modules/20/meta/counterfactuals",
               json={"episode_id": episode.id,
                     "alternatives": [{"replaces_step": 0, "action": "dry run", "risk": "bogus"}]})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "bogus" in detail and "read" in detail and "irreversible" in detail


def test_counterfactual_non_dict_alternative_rejected(client):
    c, _, _ = client
    episode = produce_episode_over_http(client)
    r = c.post("/api/modules/20/meta/counterfactuals",
               json={"episode_id": episode.id, "alternatives": ["not-a-dict"]})
    assert r.status_code == 422


def test_counterfactual_unknown_episode_still_404(client):
    c, _, _ = client
    r = c.post("/api/modules/20/meta/counterfactuals",
               json={"episode_id": "nope", "alternatives": []})
    assert r.status_code == 404


def _episode(outcome=EpisodeOutcome.SUCCEEDED) -> Episode:
    return Episode(task_id="t", goal="g", actions=[], outcome=outcome, reflection="r")


def test_simulate_direct_rejects_non_dict_alternative():
    engine = CounterfactualEngine()
    with pytest.raises(ValueError, match="must be an object"):
        engine.simulate(_episode(), ["not-a-dict"])


def test_simulate_direct_rejects_invalid_risk():
    engine = CounterfactualEngine()
    with pytest.raises(ValueError, match="invalid risk"):
        engine.simulate(_episode(), [{"action": "x", "risk": "bogus"}])


def test_simulate_default_risk_and_honest_unavailable():
    engine = CounterfactualEngine()
    out = engine.simulate(_episode(), [{"replaces_step": 0, "action": "dry run"}])
    assert out["status"] == "outcome_model_unavailable"
    assert out["alternatives"][0]["estimated_success_probability"] is None
    assert out["best_alternative"] is None


def test_simulate_supplied_estimator_labeled_not_causal():
    class FixedEstimator:
        def estimate(self, action_description, risk):
            return 0.5

    engine = CounterfactualEngine(outcome_model=FixedEstimator())
    out = engine.simulate(_episode(), [{"replaces_step": 0, "action": "dry run", "risk": "read"}])
    assert out["status"] == "supplied_estimator_only"
    assert out["capability_executed"] is False
    assert out["alternatives"][0]["estimated_success_probability"] == 0.5
    assert out["best_alternative"] is None


def test_validation_is_fail_atomic_before_estimator_runs():
    calls = []

    class SpyEstimator:
        def estimate(self, action_description, risk):
            calls.append(action_description)
            return 0.5

    engine = CounterfactualEngine(outcome_model=SpyEstimator())
    with pytest.raises(ValueError, match="invalid risk"):
        engine.simulate(_episode(), [{"action": "first-ok", "risk": "read"},
                                     {"action": "second-bad", "risk": "bogus"}])
    assert calls == []  # no early estimator side effect from the valid prefix


def test_estimator_value_error_is_not_mislabeled_as_input_error(client):
    c, service, _ = client
    episode = produce_episode_over_http(client)

    class FaultyEstimator:
        def estimate(self, action_description, risk):
            raise ValueError("provider internal failure")

    service.counterfactuals.outcome_model = FaultyEstimator()
    c2 = TestClient(c.app, raise_server_exceptions=False)
    r = c2.post("/api/modules/20/meta/counterfactuals",
                json={"episode_id": episode.id,
                      "alternatives": [{"replaces_step": 0, "action": "dry run", "risk": "read"}]})
    assert r.status_code == 500  # provider fault, not a 422 client-input error
