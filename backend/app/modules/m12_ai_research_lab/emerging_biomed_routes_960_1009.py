from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import TenantContext, require_tenant
from pydantic import BaseModel, Field
from .emerging_biomed_960_1009 import ENGINES, run
router=APIRouter(prefix="/emerging-biomed-960-1009",tags=["emerging-biomed"])
class Request(BaseModel):
    method: str = Field(min_length=1)
    data: dict[str,Any] = Field(default_factory=dict)
@router.get("/methods")
def methods():
    return [{"method":key,"feature_row":e.row,"title":e.title,"mechanism":e.mechanism} for key,e in ENGINES.items()]
@router.post("/analyze")
def analyze(body:Request,tenant:TenantContext=Depends(require_tenant)):
    try: return run(body.method,body.data,tenant_id=tenant.tenant_id,actor_id=tenant.actor_id)
    except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc: raise HTTPException(422,str(exc)) from exc
