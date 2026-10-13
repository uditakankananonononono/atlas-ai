"""Row 1297: mounted supplied-reference bookkeeping, never legal advice."""
from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import require_tenant
from .access_to_justice1297 import run

router = APIRouter(dependencies=[Depends(require_tenant)])

@router.post("/api/modules/20/legal/1297/support")
def support_row_1297(request: dict):
    try:
        return run(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
