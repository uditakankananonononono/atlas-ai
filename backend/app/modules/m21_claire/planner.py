"""Deterministic cross-module plan construction and validation."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable

from .models import ActionRequest, ExecutionPlan, PlanState, PlanStep
from .policy import ActionPolicy, PolicyViolation


class PlanValidationError(ValueError):
    pass


class CrossModulePlanner:
    def __init__(self, policy: ActionPolicy | None = None) -> None:
        self.policy = policy or ActionPolicy()

    def build(self, goal: str, requests: Iterable[ActionRequest]) -> ExecutionPlan:
        requests = tuple(requests)
        if not goal.strip() or not requests:
            raise PlanValidationError("goal and at least one action are required")
        by_id = {request.action_id: request for request in requests}
        if len(by_id) != len(requests):
            raise PlanValidationError("duplicate action ids")
        for request in requests:
            self.policy.require_allowed(request)
            unknown = set(request.dependencies) - by_id.keys()
            if unknown:
                raise PlanValidationError(f"unknown dependencies for {request.action_id}: {sorted(unknown)}")

        outgoing: dict[str, list[str]] = defaultdict(list)
        indegree = {request.action_id: 0 for request in requests}
        for request in requests:
            for dependency in request.dependencies:
                outgoing[dependency].append(request.action_id)
                indegree[request.action_id] += 1
        ready = deque(sorted(key for key, degree in indegree.items() if degree == 0))
        ordered: list[ActionRequest] = []
        while ready:
            current = ready.popleft()
            ordered.append(by_id[current])
            for child in sorted(outgoing[current]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        if len(ordered) != len(requests):
            raise PlanValidationError("action dependencies contain a cycle")
        return ExecutionPlan(goal=goal, steps=[PlanStep(request=r) for r in ordered], state=PlanState.DRAFT)
