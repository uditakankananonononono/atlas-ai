"""FastAPI routes for the Outreach Manager module."""

import os
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.approvals import approvals
from app.auth.context import TenantContext, require_tenant

from .campaigns import CampaignNotFoundError, CampaignService, CampaignStateError, MessageNotFoundError
from .delivery import (
    DeliveryApprovalError,
    DeliverySendError,
    DeliveryService,
    ModuleZeroApprovalGate,
    SmtpMailSender,
)
from .discovery import (
    DiscoveryError,
    LabDiscoveryService,
    LabPage,
    LabPageCollector,
    LabRegistry,
    RobotsDisallowedError,
)
from .enrichment import (
    ClearbitClient,
    EmailFinderResult,
    EmailVerification,
    EnrichmentNotConfiguredError,
    EnrichmentService,
    HunterIoClient,
    PersonProfile,
    UpstreamEnrichmentError,
)
from .planning import (
    OutreachPlan,
    OutreachScope,
    PRTarget,
    ProjectSummary,
    ProposalDraft,
    ScopeViolationError,
    build_micro_survey,
    draft_proposal,
    plan_campaign,
    plan_pr_outreach,
)
from .schemas import (
    CampaignCreateRequest,
    CampaignDraftRequest,
    CampaignPlanRequest,
    CampaignStatusUpdate,
    Contact,
    ContactChange,
    ContactCreate,
    DecisionRecordRequest,
    DraftEmail,
    EnrichEmailRequest,
    FailureRecordRequest,
    FollowUpDraftRequest,
    FollowUpRequest,
    LabCollectRequest,
    LabSearchRequest,
    MessageDraftRequest,
    PRPlanRequest,
    ProfessorCandidate,
    ProfessorSearchRequest,
    ProposalDraftRequest,
    ProposedAction,
    ReplyRecordRequest,
    SurveyPlanRequest,
)
from .service import (
    ContactNotFoundError,
    SemanticScholarClient,
    Service,
    UpstreamServiceError,
)
from .campaigns import Campaign, MessageEvent, OutreachMessage
from .discovery import LabEntry

router = APIRouter(prefix="/outreach-manager", tags=["outreach-manager"])


class Container:
    """Request-scoped services sharing one HTTP client and tenant context."""

    def __init__(self, tenant_id: str, client: httpx.AsyncClient) -> None:
        from .sql_repository import SqlCampaignRepository, SqlContactRepository

        contacts = SqlContactRepository(tenant_id)
        self.outreach = Service(contacts, approvals, SemanticScholarClient(client), tenant_id=tenant_id)
        self.enrichment = EnrichmentService(
            contacts,
            HunterIoClient(client, os.getenv("HUNTER_API_KEY")),
            ClearbitClient(client, os.getenv("CLEARBIT_API_KEY")),
        )
        self.discovery = LabDiscoveryService(LabRegistry.load(), LabPageCollector(client))
        self.campaigns = CampaignService(SqlCampaignRepository(tenant_id), contacts, approvals, tenant_id=tenant_id)
        self.contacts = contacts
        sender = _smtp_from_env()
        self.delivery = (
            DeliveryService(self.campaigns, ModuleZeroApprovalGate(approvals), sender)
            if sender is not None
            else None
        )


def _smtp_from_env() -> SmtpMailSender | None:
    """Build the real SMTP sender from environment, or None when unset.

    ATLAS_SMTP_HOST plus ATLAS_SMTP_FROM are the minimum; PORT/USERNAME/
    PASSWORD are optional. Partial configuration fails loudly at send
    time via DeliveryService, never silently.
    """
    host = os.getenv("ATLAS_SMTP_HOST")
    from_address = os.getenv("ATLAS_SMTP_FROM")
    if not host or not from_address:
        return None
    return SmtpMailSender(
        host=host,
        from_address=from_address,
        port=int(os.getenv("ATLAS_SMTP_PORT", "587")),
        username=os.getenv("ATLAS_SMTP_USERNAME"),
        password=os.getenv("ATLAS_SMTP_PASSWORD"),
    )


