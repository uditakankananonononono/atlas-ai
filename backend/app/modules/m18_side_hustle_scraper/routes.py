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
from .wiring import build_collectors
from .runner import HustleRunner,DurableHustleRunner,DurableRunStore
from app.auth.context import TenantContext,require_tenant
import os

router = APIRouter(prefix="/side-hustle-scraper", tags=["side-hustle-scraper"])
_service = None
_runner = HustleRunner()
_run_store=DurableRunStore(os.getenv("ATLAS_M18_RUN_DB","/tmp/atlas-m18-runs.sqlite3"))
def durable_runner(t:TenantContext=Depends(require_tenant)):return DurableHustleRunner(t.tenant_id,_run_store)


def get_service() -> Service:
    global _service
    if _service is None:
        repository = SQLiteDocumentRepository(":memory:")
        collectors = build_collectors()
        pipeline = CollectionPipeline(
            repository=repository,
            validator=DocumentValidator(),
            ranker=BlueprintRanker(),
            monitor=FreshnessMonitor(repository),
            collectors=collectors,
        )
        _service = Service(generate=generate, collectors=collectors, pipeline=pipeline)
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


@router.post("/runs")
def create_run(payload: dict):
 try:return _runner.view(_runner.create(title=str(payload.get("title", "")),first_experiment=str(payload.get("first_experiment", "")),max_budget=float(payload.get("max_budget",0)),source_urls=list(payload.get("source_urls",[]))))
 except (ValueError,TypeError) as e:raise HTTPException(422,str(e))

@router.get("/runs/{run_id}")
def get_run(run_id:str):
 try:return _runner.view(_runner.get(run_id))
 except KeyError:raise HTTPException(404,"run not found")

@router.post("/runs/{run_id}/steps/{step_id}/request-approval")
def request_step_approval(run_id:str,step_id:str,payload:dict):
 try:return _runner.view(_runner.get(run_id)) | {"requested_step":_runner.view(_runner.get(run_id))["steps"][[x.id for x in _runner.get(run_id).steps].index(step_id)]} if _runner.request_action(run_id,step_id,str(payload.get("user_id","default"))) else {}
 except KeyError:raise HTTPException(404,"run or step not found")
 except ValueError as e:raise HTTPException(422,str(e))

@router.post('/runs/{run_id}/steps/{step_id}/receipts')
def record_receipt(run_id:str,step_id:str,payload:dict):
 try:return _runner.record_adapter_receipt(run_id,step_id,adapter=str(payload.get('adapter','')),provider_receipt_id=str(payload.get('provider_receipt_id','')),status=str(payload.get('status','')),observed_at=str(payload.get('observed_at','')),payload_sha256=str(payload.get('payload_sha256','')))
 except KeyError:raise HTTPException(404,'run or step not found')
 except ValueError as error:raise HTTPException(422,str(error)) from error
@router.post('/runs/{run_id}/outcomes')
def record_outcome(run_id:str,payload:dict):
 try:return _runner.record_outcome(run_id,metric=str(payload.get('metric','')),value=float(payload.get('value')),unit=str(payload.get('unit','')),observed_at=str(payload.get('observed_at','')),source_url=payload.get('source_url'),receipt_sha256=payload.get('receipt_sha256'))
 except KeyError:raise HTTPException(404,'run not found')
 except (ValueError,TypeError) as error:raise HTTPException(422,str(error)) from error

@router.post('/durable-runs')
def create_durable_run(payload:dict,r:DurableHustleRunner=Depends(durable_runner)):
 try:return r.view(r.create(title=str(payload.get('title','')),first_experiment=str(payload.get('first_experiment','')),max_budget=float(payload.get('max_budget',0)),source_urls=list(payload.get('source_urls',[]))))
 except (ValueError,TypeError) as error:raise HTTPException(422,str(error)) from error
@router.get('/durable-runs')
def list_durable_runs(r:DurableHustleRunner=Depends(durable_runner)):return [r.view(x) for x in r.store.list(r.tenant_id)]
@router.get('/durable-runs/{run_id}')
def get_durable_run(run_id:str,r:DurableHustleRunner=Depends(durable_runner)):
 try:return r.view(r.get(run_id))
 except KeyError:raise HTTPException(404,'run not found')
@router.post('/durable-runs/{run_id}/steps/{step_id}/request-approval')
def durable_request_approval(run_id:str,step_id:str,payload:dict,r:DurableHustleRunner=Depends(durable_runner)):
 try:r.request_action(run_id,step_id,str(payload.get('user_id','default')));return r.view(r.get(run_id))
 except KeyError:raise HTTPException(404,'run or step not found')
 except ValueError as error:raise HTTPException(422,str(error)) from error
@router.post('/durable-runs/{run_id}/steps/{step_id}/receipts')
def durable_receipt(run_id:str,step_id:str,payload:dict,r:DurableHustleRunner=Depends(durable_runner)):
 try:return r.record_adapter_receipt(run_id,step_id,adapter=str(payload.get('adapter','')),provider_receipt_id=str(payload.get('provider_receipt_id','')),status=str(payload.get('status','')),observed_at=str(payload.get('observed_at','')),payload_sha256=str(payload.get('payload_sha256','')))
 except KeyError:raise HTTPException(404,'run or step not found')
 except ValueError as error:raise HTTPException(422,str(error)) from error
@router.post('/durable-runs/{run_id}/outcomes')
def durable_outcome(run_id:str,payload:dict,r:DurableHustleRunner=Depends(durable_runner)):
 try:return r.record_outcome(run_id,metric=str(payload.get('metric','')),value=float(payload.get('value')),unit=str(payload.get('unit','')),observed_at=str(payload.get('observed_at','')),source_url=payload.get('source_url'),receipt_sha256=payload.get('receipt_sha256'))
 except KeyError:raise HTTPException(404,'run not found')
 except (ValueError,TypeError) as error:raise HTTPException(422,str(error)) from error
