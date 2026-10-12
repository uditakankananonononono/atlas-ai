"""Authenticated HTTP surface for the approved-execution dispatcher.

Mounted under /api/v1/approved-executions by the integrator. Guards and
adapters live in approved_execution.py; this file translates HTTP only.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.context import TenantContext, require_tenant
from app.modules.m00_approval_center.service import ApprovalNotFoundError

import json
import os

from .approved_execution import (ApprovedExecutionDispatcher, ExecutionConflictError,
                                 M00AuthorityCheck)
from .guardrails.enforcer import GuardrailEnforcer

router = APIRouter(prefix="/approved-executions", tags=["approved_execution"])
_dispatchers: dict[str, ApprovedExecutionDispatcher] = {}


_EMPTY = {"tos": {}, "rate_limits": {}, "consent": [], "recent_actions": []}

# Default declaration (ToS UNVERIFIED): Gmail API send, 50 per 24h. Consent is the
# M00 approval binding: every send already requires the owner's approval of the
# exact draft, and the outbound gate additionally requires M00 authority bound to
# the action digest. Declared, not verified against Google's terms. Any
# ATLAS_OUTBOUND_DECLARATIONS file REPLACES these defaults.
_DEFAULT = {
    "tos": {"gmail": {"allowed_kinds": ["send"], "automation_allowed": True}},
    "rate_limits": {"gmail": {"send": {"max": 50, "window_seconds": 86400}}},
    "consent": [], "recent_actions": [],
}


def outbound_declarations() -> dict:
    """Platform-terms / rate-limit / consent declarations for person-facing actions.

    Read from the JSON file at ATLAS_OUTBOUND_DECLARATIONS (owner-maintained).
    Unset -> the gmail-send default below (ToS-unverified). A file that is set
    but unreadable -> an empty declaration set which the outbound gate DENIES
    (no declared rules), so person-facing action types stay refused until declared.
    """
    path = os.getenv("ATLAS_OUTBOUND_DECLARATIONS")
    if not path:
        return json.loads(json.dumps(_DEFAULT))
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else json.loads(json.dumps(_EMPTY))
    except (OSError, ValueError):
        return json.loads(json.dumps(_EMPTY))


def build_dispatcher(tenant_id: str) -> ApprovedExecutionDispatcher:
    """Production dispatcher: carries an enforcer whose owner-authority hook is M00."""
    from app.modules.m00_approval_center.service import default_service
    center = default_service()
    check = M00AuthorityCheck(center, tenant_id)
    return ApprovedExecutionDispatcher(
        tenant_id, actor_id=tenant_id, center=center,
        enforcer=GuardrailEnforcer(authority_check=check),
        authority_binder=check, outbound_declarations=outbound_declarations())


def get_dispatcher(tenant: TenantContext = Depends(require_tenant)) -> ApprovedExecutionDispatcher:
    if tenant.tenant_id not in _dispatchers:
        _dispatchers[tenant.tenant_id] = build_dispatcher(tenant.tenant_id)
    return _dispatchers[tenant.tenant_id]


class ExecutionRequestIn(BaseModel):
    approval_id: str = Field(min_length=1)


def _translate(error: Exception) -> HTTPException:
    if isinstance(error, (ApprovalNotFoundError, KeyError)):
        return HTTPException(status_code=404, detail=str(error).strip("'"))
    if isinstance(error, ExecutionConflictError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, PermissionError):
        return HTTPException(status_code=403, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.post("", status_code=201)
def execute(body: ExecutionRequestIn,
            dispatcher: ApprovedExecutionDispatcher = Depends(get_dispatcher)):
    """Execute one approved Module 0 item through its allowlisted adapter."""
    try:
        return dispatcher.execute(body.approval_id)
    except (ApprovalNotFoundError, KeyError, ExecutionConflictError,
            PermissionError, ValueError) as exc:
        raise _translate(exc) from exc


@router.get("/{approval_id}")
def readback(approval_id: str,
             dispatcher: ApprovedExecutionDispatcher = Depends(get_dispatcher)):
    """Read back the latest receipt for one approval (tenant-scoped)."""
    try:
        return dispatcher.readback(approval_id)
    except KeyError as exc:
        raise _translate(exc) from exc


@router.get("")
def list_receipts(limit: int = 100,
                  dispatcher: ApprovedExecutionDispatcher = Depends(get_dispatcher)):
    return dispatcher.list_receipts(limit=limit)
