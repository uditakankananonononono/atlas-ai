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
            review_state_capturer=_capture_review_state,
        )


def _capture_review_state(approval_id: str) -> None:
    from app.modules.m00_approval_center.impact import capture_review_state
    from app.modules.m00_approval_center.service import default_service

    capture_review_state(default_service(), approval_id)


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

from .promise_reconciliation import PromiseReconciliationRequest, reconcile_promise_state


@router.post('/promise-state-reconciliation/verify')
def promise_state_reconciliation(
    body: PromiseReconciliationRequest,
    tenant: TenantContext = Depends(require_tenant),
):
    try:
        return {'tenant_id': tenant.tenant_id, **reconcile_promise_state(body)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

from .promise_persistence import PersistPromiseReconciliationRequest,persist_reconciliation

def get_promise_repository(tenant:TenantContext=Depends(require_tenant)):
    return SqlEmailRepository(tenant.tenant_id)

@router.post('/promise-state-reconciliation/persist')
def persist_promise_state_reconciliation(body:PersistPromiseReconciliationRequest,tenant:TenantContext=Depends(require_tenant),repository=Depends(get_promise_repository)):
    try:return {'tenant_id':tenant.tenant_id,**persist_reconciliation(body,repository)}
    except ValueError as error:raise HTTPException(status_code=409,detail=str(error)) from error
from .authenticated_reconciliation import VerifyReconciliationEvidence,verify_reconciliation_evidence
from .reviewer_key_registry import KeyGovernanceError,ReviewerKeyRegistry,RegisterReviewerKey,RetireReviewerKey,RotateReviewerKey
def get_reviewer_key_registry(tenant:TenantContext=Depends(require_tenant)):return ReviewerKeyRegistry(tenant.tenant_id,actor_id=tenant.actor_id,roles=tenant.roles)
@router.post('/promise-state-reconciliation/evidence/verify')
def authenticated_reconciliation_evidence(body:VerifyReconciliationEvidence,tenant:TenantContext=Depends(require_tenant),registry=Depends(get_reviewer_key_registry)):
 try:return {'tenant_id':tenant.tenant_id,**verify_reconciliation_evidence(body,registry.active_public_key)}
 except ValueError as error:raise HTTPException(422,str(error)) from error
def _key_errors(fn):
 try:return fn()
 except KeyGovernanceError as error:raise HTTPException(403,str(error)) from error
 except LookupError as error:raise HTTPException(404,str(error)) from error
 except ValueError as error:raise HTTPException(409,str(error)) from error
@router.post('/promise-state-reconciliation/reviewer-keys')
def register_reviewer_key(body:RegisterReviewerKey,tenant:TenantContext=Depends(require_tenant),registry=Depends(get_reviewer_key_registry)):
 row=_key_errors(lambda:registry.register(body))
 return {'tenant_id':tenant.tenant_id,'reviewer_id':row.reviewer_id,'key_id':row.key_id,'fingerprint_sha256':row.fingerprint_sha256,'active':row.active,'enrolled_by':row.enrolled_by,'boundary':'Key enrolled with proof-of-possession by the reviewer or an atlas-admin; only active registry keys verify attestations.'}
@router.get('/promise-state-reconciliation/reviewer-keys')
def list_reviewer_keys(reviewer_id:str|None=None,registry=Depends(get_reviewer_key_registry)):return registry.list_keys(reviewer_id)
@router.get('/promise-state-reconciliation/reviewer-keys/{reviewer_id}/events')
def reviewer_key_events(reviewer_id:str,registry=Depends(get_reviewer_key_registry)):return registry.events(reviewer_id)
@router.post('/promise-state-reconciliation/reviewer-keys/{reviewer_id}/rotate')
def rotate_reviewer_key(reviewer_id:str,body:RotateReviewerKey,tenant:TenantContext=Depends(require_tenant),registry=Depends(get_reviewer_key_registry)):
 return {'tenant_id':tenant.tenant_id,**_key_errors(lambda:registry.rotate(reviewer_id,body))}
@router.post('/promise-state-reconciliation/reviewer-keys/{reviewer_id}/{key_id}/retire')
def retire_reviewer_key(reviewer_id:str,key_id:str,body:RetireReviewerKey|None=None,tenant:TenantContext=Depends(require_tenant),registry=Depends(get_reviewer_key_registry)):
 row=_key_errors(lambda:registry.retire(reviewer_id,key_id,(body.reason if body else 'retired')))
 return {'tenant_id':tenant.tenant_id,'reviewer_id':reviewer_id,'key_id':key_id,'active':row.active,'retired_at':row.retired_at,'retire_reason':row.retire_reason}
from .source_message_persistence import PersistSourceMessage,persist_source_message
from .source_message_store import SourceMessageStore
def get_source_message_store(tenant:TenantContext=Depends(require_tenant)):return SourceMessageStore(tenant.tenant_id)
@router.post('/promise-state-reconciliation/source-messages/persist')
def persist_promise_source_message(body:PersistSourceMessage,tenant:TenantContext=Depends(require_tenant),store=Depends(get_source_message_store)):
 try:return {'tenant_id':tenant.tenant_id,**persist_source_message(body,store)}
 except ValueError as error:raise HTTPException(409,str(error)) from error
