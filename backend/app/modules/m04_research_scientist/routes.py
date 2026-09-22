"""FastAPI routes for the Research Scientist module."""

from fastapi import APIRouter, HTTPException, Depends
from app.core.providers import ProviderError
from app.auth.context import TenantContext, require_tenant
from app.modules.m00_approval_center.service import default_service
from .schemas import (
    AnalysisProposalRequest,
    HypothesisRequest,
    HypothesisResponse,
    ProposedAnalysis,
    SurveillanceRequest,
    SurveillanceResponse,
    SurveillanceIngestRequest, GapEvidenceOut,
)
from .service import Service

router = APIRouter(prefix="/research-scientist", tags=["Research Scientist"])


@router.post("/literature/clusters", response_model=SurveillanceResponse)
def cluster_literature(request: SurveillanceRequest) -> SurveillanceResponse:
    """Cluster already-collected papers without making a network call."""
    try:
        return Service().cluster_papers(request.papers, request.similarity_threshold)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/hypotheses", response_model=HypothesisResponse)
async def draft_hypothesis(
    request: HypothesisRequest,
    tenant: TenantContext = Depends(require_tenant),
) -> HypothesisResponse:
    """Draft a grounded hypothesis using the configured shared BYOK provider."""
    try:
        return await Service().generate_hypothesis(request)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/analyses/proposals", response_model=ProposedAnalysis)
def propose_analysis(request: AnalysisProposalRequest, tenant: TenantContext = Depends(require_tenant)) -> ProposedAnalysis:
    """Create an approval-gated sandbox execution proposal; never execute code here."""
    try:
        proposal = Service.propose_analysis(request)
        approval = default_service().submit(module_id=4, action_type=proposal.action_type, user_id=tenant.tenant_id, payload=proposal.model_dump(mode="json"))
        return proposal.model_copy(update={"approval_id": approval["id"], "status": "pending"})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/surveillance/ingest")
async def ingest_surveillance(request:SurveillanceIngestRequest,tenant:TenantContext=Depends(require_tenant)):
    from app.core.embeddings import get_embedding_provider
    from .surveillance import SurveillancePipeline,SurveillanceRepository
    return await SurveillancePipeline(SurveillanceRepository(tenant.tenant_id),get_embedding_provider(request.embedding_provider)).ingest(request.papers)

@router.get("/surveillance/clusters")
def surveillance_clusters(threshold:float=.72,tenant:TenantContext=Depends(require_tenant)):
    from .surveillance import SurveillancePipeline,SurveillanceRepository
    return {"clusters":SurveillancePipeline(SurveillanceRepository(tenant.tenant_id),None).clusters(threshold)}

@router.get("/surveillance/gaps",response_model=list[GapEvidenceOut])
def surveillance_gaps(tenant:TenantContext=Depends(require_tenant)):
    from .surveillance import SurveillancePipeline,SurveillanceRepository
    return [GapEvidenceOut(**x.__dict__) for x in SurveillancePipeline(SurveillanceRepository(tenant.tenant_id),None).gaps()]

# Environmental domain calculators, ledger rows 1660-1709.
@router.get("/environmental-1660-1709/methods")
def environmental_methods_1660_1709():
    from .environmental_1660_1709 import ROWS
    return [{"method":m,"feature_row":r} for m,r in ROWS.items()]

@router.post("/environmental-1660-1709/analyze")
def environmental_analyze_1660_1709(payload:dict):
    from .environmental_1660_1709 import run
    try:return run(payload.get("method",""),payload.get("data",{}))
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

@router.get('/quant-methods-185-234')
def quant_methods_185_234():
    from .quant_methods_185_234 import ROWS
    return [{'row_id':i,'method':m} for i,m in ROWS.items()]
@router.post('/quant-methods-185-234/{row_id}')
def quant_method_185_234(row_id:int,payload:dict):
    from .quant_methods_185_234 import QuantError,run
    try:return run(row_id,payload)
    except QuantError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

from .core_spec_round6 import router as core_spec_round6_router
router.include_router(core_spec_round6_router)

@router.post('/expanded-211-258/{row_id}')
def expanded_211_258(row_id:int,payload:dict):
 from .expanded_211_258 import run
 try:return run(row_id,payload)
 except (ValueError,TypeError,KeyError) as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

# Owner-ledger environmental and sustainability analyses, rows 1660-1709.
from typing import Any
from pydantic import BaseModel, Field
from .environmental_1660_1709 import execute_environmental_row
class Environmental1660To1709In(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
@router.post('/environmental-1660-1709/{row_id}')
def environmental_1660_1709_route(row_id:int, body:Environmental1660To1709In, tenant:TenantContext=Depends(require_tenant)):
    try:
        result=execute_environmental_row(row_id,body.data)
        return {'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id,**result}
    except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:
        raise HTTPException(422,str(exc)) from exc

from pydantic import BaseModel
from fastapi.responses import Response
class ReproducibilityBundleIn(BaseModel):
 title:str;code:str;language:str='python';inputs:dict={};parameters:dict={};seed:int=0;expected_outputs:list[str]=[];dependencies:list[str]=[];source_urls:list[str]=[]
@router.post('/reproducibility/bundle')
def reproducibility_bundle(body:ReproducibilityBundleIn):
 from .reproducibility_bundle import build_bundle
 try:payload,manifest=build_bundle(**body.model_dump())
 except ValueError as e:raise HTTPException(422,str(e))
 return Response(payload,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="atlas-reproducibility-bundle.zip"','X-Atlas-Bundle-SHA256':manifest['bundle_sha256']})
