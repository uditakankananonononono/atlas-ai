"""FastAPI routes local to the grant-writer module."""

from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import TenantContext, require_tenant

from .schemas import (
    BudgetRequest,
    BudgetResponse,
    ExportRequest,
    ProposalRequest,
    ProposalResponse,
    ProposedExportResponse,
    SuccessAnalysisRequest,
    SuccessAnalysisResponse,
    CorpusIngestRequest, CorpusIngestResponse, CorpusSearchResult,
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


@router.post("/corpus/ingest",response_model=CorpusIngestResponse)
async def ingest_funded_corpus(request:CorpusIngestRequest,tenant:TenantContext=Depends(require_tenant)):
    from .corpus import BulkCorpusIngester,FundedCorpusRepository
    result=await BulkCorpusIngester(FundedCorpusRepository(tenant.tenant_id)).ingest(request.query,request.target)
    return CorpusIngestResponse(**result.__dict__,caveat="Official APIs returned fewer unique awards than target; no records were invented." if not result.complete else "Target met with unique official award records.")

@router.get("/corpus/search",response_model=list[CorpusSearchResult])
def search_funded_corpus(query:str,tenant:TenantContext=Depends(require_tenant)):
    from .corpus import FundedCorpusRepository
    return [CorpusSearchResult(**x.__dict__) for x in FundedCorpusRepository(tenant.tenant_id).search_text(query)]

@router.get('/expanded-owner-180-210')
def expanded_owner_catalog_180_210():
    from .expanded_owner_180_210 import ROWS
    return [{'row_id':i,'requirement':x} for i,x in ROWS.items()]
@router.post('/expanded-owner-180-210/{row_id}')
def expanded_owner_run_180_210(row_id:int,payload:dict):
    from .expanded_owner_180_210 import ExpandedM3Error,run
    try:return run(row_id,payload)
    except ExpandedM3Error as exc:raise HTTPException(422,detail=str(exc)) from exc

from .core_spec_round6 import router as core_spec_round6_router
router.include_router(core_spec_round6_router)
