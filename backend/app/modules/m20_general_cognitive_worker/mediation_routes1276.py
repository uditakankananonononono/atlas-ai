"""Row 1276 Mediation: dedicated mounted route over mediation1276.organize.

POST /mediation-1276/organize takes the exact organize() payload as the JSON body, behind the
authenticated tenant dependency, and returns the engine result inside a tenant/actor envelope.
The envelope identity comes only from the verified principal; a body that names tenant_id or
actor_id is refused by the engine's unknown-key check (422). The route adds no behavior. The
result is caller-declared bookkeeping: no mediation outcome, settlement, legal conclusion,
authority check or external effect is produced or claimed.
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.auth.context import TenantContext, require_tenant

from .mediation1276 import organize

router = APIRouter(prefix='/mediation-1276', tags=['m20-mediation-1276'])


@router.post('/organize')
def organize_route(body: dict[str, Any] = Body(...), principal: TenantContext = Depends(require_tenant)) -> dict[str, Any]:
    try:
        result = organize(body)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {'module_id': 20, 'tenant_id': principal.tenant_id, 'actor_id': principal.actor_id,
            'result': result, 'requires_licensed_counsel': True}
