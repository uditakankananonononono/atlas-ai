"""Row 1299: authenticated mounted adapter over the bounded dedicated engine."""
from typing import Any
from fastapi import APIRouter, Body, Depends, HTTPException
from app.auth.context import require_tenant
from .e_discovery1299 import run

router = APIRouter(prefix="/modules/20/rows/1299", tags=["row-1299"])

@router.post("/run", dependencies=[Depends(require_tenant)])
def row_1299_run(payload: Any = Body(...)):
    try:
        return run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
