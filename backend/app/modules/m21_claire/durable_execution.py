"""Durable execution semantics for Claire.

The in-memory ExecutionOrchestrator proves exact-review binding; this layer
makes it survive crashes and retried deliveries:

* Plans, approvals, per-step states and an append-only audit log persist in
  SQL after every transition.
* Each step executes through BoundedExecutor with the review digest as its
  idempotency fingerprint, so replaying a step after a crash returns the
  recorded result instead of re-running the side effect, and a fingerprint
  mismatch (the reviewed payload changed) refuses to execute.
* Retries are bounded per step with a retryable predicate; exhausting the
  bound fails the step and the plan, never loops forever.
* resume(plan_id) rehydrates a RUNNING/FAILED plan and continues from the
  first non-succeeded step - succeeded steps are never re-executed.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .execution import (
    AttemptsExhausted, BoundedExecutor, ExecutionResult, IdempotencyStore,
)
from .models import (
    ActionRequest, Approval, ExecutionPlan, PlanState, PlanStep, ReviewSnapshot,
    RiskLevel, StepState, utcnow,
)
from .orchestrator import ExecutionOrchestrator, ReviewMismatch
from .policy import ActionPolicy


class Base(DeclarativeBase):
    pass


class PlanRow(Base):
    __tablename__ = "claire_plans"

    plan_id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    goal = sa.Column(sa.Text, nullable=False)
    state = sa.Column(sa.String, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class StepRow(Base):
    __tablename__ = "claire_steps"

    plan_id = sa.Column(sa.String, primary_key=True)
    action_id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    request_json = sa.Column(sa.JSON, nullable=False)
    state = sa.Column(sa.String, nullable=False)
    output_json = sa.Column(sa.JSON, nullable=True)
    error = sa.Column(sa.Text, nullable=True)


class ApprovalRow(Base):
    __tablename__ = "claire_approvals"

    approval_id = sa.Column(sa.String, primary_key=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    plan_id = sa.Column(sa.String, nullable=False, index=True)
    action_id = sa.Column(sa.String, nullable=False)
    review_digest = sa.Column(sa.String, nullable=False)
    approver = sa.Column(sa.String, nullable=False)
    approved_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=True)


class AuditRow(Base):
    __tablename__ = "claire_audit"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    tenant_id = sa.Column(sa.String, nullable=False, default="default", index=True)
    plan_id = sa.Column(sa.String, nullable=False, index=True)
    action_id = sa.Column(sa.String, nullable=True)
    event = sa.Column(sa.String, nullable=False)
    detail_json = sa.Column(sa.JSON, nullable=False, default=dict)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _request_to_json(request: ActionRequest) -> dict[str, Any]:
    return {
        "module": request.module, "action": request.action,
        "parameters": dict(request.parameters), "purpose": request.purpose,
        "risk": request.risk.value, "dependencies": list(request.dependencies),
        "action_id": request.action_id,
    }


def _request_from_json(data: dict[str, Any]) -> ActionRequest:
    return ActionRequest(
        module=data["module"], action=data["action"],
        parameters=data["parameters"], purpose=data["purpose"],
        risk=RiskLevel(data["risk"]), dependencies=tuple(data["dependencies"]),
        action_id=data["action_id"],
    )


class ClaireExecutionRepository:
    """Durable plan/step/approval/audit rows. Engine injected."""

    def __init__(self, engine: sa.engine.Engine, *, tenant_id: str = "default") -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.engine = engine
        self.tenant_id = tenant_id
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    # -- plans -------------------------------------------------------------

    def save_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        with self._session_factory() as session:
            row = session.get(PlanRow, plan.plan_id)
            if row is not None and row.tenant_id != self.tenant_id:
                raise PermissionError("plan belongs to another tenant")
            if row is None:
                row = PlanRow(plan_id=plan.plan_id, tenant_id=self.tenant_id,
                              goal=plan.goal, created_at=_aware(plan.created_at))
                session.add(row)
            row.goal = plan.goal
            row.state = plan.state.value
            for step in plan.steps:
                srow = session.get(StepRow, (plan.plan_id, step.request.action_id))
                if srow is None:
                    srow = StepRow(plan_id=plan.plan_id, action_id=step.request.action_id,
                                   tenant_id=self.tenant_id)
                    session.add(srow)
                srow.request_json = _request_to_json(step.request)
                srow.state = step.state.value
                srow.output_json = step.output if _jsonable(step.output) else repr(step.output)
                srow.error = step.error
            for action_id, approval in plan.approvals.items():
                if session.get(ApprovalRow, approval.approval_id) is None:
                    session.add(ApprovalRow(
                        approval_id=approval.approval_id, tenant_id=self.tenant_id,
                        plan_id=plan.plan_id, action_id=action_id,
                        review_digest=approval.review_digest, approver=approval.approver,
                        approved_at=_aware(approval.approved_at),
                        expires_at=_aware(approval.expires_at),
                    ))
            session.commit()
        return plan

    def load_plan(self, plan_id: str) -> ExecutionPlan | None:
        with self._session_factory() as session:
            row = session.get(PlanRow, plan_id)
            if row is None or row.tenant_id != self.tenant_id:
                return None
            srows = (session.query(StepRow)
                     .filter(StepRow.plan_id == plan_id, StepRow.tenant_id == self.tenant_id)
                     .all())
            arows = (session.query(ApprovalRow)
                     .filter(ApprovalRow.plan_id == plan_id, ApprovalRow.tenant_id == self.tenant_id)
                     .all())
        plan = ExecutionPlan(
            goal=row.goal, plan_id=row.plan_id,
            steps=[PlanStep(request=_request_from_json(s.request_json),
                            state=StepState(s.state), output=s.output_json, error=s.error)
                   for s in srows],
            state=PlanState(row.state), created_at=_aware(row.created_at),
        )
        plan.approvals = {
            a.action_id: Approval(
                approval_id=a.approval_id, review_digest=a.review_digest,
                approver=a.approver, approved_at=_aware(a.approved_at),
                expires_at=_aware(a.expires_at),
            )
            for a in arows
        }
        return plan

    # -- audit ---------------------------------------------------------------

    def audit(self, plan_id: str, event: str, *, action_id: str | None = None,
              detail: dict[str, Any] | None = None) -> None:
        with self._session_factory() as session:
            session.add(AuditRow(
                tenant_id=self.tenant_id, plan_id=plan_id, action_id=action_id,
                event=event, detail_json=detail or {},
                created_at=datetime.now(timezone.utc),
            ))
            session.commit()

    def audit_log(self, plan_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = (session.query(AuditRow)
                    .filter(AuditRow.plan_id == plan_id, AuditRow.tenant_id == self.tenant_id)
                    .order_by(AuditRow.id).all())
            return [
                {"plan_id": r.plan_id, "action_id": r.action_id, "event": r.event,
                 "detail": r.detail_json, "created_at": _aware(r.created_at).isoformat()}
                for r in rows
            ]


def _jsonable(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


class DurableExecutionOrchestrator(ExecutionOrchestrator):
    """Exact-review orchestration with durable, idempotent, bounded steps."""

    def __init__(
        self,
        repo: ClaireExecutionRepository,
        policy: ActionPolicy | None = None,
        clock: Callable[[], datetime] = utcnow,
        *,
        executor: BoundedExecutor | None = None,
        max_attempts: int = 1,
        retryable: Callable[[Exception], bool] | None = None,
    ) -> None:
        super().__init__(policy=policy, clock=clock)
        self.repo = repo
        self.bounded = executor or BoundedExecutor(IdempotencyStore())
        if not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        self.max_attempts = max_attempts
        self.retryable = retryable

    def prepare(self, plan: ExecutionPlan) -> tuple[ReviewSnapshot, ...]:
        reviews = super().prepare(plan)
        self.repo.save_plan(plan)
        self.repo.audit(plan.plan_id, "prepared",
                        detail={"reviews": [r.digest for r in reviews]})
        return reviews

    def approve(self, plan: ExecutionPlan, approval: Approval) -> None:
        super().approve(plan, approval)
        self.repo.save_plan(plan)
        self.repo.audit(plan.plan_id, "approved",
                        action_id=approval.approval_id,
                        detail={"approver": approval.approver})

    def _execute_step(self, plan: ExecutionPlan, step: PlanStep) -> None:
        """Bounded, idempotent execution of one reviewed step."""
        request = step.request
        executor_fn = self._executors.get(request.capability)
        if executor_fn is None:
            from .orchestrator import ExecutorNotRegistered

            raise ExecutorNotRegistered(request.capability)
        fingerprint = self.review_snapshot(plan, request.action_id).digest
        result: ExecutionResult = self.bounded.run(
            key=f"{plan.plan_id}:{request.action_id}",
            fingerprint=fingerprint,
            operation=lambda params: executor_fn(params),
            parameters=request.parameters,
            max_attempts=self.max_attempts,
            retryable=self.retryable,
        )
        step.output = result.value
        self.repo.audit(plan.plan_id, "step_executed", action_id=request.action_id,
                        detail={"attempts": result.attempts, "replayed": result.replayed})

    def execute(self, plan: ExecutionPlan) -> ExecutionPlan:
        if plan.state not in {PlanState.APPROVED, PlanState.AWAITING_REVIEW, PlanState.RUNNING, PlanState.FAILED}:
            raise RuntimeError(f"plan cannot execute from {plan.state.value}")
        plan.state = PlanState.RUNNING
        self.repo.save_plan(plan)
        self.repo.audit(plan.plan_id, "execution_started")
        succeeded: set[str] = {
            s.request.action_id for s in plan.steps if s.state == StepState.SUCCEEDED
        }
        try:
            for step in plan.steps:
                if step.state == StepState.SUCCEEDED:
                    continue  # resume semantics: never re-run a finished step
                request = step.request
                if not set(request.dependencies) <= succeeded:
                    step.state = StepState.SKIPPED
                    step.error = "dependency did not succeed"
                    continue
                decision = self.policy.require_allowed(request)
                if decision.requires_approval:
                    approval = plan.approvals.get(request.action_id)
                    current = self.review_snapshot(plan, request.action_id)
                    if (approval is None or approval.review_digest != current.digest
                            or not approval.valid_at(self.clock())):
                        step.state = StepState.BLOCKED
                        self.repo.save_plan(plan)
                        self.repo.audit(plan.plan_id, "review_mismatch",
                                        action_id=request.action_id)
                        raise ReviewMismatch(
                            f"missing, stale, or mismatched approval for {request.action_id}")
                step.state = StepState.RUNNING
                try:
                    self._execute_step(plan, step)
                except Exception as exc:
                    step.state = StepState.FAILED
                    step.error = str(exc)
                    plan.state = PlanState.FAILED
                    self.repo.save_plan(plan)
                    self.repo.audit(plan.plan_id, "step_failed",
                                    action_id=request.action_id, detail={"error": str(exc)[:400]})
                    raise
                step.state = StepState.SUCCEEDED
                succeeded.add(request.action_id)
                self.repo.save_plan(plan)
        except Exception:
            plan.state = PlanState.FAILED
            self.repo.save_plan(plan)
            raise
        plan.state = PlanState.SUCCEEDED
        self.repo.save_plan(plan)
        self.repo.audit(plan.plan_id, "execution_succeeded")
        return plan

    def resume(self, plan_id: str) -> ExecutionPlan:
        """Crash/retry recovery: rehydrate and continue; succeeded steps and
        recorded idempotency results are replayed, never re-executed."""
        plan = self.repo.load_plan(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        self.repo.audit(plan.plan_id, "resumed")
        return self.execute(plan)
