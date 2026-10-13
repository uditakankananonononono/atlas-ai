"""Row 1289 Oral Argument: mounted route executing the row-1289 engine.

The shared legal-1260-1309 support route runs the generic analyze_legal_feature;
this dedicated route executes oral_argument1289.run() - supplied-reference
bookkeeping over caller entries only. It reaches no legal conclusion, verifies
no reference, and files, serves, contacts or sends nothing.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.context import TenantContext, require_tenant

from .oral_argument1289 import run

router = APIRouter(tags=["m20-oral-argument1289"])


class Row1289Request(BaseModel):
    data: dict[str, Any]
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None


@router.post("/legal-1289/oral-argument")
def row_1289(body: Row1289Request,
             principal: TenantContext = Depends(require_tenant)) -> dict[str, Any]:
    if ((body.tenant_id is not None and body.tenant_id != principal.tenant_id)
            or (body.actor_id is not None and body.actor_id != principal.actor_id)
            or body.data.get("tenant_id", principal.tenant_id) != principal.tenant_id
            or body.data.get("actor_id", principal.actor_id) != principal.actor_id):
        raise HTTPException(403, "legal scope mismatches authenticated principal")
    try:
        result = run(body.data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"module_id": 20, "tenant_id": principal.tenant_id, "actor_id": principal.actor_id,
            "result": result, "requires_licensed_counsel": True}