async def get_container(tenant: TenantContext = Depends(require_tenant)) -> AsyncIterator[Container]:
    """Build request-scoped network dependencies and close them deterministically."""

    async with httpx.AsyncClient(timeout=20) as client:
        yield Container(tenant.tenant_id, client)


async def get_service(container: Container = Depends(get_container)) -> Service:
    """Backward-compatible dependency for the original endpoints."""

    return container.outreach


def _scope(raw: dict | None) -> OutreachScope | None:
    if raw is None:
        return None
    try:
        return OutreachScope(**raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid scope: {exc}") from exc


# --- contacts (original surface) --------------------------------------------


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


# --- enrichment ----------------------------------------------------------------


@router.post("/contacts/{contact_id}/verify-email", response_model=EmailVerification)
async def verify_email(
    contact_id: str, container: Container = Depends(get_container)
) -> EmailVerification:
    try:
        return await container.enrichment.verify_contact_email(contact_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except EnrichmentNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamEnrichmentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/contacts/{contact_id}/enrich-email", response_model=EmailFinderResult)
async def enrich_email(
    contact_id: str,
    request: EnrichEmailRequest,
    container: Container = Depends(get_container),
) -> EmailFinderResult:
    try:
        return await container.enrichment.find_contact_email(contact_id, request.domain)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except EnrichmentNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamEnrichmentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/contacts/{contact_id}/enrich-profile", response_model=PersonProfile)
async def enrich_profile(
    contact_id: str, container: Container = Depends(get_container)
) -> PersonProfile:
    try:
        return await container.enrichment.enrich_contact_profile(contact_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except EnrichmentNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamEnrichmentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# --- lab discovery --------------------------------------------------------------


@router.post("/labs/search", response_model=list[LabEntry])
def search_labs(
    request: LabSearchRequest, container: Container = Depends(get_container)
) -> list[LabEntry]:
    return container.discovery.search_labs(query=request.query, topics=request.topics, limit=request.limit)


@router.post("/labs/collect", response_model=LabPage)
async def collect_lab(
    request: LabCollectRequest, container: Container = Depends(get_container)
) -> LabPage:
    try:
        return await container.discovery.collect_lab_page(request.url)
    except RobotsDisallowedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/labs/discover-contacts")
async def discover_lab_contacts(
    request: LabCollectRequest, container: Container = Depends(get_container)
) -> dict:
    try:
        return await container.discovery.discover_lab_contacts(request.url)
    except RobotsDisallowedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# --- professor discovery (original surface) -------------------------------------


@router.post("/professors/search", response_model=list[ProfessorCandidate])
async def search_professors(
    request: ProfessorSearchRequest, service: Service = Depends(get_service)
) -> list[ProfessorCandidate]:
    try:
        return await service.search_professors(request.query, request.limit)
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# --- legacy draft/propose endpoints (original surface, unchanged) -----------------


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


# --- campaigns: durable draft/review/follow-up pipeline ---------------------------


@router.post("/campaigns", response_model=Campaign, status_code=status.HTTP_201_CREATED)
def create_campaign(
    request: CampaignCreateRequest, container: Container = Depends(get_container)
) -> Campaign:
    try:
        return container.campaigns.create_campaign(
            project_id=request.project_id,
            name=request.name,
            goal=request.goal,
            audience=request.audience,
            max_follow_ups=request.max_follow_ups,
            follow_up_window_days=request.follow_up_window_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/campaigns", response_model=list[Campaign])
def list_campaigns(
    project_id: str | None = None, container: Container = Depends(get_container)
) -> list[Campaign]:
    return container.campaigns.campaigns.list_campaigns(project_id=project_id)


@router.get("/campaigns/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: str, container: Container = Depends(get_container)) -> Campaign:
    try:
        return container.campaigns.get_campaign(campaign_id)
    except CampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail="campaign not found") from exc


@router.post("/campaigns/{campaign_id}/status", response_model=Campaign)
def set_campaign_status(
    campaign_id: str,
    request: CampaignStatusUpdate,
    container: Container = Depends(get_container),
) -> Campaign:
    try:
        return container.campaigns.set_campaign_status(campaign_id, request.status)
    except CampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail="campaign not found") from exc


@router.get("/campaigns/{campaign_id}/messages", response_model=list[OutreachMessage])
def list_campaign_messages(
    campaign_id: str, container: Container = Depends(get_container)
) -> list[OutreachMessage]:
    try:
        container.campaigns.get_campaign(campaign_id)
    except CampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail="campaign not found") from exc
    return container.campaigns.campaigns.list_messages(campaign_id=campaign_id)


@router.get("/campaigns/{campaign_id}/delivery-report")
def campaign_delivery_report(
    campaign_id: str, container: Container = Depends(get_container)
) -> dict:
    if container.delivery is None:
        raise HTTPException(
            status_code=503,
            detail="delivery is not configured: set ATLAS_SMTP_HOST and ATLAS_SMTP_FROM",
        )
    try:
        container.campaigns.get_campaign(campaign_id)
    except CampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail="campaign not found") from exc
    return container.delivery.delivery_report(campaign_id)


@router.post("/campaigns/{campaign_id}/messages", response_model=OutreachMessage, status_code=status.HTTP_201_CREATED)
def add_message(
    campaign_id: str,
    request: MessageDraftRequest,
    container: Container = Depends(get_container),
) -> OutreachMessage:
    try:
        return container.campaigns.add_draft(
            campaign_id,
            request.contact_id,
            subject=request.subject,
            body=request.body,
            kind=request.kind,
            provider=request.provider,
            model=request.model,
        )
    except CampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail="campaign not found") from exc
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except CampaignStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# --- messages ---------------------------------------------------------------------


