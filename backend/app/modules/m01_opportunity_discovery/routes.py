"""HTTP routes for the Opportunity Discovery Engine (module 1).

Routes live under /opportunity-discovery; the integrator mounts the router
under the global /api/v1 prefix. All work is delegated to the injected
Service; the only LLM call goes through the shared BYOK provider
(``app.core.providers.generate``) and degrades to the deterministic digest
template on any provider error.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.providers import ProviderError, generate

from .schemas import (
    DigestProposalOut,
    DigestRequestIn,
    OpportunityOut,
    OpportunityType,
    ScanRequestIn,
    ScanResultOut,
    SourceOut,
)
from .service import Service

router = APIRouter(tags=["opportunity-discovery"])

_service: Service | None = None


def get_service() -> Service:
    """Lazily build the default service; overridable via FastAPI dependency_overrides."""

    global _service
    if _service is None:
        _service = Service()
    return _service


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
