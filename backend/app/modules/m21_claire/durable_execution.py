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
    AttemptsExhausted, BoundedExecutor, EffectUnknown, ExecutionResult, IdempotencyConflict,
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


class StepEffectRow(Base):
    """Effect journal for durable steps. Written (intent) BEFORE the executor runs; stores no parameters."""
    __tablename__ = "claire_step_effects"

    tenant_id = sa.Column(sa.String, primary_key=True)
    effect_key = sa.Column(sa.String, primary_key=True)
    fingerprint = sa.Column(sa.String, nullable=False)
    state = sa.Column(sa.String, nullable=False)  # intent | committed | unknown
    result_json = sa.Column(sa.JSON, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


def effect_key(plan_id: str, action_id: str) -> str:
    return f"{plan_id}:{action_id}"


class EffectResolutionError(ValueError):
    pass


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

    def __init__(self, engine: sa.engine.Engine, *, tenant_id: str = "default",
                 intent_min_age_seconds: float = 600.0) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if intent_min_age_seconds < 0:
            raise ValueError("intent_min_age_seconds must be >= 0")
        self.intent_min_age_seconds = intent_min_age_seconds
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

    # -- effect journal ------------------------------------------------------

    def effect_claim(self, key: str, fingerprint: str) -> tuple[bool, Any]:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            session.add(StepEffectRow(tenant_id=self.tenant_id, effect_key=key, fingerprint=fingerprint,
                                      state="intent", created_at=now, updated_at=now))
            try:
                session.commit()
                return True, None
            except sa.exc.IntegrityError:
                session.rollback()
        with self._session_factory() as session:
            row = session.get(StepEffectRow, (self.tenant_id, key))
            if row is None:  # raced with an abandon; refuse rather than guess
                raise EffectUnknown("effect state changed during claim")
            if row.fingerprint != fingerprint:
                raise IdempotencyConflict("key was already used for a different reviewed action")
            if row.state == "committed":
                return False, row.result_json
            raise EffectUnknown("a previous execution of this step has no recorded outcome")

    def effect_complete(self, key: str, result: Any) -> None:
        with self._session_factory() as session:
            n = (session.query(StepEffectRow)
                 .filter(StepEffectRow.tenant_id == self.tenant_id, StepEffectRow.effect_key == key,
                         StepEffectRow.state == "intent")
                 .update({"state": "committed", "result_json": result if _jsonable(result) else repr(result),
                          "updated_at": datetime.now(timezone.utc)}))
            if n != 1:
                session.rollback()
                raise KeyError(key)
            session.commit()

    def effect_mark_unknown(self, key: str) -> None:
        with self._session_factory() as session:
            (session.query(StepEffectRow)
             .filter(StepEffectRow.tenant_id == self.tenant_id, StepEffectRow.effect_key == key,
                     StepEffectRow.state == "intent")
             .update({"state": "unknown", "updated_at": datetime.now(timezone.utc)}))
            session.commit()

    def effect_abandon(self, key: str) -> None:
        with self._session_factory() as session:
            (session.query(StepEffectRow)
             .filter(StepEffectRow.tenant_id == self.tenant_id, StepEffectRow.effect_key == key,
                     StepEffectRow.state == "intent").delete())
            session.commit()

    def effect_states(self, plan_id: str) -> dict[str, str]:
        prefix = effect_key(plan_id, "")
        with self._session_factory() as session:
            rows = (session.query(StepEffectRow)
                    .filter(StepEffectRow.tenant_id == self.tenant_id, StepEffectRow.effect_key.like(prefix + "%"))
                    .all())
            return {r.effect_key[len(prefix):]: r.state for r in rows}

    def resolve_effect(self, plan_id: str, action_id: str, outcome: str, result: Any = None, *,
                       confirm_executor_stopped: bool = False) -> None:
        """Owner decision for an effect with no recorded outcome. 'committed' marks it landed (resume replays it,
        never re-runs it); 'absent' deletes the record so resume may run the step.
        FENCE: an 'unknown' row (the executor already reported failure) can be resolved directly. An 'intent' row may
        belong to a LIVE executor, so it is only resolvable when the owner passes confirm_executor_stopped=True AND the
        intent is at least intent_min_age_seconds old. There is no heartbeat, so this is a time-and-owner fence, not
        proof the executor is dead; a long synchronous effect can outlive it."""
        if outcome not in {"committed", "absent"}:
            raise EffectResolutionError("outcome must be committed or absent")
        key = effect_key(plan_id, action_id)
        with self._session_factory() as session:
            row = session.get(StepEffectRow, (self.tenant_id, key))
            if row is None or row.state not in ("intent", "unknown"):
                raise EffectResolutionError("no unresolved effect for that step")
            if row.state == "intent":
                age = (datetime.now(timezone.utc) - _aware(row.updated_at)).total_seconds()
                if not confirm_executor_stopped or age < self.intent_min_age_seconds:
                    raise EffectResolutionError("the step may still be running; confirm it stopped and wait for the fence")
            state, stamp = row.state, row.updated_at
            q = session.query(StepEffectRow).filter(
                StepEffectRow.tenant_id == self.tenant_id, StepEffectRow.effect_key == key,
                StepEffectRow.state == state, StepEffectRow.updated_at == stamp)
            if outcome == "absent":
                n = q.delete(synchronize_session=False)
            else:
                n = q.update({"state": "committed", "result_json": result if _jsonable(result) else repr(result),
                              "updated_at": datetime.now(timezone.utc)}, synchronize_session=False)
            if n != 1:
                session.rollback()
                raise EffectResolutionError("the effect changed while resolving")
            session.commit()
        self.audit(plan_id, "effect_resolved", action_id=action_id, detail={"outcome": outcome})

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


class SqlIdempotencyStore:
    """Durable claim/complete/abandon over the effect journal. claim() commits the intent row BEFORE the executor
    runs, so a crash leaves an intent that blocks re-execution (EffectUnknown) instead of silently re-running.
    A failure after the body begins is kept as 'unknown' (never re-run) unless the executor raised NotExecuted,
    its explicit proof that no side effect began; only then is the row removed and a retry allowed."""

    def __init__(self, repo: "ClaireExecutionRepository") -> None:
        self.repo = repo

    def claim(self, key: str, fingerprint: str) -> tuple[bool, Any]:
        return self.repo.effect_claim(key, fingerprint)

    def complete(self, key: str, result: Any) -> None:
        self.repo.effect_complete(key, result)

    def mark_unknown(self, key: str) -> None:
        self.repo.effect_mark_unknown(key)

    def abandon(self, key: str) -> None:
        self.repo.effect_abandon(key)


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
        if executor is not None and not isinstance(executor.store, SqlIdempotencyStore):
            raise ValueError("a durable orchestrator requires a durable idempotency store")
        self.bounded = executor or BoundedExecutor(SqlIdempotencyStore(repo))
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
            key=effect_key(plan.plan_id, request.action_id),
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
                    step.error = type(exc).__name__  # class name only: exception text can carry secrets
                    plan.state = PlanState.FAILED
                    self.repo.save_plan(plan)
                    if isinstance(exc, EffectUnknown):
                        self.repo.audit(plan.plan_id, "effect_unknown", action_id=request.action_id)
                    self.repo.audit(plan.plan_id, "step_failed",
                                    action_id=request.action_id, detail={"error": type(exc).__name__})
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
