"""FastAPI routes for the Research Scientist module."""

from fastapi import APIRouter, HTTPException
from app.core.providers import ProviderError
from .schemas import (
    AnalysisProposalRequest,
    HypothesisRequest,
    HypothesisResponse,
    ProposedAnalysis,
    SurveillanceRequest,
    SurveillanceResponse,
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
def propose_analysis(request: AnalysisProposalRequest) -> ProposedAnalysis:
    """Create an approval-gated sandbox execution proposal; never execute code here."""
    try:
        return Service.propose_analysis(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
