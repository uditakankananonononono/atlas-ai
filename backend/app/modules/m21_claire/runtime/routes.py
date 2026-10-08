from __future__ import annotations
import os
import threading
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .acceptance import ToolReceiptCriterion
from .goals import GoalStore
from .redaction import scrub_text

router = APIRouter(prefix="/runtime", tags=["claire-runtime"])
_store: GoalStore | None = None
_store_lock = threading.Lock()


def get_store() -> GoalStore:
    """Durable store from ATLAS_CLAIRE_RUNTIME_DB. Unset fails closed: no silent in-memory goals."""
    global _store
    with _store_lock:
      if _store is None:
        url = os.getenv("ATLAS_CLAIRE_RUNTIME_DB", "").strip()
        if not url:
            raise HTTPException(503, "Claire runtime store is not configured")
        _store = GoalStore(url, create_schema=os.getenv("ATLAS_AUTO_CREATE_SCHEMA") == "1")
    return _store


class RuntimeGoalIn(BaseModel):
    purpose: str = Field(min_length=3, max_length=8000)
    acceptance_criteria: list[ToolReceiptCriterion] = Field(min_length=1, max_length=20)
    max_steps: int = Field(default=12, ge=1, le=50)


@router.post("/goals", status_code=201)
def create_goal(body: RuntimeGoalIn, tenant: TenantContext = Depends(require_tenant), store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    gid = store.create(tenant.tenant_id, tenant.actor_id, scrub_text(body.purpose),
                       [c.model_dump() for c in body.acceptance_criteria], body.max_steps)
    return store.get(tenant.tenant_id, tenant.actor_id, gid)


@router.get("/goals/{goal_id}")
def read_goal(goal_id: str, tenant: TenantContext = Depends(require_tenant), store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    goal = store.get(tenant.tenant_id, tenant.actor_id, goal_id)
    if goal is None:
        raise HTTPException(404, "goal not found")
    return goal


@router.post("/goals/{goal_id}/cancel")
def cancel_goal(goal_id: str, tenant: TenantContext = Depends(require_tenant), store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    outcome = store.cancel(tenant.tenant_id, tenant.actor_id, goal_id)
    if outcome == "not_found":
        raise HTTPException(404, "goal not found")
    if outcome == "not_cancellable":
        raise HTTPException(409, "only queued goals can be cancelled in this release")
    return store.get(tenant.tenant_id, tenant.actor_id, goal_id)


class ApprovalIn(BaseModel):
    capability: str = Field(min_length=1, max_length=100)
    gate: str = Field(pattern="^(payment|comms)$")
    digest: str = Field(min_length=64, max_length=64)
    ttl_seconds: int = Field(default=900, ge=1, le=86400)


@router.post("/goals/{goal_id}/approvals", status_code=201)
def approve(goal_id: str, body: ApprovalIn, tenant: TenantContext = Depends(require_tenant), store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    """The owner approves one gate of one exact call that this goal's own report refused. Single use, expiring."""
    goal = store.get(tenant.tenant_id, tenant.actor_id, goal_id)
    if goal is None:
        raise HTTPException(404, "goal not found")
    refused = [r for r in (goal.get("report") or {}).get("refusals", [])
               if r.get("reason") == "approval_required" and r.get("digest") == body.digest
               and r.get("tool") == body.capability and body.gate in r.get("gates", [])]
    if not refused:
        raise HTTPException(422, "no refused call in this goal matches that capability, gate and digest")
    aid = store.grant(tenant.tenant_id, tenant.actor_id, goal_id, body.capability, body.gate, body.digest,
                      approver=tenant.actor_id, ttl_seconds=body.ttl_seconds)
    return {"approval_id": aid, "goal_id": goal_id, "capability": body.capability, "gate": body.gate, "single_use": True}


@router.post("/goals/{goal_id}/requeue")
def requeue_goal(goal_id: str, tenant: TenantContext = Depends(require_tenant), store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    outcome = store.requeue(tenant.tenant_id, tenant.actor_id, goal_id)
    if outcome == "not_found":
        raise HTTPException(404, "goal not found")
    if outcome == "not_requeueable":
        raise HTTPException(409, "only goals awaiting review with attempts left can be requeued")
    return store.get(tenant.tenant_id, tenant.actor_id, goal_id)


@router.get("/goals/{goal_id}/effects")
def list_effects(goal_id: str, tenant: TenantContext = Depends(require_tenant), store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    """The owner's view of the effect journal for one goal (no arguments are stored, only the digest key and state)."""
    effects = store.list_effects(tenant.tenant_id, tenant.actor_id, goal_id)
    if effects is None:
        raise HTTPException(404, "goal not found")
    return {"goal_id": goal_id, "effects": effects}


class ResolveIn(BaseModel):
    outcome: str = Field(pattern="^(committed|absent)$")


@router.post("/goals/{goal_id}/effects/{effect_id}/resolve")
def resolve_effect(goal_id: str, effect_id: str, body: ResolveIn, tenant: TenantContext = Depends(require_tenant),
                   store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    """The owner states what really happened to an effect whose outcome is unknown. committed: it happened, never re-run.
    absent: it did not happen, so the same call may be retried with a fresh exact approval. No separation of duties:
    the approver is the goal's own tenant and actor."""
    outcome = store.resolve_effect(goal_id, effect_id, body.outcome, receipt={"content": {"resolved_by_owner": True}},
                                   tenant_id=tenant.tenant_id, actor_id=tenant.actor_id, require_not_running=True)
    if outcome == "not_found":
        raise HTTPException(404, "effect not found")
    if outcome == "goal_running":
        raise HTTPException(409, "the goal is running; resolve the effect after it settles")
    if outcome == "not_pending":
        raise HTTPException(409, "only an effect with an unknown outcome can be resolved")
    return {"goal_id": goal_id, "effect_id": effect_id, "state": body.outcome}
