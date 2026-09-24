"""FastAPI routes local to the Competition Manager module."""

from uuid import uuid4

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from app.core.approvals import approvals
from app.auth.context import TenantContext, require_tenant
from app.core.models import ApprovalRequest
from app.core.providers import generate

from .schemas import (
    Competition,
    CompetitionCreate,
    DraftRequest,
    DraftResult,
    FormFillProposalRequest,
    ProposedAction,
    StatusUpdate,
    ApplicationAnswersIn, IntegratedApplicationIn,
)
from .service import (
    CompetitionNotFoundError,
    RuleExtractionError,
    Service,
    UnsafeStatusTransitionError,
)

router = APIRouter(prefix="/competition-manager", tags=["competition-manager"])



def get_service(tenant: TenantContext = Depends(require_tenant)) -> Service:
    from .sql_repository import SqlCompetitionRepository
    return Service(generator=generate, repository=SqlCompetitionRepository(tenant.tenant_id))

@router.post("/competitions", response_model=Competition)
async def create_competition(request: CompetitionCreate, service: Service = Depends(get_service)) -> Competition:
    """Create a competition from supplied official rule text."""
    try:
        return await service.create_competition(request)
    except RuleExtractionError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/competitions/{competition_id}", response_model=Competition)
def get_competition(competition_id: str, service: Service = Depends(get_service)) -> Competition:
    """Read competition state."""
    try:
        return service.get_competition(competition_id)
    except CompetitionNotFoundError as error:
        raise HTTPException(status_code=404, detail="competition not found") from error


@router.post("/competitions/{competition_id}/drafts", response_model=DraftResult)
async def draft_field(competition_id: str, request: DraftRequest, service: Service = Depends(get_service)) -> DraftResult:
    """Generate a review-required draft through the shared BYOK provider."""
    try:
        return await service.draft_field(competition_id, request)
    except CompetitionNotFoundError as error:
        raise HTTPException(status_code=404, detail="competition not found") from error


@router.post(
    "/competitions/{competition_id}/form-fill-proposals",
    response_model=ProposedAction,
)
def propose_form_fill(
    competition_id: str, request: FormFillProposalRequest, tenant: TenantContext = Depends(require_tenant),
    service: Service = Depends(get_service)
) -> ProposedAction:
    """Queue browser staging behind the shared approval boundary."""
    try:
        proposal = service.propose_form_fill(competition_id, request)
    except CompetitionNotFoundError as error:
        raise HTTPException(status_code=404, detail="competition not found") from error
    proposal.payload["tenant_id"] = tenant.tenant_id
    approval = approvals.put(
        ApprovalRequest(
            id=str(uuid4()),
            module_id=2,
            action_type=proposal.action_type,
            payload=proposal.payload,
        ),
        user_id=tenant.tenant_id,
    )
    proposal.payload["approval_id"] = approval.id
    proposal.payload["browser_agent_path"] = "/api/v1/browser-agent/submit/request"
    proposal.payload["required_preview"] = "full-page screenshot plus exact field values"
    return proposal


@router.post("/competitions/{competition_id}/status", response_model=Competition)
def update_status(competition_id: str, request: StatusUpdate, service: Service = Depends(get_service)) -> Competition:
    """Record a status update from official API, email, or manual evidence."""
    try:
        return service.update_status(competition_id, request.evidence)
    except CompetitionNotFoundError as error:
        raise HTTPException(status_code=404, detail="competition not found") from error
    except UnsafeStatusTransitionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/competitions/{competition_id}/answers/review-package")
async def prepare_humanized_answers(competition_id:str,request:ApplicationAnswersIn,tenant:TenantContext=Depends(require_tenant)):
    from .application_pipeline import ApplicationAnswerPipeline
    from .humanize import NaturalVoiceService
    return await ApplicationAnswerPipeline(NaturalVoiceService(generate),approvals,tenant.tenant_id).prepare_review(competition_id,request.answers,request.provider)


@router.post("/competitions/{competition_id}/integrated-application")
async def integrated_application(competition_id:str,request:IntegratedApplicationIn,tenant:TenantContext=Depends(require_tenant)):
    from app.core.embeddings import get_embedding_provider
    from .profile_corpus import ProfileCorpus
    from .grounded_drafting import GroundedApplicationDrafter
    from .humanize import NaturalVoiceService
    from .integrated_application import IntegratedApplicationFlow
    flow=IntegratedApplicationFlow(ProfileCorpus(tenant.tenant_id,get_embedding_provider(request.embedding_provider)),GroundedApplicationDrafter(generate),NaturalVoiceService(generate),approvals,tenant.tenant_id)
    try:return await flow.prepare(competition_id,request.official_url,[x.model_dump() for x in request.fields],request.provider)
    except ValueError as e:raise HTTPException(422,str(e))

@router.get('/expanded-owner-132-179')
def expanded_owner_catalog_132_179():
    from .expanded_owner_132_179 import ROWS
    return [{'row_id':i,'requirement':x} for i,x in ROWS.items()]
@router.post('/expanded-owner-132-179/{row_id}')
def expanded_owner_run_132_179(row_id:int,payload:dict):
    from .expanded_owner_132_179 import ExpandedM2Error,run
    try:return run(row_id,payload)
    except ExpandedM2Error as exc:raise HTTPException(422,detail=str(exc)) from exc

from .core_spec_round6 import router as core_spec_round6_router
router.include_router(core_spec_round6_router)

# End-to-end opportunity application browser workflow (M1/M2/M13).
# Imported for side effects: it declares its routes on this router directly.
from . import application_routes as _application_workflow_routes  # noqa: F401


class _EvidenceField(BaseModel):
    draft: str = Field(min_length=1, max_length=20000)
    sources: list[dict] = Field(default_factory=list, max_length=50)
    source_ids: list[int] = Field(default_factory=list, max_length=50)
    question: str | None = Field(default=None, max_length=4000)
    requirements: str = Field(default="", max_length=4000)
    evidence_limit: int = Field(default=8, ge=1, le=50)


class _EvidenceIn(BaseModel):
    fields: dict[str, _EvidenceField] = Field(min_length=1, max_length=40)
    embedding_provider: str | None = None


@router.post("/evidence-completeness")
async def evidence_completeness(body: _EvidenceIn, tenant: TenantContext = Depends(require_tenant)) -> dict:
    """Score drafted answers: each claim must cite a supporting owner source or say [NEEDS INPUT].

    Sources come from the caller, or from this tenant's stored profile corpus by
    ``source_ids`` (stable) or by re-running the drafter's ``question`` query."""
    from .evidence import score_from_corpus
    from .profile_corpus import ProfileCorpus
    fields = {k: v.model_dump() for k, v in body.fields.items()}
    needs_embed = any(f["question"] and not f["sources"] and not f["source_ids"] for f in fields.values())
    embedder = None
    if needs_embed:
        from app.core.embeddings import get_embedding_provider
        embedder = get_embedding_provider(body.embedding_provider)
    return await score_from_corpus(ProfileCorpus(tenant.tenant_id, embedder), fields)
