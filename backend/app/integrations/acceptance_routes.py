"""HTTP surface for integration acceptance evidence."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .acceptance import AcceptanceError, ExactWriteApproval, UnknownAdapter, UnsafeWriteProbe, default_catalog

router = APIRouter(prefix="/integrations/acceptance", tags=["integration-acceptance"])
catalog = default_catalog()

class ApprovalIn(BaseModel):
    approved: bool
    adapter_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    resource: str = Field(min_length=1)

class WriteProbeIn(BaseModel):
    action: str = Field(min_length=1)
    resource: str = Field(min_length=1)
    approval: ApprovalIn
    payload: dict[str, Any] = Field(default_factory=dict)

@router.get("")
def integration_acceptance(tenant: TenantContext = Depends(require_tenant)):
    return {"integrations": catalog.list(tenant.tenant_id)}

@router.post("/{adapter_id}/probe/read")
async def read_probe(adapter_id: str, tenant: TenantContext = Depends(require_tenant)):
    try: return await catalog.probe_read(tenant.tenant_id, adapter_id)
    except UnknownAdapter as exc: raise HTTPException(404, "unknown adapter") from exc
    except AcceptanceError as exc: raise HTTPException(409, str(exc)) from exc

@router.post("/{adapter_id}/probe/write")
async def write_probe(adapter_id: str, body: WriteProbeIn, tenant: TenantContext = Depends(require_tenant)):
    approval = ExactWriteApproval(**body.approval.model_dump())
    try: return await catalog.probe_write(tenant.tenant_id, adapter_id, body.action, body.resource, approval, body.payload)
    except UnknownAdapter as exc: raise HTTPException(404, "unknown adapter") from exc
    except UnsafeWriteProbe as exc: raise HTTPException(403, str(exc)) from exc
    except AcceptanceError as exc: raise HTTPException(409, str(exc)) from exc
