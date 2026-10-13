"""Row 1295: mounted supplied-reference bookkeeping, never legal advice."""
from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import require_tenant
from .pro_bono_practice1295 import run

router = APIRouter(dependencies=[Depends(require_tenant)])

@router.post("/api/modules/20/legal/1295/support")
def support_row_1295(request: dict):
    try:
        return run(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
