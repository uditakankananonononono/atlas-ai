from __future__ import annotations
from typing import Callable
from .acceptance import evaluate
from .engine import Engine
from .goals import Claim, GoalStore

EngineFactory = Callable[[Claim], Engine]


class Worker:
    """Runs one claimed goal. No blanket exception handler: an unexpected tool or engine bug
    propagates, leaves the lease to expire, and the goal is retried up to max_attempts and then
    marked failed(attempts_exhausted). Only the declared model/tool failure classes are contained."""

    def __init__(self, store: GoalStore, engine_factory: EngineFactory, worker_id: str):
        self.store, self.engine_factory, self.worker_id = store, engine_factory, worker_id

    async def run_once(self) -> str | None:
        claim = self.store.claim(self.worker_id)
        if claim is None:
            return None
        report = await self.engine_factory(claim).run(claim.purpose)
        dump = report.model_dump()
        if report.stop_reason in {"model_unavailable", "model_invalid_output"}:
            self.store.settle(claim, "blocked", blocker=report.stop_reason, report=dump, verdict=None)
        elif report.stop_reason == "step_limit":
            self.store.settle(claim, "exhausted", blocker="step_limit", report=dump, verdict=None)
        elif report.stop_reason == "cancelled":
            self.store.settle(claim, "cancelled", blocker=None, report=dump, verdict=None)
        else:
            verdict = evaluate(claim.criteria, report)
            self.store.settle(claim, "completed" if verdict.accepted else "not_accepted",
                              blocker=None if verdict.accepted else "acceptance_not_met", report=dump, verdict=verdict.model_dump())
        return claim.goal_id
