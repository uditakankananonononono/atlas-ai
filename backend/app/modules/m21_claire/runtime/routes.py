from __future__ import annotations
import os
import threading
from typing import Any
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictStr, field_validator
from app.auth.context import TenantContext, require_tenant
from .acceptance import ToolReceiptCriterion
from .goals import ApproverNotDesignated, normalize_designated, GoalNotGrantable, GoalStore, SelfApprovalRefused
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
        _store = GoalStore(url, create_schema=os.getenv("ATLAS_AUTO_CREATE_SCHEMA") == "1",
                           owner_may_self_approve=os.getenv("ATLAS_CLAIRE_RUNTIME_SELF_APPROVE") == "1")
    return _store


class RuntimeGoalIn(BaseModel):
    purpose: str = Field(min_length=3, max_length=8000)
    acceptance_criteria: list[ToolReceiptCriterion] = Field(min_length=1, max_length=20)
    max_steps: int = Field(default=12, ge=1, le=50)
    designated_approvers: list[StrictStr] | None = Field(default=None, max_length=20)

    @field_validator("designated_approvers")
    @classmethod
    def _valid_designated(cls, v: list[str] | None) -> list[str] | None:
        normalize_designated(v)  # raises ValueError -> a 422 without echoing the offending value
        return v


@router.post("/goals", status_code=201)
def create_goal(body: RuntimeGoalIn, tenant: TenantContext = Depends(require_tenant), store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    gid = store.create(tenant.tenant_id, tenant.actor_id, scrub_text(body.purpose),
                       [c.model_dump() for c in body.acceptance_criteria], body.max_steps,
                       designated_approvers=body.designated_approvers)
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
        raise HTTPException(409, "only queued or running goals can be cancelled")
    body = store.get(tenant.tenant_id, tenant.actor_id, goal_id)
    if outcome == "cancel_requested":
        return JSONResponse(status_code=202, content={**(body or {}), "cancel_requested": True})
    return body


APPROVER_ROLES = ("claire-approver", "atlas-admin")


def require_approver(tenant: TenantContext) -> None:
    """Deciding on a gated call or an unknown effect is an owner-authority act: it needs the approver role."""
    if not tenant.has_role(*APPROVER_ROLES):
        raise HTTPException(403, "approver role required")


@router.get("/goals/{goal_id}/approver-view")
def approver_view(goal_id: str, tenant: TenantContext = Depends(require_tenant), store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    """What an approver may see before deciding: the refused calls (tool, gates, digest) and unresolved effects."""
    require_approver(tenant)
    view = store.approver_view(tenant.tenant_id, goal_id)
    if view is None:
        raise HTTPException(404, "goal not found")
    return view


class ApprovalIn(BaseModel):
    capability: str = Field(min_length=1, max_length=100)
    gate: str = Field(pattern="^(payment|comms)$")
    digest: str = Field(min_length=64, max_length=64)
    ttl_seconds: int = Field(default=900, ge=1, le=86400)


@router.post("/goals/{goal_id}/approvals", status_code=201)
def approve(goal_id: str, body: ApprovalIn, tenant: TenantContext = Depends(require_tenant), store: GoalStore = Depends(get_store)) -> dict[str, Any]:
    """An approver (a different principal than the goal's actor) approves one gate of one exact call that this
    goal's own report refused. Single use, expiring. The store refuses the goal's own actor unless self-approval is
    explicitly enabled."""
    require_approver(tenant)
    goal = store.approver_view(tenant.tenant_id, goal_id)
    if goal is None:
        raise HTTPException(404, "goal not found")
    refused = [r for r in goal["refusals"] if r.get("digest") == body.digest and r.get("tool") == body.capability
               and body.gate in (r.get("gates") or [])]
    if not refused:
        raise HTTPException(422, "no refused call in this goal matches that capability, gate and digest")
    try:
        aid = store.grant(tenant.tenant_id, goal["actor_id"], goal_id, body.capability, body.gate, body.digest,
                          approver=tenant.actor_id, ttl_seconds=body.ttl_seconds)
    except SelfApprovalRefused:
        raise HTTPException(403, "self_approval_refused") from None
    except ApproverNotDesignated:
        raise HTTPException(403, "approver_not_designated") from None
    except GoalNotGrantable:
        raise HTTPException(409, "goal_not_grantable") from None
    return {"approval_id": aid, "goal_id": goal_id, "capability": body.capability, "gate": body.gate, "single_use": True,
            "approver": tenant.actor_id, "self_approved": tenant.actor_id == goal["actor_id"]}


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
    """An approver (not the goal's actor, unless self-approval is enabled) states what really happened to an effect
    whose outcome is unknown. committed: it happened, never re-run. absent: it did not happen, so the same call may be
    retried with a fresh exact approval. The resolver is recorded on the journal row.
    A goal's designated_approvers list applies here exactly as it does to approvals (403 approver_not_designated)."""
    require_approver(tenant)
    try:
        outcome = store.resolve_effect(goal_id, effect_id, body.outcome, receipt={"content": {"resolved_by_owner": True}},
                                       tenant_id=tenant.tenant_id, resolver_id=tenant.actor_id, require_not_running=True)
    except SelfApprovalRefused:
        raise HTTPException(403, "self_approval_refused") from None
    except ApproverNotDesignated:
        raise HTTPException(403, "approver_not_designated") from None
    if outcome == "not_found":
        raise HTTPException(404, "effect not found")
    if outcome == "goal_running":
        raise HTTPException(409, "the goal is running; resolve the effect after it settles")
    if outcome == "not_pending":
        raise HTTPException(409, "only an effect with an unknown outcome can be resolved")
    return {"goal_id": goal_id, "effect_id": effect_id, "state": body.outcome}
