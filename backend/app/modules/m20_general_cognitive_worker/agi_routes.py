"""Authenticated API for Atlas's measured autonomy mechanisms."""
from __future__ import annotations

import os
import threading
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.context import TenantContext, require_tenant
from .agi_service import AGIRuntimeService

router = APIRouter(prefix="/agi-runtime", tags=["m20_agi_runtime"])
_services: dict[str, AGIRuntimeService] = {}
AGI_AUTOBIND_MAX_TENANTS = 64
AGI_AUTOBIND_MAX_TENANT_ID_CHARS = 128
# One re-entrant lock orders explicit and automatic binding: an explicit
# bind_agi_service() is never overwritten by a concurrent automatic bind.
_agi_autobind_lock = threading.RLock()


def bind_agi_service(service: AGIRuntimeService, *, tenant_id: str) -> None:
    """Explicitly bind one tenant's AGI runtime service.

    Never bind the same mutable instance for two tenants. Construction is
    durable (SQLite under ATLAS_AGI_DATA_DIR), so persistence and approval
    gates must be configured for that tenant before binding.
    """
    with _agi_autobind_lock:
        _services[tenant_id] = service


def _autobind_agi(tenant_id):
    """Opt-in (ATLAS_AGI_RUNTIME_AUTOBIND exactly "1"): give an authenticated
    tenant its own durable AGIRuntimeService. Never used for "local"; creates
    SQLite files under ATLAS_AGI_DATA_DIR for the bound tenant only."""
    if os.environ.get("ATLAS_AGI_RUNTIME_AUTOBIND") != "1":
        return None
    if type(tenant_id) is not str or not tenant_id or tenant_id == "local" or len(tenant_id) > AGI_AUTOBIND_MAX_TENANT_ID_CHARS:
        return None
    with _agi_autobind_lock:
        existing = _services.get(tenant_id)
        if existing is not None:
            return existing
        if len(_services) >= AGI_AUTOBIND_MAX_TENANTS:
            return None
        service = AGIRuntimeService(tenant_id)
        bound = _services.get(tenant_id)
        if bound is not None:
            return bound  # a same-thread explicit bind inside the constructor wins (the lock is re-entrant)
        _services[tenant_id] = service
        return service


def get_agi_service(tenant: TenantContext = Depends(require_tenant)) -> AGIRuntimeService:
    service = _services.get(tenant.tenant_id)
    if service is None:
        service = _autobind_agi(tenant.tenant_id)
    if service is None:
        raise HTTPException(status_code=503, detail="AGI runtime service not bound for authenticated tenant")
    return service


class ObservationIn(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: Any
    source: str = Field(min_length=1)
    reliability: float = Field(default=1, ge=0, le=1)
    weight: float = Field(default=1, gt=0)


class GoalProposalIn(BaseModel):
    mission: str = Field(min_length=1)
    max_goals: int = Field(default=5, ge=1, le=20)


class ApprovalIn(BaseModel):
    approval_id: str = Field(min_length=1)


class TransferEvaluationIn(BaseModel):
    strategy: str
    cases: list[dict[str, Any]] = Field(min_length=2, max_length=100)


@router.post("/world/evidence", status_code=201)
def observe(body: ObservationIn, service: AGIRuntimeService = Depends(get_agi_service)):
    try:
        evidence_id = service.world.observe(**body.model_dump())
        return {"evidence_id": evidence_id}
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/world/hypotheses")
def hypotheses(subject: str, predicate: str,
               service: AGIRuntimeService = Depends(get_agi_service)):
    return service.world.hypotheses(subject, predicate)


@router.post("/world/snapshots", status_code=201)
def snapshot(service: AGIRuntimeService = Depends(get_agi_service)):
    return service.world.snapshot()


@router.get("/world/snapshots/verify")
def verify_snapshots(service: AGIRuntimeService = Depends(get_agi_service)):
    return {"valid": service.world.verify_chain(),
            "status": "stored_snapshot_hash_chain_consistency_only",
            "independent_anchor_verified": False, "evidence_truth_verified": False,
            "completeness_verified": False}


@router.post("/goals/proposals", status_code=201)
def propose_goals(body: GoalProposalIn, service: AGIRuntimeService = Depends(get_agi_service)):
    return [g.__dict__ for g in service.goals.propose_from_gaps(
        service.world, mission=body.mission, max_goals=body.max_goals)]


@router.post("/goals/{proposal_id}/request-activation")
def request_goal_activation(proposal_id: str,
                            service: AGIRuntimeService = Depends(get_agi_service)):
    try:
        return {"approval_id": service.goals.request_activation(proposal_id)}
    except KeyError as exc:
        raise HTTPException(404, "goal proposal not found") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/goals/{proposal_id}/activate")
def activate_goal(proposal_id: str, body: ApprovalIn,
                  service: AGIRuntimeService = Depends(get_agi_service)):
    try:
        return service.goals.activate(proposal_id, body.approval_id).__dict__
    except KeyError as exc:
        raise HTTPException(404, "goal proposal not found") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/evaluations/cross-domain", status_code=201)
def evaluate_transfer(body: TransferEvaluationIn,
                      service: AGIRuntimeService = Depends(get_agi_service)):
    try:
        return service.evaluate_transfer(**body.model_dump())
    except KeyError as exc:
        raise HTTPException(404, "unknown strategy") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
