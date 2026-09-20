"""FastAPI routes local to the Competition Manager module."""

from uuid import uuid4

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
    competition_id: str, request: FormFillProposalRequest, service: Service = Depends(get_service)
) -> ProposedAction:
    """Queue browser staging behind the shared approval boundary."""
    try:
        proposal = service.propose_form_fill(competition_id, request)
    except CompetitionNotFoundError as error:
        raise HTTPException(status_code=404, detail="competition not found") from error
    approval = approvals.put(
        ApprovalRequest(
            id=str(uuid4()),
            module_id=2,
            action_type=proposal.action_type,
            payload=proposal.payload,
        )
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
