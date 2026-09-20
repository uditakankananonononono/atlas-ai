from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m21_claire import (
    ActionPolicy, ActionRequest, Approval, ConsentError, CrossModulePlanner,
    DecisionRecord, DecisionStore, Evidence, ExecutionOrchestrator, PlanState,
    PlanValidationError, PolicyViolation, Preference, ReviewMismatch, RiskLevel, StepState,
)

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def evidence() -> Evidence:
    return Evidence(source="owner_channel", reference="msg-123", captured_at=NOW, excerpt="Use option A")


def test_decision_retrieval_requires_purpose_scope_evidence_and_live_consent():
    store = DecisionStore()
    record = DecisionRecord("d1", "provider", "A", "deployment", (evidence(),), frozenset({"plan"}), NOW)
    store.put_decision(record)
    assert store.require_one(subject="provider", purpose="deployment", scope="plan", now=NOW).choice == "A"
    with pytest.raises(ConsentError):
        store.require_one(subject="provider", purpose="marketing", scope="plan", now=NOW)
    store.revoke_decision("d1", replace(record, revoked_at=NOW + timedelta(seconds=1)))
    with pytest.raises(ConsentError):
        store.require_one(subject="provider", purpose="deployment", scope="plan", now=NOW + timedelta(seconds=2))


def test_preferences_are_evidence_backed_and_purpose_limited():
    store = DecisionStore()
    with pytest.raises(ValueError):
        store.put_preference(Preference("tone", "short", (), frozenset({"draft"})))
    store.put_preference(Preference("tone", "short", (evidence(),), frozenset({"draft"})))
    assert store.preference("tone", purpose="draft", now=NOW).value == "short"
    with pytest.raises(ConsentError):
        store.preference("tone", purpose="send", now=NOW)


@pytest.mark.parametrize("tag", ["deception", "piracy", "fake_account", "bot_account", "login_scraping", "self_bot"])
def test_hard_boundaries_cannot_be_approved_away(tag):
    request = ActionRequest("claire", "research", {"policy_tags": [tag]}, "goal")
    with pytest.raises(PolicyViolation):
        CrossModulePlanner().build("goal", [request])


def test_planner_topologically_orders_cross_module_work_and_rejects_cycles():
    first = ActionRequest("m04", "research", {}, "proposal", action_id="a")
    second = ActionRequest("m03", "draft", {}, "proposal", dependencies=("a",), action_id="b")
    plan = CrossModulePlanner().build("proposal", [second, first])
    assert [r.action_id for r in plan.ordered_requests()] == ["a", "b"]
    a = replace(first, dependencies=("b",))
    with pytest.raises(PlanValidationError, match="cycle"):
        CrossModulePlanner().build("bad", [a, second])


def test_exact_review_binds_parameters_and_blocks_mutation():
    request = ActionRequest("m05", "send", {"to": "a@example.com", "body": "hello"}, "outreach", RiskLevel.HIGH)
    plan = CrossModulePlanner().build("send mail", [request])
    orchestrator = ExecutionOrchestrator(clock=lambda: NOW)
    orchestrator.register("m05.send", lambda params: {"sent": params["to"]})
    review = orchestrator.prepare(plan)[0]
    orchestrator.approve(plan, Approval("ok", review.digest, "user", NOW))
    request.parameters["to"] = "wrong@example.com"  # underlying mutable input changed after review
    with pytest.raises(ReviewMismatch):
        orchestrator.execute(plan)
    assert plan.state is PlanState.FAILED
    assert plan.steps[0].state is StepState.BLOCKED


def test_approved_plan_executes_in_dependency_order():
    log = []
    first = ActionRequest("m04", "research", {"q": "x"}, "report", action_id="a")
    second = ActionRequest("m05", "publish", {"channel": "site"}, "report", RiskLevel.HIGH, ("a",), "b")
    plan = CrossModulePlanner().build("report", [second, first])
    orchestrator = ExecutionOrchestrator(clock=lambda: NOW)
    orchestrator.register("m04.research", lambda p: log.append("research") or "facts")
    orchestrator.register("m05.publish", lambda p: log.append("publish") or "url")
    review = orchestrator.prepare(plan)[0]
    orchestrator.approve(plan, Approval("approval", review.digest, "user", NOW, NOW + timedelta(minutes=5)))
    orchestrator.execute(plan)
    assert log == ["research", "publish"]
    assert plan.state is PlanState.SUCCEEDED
    assert all(step.state is StepState.SUCCEEDED for step in plan.steps)


def test_expired_approval_is_rejected_at_execution_time():
    current = [NOW]
    request = ActionRequest("m22", "install", {"tool": "safe"}, "tools", RiskLevel.HIGH)
    plan = CrossModulePlanner().build("install", [request])
    orchestrator = ExecutionOrchestrator(clock=lambda: current[0])
    orchestrator.register("m22.install", lambda p: True)
    review = orchestrator.prepare(plan)[0]
    orchestrator.approve(plan, Approval("a", review.digest, "user", NOW, NOW + timedelta(seconds=1)))
    current[0] = NOW + timedelta(seconds=2)
    with pytest.raises(ReviewMismatch):
        orchestrator.execute(plan)
