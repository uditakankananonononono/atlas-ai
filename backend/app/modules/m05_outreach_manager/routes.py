"""FastAPI routes for the Outreach Manager module."""

from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.approvals import approvals

from .schemas import (
    CampaignDraftRequest,
    Contact,
    ContactChange,
    ContactCreate,
    DraftEmail,
    FollowUpRequest,
    ProfessorCandidate,
    ProfessorSearchRequest,
    ProposedAction,
)
from .service import (
    ContactNotFoundError,
    InMemoryContactRepository,
    SemanticScholarClient,
    Service,
    UpstreamServiceError,
)

router = APIRouter(prefix="/outreach-manager", tags=["outreach-manager"])
_repository = InMemoryContactRepository()


async def get_service() -> AsyncIterator[Service]:
    """Build request-scoped network dependencies and close them deterministically."""

    async with httpx.AsyncClient(timeout=20) as client:
        yield Service(_repository, approvals, SemanticScholarClient(client))


@router.post("/contacts", response_model=Contact, status_code=status.HTTP_201_CREATED)
def create_contact(data: ContactCreate, service: Service = Depends(get_service)) -> Contact:
    return service.create_contact(data)


@router.put("/contacts/{contact_id}", response_model=Contact)
def update_contact(
    contact_id: str, data: ContactCreate, service: Service = Depends(get_service)
) -> Contact:
    try:
        return service.update_contact(contact_id, data)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc


@router.get("/contacts/{contact_id}", response_model=Contact)
def get_contact(contact_id: str, service: Service = Depends(get_service)) -> Contact:
    try:
        return service.get_contact(contact_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc


@router.get("/contacts/{contact_id}/changes", response_model=list[ContactChange])
def contact_changes(
    contact_id: str, service: Service = Depends(get_service)
) -> list[ContactChange]:
    try:
        return service.contact_changes(contact_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc


@router.post("/professors/search", response_model=list[ProfessorCandidate])
async def search_professors(
    request: ProfessorSearchRequest, service: Service = Depends(get_service)
) -> list[ProfessorCandidate]:
    try:
        return await service.search_professors(request.query, request.limit)
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/campaigns/draft", response_model=DraftEmail)
async def draft_campaign(
    request: CampaignDraftRequest, service: Service = Depends(get_service)
) -> DraftEmail:
    try:
        return await service.draft_campaign(request)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/campaigns/propose-send", response_model=ProposedAction)
def propose_send(draft: DraftEmail, service: Service = Depends(get_service)) -> ProposedAction:
    try:
        return service.propose_send(draft)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/follow-ups/draft", response_model=DraftEmail)
async def draft_follow_up(
    request: FollowUpRequest, service: Service = Depends(get_service)
) -> DraftEmail:
    try:
        return await service.draft_follow_up(request)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/follow-ups/propose-send", response_model=ProposedAction)
def propose_follow_up(
    draft: DraftEmail, service: Service = Depends(get_service)
) -> ProposedAction:
    try:
        return service.propose_follow_up(draft)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