@router.get("/messages/{message_id}", response_model=OutreachMessage)
def get_message(message_id: str, container: Container = Depends(get_container)) -> OutreachMessage:
    try:
        return container.campaigns.get_message(message_id)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc


@router.get("/messages/{message_id}/events", response_model=list[MessageEvent])
def message_events(message_id: str, container: Container = Depends(get_container)) -> list[MessageEvent]:
    try:
        return container.campaigns.message_events(message_id)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc


@router.get("/messages/{message_id}/delivery-audit", response_model=list[MessageEvent])
def message_delivery_audit(
    message_id: str, container: Container = Depends(get_container)
) -> list[MessageEvent]:
    if container.delivery is None:
        raise HTTPException(
            status_code=503,
            detail="delivery is not configured: set ATLAS_SMTP_HOST and ATLAS_SMTP_FROM",
        )
    try:
        return container.delivery.delivery_audit(message_id)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc


@router.post("/messages/{message_id}/submit", response_model=OutreachMessage)
def submit_message(message_id: str, container: Container = Depends(get_container)) -> OutreachMessage:
    try:
        container.campaigns.submit_for_approval(message_id)
        return container.campaigns.get_message(message_id)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except CampaignStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/messages/{message_id}/decision", response_model=OutreachMessage)
def record_decision(
    message_id: str,
    request: DecisionRecordRequest,
    container: Container = Depends(get_container),
) -> OutreachMessage:
    try:
        return container.campaigns.record_decision(message_id, request.approved, actor=request.actor)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    except CampaignStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/messages/{message_id}/reply", response_model=OutreachMessage)
