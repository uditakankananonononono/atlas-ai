"""Authenticated HTTP surface for the approved-execution dispatcher.

Mounted under /api/v1/approved-executions by the integrator. Guards and
adapters live in approved_execution.py; this file translates HTTP only.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.context import TenantContext, require_tenant
from app.modules.m00_approval_center.service import ApprovalNotFoundError

from .approved_execution import ApprovedExecutionDispatcher, ExecutionConflictError

router = APIRouter(prefix="/approved-executions", tags=["approved_execution"])
_dispatchers: dict[str, ApprovedExecutionDispatcher] = {}


def get_dispatcher(tenant: TenantContext = Depends(require_tenant)) -> ApprovedExecutionDispatcher:
    if tenant.tenant_id not in _dispatchers:
        _dispatchers[tenant.tenant_id] = ApprovedExecutionDispatcher(
            tenant.tenant_id, actor_id=tenant.tenant_id)
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
