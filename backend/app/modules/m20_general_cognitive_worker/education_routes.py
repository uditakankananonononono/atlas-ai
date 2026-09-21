from typing import Any
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from .education import EducationError, capabilities, execute

router=APIRouter(prefix="/education",tags=["m20-education"])

class EducationRequest(BaseModel):
    payload: dict[str,Any]=Field(default_factory=dict)

@router.get("/capabilities")
def list_capabilities():
    return capabilities()

@router.post("/{capability}")
def run_capability(
    capability:str,
    request:EducationRequest,
    x_tenant_id:str=Header(min_length=1,alias="X-Tenant-ID"),
    x_actor_id:str=Header(min_length=1,alias="X-Actor-ID"),
):
    try:
        payload=dict(request.payload)
        if payload.get("tenant_id",x_tenant_id)!=x_tenant_id or payload.get("actor_id",x_actor_id)!=x_actor_id:
            raise EducationError("header and payload scope mismatch")
        payload.pop("tenant_id",None);payload.pop("actor_id",None)
        return execute(capability,payload,tenant_id=x_tenant_id,actor_id=x_actor_id)
    except EducationError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