def record_reply(
    message_id: str,
    request: ReplyRecordRequest,
    container: Container = Depends(get_container),
) -> OutreachMessage:
    try:
        return container.campaigns.record_reply(
            message_id, thread_id=request.thread_id, snippet=request.snippet
        )
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    except CampaignStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/messages/{message_id}/failure", response_model=OutreachMessage)
def record_failure(
    message_id: str,
    request: FailureRecordRequest,
    container: Container = Depends(get_container),
) -> OutreachMessage:
    try:
        return container.campaigns.record_delivery_failure(
            message_id, reason=request.reason, bounced=request.bounced
        )
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    except CampaignStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/messages/{message_id}/send", response_model=OutreachMessage)
async def send_message(message_id: str, container: Container = Depends(get_container)) -> OutreachMessage:
    if container.delivery is None:
        raise HTTPException(
            status_code=503,
            detail="delivery is not configured: set ATLAS_SMTP_HOST and ATLAS_SMTP_FROM",
        )
    try:
        return await container.delivery.send_approved(message_id)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contact not found") from exc
    except DeliveryApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DeliverySendError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# --- follow-up automation -----------------------------------------------------------


@router.get("/follow-ups/due", response_model=list[OutreachMessage])
def due_follow_ups(container: Container = Depends(get_container)) -> list[OutreachMessage]:
    return container.campaigns.due_follow_ups()


@router.post("/messages/{message_id}/follow-up/draft", response_model=OutreachMessage)
async def draft_follow_up_message(
    message_id: str,
    request: FollowUpDraftRequest,
    container: Container = Depends(get_container),
) -> OutreachMessage:
    from app.core.providers import ProviderError, generate

    try:
        return await container.campaigns.draft_follow_up(
            message_id, generate, provider=request.provider, model=request.model
        )
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    except CampaignStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# --- planning -------------------------------------------------------------------------


@router.post("/plans/campaign", response_model=OutreachPlan)
def plan_campaign_endpoint(
    request: CampaignPlanRequest, container: Container = Depends(get_container)
) -> OutreachPlan:
    contacts = _load_contacts(container, request.contact_ids)
    try:
        return plan_campaign(
            goal=request.goal,
            audience=request.audience,
            contacts=contacts,
            scope=_scope(request.scope),
            manual_channels=request.manual_channels,
        )
    except ScopeViolationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans/micro-survey", response_model=OutreachPlan)
def plan_micro_survey_endpoint(
    request: SurveyPlanRequest, container: Container = Depends(get_container)
) -> OutreachPlan:
    contacts = _load_contacts(container, request.contact_ids)
    try:
        return build_micro_survey(
            goal=request.goal,
            contacts=contacts,
            question=request.question or "What tool do you wish you had?",
            scope=_scope(request.scope),
        )
    except ScopeViolationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans/pr", response_model=OutreachPlan)
def plan_pr_endpoint(
    request: PRPlanRequest, container: Container = Depends(get_container)
) -> OutreachPlan:
    try:
        targets = [PRTarget(**raw) for raw in request.targets]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid target: {exc}") from exc
    try:
        return plan_pr_outreach(
            goal=request.goal,
            targets=targets,
            embargo=request.embargo,
            scope=_scope(request.scope),
        )
    except ScopeViolationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/proposals/draft", response_model=ProposalDraft)
