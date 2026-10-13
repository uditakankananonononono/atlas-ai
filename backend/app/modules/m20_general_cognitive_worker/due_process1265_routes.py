"""Row 1265: bounded caller-declared bookkeeping, no legal determination."""
from typing import Any
from fastapi import APIRouter, Body, Depends, HTTPException
from app.auth.context import require_tenant
from .due_process1265 import analyze_due_process

router = APIRouter(prefix='/api/modules/20', tags=['legal-row-1265'])

@router.post('/due-process-1265/support', dependencies=[Depends(require_tenant)])
def support_1265(payload: Any = Body(...)) -> dict:
    try:
        return analyze_due_process(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
