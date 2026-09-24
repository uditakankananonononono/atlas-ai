"""FastAPI routes for the Research Scientist module."""

from fastapi import APIRouter, HTTPException, Depends
from app.core.providers import ProviderError
from app.auth.context import TenantContext, require_tenant
from app.modules.m00_approval_center.service import default_service
from .schemas import (
    AnalysisProposalRequest,
    HypothesisRequest,
    HypothesisResponse,
    ProposedAnalysis,
    SurveillanceRequest,
    SurveillanceResponse,
    SurveillanceIngestRequest, GapEvidenceOut,
)
from .service import Service

router = APIRouter(prefix="/research-scientist", tags=["Research Scientist"])


@router.post("/literature/clusters", response_model=SurveillanceResponse)
def cluster_literature(request: SurveillanceRequest) -> SurveillanceResponse:
    """Cluster already-collected papers without making a network call."""
    try:
        return Service().cluster_papers(request.papers, request.similarity_threshold)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/hypotheses", response_model=HypothesisResponse)
async def draft_hypothesis(
    request: HypothesisRequest,
    tenant: TenantContext = Depends(require_tenant),
) -> HypothesisResponse:
    """Draft a grounded hypothesis using the configured shared BYOK provider."""
    try:
        return await Service().generate_hypothesis(request)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/analyses/proposals", response_model=ProposedAnalysis)
def propose_analysis(request: AnalysisProposalRequest, tenant: TenantContext = Depends(require_tenant)) -> ProposedAnalysis:
    """Create an approval-gated sandbox execution proposal; never execute code here."""
    try:
        proposal = Service.propose_analysis(request)
        approval = default_service().submit(module_id=4, action_type=proposal.action_type, user_id=tenant.tenant_id, payload=proposal.model_dump(mode="json"))
        return proposal.model_copy(update={"approval_id": approval["id"], "status": "pending"})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/surveillance/ingest")
async def ingest_surveillance(request:SurveillanceIngestRequest,tenant:TenantContext=Depends(require_tenant)):
    from app.core.embeddings import get_embedding_provider
    from .surveillance import SurveillancePipeline,SurveillanceRepository
    return await SurveillancePipeline(SurveillanceRepository(tenant.tenant_id),get_embedding_provider(request.embedding_provider)).ingest(request.papers)

@router.get("/surveillance/clusters")
def surveillance_clusters(threshold:float=.72,tenant:TenantContext=Depends(require_tenant)):
    from .surveillance import SurveillancePipeline,SurveillanceRepository
    return {"clusters":SurveillancePipeline(SurveillanceRepository(tenant.tenant_id),None).clusters(threshold)}

@router.get("/surveillance/gaps",response_model=list[GapEvidenceOut])
def surveillance_gaps(tenant:TenantContext=Depends(require_tenant)):
    from .surveillance import SurveillancePipeline,SurveillanceRepository
    return [GapEvidenceOut(**x.__dict__) for x in SurveillancePipeline(SurveillanceRepository(tenant.tenant_id),None).gaps()]

# Environmental domain calculators, ledger rows 1660-1709.
@router.get("/environmental-1660-1709/methods")
def environmental_methods_1660_1709():
    from .environmental_1660_1709 import ROWS
    return [{"method":m,"feature_row":r} for m,r in ROWS.items()]

@router.post("/environmental-1660-1709/analyze")
def environmental_analyze_1660_1709(payload:dict):
    from .environmental_1660_1709 import run
    try:return run(payload.get("method",""),payload.get("data",{}))
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

@router.get('/quant-methods-185-234')
def quant_methods_185_234():
    from .quant_methods_185_234 import ROWS
    return [{'row_id':i,'method':m} for i,m in ROWS.items()]
@router.post('/quant-methods-185-234/{row_id}')
def quant_method_185_234(row_id:int,payload:dict):
    from .quant_methods_185_234 import QuantError,run
    try:return run(row_id,payload)
    except QuantError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

from .core_spec_round6 import router as core_spec_round6_router
router.include_router(core_spec_round6_router)

@router.post('/expanded-211-258/{row_id}')
def expanded_211_258(row_id:int,payload:dict):
 from .expanded_211_258 import run
 try:return run(row_id,payload)
 except (ValueError,TypeError,KeyError) as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

