from fastapi import APIRouter
from app.modules.registry import IMPLEMENTED_SPECS
router=APIRouter(prefix="/runtime",tags=["integrated-runtime"])
@router.get("/coherence")
def coherence():
 return {"shared_api":True,"mounted_modules":[x.id for x in IMPLEMENTED_SPECS],"shared_tenant_context":True,"shared_approval_boundary":True,"shared_workers":True,"handoff_contract":"app.runtime.integration.Handoff","integrated_workflows":["opportunity-to-application","research-to-document"]}

# Current-evidence verification for the 13 assistant-capability audit surfaces.
from .capability_audit_routes_13 import router as capability_audit_router_13
router.include_router(capability_audit_router_13)
