"""Exact-review execution orchestration with dependency and policy checks."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .models import (
    Approval, ExecutionPlan, PlanState, ReviewSnapshot, StepState, utcnow,
)
from .policy import ActionPolicy, PolicyViolation


class ReviewMismatch(PermissionError):
    pass


class ExecutorNotRegistered(LookupError):
    pass


class ExecutionOrchestrator:
    def __init__(self, policy: ActionPolicy | None = None, clock: Callable[[], datetime] = utcnow) -> None:
        self.policy = policy or ActionPolicy()
        self.clock = clock
        self._executors: dict[str, Callable[[Mapping[str, Any]], Any]] = {}

    def register(self, capability: str, executor: Callable[[Mapping[str, Any]], Any]) -> None:
        if not capability.strip() or capability in self._executors:
            raise ValueError("capability must be non-empty and registered once")
        self._executors[capability] = executor

    @staticmethod
    def _canonical(payload: Mapping[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

    def review_snapshot(self, plan: ExecutionPlan, action_id: str) -> ReviewSnapshot:
        request = plan.step(action_id).request
        payload = {
            "plan_id": plan.plan_id,
            "action_id": request.action_id,
            "capability": request.capability,
            "purpose": request.purpose,
            "parameters": request.parameters,
            "risk": request.risk.value,
        }
        digest = hashlib.sha256(self._canonical(payload).encode()).hexdigest()
        return ReviewSnapshot(
            plan_id=plan.plan_id,
            action_id=request.action_id,
            capability=request.capability,
            purpose=request.purpose,
            parameters=dict(request.parameters),
            risk=request.risk,
            digest=digest,
        )

    def approve(self, plan: ExecutionPlan, approval: Approval) -> None:
        if not approval.valid_at(self.clock()):
            raise ReviewMismatch("approval is expired")
        matching = [
            step.request.action_id for step in plan.steps
            if self.review_snapshot(plan, step.request.action_id).digest == approval.review_digest
        ]
        if len(matching) != 1:
            raise ReviewMismatch("approval does not match an exact current review")
        plan.approvals[matching[0]] = approval
        if all(
            not self.policy.require_allowed(step.request).requires_approval
            or step.request.action_id in plan.approvals
            for step in plan.steps
        ):
            plan.state = PlanState.APPROVED
        else:
            plan.state = PlanState.AWAITING_REVIEW

    def prepare(self, plan: ExecutionPlan) -> tuple[ReviewSnapshot, ...]:
        reviews: list[ReviewSnapshot] = []
        for step in plan.steps:
            decision = self.policy.require_allowed(step.request)
            if decision.requires_approval:
                reviews.append(self.review_snapshot(plan, step.request.action_id))
                step.state = StepState.BLOCKED
            else:
                step.state = StepState.READY
        plan.state = PlanState.AWAITING_REVIEW if reviews else PlanState.APPROVED
        return tuple(reviews)

    def execute(self, plan: ExecutionPlan) -> ExecutionPlan:
        if plan.state not in {PlanState.APPROVED, PlanState.AWAITING_REVIEW}:
            raise RuntimeError(f"plan cannot execute from {plan.state.value}")
        plan.state = PlanState.RUNNING
        succeeded: set[str] = set()
        try:
            for step in plan.steps:
                request = step.request
                if not set(request.dependencies) <= succeeded:
                    step.state = StepState.SKIPPED
                    step.error = "dependency did not succeed"
                    continue
                decision = self.policy.require_allowed(request)  # re-check at execution time
                if decision.requires_approval:
                    approval = plan.approvals.get(request.action_id)
                    current = self.review_snapshot(plan, request.action_id)
                    if approval is None or approval.review_digest != current.digest or not approval.valid_at(self.clock()):
                        step.state = StepState.BLOCKED
                        raise ReviewMismatch(f"missing, stale, or mismatched approval for {request.action_id}")
                executor = self._executors.get(request.capability)
                if executor is None:
                    raise ExecutorNotRegistered(request.capability)
                step.state = StepState.RUNNING
                step.output = executor(dict(request.parameters))
                step.state = StepState.SUCCEEDED
                succeeded.add(request.action_id)
        except Exception as exc:
            if step.state is StepState.RUNNING:
                step.state = StepState.FAILED
            step.error = str(exc)
            plan.state = PlanState.FAILED
            raise
        plan.state = PlanState.SUCCEEDED
        return plan
