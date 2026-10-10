from typing import Any
from fastapi import APIRouter,HTTPException
from .artificial_life import simulate
router=APIRouter(prefix='/artificial-life',tags=['m20-artificial-life'])
@router.post('/simulate')
def run(data:dict[str,Any]):
    try:return simulate(data)
    except ValueError as exc:raise HTTPException(422,str(exc))from exc
