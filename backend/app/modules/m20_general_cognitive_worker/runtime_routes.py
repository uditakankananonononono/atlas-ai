"""Mounted HTTP surface for the durable GCW runtime.

Separate router from routes.py so the integrator can reconcile the newer
registration commits without conflicts. Mounted at /api/modules/20/runtime;
bind with bind_runtime().
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .runtime import GCWRuntime
from .sandbox import SandboxViolation

router = APIRouter(prefix="/api/modules/20/runtime", tags=["m20_runtime"])

_runtime: GCWRuntime | None = None


def bind_runtime(runtime: GCWRuntime) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> GCWRuntime:
    if _runtime is None:
        raise HTTPException(status_code=503, detail="GCW runtime not bound yet")
    return _runtime


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
def submit_task(request: GoalRequest) -> dict[str, Any]:
    runtime = get_runtime()
    context = runtime.submit_goal(
        request.goal, importance=request.importance,
        deadline=request.deadline, run_immediately=request.run_immediately,
    )
    return _task_dict(context)


@router.get("/tasks")
def list_tasks() -> list[dict[str, Any]]:
    return [_task_dict(c) for c in get_runtime().list_tasks()]


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    context = get_runtime().get_task(task_id)
    if context is None:
        raise HTTPException(status_code=404, detail="unknown task")
    return _task_dict(context)


@router.post("/tasks/{task_id}/step")
def step_task(task_id: str, request: StepRequest) -> dict[str, Any]:
    runtime = get_runtime()
    if runtime.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="unknown task")
    context = runtime.run_task(task_id, max_ticks=request.max_ticks)
    return _task_dict(context)


@router.post("/step")
def step_once(request: StepRequest) -> dict[str, Any]:
    report = get_runtime().step(
        quantum_seconds=request.quantum_seconds, max_ticks=request.max_ticks,
    )
    return vars(report)


@router.get("/tasks/{task_id}/decision")
def decision(task_id: str) -> dict[str, Any]:
    artifact = get_runtime().decision_artifact(task_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="unknown task")
    return artifact.as_dict()


@router.get("/tasks/{task_id}/mcts")
def mcts(task_id: str, simulations: int = 32) -> dict[str, Any]:
    if simulations < 1 or simulations > 512:
        raise HTTPException(status_code=422, detail="simulations must be 1..512")
    result = get_runtime().run_mcts(task_id, max_simulations=simulations)
    if result is None:
        raise HTTPException(status_code=404, detail="unknown task")
    return result.as_dict()


@router.post("/tasks/{task_id}/close")
def close_task(task_id: str) -> dict[str, Any]:
    result = get_runtime().close(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="unknown task")
    return result


@router.post("/tools/select")
def select_tool(request: SelectToolRequest) -> dict[str, Any]:
    return get_runtime().select_tool(request.description, context=request.context).as_dict()


@router.post("/sandbox/run")
def sandbox_run(request: SandboxRunRequest) -> dict[str, Any]:
    runtime = get_runtime()
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
def facts() -> list[dict[str, Any]]:
    runtime = get_runtime()
    return [f.model_dump(mode="json") for f in runtime.repo.list_facts()]


@router.get("/memory/episodes")
def episodes(task_id: str | None = None) -> list[dict[str, Any]]:
    runtime = get_runtime()
    return [e.model_dump(mode="json") for e in runtime.repo.list_episodes(task_id=task_id)]


@router.get("/retrospectives")
def retrospectives(task_id: str | None = None) -> list[dict[str, Any]]:
    runtime = get_runtime()
    return [r.model_dump(mode="json") for r in runtime.repo.list_retrospectives(task_id=task_id)]


@router.get("/calibration")
def calibration() -> dict[str, Any]:
    runtime = get_runtime()
    return {
        "claims": len(runtime.calibration.claims),
        "resolved": sum(1 for c in runtime.calibration.claims.values() if c.resolved),
        "curve": runtime.calibration.calibration_curve(),
        "calibration_error": runtime.calibration.calibration_error(),
    }


@router.get("/methods")
def methods(status: str | None = None) -> list[dict[str, Any]]:
    runtime = get_runtime()
    out = []
    for method, status_value in runtime.repo.list_methods(status=status):
        data = method.model_dump(mode="json")
        data["review_status"] = runtime.planner.method_status(method.name)
        out.append(data)
    return out


@router.post("/methods/{name}/activate")
def activate_method(name: str) -> dict[str, Any]:
    runtime = get_runtime()
    if not runtime.planner.activate_method(name):
        raise HTTPException(status_code=404, detail="unknown method")
    return {"name": name, "review_status": "active"}
