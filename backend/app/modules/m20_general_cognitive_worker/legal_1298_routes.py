"""Row 1298: mounted supplied-reference bookkeeping, never legal advice."""
from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import require_tenant
from .legal_technology1298 import run

router = APIRouter(dependencies=[Depends(require_tenant)])

@router.post("/api/modules/20/legal/1298/support")
def support_row_1298(request: dict):
    try:
        return run(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
