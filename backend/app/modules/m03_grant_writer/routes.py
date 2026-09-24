"""FastAPI routes local to the grant-writer module."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel,Field
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


def get_service(tenant: TenantContext = Depends(require_tenant)) -> Service:
    """Construct a tenant-bound service with shared dependencies."""
    from app.core.approvals import approvals

    return Service(approval_sink=approvals, tenant_id=tenant.tenant_id)


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

class ComplianceLintIn(BaseModel):
 proposal:str=Field(min_length=20);guidelines:str=Field(min_length=20);budget_total:float|None=Field(default=None,ge=0);attachments:list[str]=Field(default_factory=list)
@router.post('/compliance/lint')
def compliance_lint(body:ComplianceLintIn):
 from .compliance import lint_proposal
 try:return lint_proposal(**body.model_dump())
 except ValueError as e:raise HTTPException(422,str(e))


# -- agency schema packs ---------------------------------------------------------
class SchemaPackDocIn(BaseModel):
    pages: int | None = Field(default=None, ge=0, le=1000); text: str | None = Field(default=None, max_length=200000); attached: bool = True
class SchemaPackCheckIn(BaseModel):
    field: str | None = Field(default=None, max_length=200); documents: dict[str, SchemaPackDocIn] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict); version: str | None = None


@router.get('/schema-packs')
def schema_pack_catalog(tenant: TenantContext = Depends(require_tenant)):
    from .schema_packs import catalog
    return catalog()


@router.get('/schema-packs/{agency}/{program}')
def schema_pack(agency: str, program: str, version: str | None = None, tenant: TenantContext = Depends(require_tenant)):
    from .schema_packs import PackNotFound, get_pack
    try: return get_pack(agency, program, version)
    except PackNotFound as e: raise HTTPException(404, str(e)) from e


@router.post('/schema-packs/{agency}/{program}/check')
def schema_pack_check(agency: str, program: str, body: SchemaPackCheckIn, tenant: TenantContext = Depends(require_tenant)):
    from datetime import datetime, timezone
    from .schema_packs import PackNotFound, check, get_pack
    try: pack = get_pack(agency, program, body.version)
    except PackNotFound as e: raise HTTPException(404, str(e)) from e
    sub = body.model_dump(exclude={"version"}); sub["documents"] = {k: v.model_dump() for k, v in body.documents.items()}
    return check(pack, sub, now=datetime.now(timezone.utc))


@router.get('/schema-packs/{agency}/{program}/diff')
def schema_pack_diff(agency: str, program: str, from_version: str, to_version: str, tenant: TenantContext = Depends(require_tenant)):
    from .schema_packs import PackNotFound, diff, get_pack
    try: return diff(get_pack(agency, program, from_version), get_pack(agency, program, to_version))
    except PackNotFound as e: raise HTTPException(404, str(e)) from e


@router.post('/schema-packs/{agency}/{program}/verify-source')
async def schema_pack_verify(agency: str, program: str, version: str | None = None, tenant: TenantContext = Depends(require_tenant)):
    """Read-only re-read of the public official call; reports anchors that changed."""
    import httpx
    from .schema_packs import PackNotFound, get_pack, verify_source
    try: pack = get_pack(agency, program, version)
    except PackNotFound as e: raise HTTPException(404, str(e)) from e
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "Atlas-grant-pack-verifier"}) as client:
        try:
            resp = await client.get(pack["source_url"]); resp.raise_for_status()
        except httpx.HTTPError as e: raise HTTPException(502, f"could not read official source: {e.__class__.__name__}") from e
    return verify_source(pack, lambda _url: resp.text)
