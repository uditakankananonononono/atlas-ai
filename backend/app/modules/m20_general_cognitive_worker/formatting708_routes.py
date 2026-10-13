"""Row708: mounted caller-supplied computation, closed-scoped, NOT literal breadth.
Authorizes, executes, merges, releases or approves nothing.
"""
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .computation_boundary import owner_payload
from .legacy_modernizer_routes694 import reject_surrogate_source
from .code_formatting708 import run as engine

router=APIRouter(prefix='/code-formatting/708',tags=['m20-formatting708'])
class Request708(BaseModel):
    data:dict[str,Any]
    tenant_id:Optional[str]=None
    actor_id:Optional[str]=None
    resource_refs:list[dict[str,Any]]=Field(default_factory=list,max_length=64)

@router.post('/inspect',dependencies=[Depends(reject_surrogate_source)])
def run(body:Request708,tenant:TenantContext=Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True),tenant)
    try:
        result=engine(body.data)
        return {**result,'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id}
    except (ValueError,TypeError,KeyError)as exc:
        raise HTTPException(422,str(exc))from exc

# Real formatter, separate from compatibility-only caller declaration inspection.
from pydantic import ConfigDict, StrictInt
from .python_formatter708 import format_python, FormatterUnavailable


class PythonFormat708(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: str = Field(max_length=25000)
    line_length: StrictInt = Field(default=88, ge=40, le=200)
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=64)


@router.post('/format-python', dependencies=[Depends(reject_surrogate_source)])
def format_python_source(body: PythonFormat708, tenant: TenantContext = Depends(require_tenant)):
    owner_payload(body.model_dump(exclude_none=True), tenant)
    try:
        return {**format_python(body.source, body.line_length),
                'tenant_id': tenant.tenant_id, 'actor_id': tenant.actor_id}
    except FormatterUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
