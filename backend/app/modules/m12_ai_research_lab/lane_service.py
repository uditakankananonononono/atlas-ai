"""Service facade for the M12 AI Research Lab.

Ties the router, budget ledger, workflow engine, eval harness, and store
into one object the HTTP layer (or other modules) can drive. Every
mutating operation is budget-checked, journaled, and persisted; readbacks
come from the store, not from memory.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from .lane_budgets import BudgetLedger
from .lane_evaluation import run_evaluation
from .lane_models import (
    BudgetStatus,
    EvalCase,
    EvalReport,
    ModelProfile,
    RouteDecision,
    RunManifest,
    TaskRequirements,
)
from .lane_routing import ModelRouter
from .lane_runs import build_manifest, manifest_file_payload
from .lane_store import SQLiteLabStore
from .lane_workflows import Workflow, WorkflowEngine, WorkflowRunResult


class AIResearchLabService:
    def __init__(
        self,
        router: ModelRouter,
        ledger: BudgetLedger,
        engine: WorkflowEngine,
        store: Optional[SQLiteLabStore] = None,
    ) -> None:
        self.router = router
        self.ledger = ledger
        self.engine = engine
        self.store = store or SQLiteLabStore(":memory:")

    # ---- models & routing -------------------------------------------------

    def list_models(self, include_disabled: bool = False) -> List[ModelProfile]:
        return self.router.list_models(include_disabled=include_disabled)

    def route_preview(self, requirements: TaskRequirements) -> RouteDecision:
        """Dry-run routing: picks a model and explains, reserves nothing."""
        return self.router.route(requirements)

    # ---- budgets -----------------------------------------------------------

    def budget_status(self) -> BudgetStatus:
        return self.ledger.status()

    def spend_by_run(self, run_id: str) -> int:
        return self.store.spend_by_run(run_id)

    # ---- workflows + manifests ----------------------------------------------

    def run_workflow(
        self,
        workflow: Workflow,
        run_id: Optional[str] = None,
        seed: Optional[int] = None,
        workflow_params: Optional[Dict[str, Any]] = None,
        code_version: str = "unknown",
        resume: bool = True,
    ) -> Tuple[WorkflowRunResult, RunManifest]:
        """Execute a workflow end to end and persist an auditable manifest."""
        result = self.engine.run(
            workflow,
            run_id=run_id,
            seed=seed,
            workflow_params=workflow_params,
            resume=resume,
        )
        manifest = build_manifest(
            run_id=result.run_id,
            workflow_name=result.workflow_name,
            config={
                "steps": [
                    {
                        "step_id": s.step_id,
                        "kind": s.kind,
                        "params": s.params,
                        "depends_on": list(s.depends_on),
                        "max_retries": s.max_retries,
                    }
                    for s in workflow.steps
                ],
                "workflow_params": dict(workflow_params or {}),
            },
            run_input={
                "workflow": workflow.name,
                "params": dict(workflow_params or {}),
            },
            code_version=code_version,
            seed=seed,
            steps=result.steps,
            status=result.status,
            total_cost_micro=result.total_cost_micro,
        )
        self.store.save_manifest(result.run_id, manifest_file_payload(manifest))
        return result, manifest

    def get_run_manifest(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.store.load_manifest(run_id)

    def list_runs(self, limit: int = 100) -> List[str]:
        return self.store.list_manifests(limit=limit)

    # ---- evaluation ------------------------------------------------------------

    def evaluate(
        self,
        cases: Tuple[EvalCase, ...] | List[EvalCase],
        runner: Callable[[Any], Any],
        eval_id: Optional[str] = None,
    ) -> EvalReport:
        report = run_evaluation(cases, runner, eval_id=eval_id)
        self.store.save_eval_report(report.eval_id, report.to_dict())
        return report

    def get_eval_report(self, eval_id: str) -> Optional[Dict[str, Any]]:
        return self.store.load_eval_report(eval_id)


def build_default_service(db_path: str = ":memory:") -> AIResearchLabService:
    """Convenience wiring for local use and for the HTTP layer's default.

    Ships with no models registered: the platform registers real provider
    profiles at startup. An empty registry makes route_preview raise
    NoEligibleModelError, which the HTTP layer surfaces as 422.
    """
    from .lane_budgets import BudgetLedger
    from .lane_models import BudgetPolicy
    from .lane_routing import ModelRouter
    from .lane_workflows import WorkflowEngine

    store = SQLiteLabStore(db_path)
    router = ModelRouter()
    ledger = BudgetLedger(BudgetPolicy(), store=store)
    engine = WorkflowEngine({"echo": lambda params, ctx: params},
                            router=router, ledger=ledger, state_store=store)
    return AIResearchLabService(router=router, ledger=ledger, engine=engine, store=store)
