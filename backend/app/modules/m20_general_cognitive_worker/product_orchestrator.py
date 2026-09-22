"""Goal-first product orchestration for the General Cognitive Worker (M20).

The contract, in order:

1. A goal is registered together with the sources it may draw on.
2. A plan is accepted only when every step cites at least one of those
   sources (a "cited plan" - uncited work cannot enter the pipeline).
3. Execution is gated on a Module 0 (Human Approval Center) request;
   nothing runs while the request is pending, rejected or expired.
4. Execution state is read back through the execution-truth ledger, so
   planned, simulated, externally executed and independently verified
   work never blur together, and claims of real execution need evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Mapping

from .execution_truth import execution_truth_ledger
from .safety import ApprovalGate
from .schemas import (
    MODULE_ID,
    ApprovalGateDecision,
    ApprovalGateRequest,
    Risk,
    new_id,
    utcnow,
)

RISK_ORDER = {Risk.READ: 0, Risk.REVERSIBLE: 1, Risk.EXTERNAL: 2, Risk.IRREVERSIBLE: 3}

# An executor runs one plan step and reports what actually happened. It must
# return a mapping with a `state` from the execution-truth vocabulary;
# `externally_executed` and `independently_verified` additionally require
# `evidence_ids`, and `independently_verified` requires a `verifier`. The
# ledger enforces this again at readback time.
StepExecutor = Callable[["PlanStep", dict[str, Any]], Mapping[str, Any]]


class OrchestrationConflictError(RuntimeError):
    """Raised when a second approval or a replayed execution is attempted."""


@dataclass
class OrchestratedSource:
    id: str
    uri: str
    note: str = ""


@dataclass
class PlanStep:
    id: str
    title: str
    action_type: str
    citations: list[str]
    risk: Risk = Risk.REVERSIBLE
    detail: str = ""


@dataclass
class StepExecution:
    step_id: str
    title: str
    action_type: str
    state: str = "planned"
    evidence_ids: list[str] = field(default_factory=list)
    verifier: str | None = None
    detail: str = ""
    error: str | None = None


@dataclass
class OrchestratedGoal:
    id: str
    tenant_id: str
    statement: str
    sources: dict[str, OrchestratedSource]
    status: str = "registered"
    steps: list[PlanStep] = field(default_factory=list)
    approval_id: str | None = None
    executions: dict[str, StepExecution] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: utcnow().isoformat())


def _simulation_executor(step: "PlanStep", goal: dict[str, Any]) -> Mapping[str, Any]:
    """Default executor: rehearses the step without any external effect."""
    return {
        "state": "simulated",
        "detail": f"no executor registered for {step.action_type!r}; simulated only",
    }


class ProductOrchestrator:
    """One tenant's goal -> cited plan -> approval -> execution pipeline."""

    def __init__(
        self,
        tenant_id: str,
        *,
        approval_gate: ApprovalGate,
        executors: dict[str, StepExecutor] | None = None,
        approval_ttl_seconds: int = 3600,
    ) -> None:
        self.tenant_id = tenant_id
        self.gate = approval_gate
        self.executors: dict[str, StepExecutor] = dict(executors or {})
        self.approval_ttl_seconds = approval_ttl_seconds
        self.goals: dict[str, OrchestratedGoal] = {}

    # -- 1. goal + sources -------------------------------------------------

    def register_goal(self, *, statement: str, sources: list[dict[str, str]]) -> OrchestratedGoal:
        statement = statement.strip()
        if len(statement) < 3:
            raise ValueError("goal statement must be at least 3 characters")
        if not sources:
            raise ValueError("a goal needs at least one source before it can be planned")
        registered: dict[str, OrchestratedSource] = {}
        for raw in sources:
            uri = str(raw.get("uri", "")).strip()
            if not uri:
                raise ValueError("every source needs a uri")
            source = OrchestratedSource(id=new_id(), uri=uri, note=str(raw.get("note", "")))
            registered[source.id] = source
        goal = OrchestratedGoal(id=new_id(), tenant_id=self.tenant_id, statement=statement, sources=registered)
        self.goals[goal.id] = goal
        return goal

    # -- 2. cited plan ------------------------------------------------------

    def build_plan(self, goal_id: str, steps: list[dict[str, Any]]) -> OrchestratedGoal:
        goal = self._goal(goal_id)
        if goal.approval_id is not None:
            raise OrchestrationConflictError("plan is locked once an approval request exists")
        if not steps:
            raise ValueError("a plan needs at least one step")
        planned: list[PlanStep] = []
        seen: set[str] = set()
        for raw in steps:
            title = str(raw.get("title", "")).strip()
            action_type = str(raw.get("action_type", "")).strip()
            citations = [str(c) for c in raw.get("citations", [])]
            if not title:
                raise ValueError("every plan step needs a title")
            if not action_type:
                raise ValueError(f"plan step {title!r} needs an action_type")
            if not citations:
                raise ValueError(f"plan step {title!r} needs at least one source citation")
            unknown = [c for c in citations if c not in goal.sources]
            if unknown:
                raise ValueError(f"plan step {title!r} cites unregistered sources: {unknown}")
            risk = raw.get("risk", Risk.REVERSIBLE)
            risk = risk if isinstance(risk, Risk) else Risk(str(risk))
            step = PlanStep(
                id=new_id(), title=title, action_type=action_type,
                citations=citations, risk=risk, detail=str(raw.get("detail", "")),
            )
            if step.id in seen:
                raise ValueError("duplicate plan step id")
            seen.add(step.id)
            planned.append(step)
        goal.steps = planned
        goal.executions = {
            step.id: StepExecution(step_id=step.id, title=step.title, action_type=step.action_type)
            for step in planned
        }
        goal.status = "planned"
        return goal

    # -- 3. approval request -------------------------------------------------

    def request_approval(self, goal_id: str) -> dict[str, Any]:
        goal = self._goal(goal_id)
        if not goal.steps:
            raise ValueError("build a cited plan before requesting approval")
        if goal.approval_id is not None:
            if self.gate.decision(goal.approval_id) == ApprovalGateDecision.PENDING:
                raise OrchestrationConflictError("an approval request for this goal is already pending")
        risk = max((step.risk for step in goal.steps), key=lambda r: RISK_ORDER[r])
        request = ApprovalGateRequest(
            action_type="execute_product_plan",
            summary=f"Execute plan for goal: {goal.statement}",
            risk=risk,
            expires_at=utcnow() + timedelta(seconds=self.approval_ttl_seconds),
            payload={
                "goal_id": goal.id,
                "tenant_id": self.tenant_id,
                "steps": [
                    {
                        "step_id": step.id,
                        "title": step.title,
                        "action_type": step.action_type,
                        "risk": step.risk.value,
                        "citations": [
                            {"source_id": c, "uri": goal.sources[c].uri} for c in step.citations
                        ],
                    }
                    for step in goal.steps
                ],
            },
        )
        goal.approval_id = self.gate.request(request)
        goal.status = "waiting_approval"
        return {"goal_id": goal.id, "approval_id": goal.approval_id}

    # -- 4. execution + readback ---------------------------------------------

    def execute(self, goal_id: str, *, approval_id: str) -> dict[str, Any]:
        goal = self._goal(goal_id)
        if goal.approval_id is None or approval_id != goal.approval_id:
            raise PermissionError("execution requires this goal's own approval request")
        decision = self.gate.decision(approval_id)
        if decision != ApprovalGateDecision.APPROVED:
            raise PermissionError(f"plan execution is not approved (decision: {decision.value})")
        if goal.status == "executed":
            raise OrchestrationConflictError("this approved plan was already executed; re-plan for another run")
        failures = 0
        for step in goal.steps:
            record = goal.executions[step.id]
            executor = self.executors.get(step.action_type, _simulation_executor)
            try:
                outcome = dict(executor(step, {"goal_id": goal.id, "tenant_id": self.tenant_id}))
                state = str(outcome.get("state", ""))
                # Validate the claim against the execution-truth vocabulary
                # before anything is recorded.
                execution_truth_ledger([{
                    "id": step.id,
                    "claim": step.title,
                    "state": state,
                    "evidence_ids": outcome.get("evidence_ids", []),
                    "verifier": outcome.get("verifier"),
                }])
            except Exception as exc:  # executor failure or dishonest state claim
                record.error = str(exc)
                failures += 1
                continue
            record.state = state
            record.evidence_ids = [str(e) for e in outcome.get("evidence_ids", [])]
            record.verifier = outcome.get("verifier")
            record.detail = str(outcome.get("detail", ""))
        goal.status = "failed" if failures else "executed"
        return {"goal_id": goal.id, "status": goal.status, "failed_steps": failures}

    def execution_state(self, goal_id: str) -> dict[str, Any]:
        """Readback contract: the goal's execution-truth ledger plus context."""
        goal = self._goal(goal_id)
        items = [
            {
                "id": record.step_id,
                "claim": record.title,
                "state": record.state,
                "evidence_ids": record.evidence_ids,
                "verifier": record.verifier,
                "source_module": "m20_product_orchestrator",
            }
            for record in goal.executions.values()
        ]
        ledger = execution_truth_ledger(items)
        return {
            "goal_id": goal.id,
            "tenant_id": goal.tenant_id,
            "statement": goal.statement,
            "status": goal.status,
            "approval_id": goal.approval_id,
            "approval_decision": (
                self.gate.decision(goal.approval_id).value if goal.approval_id else None
            ),
            "errors": {
                record.step_id: record.error
                for record in goal.executions.values()
                if record.error
            },
            "ledger": ledger,
        }

    # -- views ----------------------------------------------------------------

    def describe(self, goal_id: str) -> dict[str, Any]:
        goal = self._goal(goal_id)
        return {
            "id": goal.id,
            "tenant_id": goal.tenant_id,
            "statement": goal.statement,
            "status": goal.status,
            "created_at": goal.created_at,
            "sources": [
                {"id": s.id, "uri": s.uri, "note": s.note} for s in goal.sources.values()
            ],
            "steps": [
                {
                    "id": step.id,
                    "title": step.title,
                    "action_type": step.action_type,
                    "risk": step.risk.value,
                    "citations": step.citations,
                    "detail": step.detail,
                }
                for step in goal.steps
            ],
            "approval_id": goal.approval_id,
        }

    def _goal(self, goal_id: str) -> OrchestratedGoal:
        try:
            goal = self.goals[goal_id]
        except KeyError:
            raise KeyError(f"unknown goal: {goal_id}") from None
        if goal.tenant_id != self.tenant_id:
            raise KeyError(f"unknown goal: {goal_id}")
        return goal


__all__ = [
    "MODULE_ID",
    "OrchestrationConflictError",
    "OrchestratedGoal",
    "OrchestratedSource",
    "PlanStep",
    "ProductOrchestrator",
    "StepExecution",
]
