"""FastAPI router for the M12 AI Research Lab.

Exported as `build_router(service)`; the integrator mounts it (suggested
prefix: /api/v1/research-lab). Service wiring stays outside this file so
the router is testable in isolation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .lane_budgets import BudgetExceeded
from .lane_models import EvalCase, ModelProfile, TaskRequirements, micro_to_usd
from .lane_routing import NoEligibleModelError
from .lane_service import AIResearchLabService
from .lane_workflows import Workflow, WorkflowStep, WorkflowValidationError


class ModelRegisterRequest(BaseModel):
    model_id: str
    provider: str
    display_name: str
    cost_per_1k_input_micro: int = Field(ge=0)
    cost_per_1k_output_micro: int = Field(ge=0)
    capabilities: List[str] = ["chat"]
    max_context_tokens: int = Field(default=8192, gt=0)
    quality_tier: int = Field(default=3, ge=1, le=5)
    latency_tier: int = Field(default=2, ge=1, le=3)
    enabled: bool = True


class RoutePreviewRequest(BaseModel):
    required_capabilities: List[str] = ["chat"]
    estimated_input_tokens: int = Field(default=0, ge=0)
    estimated_output_tokens: int = Field(default=0, ge=0)
    min_quality_tier: int = Field(default=1, ge=1, le=5)
    max_cost_micro: Optional[int] = Field(default=None, gt=0)
    prefer_low_latency: bool = False


class WorkflowStepIn(BaseModel):
    step_id: str
    kind: str
    params: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    max_retries: int = Field(default=2, ge=0)
    route_requirements: Optional[RoutePreviewRequest] = None


class WorkflowRunRequest(BaseModel):
    name: str
    steps: List[WorkflowStepIn]
    run_id: Optional[str] = None
    seed: Optional[int] = None
    workflow_params: Dict[str, Any] = Field(default_factory=dict)
    code_version: str = "unknown"
    resume: bool = True


class EvalCaseIn(BaseModel):
    case_id: str
    input: Any
    checks: List[Dict[str, Any]]


class EvalRunRequest(BaseModel):
    cases: List[EvalCaseIn]
    eval_id: Optional[str] = None
    runner_kind: str  # executor kind from the workflow engine registry


def _model_dict(m: ModelProfile) -> Dict[str, Any]:
    return {
        "model_id": m.model_id,
        "provider": m.provider,
        "display_name": m.display_name,
        "cost_per_1k_input_micro": m.cost_per_1k_input_micro,
        "cost_per_1k_output_micro": m.cost_per_1k_output_micro,
        "capabilities": sorted(m.capabilities),
        "max_context_tokens": m.max_context_tokens,
        "quality_tier": m.quality_tier,
        "latency_tier": m.latency_tier,
        "enabled": m.enabled,
    }


def _requirements(body: RoutePreviewRequest) -> TaskRequirements:
    return TaskRequirements(
        required_capabilities=frozenset(body.required_capabilities),
        estimated_input_tokens=body.estimated_input_tokens,
        estimated_output_tokens=body.estimated_output_tokens,
        min_quality_tier=body.min_quality_tier,
        max_cost_micro=body.max_cost_micro,
        prefer_low_latency=body.prefer_low_latency,
    )


def build_router(service: AIResearchLabService) -> APIRouter:
    router = APIRouter(tags=["m12-ai-research-lab"])

    @router.get("/models")
    def list_models(include_disabled: bool = False) -> Dict[str, Any]:
        return {
            "models": [
                _model_dict(m)
                for m in service.list_models(include_disabled=include_disabled)
            ]
        }

    @router.post("/models", status_code=201)
    def register_model(body: ModelRegisterRequest) -> Dict[str, Any]:
        try:
            profile = ModelProfile(
                model_id=body.model_id,
                provider=body.provider,
                display_name=body.display_name,
                cost_per_1k_input_micro=body.cost_per_1k_input_micro,
                cost_per_1k_output_micro=body.cost_per_1k_output_micro,
                capabilities=frozenset(body.capabilities),
                max_context_tokens=body.max_context_tokens,
                quality_tier=body.quality_tier,
                latency_tier=body.latency_tier,
                enabled=body.enabled,
            )
            service.router.register(profile)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"registered": profile.model_id}

    @router.post("/route")
    def route_preview(body: RoutePreviewRequest) -> Dict[str, Any]:
        try:
            decision = service.route_preview(_requirements(body))
        except NoEligibleModelError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "no eligible model",
                    "verdicts": [
                        {"model_id": v.model_id, "eligible": v.eligible,
                         "reasons": list(v.reasons)}
                        for v in exc.verdicts
                    ],
                },
            ) from exc
        return {
            "chosen": _model_dict(decision.chosen),
            "estimated_cost_micro": decision.estimated_cost_micro,
            "estimated_cost_usd": micro_to_usd(decision.estimated_cost_micro),
            "reasons": list(decision.reasons),
            "verdicts": [
                {"model_id": v.model_id, "eligible": v.eligible,
                 "reasons": list(v.reasons), "score": v.score}
                for v in decision.verdicts
            ],
        }

    @router.get("/budget")
    def budget_status() -> Dict[str, Any]:
        return service.budget_status().to_dict()

    @router.post("/workflows/run", status_code=200)
    def run_workflow(body: WorkflowRunRequest) -> Dict[str, Any]:
        try:
            steps = tuple(
                WorkflowStep(
                    step_id=s.step_id,
                    kind=s.kind,
                    params=s.params,
                    depends_on=tuple(s.depends_on),
                    max_retries=s.max_retries,
                    route_requirements=_requirements(s.route_requirements)
                    if s.route_requirements else None,
                )
                for s in body.steps
            )
            workflow = Workflow(name=body.name, steps=steps)
            workflow.validate()
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            result, manifest = service.run_workflow(
                workflow,
                run_id=body.run_id,
                seed=body.seed,
                workflow_params=body.workflow_params,
                code_version=body.code_version,
                resume=body.resume,
            )
        except BudgetExceeded as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc
        return {
            "run_id": result.run_id,
            "status": result.status,
            "failed_step_id": result.failed_step_id,
            "total_cost_micro": result.total_cost_micro,
            "total_cost_usd": micro_to_usd(result.total_cost_micro),
            "steps": [
                {
                    "step_id": s.step_id, "kind": s.kind, "status": s.status,
                    "model_id": s.model_id, "attempts": s.attempts,
                    "cost_micro": s.cost_micro, "error": s.error,
                }
                for s in result.steps
            ],
            "journal": [
                {"event": e.event, "step_id": e.step_id, "detail": e.detail}
                for e in result.journal
            ],
            "manifest_digest": manifest.digest(),
        }

    @router.post("/evals/run", status_code=200)
    def run_eval(body: EvalRunRequest) -> Dict[str, Any]:
        try:
            executor = service.engine.executor_for(body.runner_kind)
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            cases = tuple(
                EvalCase(case_id=c.case_id, input=c.input, checks=tuple(c.checks))
                for c in body.cases
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        def runner(case_input: Any) -> Any:
            from .lane_workflows import StepContext
            ctx = StepContext(
                run_id=f"eval-{body.eval_id or 'adhoc'}",
                step_id="eval",
                seed=None,
                workflow_params={},
                dependency_outputs={},
            )
            return executor(case_input if isinstance(case_input, dict) else {"input": case_input}, ctx)

        report = service.evaluate(cases, runner, eval_id=body.eval_id)
        return report.to_dict()

    @router.get("/evals/{eval_id}")
    def get_eval(eval_id: str) -> Dict[str, Any]:
        payload = service.get_eval_report(eval_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"unknown eval_id {eval_id}")
        return payload

    @router.get("/runs")
    def list_runs(limit: int = 100) -> Dict[str, Any]:
        return {"run_ids": service.list_runs(limit=limit)}

    @router.get("/runs/{run_id}/diff/{other_run_id}")
    def diff_runs(run_id: str, other_run_id: str) -> Dict[str, Any]:
        from .lane_analytics import diff_manifest_payloads

        before = service.get_run_manifest(run_id)
        after = service.get_run_manifest(other_run_id)
        if before is None:
            raise HTTPException(status_code=404, detail=f"unknown run_id {run_id}")
        if after is None:
            raise HTTPException(status_code=404, detail=f"unknown run_id {other_run_id}")
        d = diff_manifest_payloads(before, after)
        return {
            "run_id_before": d.run_id_before,
            "run_id_after": d.run_id_after,
            "identical": d.identical,
            "config_changed": d.config_changed,
            "input_changed": d.input_changed,
            "seed_changed": d.seed_changed,
            "code_version_changed": d.code_version_changed,
            "status_change": list(d.status_change),
            "cost_delta_micro": d.cost_delta_micro,
            "step_diffs": [
                {"step_id": s.step_id, "change": s.change,
                 "changed_fields": list(s.changed_fields)}
                for s in d.step_diffs
            ],
        }

    @router.get("/runs/{run_id}")
    def get_run(run_id: str) -> Dict[str, Any]:
        payload = service.get_run_manifest(run_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"unknown run_id {run_id}")
        return payload

    return router
