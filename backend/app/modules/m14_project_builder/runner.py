"""Bounded DAG task runner for Atlas Module 14 (Project Builder).

Walks a ProjectPlan in dependency order through an injected executor,
consuming a BudgetLedger for every agent call, second of runtime, and
refinement iteration. Successful tasks land in "review" (human gate); a
reviewer approves them to "completed" so dependents unlock, or the runner
is constructed with auto_approve for trusted dry runs. Failures retry up to
max_task_attempts, each retry consuming a budget iteration. The runner
never executes anything itself: the executor is supplied by the caller,
which keeps approval-gated, sandboxed execution outside this engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .budgets import BudgetExceeded, BudgetLedger
from .schemas import ProjectPlan, ProjectTask


class RunnerError(ValueError):
    """Base error for runner operations."""


@dataclass(frozen=True)
class TaskOutput:
    """What an executor returns for one task attempt."""

    success: bool
    summary: str = ""
    cost_usd: float = 0.0
    runtime_seconds: float = 0.0
    artifact_ids: Tuple[str, ...] = ()
    failure_reason: str = ""

    def __post_init__(self) -> None:
        if self.cost_usd < 0:
            raise RunnerError("cost_usd must be >= 0")
        if self.runtime_seconds < 0:
            raise RunnerError("runtime_seconds must be >= 0")
        if self.success and self.failure_reason:
            raise RunnerError("successful output cannot carry a failure_reason")


ExecutorFn = Callable[[ProjectTask], TaskOutput]


@dataclass(frozen=True)
class RunReport:
    plan: ProjectPlan
    stopped_reason: str  # completed | awaiting_review | budget_exhausted | blocked_failures
    tasks_completed: Tuple[str, ...]
    tasks_in_review: Tuple[str, ...]
    tasks_failed: Tuple[str, ...]
    budget_status: object  # budgets.BudgetStatus


def _ready(plan: ProjectPlan) -> List[ProjectTask]:
    complete = {t.id for t in plan.tasks if t.status == "completed"}
    return [
        t for t in plan.tasks
        if t.status in {"blocked", "ready"} and set(t.dependencies) <= complete
    ]


class TaskRunner:
    """Executes a plan DAG through an executor within a budget ledger."""

    def __init__(
        self,
        ledger: BudgetLedger,
        executor: ExecutorFn,
        max_task_attempts: int = 2,
        auto_approve: bool = False,
    ):
        if max_task_attempts < 1:
            raise RunnerError("max_task_attempts must be >= 1")
        self.ledger = ledger
        self.executor = executor
        self.max_task_attempts = max_task_attempts
        self.auto_approve = auto_approve

    def _update(self, plan: ProjectPlan, task_id: str, **changes) -> ProjectPlan:
        tasks = [
            t.model_copy(update=changes) if t.id == task_id else t
            for t in plan.tasks
        ]
        return plan.model_copy(update={"tasks": tasks})

    def approve_reviewed(self, plan: ProjectPlan, task_id: str) -> ProjectPlan:
        """Human gate: move a reviewed task to completed."""
        task = next((t for t in plan.tasks if t.id == task_id), None)
        if task is None:
            raise RunnerError(f"unknown task {task_id!r}")
        if task.status != "review":
            raise RunnerError(
                f"task {task_id!r} is {task.status}, not awaiting review"
            )
        return self._update(plan, task_id, status="completed")

    def reject_reviewed(self, plan: ProjectPlan, task_id: str) -> ProjectPlan:
        """Human gate: send a reviewed task back for another attempt."""
        task = next((t for t in plan.tasks if t.id == task_id), None)
        if task is None:
            raise RunnerError(f"unknown task {task_id!r}")
        if task.status != "review":
            raise RunnerError(
                f"task {task_id!r} is {task.status}, not awaiting review"
            )
        return self._update(plan, task_id, status="ready")

    def _run_task(self, plan: ProjectPlan, task: ProjectTask) -> ProjectPlan:
        plan = self._update(plan, task.id, status="running")
        output = self.executor(task)
        self.ledger.record_agent_call(
            cost_usd=output.cost_usd, note=f"task {task.id}"
        )
        if output.runtime_seconds:
            self.ledger.record_runtime(
                output.runtime_seconds, note=f"task {task.id}"
            )
        if output.success:
            next_status = "completed" if self.auto_approve else "review"
            return self._update(plan, task.id, status=next_status)
        attempts = task.attempt + 1
        if attempts < self.max_task_attempts:
            self.ledger.record_iteration(note=f"retry task {task.id}")
            return self._update(plan, task.id, status="ready", attempt=attempts)
        return self._update(plan, task.id, status="failed", attempt=attempts)

    def run(self, plan: ProjectPlan) -> RunReport:
        """Walk the DAG until done, blocked, awaiting review, or out of budget."""
        current = plan
        while True:
            review_pending = [t for t in current.tasks if t.status == "review"]
            ready = _ready(current)
            if not ready:
                failed = [t for t in current.tasks if t.status == "failed"]
                incomplete = [
                    t for t in current.tasks
                    if t.status not in {"completed", "failed"}
                ]
                if review_pending:
                    reason = "awaiting_review"
                elif not incomplete:
                    reason = "completed"
                elif failed:
                    reason = "blocked_failures"
                else:  # pragma: no cover - defensive; statuses are closed
                    reason = "blocked_failures"
                break
            progressed = False
            for task in ready:
                if not self.ledger.can_afford_call():
                    return self._report(current, "budget_exhausted")
                try:
                    current = self._run_task(current, task)
                except BudgetExceeded:
                    return self._report(current, "budget_exhausted")
                progressed = True
            if not progressed:  # pragma: no cover - defensive
                break
        return self._report(current, reason)

    def _report(self, plan: ProjectPlan, reason: str) -> RunReport:
        return RunReport(
            plan=plan,
            stopped_reason=reason,
            tasks_completed=tuple(
                t.id for t in plan.tasks if t.status == "completed"
            ),
            tasks_in_review=tuple(t.id for t in plan.tasks if t.status == "review"),
            tasks_failed=tuple(t.id for t in plan.tasks if t.status == "failed"),
            budget_status=self.ledger.status(),
        )
