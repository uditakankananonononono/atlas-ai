"""Row 849: authenticated mounted adapter over the bounded dedicated engine."""
from typing import Any
from fastapi import APIRouter, Body, Depends, HTTPException
from app.auth.context import require_tenant
from .nonmonotonic849 import revise

router = APIRouter(prefix="/modules/20/rows/849", tags=["row-849"])

@router.post("/run", dependencies=[Depends(require_tenant)])
def row_849_run(payload: Any = Body(...)):
    try:
        return revise(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
