"""Optional FastAPI surface for module self-improvement.

Read endpoints are open to the host process; mutations (cycle, activate,
rollback) go through the same approval gates as everything else. Import
fastapi lazily is unnecessary - this module is only imported where the web
stack runs.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .wiring import engine_for

router = APIRouter(prefix="/self-improve", tags=["self-improvement"])


class GapReport(BaseModel):
    signature: str
    kind: str = "capability_miss"
    detail: str = ""
    exemplar: Any = None


class CycleRequest(BaseModel):
    max_new: int = 1


class ActivateRequest(BaseModel):
    approval_id: str


class DispatchRequest(BaseModel):
    items: list[Any]
    params: dict[str, Any] | None = None


@router.get("/{slug}/status")
def status(slug: str) -> dict[str, Any]:
    try:
        return engine_for(slug).status()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{slug}/gaps")
def report_gap(slug: str, report: GapReport) -> dict[str, str]:
    try:
        event = engine_for(slug).record_gap(
            report.signature, kind=report.kind, detail=report.detail,
            exemplar=report.exemplar)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"event_id": event.event_id}


@router.post("/{slug}/cycle")
def run_cycle(slug: str, request: CycleRequest) -> dict[str, Any]:
    try:
        return engine_for(slug).run_cycle(max_new=request.max_new)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{slug}/candidates/{key}/activate")
def activate(slug: str, key: str, request: ActivateRequest) -> dict[str, Any]:
    try:
        return engine_for(slug).activate(key, approval_id=request.approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{slug}/features/{name}/rollback")
def rollback(slug: str, name: str, request: ActivateRequest) -> dict[str, Any]:
    try:
        return engine_for(slug).rollback(name, approval_id=request.approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{slug}/features/{name}/dispatch")
def dispatch(slug: str, name: str, request: DispatchRequest) -> dict[str, Any]:
    try:
        return engine_for(slug).dispatch(name, request.items, request.params)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
