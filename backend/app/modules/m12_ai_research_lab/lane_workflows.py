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

import threading
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
        for count in (input_tokens, output_tokens):
            if type(count) is not int:
                raise ValueError("token counts must be integers")
            if count < 0:
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

    # Durable fenced step claims (duck-typed). The engine REQUIRES all of these for every
    # executor step and fails closed before executing when a store lacks any of them:
    #   claim_step(run_id, step_id) -> Optional[str]     atomic; returns the owner token,
    #                                                    None when a claim already exists
    #   complete_step(run_id, step_id, token, output) -> bool   atomically checks the
    #                                  token, checkpoints the output and drops the claim
    #   mark_unknown(run_id, step_id, token, detail) -> bool    owner-fenced pending -> unknown
    #   release_claim(run_id, step_id, token) -> bool           owner-fenced drop
    #   load_claims(run_id) -> {step_id: (state, detail)}  state "pending" | "unknown"
    #   inspect_claim(run_id, step_id) -> (state, detail, generation) | None
    #   resolve_claim_completed(run_id, step_id, expected_state, expected_gen, output) -> bool
    #   clear_claim_for_retry(run_id, step_id, expected_state, expected_gen) -> bool
    #   takeover_pending(run_id, step_id, expected_gen) -> bool  pending -> unknown, new token+gen
    # Reconcile calls are compare-and-set on the generation the CALLER observed through
    # inspect_claim; the generation changes on every claim state change (ABA-safe).
    # A claim is persisted BEFORE the executor runs. "pending" means in flight OR crashed:
    # the two cannot be told apart without a liveness proof, and no time expiry is used.
    # Owner-fenced calls with a stale token change nothing (a revoked or replaced owner
    # cannot clear, update or checkpoint over a newer claim).


def _is_unknown_outcome(exc: BaseException) -> bool:
    """An executor reports an indeterminate external effect with outcome == 'unknown'
    (ProviderOutcomeUnknown does). Duck-typed so the lane engine keeps no provider import."""
    return getattr(exc, "outcome", None) == "unknown"


class InMemoryStepStateStore:
    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        self._claims: Dict[str, Dict[str, List[str]]] = {}   # [state, detail, token, gen]
        self._claim_lock = threading.Lock()

    def claim_step(self, run_id: str, step_id: str) -> Optional[str]:
        with self._claim_lock:
            run = self._claims.setdefault(run_id, {})
            if step_id in run:
                return None
            token = uuid.uuid4().hex
            run[step_id] = ["pending", "", token, uuid.uuid4().hex]
            return token

    def complete_step(self, run_id: str, step_id: str, token: str, output: Any) -> bool:
        with self._claim_lock:
            row = self._claims.get(run_id, {}).get(step_id)
            if row is None or row[2] != token:
                return False
            self._data.setdefault(run_id, {})[step_id] = output
            del self._claims[run_id][step_id]
            return True

    def mark_unknown(self, run_id: str, step_id: str, token: str, detail: str) -> bool:
        with self._claim_lock:
            row = self._claims.get(run_id, {}).get(step_id)
            if row is None or row[2] != token:
                return False
            row[0], row[1], row[3] = "unknown", str(detail), uuid.uuid4().hex
            return True

    def release_claim(self, run_id: str, step_id: str, token: str) -> bool:
        with self._claim_lock:
            row = self._claims.get(run_id, {}).get(step_id)
            if row is None or row[2] != token:
                return False
            del self._claims[run_id][step_id]
            return True

    def load_claims(self, run_id: str) -> Dict[str, Tuple[str, str]]:
        with self._claim_lock:
            return {k: (v[0], v[1]) for k, v in self._claims.get(run_id, {}).items()}

    def inspect_claim(self, run_id: str, step_id: str) -> Optional[Tuple[str, str, str]]:
        with self._claim_lock:
            row = self._claims.get(run_id, {}).get(step_id)
            return None if row is None else (row[0], row[1], row[3])

    def resolve_claim_completed(self, run_id: str, step_id: str, expected_state: str,
                                expected_gen: str, output: Any) -> bool:
        with self._claim_lock:
            row = self._claims.get(run_id, {}).get(step_id)
            if row is None or row[0] != expected_state or row[3] != expected_gen:
                return False
            self._data.setdefault(run_id, {})[step_id] = output
            del self._claims[run_id][step_id]
            return True

    def clear_claim_for_retry(self, run_id: str, step_id: str, expected_state: str,
                              expected_gen: str) -> bool:
        with self._claim_lock:
            row = self._claims.get(run_id, {}).get(step_id)
            if row is None or row[0] != expected_state or row[3] != expected_gen:
                return False
            del self._claims[run_id][step_id]
            return True

    def takeover_pending(self, run_id: str, step_id: str, expected_gen: str) -> bool:
        with self._claim_lock:
            row = self._claims.get(run_id, {}).get(step_id)
            if row is None or row[0] != "pending" or row[3] != expected_gen:
                return False
            row[0], row[1], row[2], row[3] = ("unknown", "pending claim taken over; earlier owner revoked",
                                            uuid.uuid4().hex, uuid.uuid4().hex)
            return True

    def load_completed(self, run_id: str) -> Dict[str, Any]:
        return dict(self._data.get(run_id, {}))

    def save_completed(self, run_id: str, step_id: str, output: Any) -> None:
        self._data.setdefault(run_id, {})[step_id] = output

    def clear_run(self, run_id: str) -> None:
        self._data.pop(run_id, None)
        with self._claim_lock:
            self._claims.pop(run_id, None)


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


