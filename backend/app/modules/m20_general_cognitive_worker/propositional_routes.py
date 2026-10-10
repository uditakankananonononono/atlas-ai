from typing import Any
from fastapi import APIRouter,HTTPException
from .propositional_reasoning import reason
router=APIRouter(prefix='/propositional-reasoning',tags=['m20-propositional-reasoning'])
@router.post('/entail')
def entail(data:dict[str,Any]):
    try:return reason(data)
    except ValueError as exc:raise HTTPException(422,str(exc))from exc
