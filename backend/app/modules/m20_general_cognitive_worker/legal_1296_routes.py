"""Row 1296: mounted supplied-reference bookkeeping, never legal advice."""
from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import require_tenant
from .legal_aid1296 import run

router = APIRouter(dependencies=[Depends(require_tenant)])

@router.post("/api/modules/20/legal/1296/support")
def support_row_1296(request: dict):
    try:
        return run(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