@dataclass(frozen=True)
class ClaimView:
    run_id: str
    step_id: str
    state: str          # "pending" (in flight or crashed, indistinguishable) | "unknown"
    detail: str
    generation: str     # opaque; changes on every claim state change


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
        # Claims are honored whatever `resume` says: restarting a run is not
        # permission to repeat a possibly-incurred external effect. A store that
        # cannot load claims fails closed per step below, before any execution.
        claims: Dict[str, Tuple[str, str]] = (
            dict(self._state.load_claims(run_id)) if self._supports_claims() else {}
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

            if not self._supports_claims():
                return self._fail(
                    run_id, workflow, records, journal, completed, total_cost,
                    step.step_id,
                    "state store lacks durable step-claim support; step not executed",
                )

            if step.step_id in claims:
                return self._blocked_by_claim(
                    run_id, workflow, step, records, journal, completed, total_cost,
                    claims[step.step_id],
                )

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
                    # Fail closed: a priced model under any spend limit needs a
                    # nonzero cost estimate, otherwise the hold is zero and the
                    # step runs effectively unmetered. Free models and unlimited
                    # policies are unaffected. Refused before claim and effect.
                    pol = self._ledger.policy
                    limited = (pol.daily_limit_micro is not None
                               or pol.monthly_limit_micro is not None
                               or pol.per_run_limit_micro is not None)
                    priced = (model.cost_per_1k_input_micro > 0
                              or model.cost_per_1k_output_micro > 0)
                    if limited and priced and decision.estimated_cost_micro <= 0:
                        return self._fail(
                            run_id, workflow, records, journal, completed, total_cost,
                            step.step_id,
                            "budget reservation refused: priced model under a spend limit "
                            "has no cost estimate (set estimated_input_tokens/estimated_output_tokens)",
                        )
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
            # Persist the claim BEFORE the effect. Any failure here, or losing the
            # race to another engine, means the executor is never called.
            try:
                token = self._state.claim_step(run_id, step.step_id)
            except Exception as exc:
                self._release_budget_hold_quiet(budget_key)
                return self._fail(
                    run_id, workflow, records, journal, completed, total_cost,
                    step.step_id, f"step claim could not be persisted; not executed: {type(exc).__name__}",
                )
            if token is None:
                self._release_budget_hold_quiet(budget_key)
                return self._blocked_by_claim(
                    run_id, workflow, step, records, journal, completed, total_cost,
                    ("pending", "claimed by another execution"),
                )

            attempts_allowed = 1 + step.max_retries
            attempt = 0
            last_error: Optional[str] = None
            output: Any = None
            unknown_detail: Optional[str] = None
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
                    if _is_unknown_outcome(exc):
                        unknown_detail = last_error
                        break
                    if attempt < attempts_allowed:
                        journal.append(
                            JournalEvent("retry", step.step_id, last_error)
                        )
            else:
                # Exhausted attempts: ordinary determinate failure. Drop the claim so a
                # rerun may retry; if that write fails the claim stays and blocks.
                incurred = ctx.cost_micro()
                book_failed = False
                if budget_key is not None and self._ledger is not None:
                    if incurred > 0:
                        try:
                            self._ledger.record_incurred(budget_key, incurred)
                        except Exception as exc:
                            # Consumed usage could not be booked: keep the claim so
                            # a rerun is blocked (no unpaid-looking repeat paid call).
                            book_failed = True
                            last_error = (f"{last_error}; incurred {incurred} micro NOT booked "
                                          f"({type(exc).__name__}); claim kept")
                    else:
                        self._ledger.release(budget_key)
                if not book_failed:
                    # Ordinary determinate failure: drop the claim so a rerun may retry;
                    # if that write fails the claim stays and blocks.
                    try:
                        self._state.release_claim(run_id, step.step_id, token)
                    except Exception:
                        pass
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
                        cost_micro=incurred,
                        attempts=attempt,
                        input_hash=sha256_hex(canonical_json(step.params)),
                        error=last_error,
                    )
                )
                return self._fail(
                    run_id, workflow, records, journal, completed, total_cost,
                    step.step_id, last_error or "unknown error",
                )

            if unknown_detail is not None:
                # Indeterminate external effect: no retry, not success, not failure.
                # The budget reservation stays held (spend may have happened and is
                # not booked), the step is not checkpointed, and a durable marker
                # claim (already persisted before execution) blocks a later rerun.
                try:
                    self._state.mark_unknown(run_id, step.step_id, token, unknown_detail)
                except Exception:
                    pass  # the pending claim written before execution still blocks reruns
                journal.append(
                    JournalEvent("step_outcome_unknown", step.step_id, unknown_detail)
                )
                records.append(
                    StepRecord(
                        step_id=step.step_id,
                        kind=step.kind,
                        status="unknown_outcome",
                        model_id=model.model_id if model else None,
                        input_tokens=ctx.input_tokens,
                        output_tokens=ctx.output_tokens,
                        cost_micro=0,
                        attempts=attempt,
                        input_hash=sha256_hex(canonical_json(step.params)),
                        error=unknown_detail,
                    )
                )
                return self._fail(
                    run_id, workflow, records, journal, completed, total_cost,
                    step.step_id, "outcome unknown: " + unknown_detail,
                )

            cost = ctx.cost_micro()
            if budget_key is not None and self._ledger is not None:
                try:
                    self._ledger.commit(budget_key, cost)
                except Exception as exc:
                    # Usage already consumed: book it as incurred (limits not
                    # enforced). The claim stays, so a rerun is still blocked.
                    booked = True
                    try:
                        self._ledger.record_incurred(budget_key, cost)
                    except Exception:
                        booked = False
                    return self._fail(
                        run_id, workflow, records, journal, completed, total_cost,
                        step.step_id, f"budget commit failed: {exc} (incurred {cost} micro " + ("booked" if booked else "NOT booked") + ")",
                    )
            # Atomic fenced checkpoint: only the current claim owner may record the
            # output. A revoked or replaced owner records nothing.
            if not self._state.complete_step(run_id, step.step_id, token, output):
                journal.append(
                    JournalEvent("step_outcome_unknown", step.step_id,
                                 "claim revoked or replaced before checkpoint; output not recorded")
                )
                records.append(
                    StepRecord(
                        step_id=step.step_id, kind=step.kind, status="unknown_outcome",
                        model_id=model.model_id if model else None,
                        input_tokens=ctx.input_tokens, output_tokens=ctx.output_tokens,
                        cost_micro=cost, attempts=attempt,
                        input_hash=sha256_hex(canonical_json(step.params)),
                        error="claim revoked or replaced before checkpoint; effect happened, output not recorded",
                    )
                )
                return self._fail(
                    run_id, workflow, records, journal, completed, total_cost,
                    step.step_id,
                    "outcome unknown: claim revoked or replaced before checkpoint; output not recorded",
                )
            completed[step.step_id] = output
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

    def _supports_claims(self) -> bool:
        return all(
            callable(getattr(self._state, name, None))
            for name in ("claim_step", "complete_step", "mark_unknown", "load_claims",
                         "release_claim", "inspect_claim", "resolve_claim_completed",
                         "clear_claim_for_retry", "takeover_pending")
        )

    def _release_budget_hold_quiet(self, budget_key: Optional[str]) -> None:
        if budget_key is not None and self._ledger is not None:
            self._ledger.release(budget_key)

    def _blocked_by_claim(self, run_id, workflow, step, records, journal, completed,
                          total_cost, claim: Tuple[str, str]) -> WorkflowRunResult:
        state, detail = claim
        view = self.inspect_claim(run_id, step.step_id) if self._supports_claims() else None
        gen_note = f" [claim_generation={view.generation}]" if view is not None else ""
        why = (
            "earlier attempt outcome unknown" if state == "unknown"
            else "earlier or concurrent execution has no recorded outcome (interrupted, crashed or in flight)"
        )
        journal.append(JournalEvent("step_outcome_unknown", step.step_id, f"{why}; not re-executed"))
        records.append(
            StepRecord(
                step_id=step.step_id, kind=step.kind, status="unknown_outcome",
                input_hash=sha256_hex(canonical_json(step.params)),
                error=why + "; reconcile explicitly (mark completed or authorize retry)" + gen_note,
            )
        )
        return self._fail(
            run_id, workflow, records, journal, completed, total_cost, step.step_id,
            "outcome unknown: " + why + "; not re-executed until explicitly reconciled" + gen_note,
        )

    def _claim_state_error(self, run_id: str, step_id: str) -> ValueError:
        if not self._supports_claims():
            return ValueError("state store does not support step claims")
        claim = self._state.load_claims(run_id).get(step_id)
        if claim is None:
            return ValueError(f"step {step_id} has no unresolved claim for run {run_id}")
        if claim[0] == "pending":
            return ValueError(
                f"step {step_id} has a pending claim: it may be executing right now or may "
                "have crashed (these cannot be told apart); ordinary reconciliation is "
                "refused, use take_over_pending_claim with its explicit acknowledgement"
            )
        return ValueError(
            f"step {step_id} claim is in state {claim[0]} or changed since it was inspected; "
            "re-inspect and retry with the current generation"
        )

    def _release_hold(self, run_id: str, step_id: str) -> None:
        if self._ledger is not None:
            # explicit reconcile path (generation-checked, acknowledged): may drop a
            # hold left by a crashed ledger instance
            self._ledger.release(self._budget_key(run_id, step_id), takeover=True)

    def inspect_claim(self, run_id: str, step_id: str) -> Optional["ClaimView"]:
        """Read-only view of the current claim for a caller that wants to reconcile. The
        generation is opaque and changes on every claim state change; pass it back as
        expected_generation. Reading it grants nothing: each reconcile call is a
        compare-and-set that fails if the claim changed since this view."""
        if not self._supports_claims():
            raise ValueError("state store does not support step claims")
        row = self._state.inspect_claim(run_id, step_id)
        return None if row is None else ClaimView(run_id, step_id, row[0], row[1], row[2])

    @staticmethod
    def _need_generation(expected_generation: Any) -> str:
        if not isinstance(expected_generation, str) or not expected_generation:
            raise ValueError("expected_generation (from inspect_claim) is required")
        return expected_generation

    def take_over_pending_claim(
        self, run_id: str, step_id: str, *, expected_generation: str,
        acknowledge_inflight_effect_may_still_complete: bool,
    ) -> None:
        """Separate, explicit takeover of a PENDING claim (in flight or crashed; not
        distinguishable). It revokes the earlier owner's token so a late checkpoint,
        release or update by that owner changes nothing, and moves the claim to
        'unknown' so ordinary reconciliation can follow. It does NOT prove whether
        the effect occurred or will still complete."""
        if acknowledge_inflight_effect_may_still_complete is not True:
            raise ValueError("takeover requires acknowledge_inflight_effect_may_still_complete=True")
        if not self._supports_claims():
            raise ValueError("state store does not support step claims")
        gen = self._need_generation(expected_generation)
        if not self._state.takeover_pending(run_id, step_id, gen):
            raise self._claim_state_error(run_id, step_id)

    def resolve_unknown_as_completed(
        self, run_id: str, step_id: str, *, expected_generation: str, output: Any,
        release_budget_hold: bool = False,
    ) -> None:
        """Reconciliation of an UNKNOWN claim: the caller asserts the step took effect
        and supplies its output (None is a legitimate output). Refused for a pending
        claim. The possibly-incurred spend is NOT booked; release_budget_hold only
        frees the hold."""
        if not self._supports_claims():
            raise ValueError("state store does not support step claims")
        gen = self._need_generation(expected_generation)
        if not self._state.resolve_claim_completed(run_id, step_id, "unknown", gen, output):
            raise self._claim_state_error(run_id, step_id)
        if release_budget_hold:
            self._release_hold(run_id, step_id)

    def authorize_retry_after_reconciliation(
        self, run_id: str, step_id: str, *, expected_generation: str,
        confirm_effect_did_not_occur: bool, release_budget_hold: bool,
    ) -> None:
        """Deliberate decision to run an UNKNOWN step again. Both flags must be passed
        explicitly and be True: the caller asserts the earlier effect did not occur
        (or accepts a duplicate) and that the budget hold is released (without
        booking the earlier possibly-incurred spend). Refused for a pending claim."""
        if confirm_effect_did_not_occur is not True or release_budget_hold is not True:
            raise ValueError(
                "retry after reconciliation requires confirm_effect_did_not_occur=True "
                "and release_budget_hold=True"
            )
        if not self._supports_claims():
            raise ValueError("state store does not support step claims")
        gen = self._need_generation(expected_generation)
        if not self._state.clear_claim_for_retry(run_id, step_id, "unknown", gen):
            raise self._claim_state_error(run_id, step_id)
        self._release_hold(run_id, step_id)

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