async def draft_proposal_endpoint(
    request: ProposalDraftRequest, container: Container = Depends(get_container)
) -> ProposalDraft:
    from app.core.providers import ProviderError, generate

    try:
        project = ProjectSummary(**request.project)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid project: {exc}") from exc
    try:
        return await draft_proposal(
            project=project,
            recipient_context=request.recipient_context,
            llm_generate=generate,
            provider=request.provider,
            model=request.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _load_contacts(container: Container, contact_ids: list[str]) -> list[Contact]:
    contacts = []
    for contact_id in contact_ids:
        contact = container.contacts.get(contact_id)
        if contact is None:
            raise HTTPException(status_code=404, detail=f"contact not found: {contact_id}")
        contacts.append(contact)
    return contacts


# --- growth planning endpoints (feature rows 417-450) -----------------------------

from . import growth as _growth
from .growth import BusinessArtifact, ElasticityResult, EvidenceItem, GrowthPlanError, LeadScoringResult
from .schemas import GrowthPlanRequest

_GROWTH_ENDPOINTS: list[tuple[str, str, type]] = [
    ("public-relations", "plan_public_relations", BusinessArtifact),
    ("media-relations", "plan_media_relations", BusinessArtifact),
    ("crisis-communication", "plan_crisis_communication", BusinessArtifact),
    ("social-media-strategy", "plan_social_media_strategy", BusinessArtifact),
    ("community-management", "plan_community_management", BusinessArtifact),
    ("influencer-marketing", "plan_influencer_marketing", BusinessArtifact),
    ("affiliate-marketing", "plan_affiliate_marketing", BusinessArtifact),
    ("referral-program", "plan_referral_program", BusinessArtifact),
    ("email-marketing", "plan_email_marketing", BusinessArtifact),
    ("marketing-automation", "plan_marketing_automation", BusinessArtifact),
    ("lead-scoring", "score_leads", LeadScoringResult),
    ("sales-funnel", "design_sales_funnel", BusinessArtifact),
    ("conversion-optimization", "plan_conversion_optimization", BusinessArtifact),
    ("landing-page", "plan_landing_page", BusinessArtifact),
    ("sales-script", "develop_sales_script", BusinessArtifact),
    ("objection-handling", "plan_objection_handling", BusinessArtifact),
    ("negotiation", "plan_negotiation", BusinessArtifact),
    ("deal-structuring", "structure_deal", BusinessArtifact),
    ("pricing-strategy", "plan_pricing_strategy", BusinessArtifact),
    ("price-elasticity", "analyze_price_elasticity", ElasticityResult),
    ("revenue-model", "design_revenue_model", BusinessArtifact),
    ("subscription-design", "design_subscription", BusinessArtifact),
    ("freemium", "plan_freemium", BusinessArtifact),
    ("usage-based-pricing", "plan_usage_based_pricing", BusinessArtifact),
    ("tiered-pricing", "plan_tiered_pricing", BusinessArtifact),
    ("dynamic-pricing", "plan_dynamic_pricing", BusinessArtifact),
    ("bundling", "plan_bundling", BusinessArtifact),
    ("upselling", "plan_upselling", BusinessArtifact),
    ("cross-selling", "plan_cross_selling", BusinessArtifact),
    ("customer-success", "plan_customer_success", BusinessArtifact),
    ("onboarding", "plan_onboarding", BusinessArtifact),
    ("support-system", "design_support_system", BusinessArtifact),
    ("knowledge-base", "plan_knowledge_base", BusinessArtifact),
    ("community-support", "plan_community_support", BusinessArtifact),
]


def _coerce_value(hint, value):
    """Coerce JSON input dicts into the builder's typed models by annotation."""
    import types
    import typing

    from pydantic import BaseModel

    if hint is None:
        return value
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        for arg in typing.get_args(hint):
            if arg is type(None):
                continue
            coerced = _coerce_value(arg, value)
            if coerced is not value:
                return coerced
        return value
    if origin is list and isinstance(value, list):
        args = typing.get_args(hint)
        if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
            return [args[0](**item) if isinstance(item, dict) else item for item in value]
        return value
    if isinstance(hint, type) and issubclass(hint, BaseModel) and isinstance(value, dict):
        return hint(**value)
    return value


def _growth_view(builder_name: str, module=None):
    import inspect
    import typing

    from pydantic import ValidationError

    builder = getattr(module or _growth, builder_name)
    params = inspect.signature(builder).parameters
    hints = typing.get_type_hints(builder)

    def view(request: GrowthPlanRequest, container: Container = Depends(get_container)):
        evidence = [
            EvidenceItem(key=e.key or f"ev{i + 1}", source=e.source, fact=e.fact)
            for i, e in enumerate(request.evidence)
        ]
        kwargs = {name: _coerce_value(hints.get(name), value) for name, value in request.inputs.items()}
        if request.title is not None and "title" in params:
            kwargs["title"] = request.title
        if "goal" in params and "goal" not in kwargs:
            kwargs["goal"] = request.goal
        if builder_name == "plan_email_marketing":
            kwargs["contacts"] = _load_contacts(container, request.contact_ids)
        if "title" not in params and "title" in kwargs:
            del kwargs["title"]
        try:
            artifact = builder(evidence=evidence, **kwargs)
            # Scope every review artifact to the authenticated request context. The
            # module still performs no external effect; these identifiers prevent
            # a caller from confusing another tenant's review result with its own.
            return artifact.model_copy(update={
                "tenant_id": request.tenant_id,
                "actor_id": request.actor_id,
            })
        except GrowthPlanError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=f"invalid inputs: {exc}") from exc
        except TypeError as exc:
            raise HTTPException(
                status_code=422, detail=f"missing or unknown inputs for {builder_name}: {exc}"
            ) from exc

    return view


