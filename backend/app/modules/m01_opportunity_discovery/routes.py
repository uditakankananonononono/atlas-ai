"""HTTP routes for the Opportunity Discovery Engine (module 1).

Routes live under /opportunity-discovery; the integrator mounts the router
under the global /api/v1 prefix. All work is delegated to the injected
Service; the only LLM call goes through the shared BYOK provider
(``app.core.providers.generate``) and degrades to the deterministic digest
template on any provider error.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.context import TenantContext, require_tenant
from app.core.providers import ProviderError, generate

from .schemas import (
    DigestProposalOut,
    DigestRequestIn,
    NlpStatusOut,
    OpportunityOut,
    OpportunityType,
    ScanRequestIn,
    ScanResultOut,
    SourceOut,
)
from .nlp_stack import default_stack
from .service import Service

router = APIRouter(tags=["opportunity-discovery"])

def get_service(tenant: TenantContext = Depends(require_tenant)) -> Service:
    """Build a tenant-bound service; tests may override this dependency."""
    return Service(tenant_id=tenant.tenant_id, nlp_stack=default_stack())


@router.get("/opportunity-discovery/nlp-status", response_model=NlpStatusOut)
def nlp_status(service: Service = Depends(get_service)) -> NlpStatusOut:
    """Which NER, deadline and match engines are live, and why any is degraded."""

    return NlpStatusOut(**service.nlp_status())


@router.get("/opportunity-discovery/sources", response_model=list[SourceOut])
def list_sources(service: Service = Depends(get_service)) -> list[SourceOut]:
    """List the configured compliant discovery sources."""

    return service.list_sources()


@router.post("/opportunity-discovery/scans", response_model=ScanResultOut)
def run_scan(request: ScanRequestIn, service: Service = Depends(get_service)) -> ScanResultOut:
    """Run a discovery scan: fetch, parse, normalize, score, and store."""

    return service.run_scan(
        source_ids=request.source_ids,
        profile=request.profile,
        notify_threshold=request.notify_threshold,
    )


@router.get("/opportunity-discovery/opportunities", response_model=list[OpportunityOut])
def list_opportunities(
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    opportunity_type: OpportunityType | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    service: Service = Depends(get_service),
) -> list[OpportunityOut]:
    """List stored opportunities, best match first."""

    return service.list_opportunities(min_score=min_score, opportunity_type=opportunity_type, limit=limit)


@router.get("/opportunity-discovery/opportunities/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(opportunity_id: str, service: Service = Depends(get_service)) -> OpportunityOut:
    """Fetch one opportunity by ID."""

    opportunity = service.get_opportunity(opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return opportunity


@router.post("/opportunity-discovery/digests", response_model=DigestProposalOut)
async def propose_digest(request: DigestRequestIn, service: Service = Depends(get_service)) -> DigestProposalOut:
    """Draft a digest and gate its send behind the Human Approval Center.

    The digest is never sent here. With ``use_llm`` the prose is polished
    through the shared BYOK provider; a missing key or provider failure falls
    back to the deterministic template so the approval flow still works.
    """

    items = service.top_opportunities(min_score=request.min_score, limit=request.max_items)
    if not items:
        raise HTTPException(status_code=404, detail="no opportunities at or above the requested score")
    body = service.render_digest(items)
    if request.use_llm:
        try:
            _, polished = await generate(service.digest_prompt(items), request.provider, request.model)
            body = polished
        except ProviderError:
            pass  # deterministic template remains the body
    approval = service.propose_digest(items=items, body=body, recipient=request.recipient)
    return DigestProposalOut(
        approval_id=approval.id,
        status=approval.status.value,
        item_count=len(items),
        subject=service.digest_subject(items),
        preview=body[:500],
    )

# Expanded owner-spec opportunity collection and understanding rows 67-131.
from .expanded_spec_routes_67_131 import router as expanded_spec_router_67_131
router.include_router(expanded_spec_router_67_131)

from .core_spec_round6 import router as core_spec_round6_router
router.include_router(core_spec_round6_router)

from .expanded_spec_routes_1_66 import router as expanded_spec_router_1_66
router.include_router(expanded_spec_router_1_66)

# Free student platform read-only discovery and launch routes (17 explicit sources).
from .student_platforms import BY_ID, PLATFORMS, PlatformUnavailable, discover

@router.get('/opportunity-discovery/student-platforms')
def student_platforms(tenant: TenantContext = Depends(require_tenant)) -> list[dict]:
    return [vars(p) for p in PLATFORMS]

@router.get('/opportunity-discovery/student-platforms/{platform_id}/discover')
def discover_student_platform(platform_id: str, query: str = '', limit: int = Query(default=25, ge=1, le=100), tenant: TenantContext = Depends(require_tenant)) -> dict:
    if platform_id not in BY_ID:
        raise HTTPException(status_code=404, detail='unknown student platform')
    try:
        return discover(platform_id, query, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PlatformUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

from .student_intelligence import search_and_analyze

@router.get('/opportunity-discovery/student-insights')
def student_insights(platform_id: list[str] = Query(...), query: str = '', per_platform: int = Query(default=25, ge=1, le=100), tenant: TenantContext = Depends(require_tenant)) -> dict:
    """Cross-platform public results, evidence annotations and isolated failures."""
    try:
        return search_and_analyze(platform_id, query, per_platform=per_platform)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

from datetime import date as _date
from pydantic import BaseModel as _BaseModel, Field as _Field
from .student_intelligence import refine, source_breakdown

class StudentInsightRequest(_BaseModel):
    platform_ids: list[str] = _Field(min_length=1, max_length=5)
    query: str = _Field(default='', max_length=200)
    per_platform: int = _Field(default=25, ge=1, le=100)
    kind: str | None = None
    platform: str | None = None
    terms: list[str] = _Field(default_factory=list, max_length=10)
    require_all_terms: bool = False
    exclude: list[str] = _Field(default_factory=list, max_length=10)
    start: _date | None = None
    end: _date | None = None
    hide_expired: bool = False
    min_award: int | None = _Field(default=None, ge=0)
    currency: str | None = None
    delivery: str | None = None
    level: str | None = None
    region: str | None = None
    include_unknown: bool = False


@router.post('/opportunity-discovery/student-insights/search')
def search_student_insights(request: StudentInsightRequest, tenant: TenantContext = Depends(require_tenant)) -> dict:
    """Fetch selected real public listings, annotate, dedupe, filter and report gaps."""
    if any(len(term) > 80 for term in request.terms + request.exclude):
        raise HTTPException(status_code=422, detail='each term must be at most 80 characters')
    try:
        result = search_and_analyze(request.platform_ids, request.query, per_platform=request.per_platform)
        result['items'] = refine(result['items'], kind=request.kind, platform=request.platform,
            terms=request.terms, require_all_terms=request.require_all_terms,
            exclude=request.exclude, start=request.start, end=request.end,
            hide_expired=request.hide_expired, min_award=request.min_award,
            currency=request.currency, delivery=request.delivery, level=request.level,
            region=request.region, include_unknown=request.include_unknown)
        result['breakdown'] = source_breakdown(result['items'])
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
