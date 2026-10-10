"""Bounded in-process async DAG execution through a caller-owned executor.

This is not a distributed builder deployment. The caller must supply an already
approved, cooperative executor. No API, sandbox or external dispatch is added.
Reservations charge declared worst-case cost/runtime before dispatch, without
refunds, so concurrent calls cannot spend the same remaining budget. A timeout
requests coroutine cancellation; it cannot kill blocking code or remote work.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Awaitable, Callable

from .budgets import BudgetLedger
from .runner import RunnerError, RunReport, TaskOutput, TaskRunner, _ready
from .schemas import ProjectPlan, ProjectTask


@dataclass(frozen=True)
class TaskReservation:
    cost_usd: float
    runtime_seconds: float

    def __post_init__(self):
        for name, value in (("cost_usd", self.cost_usd), ("runtime_seconds", self.runtime_seconds)):
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise RunnerError(f"{name} must be finite nonnegative numeric, not bool")
        if self.runtime_seconds == 0:
            raise RunnerError("runtime reservation must be positive")


class ConcurrentTaskRunner(TaskRunner):
    """Async ready-wave runner with review barriers and conservative budgets.

    Give this runner exclusive ownership of its ledger during a run. Executors
    receive task copies, not plan-owned mutable objects. A wave is fully settled
    before its dependents or retries can dispatch. Review is required by default.
    """

    def __init__(self, ledger: BudgetLedger,
                 executor: Callable[[ProjectTask], Awaitable[TaskOutput]],
                 reservation: Callable[[ProjectTask], TaskReservation], *,
                 max_parallel: int = 6, max_task_attempts: int = 2,
                 auto_approve: bool = False):
        super().__init__(ledger, executor, max_task_attempts, auto_approve)
        if type(max_parallel) is not int or not 1 <= max_parallel <= 1000:
            raise RunnerError("max_parallel must be integer1..1000")
        if type(max_task_attempts) is not int:
            raise RunnerError("max_task_attempts must be integer")
        limits = ledger.limits
        for name in ('max_iterations', 'max_agent_calls', 'max_runtime_seconds'):
            if type(getattr(limits, name)) is not int or getattr(limits, name) < 1:
                raise RunnerError("ledger limits must be positive integers")
        if type(limits.max_cost_usd) not in (int, float) or not math.isfinite(limits.max_cost_usd) or limits.max_cost_usd < 0:
            raise RunnerError("ledger cost limit must be finite nonnegative")
        self.max_parallel = max_parallel
        self.reservation = reservation
        self._running = False

    def _reserve(self, task, bound):
        state = self.ledger.status()
        if (state.agent_calls_remaining < 1 or not self.ledger.can_afford_call(bound.cost_usd)
                or bound.runtime_seconds > state.runtime_seconds_remaining):
            return False
        # No await between capacity check and conservative charge.
        self.ledger.record_agent_call(bound.cost_usd, note=f"reserved task {task.id}")
        self.ledger.record_runtime(bound.runtime_seconds, note=f"reserved task {task.id}")
        return True

    async def _execute(self, task, bound):
        try:
            output = await asyncio.wait_for(self.executor(task.model_copy(deep=True)), bound.runtime_seconds)
            if not isinstance(output, TaskOutput):
                raise RunnerError("executor must return TaskOutput")
            if (type(output.cost_usd) not in (int, float) or type(output.runtime_seconds) not in (int, float)
                    or not math.isfinite(output.cost_usd) or not math.isfinite(output.runtime_seconds)
                    or output.cost_usd > bound.cost_usd or output.runtime_seconds > bound.runtime_seconds):
                raise RunnerError("executor exceeded its declared reservation")
            return output
        except asyncio.CancelledError:
            raise
        except Exception:
            # Raw exception text can contain credentials or private data.
            return TaskOutput(success=False, failure_reason="executor-failure-or-reservation-breach")

    async def run(self, plan: ProjectPlan) -> RunReport:
        if self._running:
            raise RunnerError("runner already active")
        self._running = True
        children = []
        current = plan.model_copy(deep=True)
        try:
            while True:
                ready = _ready(current)
                if not ready:
                    review = any(t.status == "review" for t in current.tasks)
                    incomplete = any(t.status not in {"completed", "failed"} for t in current.tasks)
                    return self._report(current, "awaiting_review" if review else "blocked_failures" if incomplete or any(t.status == "failed" for t in current.tasks) else "completed")
                wave = []
                blocked_budget = False
                # Validate every chosen bound before creating any child task.
                candidates = [(t, self.reservation(t.model_copy(deep=True))) for t in ready[:self.max_parallel]]
                if any(not isinstance(b, TaskReservation) for _, b in candidates):
                    raise RunnerError("reservation callback must return TaskReservation")
                for task, bound in candidates:
                    if not self._reserve(task, bound):
                        blocked_budget = True
                        break
                    current = self._update(current, task.id, status="running")
                    wave.append((task, bound))
                if not wave:
                    return self._report(current, "budget_exhausted")
                children = [asyncio.create_task(self._execute(t, b)) for t, b in wave]
                outputs = await asyncio.gather(*children)
                children = []
                for (task, _), output in zip(wave, outputs):
                    if output.success:
                        current = self._update(current, task.id, status="completed" if self.auto_approve else "review")
                    else:
                        attempts = task.attempt + 1
                        # Failed attempts are explicit even if retries cannot be funded.
                        current = self._update(current, task.id, status="failed", attempt=attempts)
                        if attempts < self.max_task_attempts:
                            if self.ledger.status().iterations_remaining < 1:
                                blocked_budget = True
                            else:
                                self.ledger.record_iteration(note=f"retry task {task.id}")
                                current = self._update(current, task.id, status="ready")
                if blocked_budget:
                    return self._report(current, "budget_exhausted")
        finally:
            for child in children:
                if not child.done():
                    child.cancel()
            if children:
                await asyncio.gather(*children, return_exceptions=True)
            self._running = False
