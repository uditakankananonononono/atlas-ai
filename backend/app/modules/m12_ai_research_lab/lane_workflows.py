"""Declarative multi-step workflow engine.

Workflows are validated (duplicate ids, unknown deps, cycles) and executed
in deterministic topological order. Executors are an injected registry so
the engine itself has no I/O. Optional router + budget ledger integration
routes each step's model and reserves/commits cost around execution.
Progress is checkpointed after every step through an injectable state
store so a crashed run resumes from completed steps without repeating
their side effects.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from .lane_budgets import BudgetLedger
from .lane_models import ModelProfile, StepRecord, TaskRequirements, canonical_json, sha256_hex
from .lane_routing import ModelRouter


class WorkflowValidationError(ValueError):
    pass


class WorkflowExecutionError(RuntimeError):
    def __init__(self, run_id: str, step_id: str, message: str):
        self.run_id = run_id
        self.step_id = step_id
        super().__init__(f"run {run_id} failed at step {step_id}: {message}")


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: Tuple[str, ...] = ()
    max_retries: int = 2  # additional attempts after the first
    route_requirements: Optional[TaskRequirements] = None

    def __post_init__(self) -> None:
        if not self.step_id:
            raise WorkflowValidationError("step_id must be non-empty")
        if not self.kind:
            raise WorkflowValidationError(f"step {self.step_id}: kind must be non-empty")
        if self.max_retries < 0:
            raise WorkflowValidationError(
                f"step {self.step_id}: max_retries must be >= 0"
            )


@dataclass(frozen=True)
class Workflow:
    name: str
    steps: Tuple[WorkflowStep, ...]

    def validate(self) -> Tuple[WorkflowStep, ...]:
        """Return steps in deterministic topological order, or raise."""
        if not self.name:
            raise WorkflowValidationError("workflow name must be non-empty")
        if not self.steps:
            raise WorkflowValidationError("workflow needs at least one step")
        ids = [s.step_id for s in self.steps]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise WorkflowValidationError(f"duplicate step ids: {', '.join(dupes)}")
        by_id = {s.step_id: s for s in self.steps}
        for s in self.steps:
            for dep in s.depends_on:
                if dep not in by_id:
                    raise WorkflowValidationError(
                        f"step {s.step_id} depends on unknown step {dep}"
                    )
                if dep == s.step_id:
                    raise WorkflowValidationError(
                        f"step {s.step_id} depends on itself"
                    )
        # Kahn's algorithm with lexicographic tie-break for determinism.
        indegree: Dict[str, int] = {s.step_id: 0 for s in self.steps}
        dependents: Dict[str, List[str]] = {s.step_id: [] for s in self.steps}
        for s in self.steps:
            for dep in s.depends_on:
                indegree[s.step_id] += 1
                dependents[dep].append(s.step_id)
        ready = sorted(i for i, d in indegree.items() if d == 0)
        order: List[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for nxt in dependents[current]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
            ready.sort()
        if len(order) != len(self.steps):
            remaining = sorted(i for i, d in indegree.items() if d > 0)
            raise WorkflowValidationError(
                f"dependency cycle among steps: {', '.join(remaining)}"
            )
        return tuple(by_id[i] for i in order)


@dataclass
class StepContext:
    """Passed to every executor. record_usage() is how LLM executors report
    token consumption; the engine turns it into exact micro-dollar cost via
    the routed model."""

    run_id: str
    step_id: str
    seed: Optional[int]
    workflow_params: Dict[str, Any]
    dependency_outputs: Dict[str, Any]
    model: Optional[ModelProfile] = None
    input_tokens: int = 0
    output_tokens: int = 0

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts must be non-negative")
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def cost_micro(self) -> int:
        if self.model is None:
            return 0
        return self.model.estimate_cost_micro(self.input_tokens, self.output_tokens)


class StepStateStore(Protocol):
    """Checkpoint seam: completed step outputs per run."""

    def load_completed(self, run_id: str) -> Dict[str, Any]: ...
    def save_completed(self, run_id: str, step_id: str, output: Any) -> None: ...
    def clear_run(self, run_id: str) -> None: ...


class InMemoryStepStateStore:
    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}

    def load_completed(self, run_id: str) -> Dict[str, Any]:
        return dict(self._data.get(run_id, {}))

    def save_completed(self, run_id: str, step_id: str, output: Any) -> None:
        self._data.setdefault(run_id, {})[step_id] = output

    def clear_run(self, run_id: str) -> None:
        self._data.pop(run_id, None)


@dataclass(frozen=True)
class JournalEvent:
    event: str  # step_started|step_completed|step_failed|step_skipped|retry
    step_id: str
    detail: str = ""


@dataclass(frozen=True)
class WorkflowRunResult:
    run_id: str
    workflow_name: str
    status: str  # completed | failed
    steps: Tuple[StepRecord, ...]
    outputs: Dict[str, Any]
    journal: Tuple[JournalEvent, ...]
    total_cost_micro: int
    failed_step_id: Optional[str] = None


Executor = Callable[[Dict[str, Any], StepContext], Any]


class WorkflowEngine:
    def __init__(
        self,
        executors: Dict[str, Executor],
        router: Optional[ModelRouter] = None,
        ledger: Optional[BudgetLedger] = None,
        state_store: Optional[StepStateStore] = None,
    ) -> None:
        if not executors:
            raise ValueError("engine needs at least one executor")
        self._executors = dict(executors)
        self._router = router
        self._ledger = ledger
        self._state = state_store or InMemoryStepStateStore()

    def register_executor(self, kind: str, fn: Executor) -> None:
        if not kind:
            raise ValueError("kind must be non-empty")
        self._executors[kind] = fn

    def executor_for(self, kind: str) -> Executor:
        try:
            return self._executors[kind]
        except KeyError:
            raise KeyError(f"no executor registered for kind '{kind}'") from None

    def executor_kinds(self) -> List[str]:
        return sorted(self._executors)

    def _budget_key(self, run_id: str, step_id: str) -> str:
        return f"{run_id}:{step_id}"

    def run(
        self,
        workflow: Workflow,
        run_id: Optional[str] = None,
        seed: Optional[int] = None,
        workflow_params: Optional[Dict[str, Any]] = None,
        resume: bool = True,
    ) -> WorkflowRunResult:
        ordered = workflow.validate()
        run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        workflow_params = dict(workflow_params or {})
        completed: Dict[str, Any] = (
            self._state.load_completed(run_id) if resume else {}
        )
        journal: List[JournalEvent] = []
        records: List[StepRecord] = []
        total_cost = 0

        for step in ordered:
            if step.step_id in completed:
                journal.append(
                    JournalEvent("step_skipped", step.step_id, "already completed")
                )
                records.append(
                    StepRecord(
                        step_id=step.step_id,
                        kind=step.kind,
                        status="skipped",
                        output_hash=sha256_hex(canonical_json(completed[step.step_id]))
                        if _jsonable(completed[step.step_id]) else None,
                    )
                )
                continue

            executor = self._executors.get(step.kind)
            if executor is None:
                return self._fail(
                    run_id, workflow, records, journal, completed, total_cost,
                    step.step_id, f"no executor registered for kind '{step.kind}'",
                )

            # Route + budget for steps that declare model requirements.
            model: Optional[ModelProfile] = None
            budget_key: Optional[str] = None
            if step.route_requirements is not None:
                if self._router is None:
                    return self._fail(
                        run_id, workflow, records, journal, completed, total_cost,
                        step.step_id,
                        "step declares route_requirements but engine has no router",
                    )
                try:
                    decision = self._router.route(step.route_requirements)
                except Exception as exc:
                    return self._fail(
                        run_id, workflow, records, journal, completed, total_cost,
                        step.step_id, f"routing failed: {exc}",
                    )
                model = decision.chosen
                if self._ledger is not None:
                    budget_key = self._budget_key(run_id, step.step_id)
                    try:
                        self._ledger.reserve(budget_key, decision.estimated_cost_micro)
                    except Exception as exc:
                        return self._fail(
                            run_id, workflow, records, journal, completed, total_cost,
                            step.step_id, f"budget reservation failed: {exc}",
                        )

            ctx = StepContext(
                run_id=run_id,
                step_id=step.step_id,
                seed=seed,
                workflow_params=workflow_params,
                dependency_outputs={d: completed[d] for d in step.depends_on},
                model=model,
            )
            attempts_allowed = 1 + step.max_retries
            attempt = 0
            last_error: Optional[str] = None
            output: Any = None
            while attempt < attempts_allowed:
                attempt += 1
                journal.append(
                    JournalEvent("step_started", step.step_id, f"attempt {attempt}")
                )
                try:
                    output = executor(step.params, ctx)
                    break
                except Exception as exc:  # executor failure is data, not a crash
                    last_error = f"{type(exc).__name__}: {exc}"
                    if attempt < attempts_allowed:
                        journal.append(
                            JournalEvent("retry", step.step_id, last_error)
                        )
            else:
                # Exhausted attempts.
                if budget_key is not None and self._ledger is not None:
                    self._ledger.release(budget_key)
                journal.append(
                    JournalEvent("step_failed", step.step_id, last_error or "unknown")
                )
                records.append(
                    StepRecord(
                        step_id=step.step_id,
                        kind=step.kind,
                        status="failed",
                        model_id=model.model_id if model else None,
                        input_tokens=ctx.input_tokens,
                        output_tokens=ctx.output_tokens,
                        cost_micro=0,
                        attempts=attempt,
                        input_hash=sha256_hex(canonical_json(step.params)),
                        error=last_error,
                    )
                )
                return self._fail(
                    run_id, workflow, records, journal, completed, total_cost,
                    step.step_id, last_error or "unknown error",
                )

            cost = ctx.cost_micro()
            if budget_key is not None and self._ledger is not None:
                try:
                    self._ledger.commit(budget_key, cost)
                except Exception as exc:
                    # Do not spend what cannot be booked: fail the run and
                    # do not checkpoint the step, so resume re-executes it.
                    return self._fail(
                        run_id, workflow, records, journal, completed, total_cost,
                        step.step_id, f"budget commit failed: {exc}",
                    )
            completed[step.step_id] = output
            self._state.save_completed(run_id, step.step_id, output)
            total_cost += cost
            journal.append(
                JournalEvent("step_completed", step.step_id, f"cost {cost} micro")
            )
            records.append(
                StepRecord(
                    step_id=step.step_id,
                    kind=step.kind,
                    status="completed",
                    model_id=model.model_id if model else None,
                    input_tokens=ctx.input_tokens,
                    output_tokens=ctx.output_tokens,
                    cost_micro=cost,
                    attempts=attempt,
                    input_hash=sha256_hex(canonical_json(step.params)),
                    output_hash=sha256_hex(canonical_json(output))
                    if _jsonable(output) else None,
                )
            )

        return WorkflowRunResult(
            run_id=run_id,
            workflow_name=workflow.name,
            status="completed",
            steps=tuple(records),
            outputs=completed,
            journal=tuple(journal),
            total_cost_micro=total_cost,
        )

    def _fail(
        self,
        run_id: str,
        workflow: Workflow,
        records: List[StepRecord],
        journal: List[JournalEvent],
        completed: Dict[str, Any],
        total_cost: int,
        step_id: str,
        message: str,
    ) -> WorkflowRunResult:
        journal.append(JournalEvent("step_failed", step_id, message))
        return WorkflowRunResult(
            run_id=run_id,
            workflow_name=workflow.name,
            status="failed",
            steps=tuple(records),
            outputs=completed,
            journal=tuple(journal),
            total_cost_micro=total_cost,
            failed_step_id=step_id,
        )


def _jsonable(value: Any) -> bool:
    try:
        canonical_json(value)
        return True
    except (TypeError, ValueError):
        return False