# Owner-ledger environmental and sustainability analyses, rows 1660-1709.
from typing import Any
from pydantic import BaseModel, Field
from .environmental_1660_1709 import execute_environmental_row
class Environmental1660To1709In(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
@router.post('/environmental-1660-1709/{row_id}')
def environmental_1660_1709_route(row_id:int, body:Environmental1660To1709In, tenant:TenantContext=Depends(require_tenant)):
    try:
        result=execute_environmental_row(row_id,body.data)
        return {'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id,**result}
    except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:
        raise HTTPException(422,str(exc)) from exc

from pydantic import BaseModel
from fastapi.responses import Response
class ReproducibilityBundleIn(BaseModel):
 title:str;code:str;language:str='python';inputs:dict={};parameters:dict={};seed:int=0;expected_outputs:list[str]=[];dependencies:list[str]=[];source_urls:list[str]=[]
@router.post('/reproducibility/bundle')
def reproducibility_bundle(body:ReproducibilityBundleIn):
 from .reproducibility_bundle import build_bundle
 try:payload,manifest=build_bundle(**body.model_dump())
 except ValueError as e:raise HTTPException(422,str(e))
 return Response(payload,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="atlas-reproducibility-bundle.zip"','X-Atlas-Bundle-SHA256':manifest['bundle_sha256']})


# Approved sandbox execution: runs an approved execute_sandboxed_analysis item.
from fastapi import Response
from .approved_sandbox import (
    ApprovedSandboxExecutor,
)
from .approved_sandbox import (
    BackendUnavailableError as _SbxBackendUnavailable,
    ExecutionConflictError as _SbxConflict,
    ExecutionForbiddenError as _SbxForbidden,
    ExecutionNotFoundError as _SbxNotFound,
)

_sandbox_executors: dict[str, ApprovedSandboxExecutor] = {}


def get_sandbox_executor(tenant: TenantContext = Depends(require_tenant)) -> ApprovedSandboxExecutor:
    if tenant.tenant_id not in _sandbox_executors:
        _sandbox_executors[tenant.tenant_id] = ApprovedSandboxExecutor(tenant.tenant_id, actor_id=tenant.actor_id)
    return _sandbox_executors[tenant.tenant_id]


def _sandbox_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, _SbxNotFound):
        return HTTPException(status_code=404, detail="not found")
    if isinstance(exc, _SbxForbidden):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, _SbxConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, _SbxBackendUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.post("/analyses/{approval_id}/execute", status_code=201)
def execute_approved_analysis(approval_id: str, executor: ApprovedSandboxExecutor = Depends(get_sandbox_executor)):
    """Run the exact approved analysis in the sandbox and return its sealed receipt."""
    try:
        return executor.execute(approval_id)
    except (_SbxNotFound, _SbxForbidden, _SbxConflict, _SbxBackendUnavailable) as exc:
        raise _sandbox_http_error(exc) from exc


@router.get("/analyses/executions")
def list_analysis_executions(limit: int = 100, executor: ApprovedSandboxExecutor = Depends(get_sandbox_executor)):
    return executor.list_receipts(limit=min(max(limit, 1), 500))


@router.get("/analyses/{approval_id}/execution")
def read_analysis_execution(approval_id: str, executor: ApprovedSandboxExecutor = Depends(get_sandbox_executor)):
    try:
        return executor.readback(approval_id)
    except _SbxNotFound as exc:
        raise _sandbox_http_error(exc) from exc


@router.get("/analyses/artifacts/{sha256}")
def download_analysis_artifact(sha256: str, executor: ApprovedSandboxExecutor = Depends(get_sandbox_executor)):
    """Download a log or output file by hash; integrity is re-checked on read."""
    try:
        data = executor.artifact(sha256)
    except _SbxNotFound as exc:
        raise _sandbox_http_error(exc) from exc
    return Response(content=data, media_type="application/octet-stream",
                    headers={"X-Content-SHA256": sha256,
                             "Content-Disposition": f'attachment; filename="{sha256}"'})


@router.get("/analyses/{approval_id}/bundle")
def download_execution_bundle(approval_id: str, executor: ApprovedSandboxExecutor = Depends(get_sandbox_executor)):
    """Executed reproducibility bundle: code, datasets, environment lock, logs and outputs, all hashed."""
    from .execution_bundle import build_execution_bundle
    try:
        receipt = executor.readback(approval_id)
        payload, manifest = build_execution_bundle(receipt, executor.store, executor.tenant_id)
    except _SbxNotFound as exc:
        raise _sandbox_http_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(content=payload, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="atlas-execution-{approval_id}.zip"',
        "X-Atlas-Bundle-SHA256": manifest["bundle_sha256"],
        "X-Atlas-Manifest-SHA256": manifest["manifest_sha256"]})


# Approval-gated re-run with output-hash diff against the original receipt.
from pydantic import BaseModel as _BaseModel, Field as _Field


class RerunProposalIn(_BaseModel):
    reason: str = _Field(default="", max_length=1000)


@router.post("/analyses/{approval_id}/reruns", status_code=202)
def propose_analysis_rerun(approval_id: str, body: RerunProposalIn | None = None,
                           executor: ApprovedSandboxExecutor = Depends(get_sandbox_executor)):
    """File an approval to re-run a finished analysis; nothing executes here."""
    from .rerun import RerunService
    try:
        return RerunService(executor).propose(approval_id, (body.reason if body else ""))
    except (_SbxNotFound, _SbxConflict) as exc:
        raise _sandbox_http_error(exc) from exc


@router.post("/analyses/reruns/{rerun_approval_id}/execute", status_code=201)
def execute_analysis_rerun(rerun_approval_id: str, executor: ApprovedSandboxExecutor = Depends(get_sandbox_executor)):
    """Re-run the stored approved code on stored datasets and diff hashes against the original."""
    from .rerun import RerunService
    try:
        return RerunService(executor).execute(rerun_approval_id)
    except (_SbxNotFound, _SbxForbidden, _SbxConflict, _SbxBackendUnavailable) as exc:
        raise _sandbox_http_error(exc) from exc
