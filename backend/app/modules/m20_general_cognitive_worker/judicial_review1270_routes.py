"""Row 1270: bounded caller-declared bookkeeping, no legal determination."""
from typing import Any
from fastapi import APIRouter, Body, Depends, HTTPException
from app.auth.context import require_tenant
from .judicial_review1270 import organize

router = APIRouter(prefix='/api/modules/20', tags=['legal-row-1270'])

@router.post('/judicial-review-1270/support', dependencies=[Depends(require_tenant)])
def support_1270(payload: Any = Body(...)) -> dict:
    try:
        return organize(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
