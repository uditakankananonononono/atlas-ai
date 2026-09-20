"""FastAPI routes local to the grant-writer module."""

from fastapi import APIRouter, Depends

from .schemas import (
    BudgetRequest,
    BudgetResponse,
    ExportRequest,
    ProposalRequest,
    ProposalResponse,
    ProposedExportResponse,
    SuccessAnalysisRequest,
    SuccessAnalysisResponse,
)
from .service import Service

router = APIRouter(prefix="/grant-writer", tags=["grant-writer"])


def get_service() -> Service:
    """Construct the service with shared dependencies at request time."""
    from app.core.approvals import approvals

    return Service(approval_sink=approvals)


@router.post("/proposals", response_model=ProposalResponse)
async def generate_proposal(request: ProposalRequest, service: Service = Depends(get_service)) -> ProposalResponse:
    """Generate an auditable, review-required proposal draft."""
    return await service.generate_proposal(request)


@router.post("/budgets", response_model=BudgetResponse)
def build_budget(request: BudgetRequest, service: Service = Depends(get_service)) -> BudgetResponse:
    """Calculate a proposed budget from explicit line-item inputs."""
    return service.build_budget(request)


@router.post("/success-analysis", response_model=SuccessAnalysisResponse)
def analyze_success(
    request: SuccessAnalysisRequest, service: Service = Depends(get_service)
) -> SuccessAnalysisResponse:
    """Find language gaps against permissioned funded examples."""
    return service.analyze_success(request)


@router.post("/exports", response_model=ProposedExportResponse, status_code=202)
def propose_export(request: ExportRequest, service: Service = Depends(get_service)) -> ProposedExportResponse:
    """Queue document generation for explicit approval instead of executing it."""
    return service.propose_export(request)
