"""FastAPI routes for the Email Assistant module."""

import os
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.context import TenantContext, require_tenant
from app.core.approvals import approvals
from app.core.token_crypto import TokenCipher, TokenCryptoError

from .gmail import HttpxGmailClient, UpstreamServiceError
from .schemas import (
    EmailCategory,
    EmailDraftView,
    EmailMessageView,
    GmailAccountView,
    GmailConnectRequest,
    IngestResult,
    PriorityMessage,
    PubSubPush,
    WatchRenewalResult,
)
from .service import AccountNotFoundError, PubSubVerificationError, Service
from .sql_repository import SqlEmailRepository

router = APIRouter(prefix="/email-assistant", tags=["email-assistant"])


async def get_service(tenant: TenantContext = Depends(require_tenant)) -> AsyncIterator[Service]:
    """Build request-scoped clients and close them deterministically."""
    try:
        cipher = TokenCipher(tenant.tenant_id)
    except TokenCryptoError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    async with httpx.AsyncClient(timeout=30) as client:
        yield Service(
            SqlEmailRepository(tenant.tenant_id),
            approvals,
            HttpxGmailClient(client),
            client,
            cipher=cipher,
            google_client_id=os.getenv("ATLAS_GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("ATLAS_GOOGLE_CLIENT_SECRET", ""),
            pubsub_verification_token=os.getenv("ATLAS_PUBSUB_VERIFICATION_TOKEN", ""),
        )


@router.post("/connect", response_model=GmailAccountView, status_code=status.HTTP_201_CREATED)
async def connect_account(
    request: GmailConnectRequest, service: Service = Depends(get_service)
) -> GmailAccountView:
    try:
        return await service.connect_account(request.auth_code, request.redirect_uri)
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/accounts", response_model=list[GmailAccountView])
def list_accounts(service: Service = Depends(get_service)) -> list[GmailAccountView]:
    return service.list_accounts()


@router.post("/pubsub", response_model=IngestResult)
async def pubsub_push(
    envelope: PubSubPush,
    token: str = Query(default=""),
    service: Service = Depends(get_service),
) -> IngestResult:
    """Google Cloud Pub/Sub push endpoint. The verification token is the one
    configured when the push subscription was created."""
    try:
        return await service.handle_push(envelope.model_dump(), token)
    except PubSubVerificationError as exc:
        raise HTTPException(status_code=403, detail="invalid verification token") from exc
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail="gmail account not connected") from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/watches/renew", response_model=WatchRenewalResult)
async def renew_watches(
    topic: str = Query(min_length=3), service: Service = Depends(get_service)
) -> WatchRenewalResult:
    try:
        return await service.renew_watches(topic)
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/messages", response_model=list[EmailMessageView])
def list_messages(
    category: EmailCategory | None = None,
    service: Service = Depends(get_service),
) -> list[EmailMessageView]:
    return service.list_messages(category=category)


@router.get("/action-items")
def list_action_items(service: Service = Depends(get_service)) -> list[dict]:
    return service.list_action_items()


@router.get("/drafts", response_model=list[EmailDraftView])
def list_drafts(service: Service = Depends(get_service)) -> list[EmailDraftView]:
    return service.list_drafts()


@router.get("/priority", response_model=list[PriorityMessage])
def priority_inbox(service: Service = Depends(get_service)) -> list[PriorityMessage]:
    return service.priority_inbox()


@router.get("/follow-ups")
def follow_ups_due(
    within_hours: int = Query(default=48, ge=1, le=720),
    service: Service = Depends(get_service),
) -> list[dict]:
    return service.follow_ups_due(within_hours=within_hours)

from .promises import PromiseTrackerRequest, track_promises

@router.post('/promise-tracker')
def promise_tracker(body: PromiseTrackerRequest, tenant: TenantContext = Depends(require_tenant)):
    try:
        return {'tenant_id': tenant.tenant_id, **track_promises(body)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
