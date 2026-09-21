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
async def draft_hypothesis(request: HypothesisRequest) -> HypothesisResponse:
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
