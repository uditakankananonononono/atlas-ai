"""Claire durable execution semantics: crash-safe, idempotent, bounded."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.modules.m21_claire.durable_execution import (
    ClaireExecutionRepository, DurableExecutionOrchestrator,
)
from app.modules.m21_claire.execution import AttemptsExhausted, BoundedExecutor, IdempotencyStore
from app.modules.m21_claire.models import (
    ActionRequest, Approval, ExecutionPlan, PlanState, RiskLevel, StepState, utcnow,
)
from app.modules.m21_claire.orchestrator import ExecutionOrchestrator, ReviewMismatch
from app.modules.m21_claire.planner import CrossModulePlanner


def make_repo():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repo = ClaireExecutionRepository(engine)
    repo.create_schema()
    return repo


def make_plan(orchestrator_planner=None):
    planner = CrossModulePlanner()
    return planner.build("ship the report", [
        ActionRequest(module="docs", action="draft", parameters={"topic": "q3"},
                      purpose="report", risk=RiskLevel.LOW, action_id="draft-1"),
        ActionRequest(module="mail", action="send", parameters={"to": "team"},
                      purpose="report", risk=RiskLevel.HIGH,
                      dependencies=("draft-1",), action_id="send-1"),
    ])


def approve_all(orch, plan):
    for step in plan.steps:
        if orch.policy.require_allowed(step.request).requires_approval:
            snapshot = orch.review_snapshot(plan, step.request.action_id)
            orch.approve(plan, Approval(
                approval_id=f"ap-{snapshot.action_id}",
                review_digest=snapshot.digest, approver="udita",
                approved_at=utcnow(),
            ))


def test_prepare_approve_execute_persisted():
    repo = make_repo()
    orch = DurableExecutionOrchestrator(repo)
    calls = []
    orch.register("docs.draft", lambda p: calls.append("draft") or {"doc": "v1"})
    orch.register("mail.send", lambda p: calls.append("send") or {"sent": True})
    plan = make_plan()
    reviews = orch.prepare(plan)
    assert len(reviews) == 1 and reviews[0].action_id == "send-1"  # only HIGH risk gates
    approve_all(orch, plan)
    assert repo.load_plan(plan.plan_id).state == PlanState.APPROVED
    orch.execute(plan)
    assert plan.state == PlanState.SUCCEEDED
    assert calls == ["draft", "send"]
    stored = repo.load_plan(plan.plan_id)
    assert stored.state == PlanState.SUCCEEDED
    assert stored.step("draft-1").output == {"doc": "v1"}
    events = [row["event"] for row in repo.audit_log(plan.plan_id)]
    assert events == ["prepared", "approved", "execution_started",
                      "step_executed", "step_executed", "execution_succeeded"]


def test_resume_after_crash_never_reruns_succeeded_steps():
    repo = make_repo()
    calls = []

    def flaky_send(params):
        calls.append("send")
        raise ConnectionError("smtp down")

    orch = DurableExecutionOrchestrator(repo, max_attempts=1)
    orch.register("docs.draft", lambda p: calls.append("draft") or {"doc": "v1"})
    orch.register("mail.send", flaky_send)
    plan = make_plan()
    approve_all(orch, plan)
    with pytest.raises(AttemptsExhausted):
        orch.execute(plan)
    assert plan.state == PlanState.FAILED
    assert calls == ["draft", "send"]

    # "restart": a new orchestrator over the same repository resumes the plan
    orch2 = DurableExecutionOrchestrator(repo, max_attempts=2,
                                         retryable=lambda e: isinstance(e, ConnectionError))
    orch2.register("docs.draft", lambda p: calls.append("draft") or {"doc": "v1"})
    orch2.register("mail.send", lambda p: calls.append("send") or {"sent": True})
    resumed = orch2.resume(plan.plan_id)
    assert resumed.state == PlanState.SUCCEEDED
    assert calls == ["draft", "send", "send"]  # draft replayed from record, not re-run


def test_bounded_retries_exhaustion_and_replay():
    store = IdempotencyStore()
    executor = BoundedExecutor(store)
    attempts = []

    def flaky(params):
        attempts.append(1)
        if len(attempts) < 3:
            raise TimeoutError("slow")
        return "ok"

    result = executor.run(key="k1", fingerprint="fp", operation=flaky,
                          parameters={}, max_attempts=3,
                          retryable=lambda e: isinstance(e, TimeoutError))
    assert result.value == "ok" and result.attempts == 3 and not result.replayed
    again = executor.run(key="k1", fingerprint="fp", operation=lambda p: "new",
                         parameters={}, max_attempts=3)
    assert again.replayed and again.attempts == 0 and again.value == "ok"

    def always_fails(params):
        raise ValueError("nope")

    with pytest.raises(AttemptsExhausted) as caught:
        executor.run(key="k2", fingerprint="fp", operation=always_fails,
                     parameters={}, max_attempts=2,
                     retryable=lambda e: True)
    assert caught.value.attempts == 2
    with pytest.raises(ValueError):
        executor.run(key="k3", fingerprint="fp", operation=always_fails,
                     parameters={}, max_attempts=6)


def test_review_mismatch_blocks_and_audits():
    repo = make_repo()
    orch = DurableExecutionOrchestrator(repo)
    orch.register("docs.draft", lambda p: {"doc": "v1"})
    orch.register("mail.send", lambda p: {"sent": True})
    plan = make_plan()
    approve_all(orch, plan)
    # tamper with the reviewed parameters after approval
    step = plan.step("send-1")
    object.__setattr__(step.request, "parameters", {"to": "everyone@external"})
    with pytest.raises(ReviewMismatch):
        orch.execute(plan)
    stored = repo.load_plan(plan.plan_id)
    assert stored.step("send-1").state == StepState.BLOCKED
    assert any(row["event"] == "review_mismatch" for row in repo.audit_log(plan.plan_id))


def test_expired_approval_rejected():
    repo = make_repo()
    orch = DurableExecutionOrchestrator(repo)
    plan = make_plan()
    (snapshot,) = orch.prepare(plan)
    with pytest.raises(ReviewMismatch):
        orch.approve(plan, Approval(
            approval_id="ap-x", review_digest=snapshot.digest, approver="udita",
            approved_at=utcnow(), expires_at=utcnow() - timedelta(seconds=1),
        ))


def test_tenant_isolation():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    repo_a = ClaireExecutionRepository(engine, tenant_id="a")
    repo_a.create_schema()
    repo_b = ClaireExecutionRepository(engine, tenant_id="b")
    orch = DurableExecutionOrchestrator(repo_a)
    plan = make_plan()
    orch.prepare(plan)
    assert repo_b.load_plan(plan.plan_id) is None
    assert repo_b.audit_log(plan.plan_id) == []
