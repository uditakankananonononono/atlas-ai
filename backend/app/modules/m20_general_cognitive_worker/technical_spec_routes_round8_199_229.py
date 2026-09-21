from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .technical_spec_round8_199_229 import ROWS, mapping, semantic_behavior, safety_replacement, verify_production

router=APIRouter(prefix="/technical-spec/199-229",tags=["technical spec 199-229"])
class RunRequest(BaseModel): payload:dict[str,Any]=Field(default_factory=dict)
@router.get("/requirements")
def requirements(): return [mapping(row).__dict__ for row in sorted(ROWS)]
@router.post("/{row}")
def run(row:int,request:RunRequest):
    try:
        if 208<=row<=221:
            if row in {213,214,215,216,217}: result=semantic_behavior(row,request.payload)
            else: result=verify_production(row,request.payload)
        elif 222<=row<=229: result=safety_replacement(row,str(request.payload.get("mechanism","")))
        else: result=semantic_behavior(row,request.payload)
        return {"mapping":result.mapping.__dict__,"status":result.status,"output":result.output,"evidence":result.evidence}
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
