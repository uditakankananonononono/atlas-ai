from fastapi import APIRouter,HTTPException
from app.modules.registry import IMPLEMENTED_SPECS
router=APIRouter(prefix="/runtime",tags=["integrated-runtime"])
@router.get("/coherence")
def coherence():
 return {"shared_api":True,"mounted_modules":[x.id for x in IMPLEMENTED_SPECS],"shared_tenant_context":True,"shared_approval_boundary":True,"shared_workers":True,"handoff_contract":"app.runtime.integration.Handoff","integrated_workflows":["opportunity-to-application","research-to-document"]}

# Current-evidence verification for the 13 assistant-capability audit surfaces.
from .capability_audit_routes_13 import router as capability_audit_router_13
router.include_router(capability_audit_router_13)

from typing import Any
from pydantic import BaseModel,Field
from .technical_spec_100_132 import technical_spec_100_132
class TechnicalSpec100To132In(BaseModel):
    row:int=Field(ge=100,le=132)
    data:dict[str,Any]=Field(default_factory=dict)
@router.post('/technical-spec-100-132')
def technical_spec_100_132_route(body:TechnicalSpec100To132In):
    try:return technical_spec_100_132(body.row,body.data)
    except ValueError as error:raise HTTPException(422,str(error)) from error

from .technical_spec_routes_166_198 import router as technical_spec_router_166_198
router.include_router(technical_spec_router_166_198)

# Executable technical architecture contracts, source-mapped rows A01-A33.
from .technical_architecture_routes_a01_a33 import router as technical_architecture_router_a01_a33
router.include_router(technical_architecture_router_a01_a33)
