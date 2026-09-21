from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .education import EducationError, capabilities, execute
router=APIRouter(prefix="/education",tags=["m20-education"])
class EducationRequest(BaseModel):
    payload: dict[str,Any]=Field(default_factory=dict)
@router.get("/capabilities")
def list_capabilities(): return capabilities()
@router.post("/{capability}")
def run_capability(capability:str,request:EducationRequest):
    try:return execute(capability,request.payload)
    except EducationError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
