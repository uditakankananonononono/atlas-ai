"""HTTP surface for Module 18.

Original endpoints (POST /blueprints, POST /feasibility) unchanged. Pipeline
endpoints added: /collect, /rank, /refresh, /freshness. get_service wires a
development pipeline; the integrator replaces repository/collectors/monitor
with the shared Postgres adapter, real collector config and tenant resolution.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.providers import generate

from .lane_freshness import FreshnessMonitor
from .lane_pipeline import CollectionPipeline
from .lane_ranking import BlueprintRanker
from .lane_repository import SQLiteDocumentRepository
from .schemas import (
    AnalyzeIn,
    BlueprintOut,
    CollectIn,
    CollectReportOut,
    DiscoverIn,
    FeasibilityOut,
    FreshnessReportOut,
    PlatformReportOut,
    RankIn,
    RankedOut,
    RefreshOut,
    SignalOut,
)
from .service import Service
from .lane_validation import DocumentValidator

router = APIRouter(prefix="/side-hustle-scraper", tags=["side-hustle-scraper"])
_service = None


def get_service() -> Service:
    global _service
    if _service is None:
        repository = SQLiteDocumentRepository(":memory:")
        pipeline = CollectionPipeline(
            repository=repository,
            validator=DocumentValidator(),
            ranker=BlueprintRanker(),
            monitor=FreshnessMonitor(repository),
            collectors={},
        )
        _service = Service(generate=generate, collectors={}, pipeline=pipeline)
    return _service


@router.post("/blueprints", response_model=list[BlueprintOut])
async def discover(request: DiscoverIn, service: Service = Depends(get_service)):
    try:
        return await service.discover(request)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(422, str(e))


@router.post("/feasibility", response_model=FeasibilityOut)
async def analyze(request: AnalyzeIn, service: Service = Depends(get_service)):
    return await service.analyze(request)


@router.post("/collect", response_model=CollectReportOut)
async def collect(request: CollectIn, service: Service = Depends(get_service)):
    try:
        report = await service.collect(request)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return CollectReportOut(
        query=report.query,
        platforms=[PlatformReportOut(platform=p.platform, collected=p.collected,
                                     accepted_new=p.accepted_new,
                                     accepted_duplicate=p.accepted_duplicate,
                                     rejected=p.rejected,
                                     rejection_reasons=list(p.rejection_reasons),
                                     errors=list(p.errors)) for p in report.platforms],
        documents_found=report.documents_found,
        documents_new=report.documents_new,
        documents_duplicate=report.documents_duplicate,
        documents_rejected=report.documents_rejected,
    )


@router.post("/rank", response_model=list[RankedOut])
async def rank(request: RankIn, service: Service = Depends(get_service)):
    ranked = await service.ranked(request)
    return [
        RankedOut(
            doc_id=r.doc_id, url=r.url, platform=r.platform, title=r.title,
            score=r.score, rank=r.rank,
            breakdown=[SignalOut(signal=b.signal, weight=b.weight, raw_value=b.raw_value,
                                 contribution=b.contribution, note=b.note) for b in r.breakdown],
            corroborating_platforms=list(r.corroborating_platforms),
            scam_penalty=r.scam_penalty,
        )
        for r in ranked
    ]


@router.post("/refresh", response_model=RefreshOut)
async def refresh(service: Service = Depends(get_service)):
    raise HTTPException(
        501,
        "refresh requires integrator-wired per-kind refetchers; call Service.refresh "
        "from the Celery freshness task with the shared HTTP client",
    )


@router.get("/freshness", response_model=FreshnessReportOut)
async def freshness(service: Service = Depends(get_service)):
    report = await service.freshness_report()
    return FreshnessReportOut(**{k: report[k] for k in
                                 ("watched", "alive", "dead", "due_now", "by_class", "generated_at")})
