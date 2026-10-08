from __future__ import annotations
import os
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .acceptance import ToolReceiptCriterion
from .goals import GoalStore
from .redaction import scrub_text

router = APIRouter(prefix="/runtime", tags=["claire-runtime"])
_store: GoalStore | None = None


def get_store() -> GoalStore:
    """Durable store from ATLAS_CLAIRE_RUNTIME_DB. Unset fails closed: no silent in-memory goals."""
    global _store
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
