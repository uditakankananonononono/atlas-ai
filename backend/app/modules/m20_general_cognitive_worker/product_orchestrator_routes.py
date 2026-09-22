"""Authenticated HTTP surface for goal-first product orchestration (M20).

Mounted under /api/v1/product-orchestrator by the integrator. All domain
behavior lives in product_orchestrator.py; this file only translates
between HTTP and the service, and scopes every goal to the caller's tenant.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.context import TenantContext, require_tenant

from .agi_service import ModuleZeroGCWApprovalGate
from .product_orchestrator import OrchestrationConflictError, ProductOrchestrator
from .schemas import Risk

router = APIRouter(prefix="/product-orchestrator", tags=["m20_product_orchestrator"])
_orchestrators: dict[str, ProductOrchestrator] = {}


def get_orchestrator(tenant: TenantContext = Depends(require_tenant)) -> ProductOrchestrator:
    """FastAPI dependency: the tenant's orchestrator, gated on Module 0."""
    if tenant.tenant_id not in _orchestrators:
        _orchestrators[tenant.tenant_id] = ProductOrchestrator(
            tenant.tenant_id,
            approval_gate=ModuleZeroGCWApprovalGate(tenant.tenant_id),
        )
    return _orchestrators[tenant.tenant_id]


class SourceIn(BaseModel):
    uri: str = Field(min_length=1)
    note: str = ""


class GoalIn(BaseModel):
    statement: str = Field(min_length=3, max_length=2000)
    sources: list[SourceIn] = Field(min_length=1)


class StepIn(BaseModel):
    title: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    citations: list[str] = Field(min_length=1)
    risk: Risk = Risk.REVERSIBLE
    detail: str = ""


class PlanIn(BaseModel):
    steps: list[StepIn] = Field(min_length=1)


class ExecutionIn(BaseModel):
    approval_id: str = Field(min_length=1)


def _translate(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error).strip("'"))
    if isinstance(error, OrchestrationConflictError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, PermissionError):
        return HTTPException(status_code=403, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.post("/goals", status_code=201)
def register_goal(body: GoalIn, orchestrator: ProductOrchestrator = Depends(get_orchestrator)) -> Any:
    try:
        goal = orchestrator.register_goal(
            statement=body.statement,
            sources=[s.model_dump() for s in body.sources],
        )
    except (KeyError, OrchestrationConflictError, PermissionError, ValueError) as exc:
        raise _translate(exc) from exc
    return orchestrator.describe(goal.id)


@router.get("/goals/{goal_id}")
def get_goal(goal_id: str, orchestrator: ProductOrchestrator = Depends(get_orchestrator)) -> Any:
    try:
        return orchestrator.describe(goal_id)
    except KeyError as exc:
        raise _translate(exc) from exc


@router.post("/goals/{goal_id}/plan", status_code=201)
def build_plan(goal_id: str, body: PlanIn, orchestrator: ProductOrchestrator = Depends(get_orchestrator)) -> Any:
    try:
        goal = orchestrator.build_plan(goal_id, [s.model_dump() for s in body.steps])
    except (KeyError, OrchestrationConflictError, PermissionError, ValueError) as exc:
        raise _translate(exc) from exc
    return orchestrator.describe(goal.id)


@router.post("/goals/{goal_id}/approval-requests", status_code=201)
def request_approval(goal_id: str, orchestrator: ProductOrchestrator = Depends(get_orchestrator)) -> Any:
    try:
        return orchestrator.request_approval(goal_id)
    except (KeyError, OrchestrationConflictError, PermissionError, ValueError) as exc:
        raise _translate(exc) from exc


@router.post("/goals/{goal_id}/executions")
def execute_plan(goal_id: str, body: ExecutionIn, orchestrator: ProductOrchestrator = Depends(get_orchestrator)) -> Any:
    try:
        return orchestrator.execute(goal_id, approval_id=body.approval_id)
    except (KeyError, OrchestrationConflictError, PermissionError, ValueError) as exc:
        raise _translate(exc) from exc


@router.get("/goals/{goal_id}/execution-state")
def execution_state(goal_id: str, orchestrator: ProductOrchestrator = Depends(get_orchestrator)) -> Any:
    try:
        return orchestrator.execution_state(goal_id)
    except KeyError as exc:
        raise _translate(exc) from exc