for _path, _builder_name, _model in _GROWTH_ENDPOINTS:
    router.add_api_route(
        f"/growth/{_path}",
        _growth_view(_builder_name),
        methods=["POST"],
        response_model=_model,
        name=f"growth_{_builder_name}",
    )


# --- corporate review artifacts (feature rows 476-509) ----------------------------

from . import corporate as _corporate

_CORPORATE_ENDPOINTS: list[tuple[str, str, type]] = [
    ("stakeholder-analysis", "analyze_stakeholders", BusinessArtifact),
    ("communication-planning", "plan_communication", BusinessArtifact),
    ("training-design", "design_training", BusinessArtifact),
    ("organizational-design", "design_organization", BusinessArtifact),
    ("span-of-control", "analyze_span_of_control", BusinessArtifact),
    ("matrix-organization", "design_matrix_organization", BusinessArtifact),
    ("team-topology", "design_team_topology", BusinessArtifact),
    ("culture-design", "design_culture", BusinessArtifact),
    ("values-definition", "define_values", BusinessArtifact),
    ("mission-statement", "create_mission_statement", BusinessArtifact),
    ("vision-statement", "create_vision_statement", BusinessArtifact),
    ("strategy-development", "develop_strategy", BusinessArtifact),
    ("swot-analysis", "analyze_swot", BusinessArtifact),
    ("pestle-analysis", "analyze_pestle", BusinessArtifact),
    ("scenario-planning", "plan_scenarios", BusinessArtifact),
    ("strategic-planning", "plan_strategy", BusinessArtifact),
    ("okr-setting", "set_okrs", BusinessArtifact),
    ("kpi-selection", "select_kpis", BusinessArtifact),
    ("balanced-scorecard", "build_balanced_scorecard", BusinessArtifact),
    ("performance-management", "plan_performance_management", BusinessArtifact),
    ("compensation-design", "design_compensation", BusinessArtifact),
    ("equity-distribution", "plan_equity_distribution", BusinessArtifact),
    ("cap-table", "manage_cap_table", BusinessArtifact),
    ("fundraising-strategy", "plan_fundraising", BusinessArtifact),
    ("pitch-deck", "create_pitch_deck", BusinessArtifact),
    ("financial-model", "build_financial_model", BusinessArtifact),
    ("valuation-analysis", "analyze_valuation", BusinessArtifact),
    ("due-diligence", "prepare_due_diligence", BusinessArtifact),
    ("term-sheet", "negotiate_term_sheet", BusinessArtifact),
    ("investor-relations", "plan_investor_relations", BusinessArtifact),
    ("board-management", "manage_board", BusinessArtifact),
    ("exit-planning", "plan_exit", BusinessArtifact),
    ("mna-analysis", "analyze_acquisition", BusinessArtifact),
    ("ipo-preparation", "prepare_ipo", BusinessArtifact),
]

for _path, _builder_name, _model in _CORPORATE_ENDPOINTS:
    router.add_api_route(
        f"/corporate/{_path}",
        _growth_view(_builder_name, module=_corporate),
        methods=["POST"],
        response_model=_model,
        name=f"corporate_{_builder_name}",
    )
