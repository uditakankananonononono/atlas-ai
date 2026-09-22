"""Goal-first orchestration: cited plans, approval gating, honest readback."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.m20_general_cognitive_worker.product_orchestrator import (
    OrchestrationConflictError,
    ProductOrchestrator,
)
from app.modules.m20_general_cognitive_worker.product_orchestrator_routes import (
    get_orchestrator,
)
from app.modules.m20_general_cognitive_worker.safety import InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.schemas import ApprovalGateDecision


def make_orchestrator(executors=None):
    gate = InMemoryApprovalGate()
    service = ProductOrchestrator("tenant-a", approval_gate=gate, executors=executors)
    return service, gate


def registered_goal(service):
    return service.register_goal(
        statement="Ship a cited launch plan",
        sources=[
            {"uri": "https://example.test/spec", "note": "product spec"},
            {"uri": "https://example.test/metrics", "note": "baseline metrics"},
        ],
    )


def plan_steps(goal, citations=None):
    citations = citations or [goal.sources[next(iter(goal.sources))].id]
    return [
        {"title": "Draft launch checklist", "action_type": "draft_document", "citations": citations},
        {"title": "Simulate rollout", "action_type": "simulate_rollout", "citations": citations},
    ]


def test_plan_rejects_missing_and_unknown_citations():
    service, _ = make_orchestrator()
    goal = registered_goal(service)
    with pytest.raises(ValueError, match="at least one source citation"):
        service.build_plan(goal.id, [{"title": "Uncited", "action_type": "x", "citations": []}])
    with pytest.raises(ValueError, match="unregistered sources"):
        service.build_plan(goal.id, [{"title": "Bad cite", "action_type": "x", "citations": ["nope"]}])
    with pytest.raises(ValueError, match="at least one source"):
        service.register_goal(statement="No sources", sources=[])


def test_execution_waits_for_human_approval_and_cannot_replay():
    service, gate = make_orchestrator()
    goal = registered_goal(service)
    service.build_plan(goal.id, plan_steps(goal))
    approval_id = service.request_approval(goal.id)["approval_id"]
    assert service.describe(goal.id)["status"] == "waiting_approval"
    with pytest.raises(PermissionError, match="not approved"):
        service.execute(goal.id, approval_id=approval_id)
    with pytest.raises(OrchestrationConflictError, match="already pending"):
        service.request_approval(goal.id)
    gate.decide(approval_id, ApprovalGateDecision.APPROVED)
    result = service.execute(goal.id, approval_id=approval_id)
    assert result["status"] == "executed"
    with pytest.raises(OrchestrationConflictError, match="already executed"):
        service.execute(goal.id, approval_id=approval_id)


def test_rejected_approval_blocks_execution_until_a_new_request_is_approved():
    service, gate = make_orchestrator()
    goal = registered_goal(service)
    service.build_plan(goal.id, plan_steps(goal))
    first = service.request_approval(goal.id)["approval_id"]
    gate.decide(first, ApprovalGateDecision.REJECTED)
    with pytest.raises(PermissionError, match="rejected"):
        service.execute(goal.id, approval_id=first)
    second = service.request_approval(goal.id)["approval_id"]
    assert second != first
    gate.decide(second, ApprovalGateDecision.APPROVED)
    assert service.execute(goal.id, approval_id=second)["status"] == "executed"


def test_default_executor_simulates_and_never_claims_external_effect():
    service, gate = make_orchestrator()
    goal = registered_goal(service)
    service.build_plan(goal.id, plan_steps(goal))
    approval_id = service.request_approval(goal.id)["approval_id"]
    gate.decide(approval_id, ApprovalGateDecision.APPROVED)
    service.execute(goal.id, approval_id=approval_id)
    state = service.execution_state(goal.id)
    assert state["ledger"]["counts"]["simulated"] == 2
    assert state["ledger"]["counts"]["externally_executed"] == 0
    assert state["ledger"]["highest_observed_state"] == "simulated"
    assert "never promoted" in state["ledger"]["boundary"]


def test_external_execution_claim_without_evidence_fails_the_step():
    def dishonest(step, context):
        return {"state": "externally_executed"}  # no evidence_ids

    service, gate = make_orchestrator(executors={"draft_document": dishonest})
    goal = registered_goal(service)
    service.build_plan(goal.id, plan_steps(goal))
    approval_id = service.request_approval(goal.id)["approval_id"]
    gate.decide(approval_id, ApprovalGateDecision.APPROVED)
    result = service.execute(goal.id, approval_id=approval_id)
    assert result["status"] == "failed" and result["failed_steps"] == 1
    state = service.execution_state(goal.id)
    assert state["ledger"]["counts"]["externally_executed"] == 0
    assert len(state["errors"]) == 1
    assert "requires evidence_ids" in next(iter(state["errors"].values()))


def test_evidenced_execution_and_verified_readback():
    def executor(step, context):
        if step.action_type == "draft_document":
            return {"state": "externally_executed", "evidence_ids": ["ev-1"], "detail": "stored"}
        return {"state": "independently_verified", "evidence_ids": ["ev-2"], "verifier": "qa-bot"}

    service, gate = make_orchestrator(executors={
        "draft_document": executor, "simulate_rollout": executor,
    })
    goal = registered_goal(service)
    service.build_plan(goal.id, plan_steps(goal))
    approval_id = service.request_approval(goal.id)["approval_id"]
    gate.decide(approval_id, ApprovalGateDecision.APPROVED)
    service.execute(goal.id, approval_id=approval_id)
    ledger = service.execution_state(goal.id)["ledger"]
    assert ledger["counts"]["externally_executed"] == 1
    assert ledger["counts"]["independently_verified"] == 1
    assert ledger["highest_observed_state"] == "independently_verified"
    assert ledger["verified_fraction"] == 0.5


def test_approval_payload_carries_cited_steps_to_module_zero():
    service, gate = make_orchestrator()
    goal = registered_goal(service)
    service.build_plan(goal.id, plan_steps(goal))
    approval_id = service.request_approval(goal.id)["approval_id"]
    request = gate.requests[approval_id]
    assert request.action_type == "execute_product_plan"
    payload_steps = request.payload["steps"]
    assert payload_steps[0]["citations"][0]["uri"] == "https://example.test/spec"
    assert request.payload["tenant_id"] == "tenant-a"


def test_orchestrator_routes_cover_the_full_loop():
    gate = InMemoryApprovalGate()
    service = ProductOrchestrator("tenant", approval_gate=gate)
    app.dependency_overrides[get_orchestrator] = lambda: service
    client = TestClient(app)
    try:
        bad = client.post("/api/v1/product-orchestrator/goals", json={
            "statement": "Sourceless goal", "sources": []})
        assert bad.status_code == 422

        goal = client.post("/api/v1/product-orchestrator/goals", json={
            "statement": "Ship a cited launch plan",
            "sources": [{"uri": "https://example.test/spec", "note": "spec"}],
        })
        assert goal.status_code == 201
        goal_id = goal.json()["id"]
        source_id = goal.json()["sources"][0]["id"]

        assert client.get("/api/v1/product-orchestrator/goals/does-not-exist").status_code == 404

        uncited = client.post(f"/api/v1/product-orchestrator/goals/{goal_id}/plan", json={
            "steps": [{"title": "Uncited", "action_type": "x", "citations": ["nope"]}]})
        assert uncited.status_code == 422

        plan = client.post(f"/api/v1/product-orchestrator/goals/{goal_id}/plan", json={
            "steps": [
                {"title": "Draft checklist", "action_type": "draft_document", "citations": [source_id]},
                {"title": "Simulate rollout", "action_type": "simulate_rollout", "citations": [source_id]},
            ]})
        assert plan.status_code == 201
        assert plan.json()["status"] == "planned"

        approval = client.post(f"/api/v1/product-orchestrator/goals/{goal_id}/approval-requests")
        assert approval.status_code == 201
        approval_id = approval.json()["approval_id"]
        assert client.post(f"/api/v1/product-orchestrator/goals/{goal_id}/approval-requests").status_code == 409

        blocked = client.post(f"/api/v1/product-orchestrator/goals/{goal_id}/executions",
                              json={"approval_id": approval_id})
        assert blocked.status_code == 403

        gate.decide(approval_id, ApprovalGateDecision.APPROVED)
        executed = client.post(f"/api/v1/product-orchestrator/goals/{goal_id}/executions",
                               json={"approval_id": approval_id})
        assert executed.status_code == 200
        assert executed.json()["status"] == "executed"
        assert client.post(f"/api/v1/product-orchestrator/goals/{goal_id}/executions",
                           json={"approval_id": approval_id}).status_code == 409

        state = client.get(f"/api/v1/product-orchestrator/goals/{goal_id}/execution-state")
        assert state.status_code == 200
        body = state.json()
        assert body["approval_decision"] == "approved"
        assert body["ledger"]["counts"] == {
            "planned": 0, "simulated": 2, "externally_executed": 0, "independently_verified": 0}
        assert body["ledger"]["items"][0]["source_module"] == "m20_product_orchestrator"
    finally:
        app.dependency_overrides.clear()


def test_goals_are_scoped_to_their_tenant():
    gate = InMemoryApprovalGate()
    service_a = ProductOrchestrator("tenant-a", approval_gate=gate)
    service_b = ProductOrchestrator("tenant-b", approval_gate=gate)
    goal = registered_goal(service_a)
    service_b.goals[goal.id] = goal  # same store, different tenant facade
    with pytest.raises(KeyError):
        service_b.describe(goal.id)
