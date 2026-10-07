"""Mounted HTTP surface for the durable GCW runtime.

Separate router from routes.py so the integrator can reconcile the newer
registration commits without conflicts. Mounted at /api/modules/20/runtime;
bind with bind_runtime().
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from app.auth.context import TenantContext,require_tenant
from app.auth.environment import insecure_development_auth_enabled
from pydantic import BaseModel, Field

from .runtime import GCWRuntime
from .schemas import Budget
from .sandbox import SandboxViolation

router = APIRouter(prefix="/api/modules/20/runtime", tags=["m20_runtime"])

_runtime: GCWRuntime | None = None  # explicit insecure local test binding
_runtimes: dict[str, GCWRuntime] = {}


def bind_runtime(runtime: GCWRuntime, *, tenant_id: str | None = None) -> None:
    global _runtime
    owner=runtime.repo.tenant_id if tenant_id is None else tenant_id
    if not owner or owner != runtime.repo.tenant_id:
        raise ValueError("runtime binding must match repository tenant")
    if any(k!=owner and r is runtime for k,r in _runtimes.items()):
        raise ValueError("runtime instance already bound to another tenant")
    _runtimes[owner]=runtime
    _runtime=runtime


def get_runtime(tenant: TenantContext = Depends(require_tenant)) -> GCWRuntime:
    if tenant.tenant_id == "local" and not insecure_development_auth_enabled():
        raise HTTPException(403,"local is reserved for insecure development, not an authenticated tenant")
    runtime=_runtimes.get(tenant.tenant_id)
    if tenant.tenant_id == "local" and insecure_development_auth_enabled():
        runtime=_runtime
    if runtime is None:
        raise HTTPException(status_code=503, detail="GCW runtime not bound for authenticated tenant")
    if not insecure_development_auth_enabled() and runtime.repo.tenant_id!=tenant.tenant_id:
        raise HTTPException(503,"runtime repository owner mismatch")
    return runtime


def _task_dict(context) -> dict[str, Any]:
    data = context.model_dump(mode="json")
    data["task_id"] = context.id
    return data


class GoalRequest(BaseModel):
    goal: str = Field(min_length=1)
    importance: int = Field(default=3, ge=1, le=5)
    deadline: datetime | None = None
    run_immediately: bool = True


class StepRequest(BaseModel):
    quantum_seconds: float = Field(default=5.0, gt=0, le=300)
    max_ticks: int = Field(default=10, ge=1, le=100)


class SelectToolRequest(BaseModel):
    description: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class SandboxRunRequest(BaseModel):
    project_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    timeout_seconds: int | None = Field(default=None, ge=1, le=120)
    allowed_hosts: list[str] = Field(default_factory=list)


@router.post("/tasks", status_code=201)
def submit_task(request: GoalRequest, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    context = runtime.submit_goal(
        request.goal, importance=request.importance,
        deadline=request.deadline, run_immediately=request.run_immediately,
    )
    return _task_dict(context)


@router.get("/tasks")
def list_tasks( runtime: Any = Depends(get_runtime)) -> list[dict[str, Any]]:
    return [_task_dict(c) for c in runtime.list_tasks()]


@router.get("/tasks/{task_id}")
def get_task(task_id: str, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    context = runtime.get_task(task_id)
    if context is None:
        raise HTTPException(status_code=404, detail="unknown task")
    return _task_dict(context)


@router.post("/tasks/{task_id}/step")
def step_task(task_id: str, request: StepRequest, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    if runtime.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="unknown task")
    context = runtime.run_task(task_id, max_ticks=request.max_ticks,
                               budget=Budget(seconds=request.quantum_seconds), yield_on_boundary=True)
    return _task_dict(context)


@router.post("/step")
def step_once(request: StepRequest, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    report = runtime.step(
        quantum_seconds=request.quantum_seconds, max_ticks=request.max_ticks,
    )
    return vars(report)


@router.get("/tasks/{task_id}/decision")
def decision(task_id: str, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    artifact = runtime.decision_artifact(task_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="unknown task")
    return artifact.as_dict()


@router.get("/tasks/{task_id}/mcts")
def mcts(task_id: str, simulations: int = 32, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    if simulations < 1 or simulations > 512:
        raise HTTPException(status_code=422, detail="simulations must be 1..512")
    result = runtime.run_mcts(task_id, max_simulations=simulations)
    if result is None:
        raise HTTPException(status_code=404, detail="unknown task")
    return result.as_dict()


@router.post("/tasks/{task_id}/close")
def close_task(task_id: str, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    result = runtime.close(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="unknown task")
    return result


@router.post("/tools/select")
def select_tool(request: SelectToolRequest, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    return runtime.select_tool(request.description, context=request.context).as_dict()


@router.post("/sandbox/run")
def sandbox_run(request: SandboxRunRequest, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    try:
        result = runtime.sandbox.run_python(
            request.project_id, request.code,
            timeout_seconds=request.timeout_seconds,
            allowed_hosts=request.allowed_hosts or None,
        )
    except SandboxViolation as violation:
        raise HTTPException(status_code=403, detail=violation.reasons)
    return result.as_dict()


@router.get("/memory/facts")
def facts( runtime: Any = Depends(get_runtime)) -> list[dict[str, Any]]:
    return [f.model_dump(mode="json") for f in runtime.repo.list_facts()]


@router.get("/memory/episodes")
def episodes(task_id: str | None = None, runtime: Any = Depends(get_runtime)) -> list[dict[str, Any]]:
    return [e.model_dump(mode="json") for e in runtime.repo.list_episodes(task_id=task_id)]


@router.get("/retrospectives")
def retrospectives(task_id: str | None = None, runtime: Any = Depends(get_runtime)) -> list[dict[str, Any]]:
    return [r.model_dump(mode="json") for r in runtime.repo.list_retrospectives(task_id=task_id)]


@router.get("/calibration")
def calibration( runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    return {
        "claims": len(runtime.calibration.claims),
        "resolved": sum(1 for c in runtime.calibration.claims.values() if c.resolved),
        "curve": runtime.calibration.calibration_curve(),
        "calibration_error": runtime.calibration.calibration_error(),
    }


@router.get("/methods")
def methods(status: str | None = None, runtime: Any = Depends(get_runtime)) -> list[dict[str, Any]]:
    out = []
    for method, status_value in runtime.repo.list_methods(status=status):
        data = method.model_dump(mode="json")
        data["review_status"] = runtime.planner.method_status(method.name)
        data["review_hash"] = runtime.planner.method_review_hash(method)
        out.append(data)
    return out


class MethodReviewIn(BaseModel):
    expected_hash: str = Field(min_length=64, max_length=64)


@router.post("/methods/{name}/activate")
def activate_method(name: str, body: MethodReviewIn, runtime: Any = Depends(get_runtime)) -> dict[str, Any]:
    try:
        if not runtime.planner.activate_method(name, expected_hash=body.expected_hash):
            raise HTTPException(status_code=404, detail="unknown method")
    except PermissionError as exc:
        raise HTTPException(409,str(exc)) from exc
    return {"name": name, "review_status": "active"}


class RiskRegisterCreateRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    risks: list[dict[str, Any]] = Field(min_length=1, max_length=100)


class RiskRegisterRevisionRequest(BaseModel):
    expected_revision: int = Field(ge=1, strict=True)
    risks: list[dict[str, Any]] = Field(min_length=1, max_length=100)


@router.post("/risk-registers", status_code=201)
def create_risk_register(request: RiskRegisterCreateRequest, runtime: GCWRuntime = Depends(get_runtime)):
    try:
        return runtime.risk_registers.create(goal=request.goal, risks=request.risks)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/risk-registers")
def list_risk_registers(limit: int = 50, runtime: GCWRuntime = Depends(get_runtime)):
    try:
        return runtime.risk_registers.list(limit=limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/risk-registers/{identifier}")
def get_risk_register(identifier: str, runtime: GCWRuntime = Depends(get_runtime)):
    result = runtime.risk_registers.get(identifier)
    if result is None: raise HTTPException(404, "register not found")
    return result


@router.get("/risk-registers/{identifier}/history")
def risk_register_history(identifier: str, runtime: GCWRuntime = Depends(get_runtime)):
    if runtime.risk_registers.get(identifier) is None: raise HTTPException(404, "register not found")
    return runtime.risk_registers.history(identifier)


@router.post("/risk-registers/{identifier}/revise")
def revise_risk_register(identifier: str, request: RiskRegisterRevisionRequest, runtime: GCWRuntime = Depends(get_runtime)):
    try:
        return runtime.risk_registers.revise(identifier, expected_revision=request.expected_revision, risks=request.risks)
    except KeyError:
        raise HTTPException(404, "register not found")
    except ValueError as exc:
        raise HTTPException(409 if str(exc).startswith('revision conflict') else 422, str(exc))


@router.get('/risk-registers/{identifier}/compare')
def compare_risk_register(identifier: str, from_revision: int, to_revision: int, runtime: GCWRuntime = Depends(get_runtime)):
    try:
        return runtime.risk_registers.compare(identifier, from_revision=from_revision, to_revision=to_revision)
    except KeyError:
        raise HTTPException(404, 'register revision not found')
    except ValueError as exc:
        raise HTTPException(422, str(exc))


class RiskControlPatchRequest(BaseModel):
    expected_revision: int = Field(ge=1, strict=True)
    changes: dict[str, Any]


@router.patch('/risk-registers/{identifier}/risks/{risk_id}')
def patch_risk_control(identifier: str, risk_id: str, request: RiskControlPatchRequest,
                       runtime: GCWRuntime = Depends(get_runtime)):
    try:
        return runtime.risk_registers.patch_risk(identifier, risk_id,
            expected_revision=request.expected_revision, changes=request.changes)
    except KeyError:
        raise HTTPException(404, 'register or risk not found')
    except ValueError as exc:
        raise HTTPException(409 if str(exc).startswith('revision conflict') else 422, str(exc))


class TaskContextInputRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    source: str = Field(min_length=1, max_length=200)
    reference: str = Field(min_length=1, max_length=200)


@router.post('/tasks/{task_id}/context', status_code=201)
def add_task_context(task_id: str, request: TaskContextInputRequest,
                     runtime: GCWRuntime = Depends(get_runtime)):
    try:
        return runtime.add_task_context(task_id, text=request.text, source=request.source,
                                        reference=request.reference)
    except KeyError:
        raise HTTPException(404, 'task not found')
    except ValueError as exc:
        raise HTTPException(409 if str(exc).startswith('context conflict') else 422, str(exc))


class TaskSchedulePatchRequest(BaseModel):
    importance: int | None = Field(default=None, ge=1, le=5, strict=True)
    deadline: datetime | None = None


@router.patch('/tasks/{task_id}/schedule')
def update_task_schedule(task_id: str, request: TaskSchedulePatchRequest,
                         runtime: GCWRuntime = Depends(get_runtime)):
    try:
        result = runtime.update_task_schedule(task_id, changes=request.model_dump(exclude_unset=True))
        return _task_dict(result)
    except KeyError:
        raise HTTPException(404, 'task not found')
    except ValueError as exc:
        raise HTTPException(409 if str(exc).startswith('schedule conflict') else 422, str(exc))


@router.get('/tasks/{task_id}/evidence')
def task_execution_evidence(task_id: str, limit: int = 50,
                            runtime: GCWRuntime = Depends(get_runtime)):
    try:
        return runtime.task_evidence(task_id, limit=limit)
    except KeyError:
        raise HTTPException(404, 'task not found')
    except ValueError as exc:
        raise HTTPException(422, str(exc))


class SuppliedTaskPlanRequest(BaseModel):
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=128)


@router.put('/tasks/{task_id}/plan')
def prepare_supplied_task_plan(task_id: str, request: SuppliedTaskPlanRequest,
                               runtime: GCWRuntime = Depends(get_runtime)):
    from .htn_planner import PlanError
    try:
        return _task_dict(runtime.prepare_supplied_plan(task_id, steps=request.steps))
    except KeyError:
        raise HTTPException(404, 'task not found')
    except PlanError as exc:
        raise HTTPException(422, str(exc))
    except ValueError as exc:
        raise HTTPException(409 if str(exc).startswith('plan conflict') else 422, str(exc))
