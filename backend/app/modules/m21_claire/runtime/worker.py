from __future__ import annotations
from typing import Any, Callable
from .acceptance import evaluate
from .engine import Engine
from .gates import Principal
from .goals import Claim, GoalStore

EngineFactory = Callable[[Claim], Engine]


class Worker:
    """Runs one claimed goal. No blanket exception handler: an unexpected tool or engine bug
    propagates, leaves the lease to expire, and the goal is retried up to max_attempts and then
    marked failed(attempts_exhausted). Only the declared model/tool failure classes are contained."""

    def __init__(self, store: GoalStore, engine_factory: EngineFactory, worker_id: str):
        self.store, self.engine_factory, self.worker_id = store, engine_factory, worker_id
        self.last_outcome: str | None = None  # the status the store accepted, 'lease_lost' (nothing settled), or None

    async def run_once(self) -> str | None:
        claim = self.store.claim(self.worker_id)
        if claim is None:
            return None
        principal = Principal(claim.tenant_id, claim.actor_id, claim.goal_id, claim.lease_token)
        engine = self.engine_factory(claim)
        if engine.tools.call_timeout >= self.store.lease_seconds:
            # A call allowed to block past the lease defeats renewal: refuse to run at all.
            self._settle(claim, "blocked", blocker="timeout_not_below_lease", report={}, verdict=None)
            return claim.goal_id
        if engine.tools.journal is self.store and await engine.tools.reconcile_pending(claim.goal_id):
            # An earlier attempt left an effect with no recorded outcome: run nothing new until it is resolved.
            self._settle(claim, "awaiting_review", blocker="effect_unknown", report={}, verdict=None)
            return claim.goal_id
        report = await engine.run(claim.purpose, principal=principal, lease=lambda: self.store.renew(claim))
        dump = report.model_dump()
        if report.stop_reason == "lease_lost" or any(r.reason == "lease_lost" for r in report.refusals):
            self.last_outcome = "lease_lost"  # another worker owns it, or the lease expired: settle nothing
            return claim.goal_id
        if engine.tools.journal is self.store and engine.tools.blocking_effects(claim.goal_id):
            # Some write ended without a recorded outcome (timeout, error, crash): never report such a goal complete.
            self._settle(claim, "awaiting_review", blocker="effect_unknown", report=dump, verdict=None)
        elif any(r.reason == "effect_unknown" for r in report.refusals):
            self._settle(claim, "awaiting_review", blocker="effect_unknown", report=dump, verdict=None)
        elif any(r.reason == "approval_required" for r in report.refusals):
            # A gated action was refused: the goal waits for the owner; it can never be completed from this run.
            self._settle(claim, "awaiting_review", blocker="approval_required", report=dump, verdict=None)
        elif report.stop_reason in {"model_unavailable", "model_invalid_output"}:
            self._settle(claim, "blocked", blocker=report.stop_reason, report=dump, verdict=None)
        elif report.stop_reason in {"step_limit", "replan_limit"}:
            self._settle(claim, "exhausted", blocker=report.stop_reason, report=dump, verdict=None)
        elif report.stop_reason == "cancelled":
            self._settle(claim, "cancelled", blocker=None, report=dump, verdict=None)
        else:
            verdict = evaluate(claim.criteria, report)
            self._settle(claim, "completed" if verdict.accepted else "not_accepted",
                         blocker=None if verdict.accepted else "acceptance_not_met", report=dump, verdict=verdict.model_dump())
        return claim.goal_id

    def _settle(self, claim: Claim, status: str, **kw: Any) -> None:
        """last_outcome reflects what the store actually did: the settled status, or lease_lost if settle was refused."""
        self.last_outcome = status if self.store.settle(claim, status, **kw) else "lease_lost"
