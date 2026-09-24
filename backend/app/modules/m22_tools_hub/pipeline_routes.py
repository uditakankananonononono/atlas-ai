"""HTTP surface for the durable Tools Hub install pipeline (tenant-scoped)."""
from __future__ import annotations

import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.context import TenantContext, require_tenant

from .pipeline import InstallPipeline, PipelineConflict, PipelineError

router = APIRouter(prefix="/pipeline", tags=["tools-hub-pipeline"])
_pipelines: dict[str, InstallPipeline] = {}
MAX_ARTIFACT_B64 = 70 * 1024 * 1024


def get_pipeline(tenant: TenantContext = Depends(require_tenant)) -> InstallPipeline:
    if tenant.tenant_id not in _pipelines:
        _pipelines[tenant.tenant_id] = InstallPipeline(tenant.tenant_id)
    return _pipelines[tenant.tenant_id]


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, str(exc).strip("'"))
    if isinstance(exc, PipelineConflict):
        return HTTPException(409, str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc))
    return HTTPException(422, str(exc))


ERRORS = (KeyError, PipelineConflict, PipelineError, PermissionError, ValueError)


class ProposalIn(BaseModel):
    artifact_base64: str = Field(min_length=4, max_length=MAX_ARTIFACT_B64)
    manifest: dict[str, Any]
    candidate: dict[str, Any] = Field(default_factory=dict)


class RollbackEnqueueIn(BaseModel):
    approval_id: str = Field(min_length=1)


@router.post("/proposals", status_code=201)
def create_proposal(body: ProposalIn, tenant: TenantContext = Depends(require_tenant),
                    p: InstallPipeline = Depends(get_pipeline)):
    try:
        artifact = base64.b64decode(body.artifact_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "artifact_base64 is not valid base64") from exc
    try:
        return p.propose(artifact=artifact, manifest=body.manifest, requested_by=tenant.actor_id,
                         candidate=body.candidate)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.get("/proposals")
def list_proposals(status: str | None = None, p: InstallPipeline = Depends(get_pipeline)):
    return p.list_proposals(status)


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str, p: InstallPipeline = Depends(get_pipeline)):
    try:
        return p.get_proposal(proposal_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/proposals/{proposal_id}/install-jobs", status_code=202)
def enqueue_install(proposal_id: str, p: InstallPipeline = Depends(get_pipeline)):
    try:
        return p.enqueue_install(proposal_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/installs/{operation_id}/rollback-proposals", status_code=201)
def propose_rollback(operation_id: str, tenant: TenantContext = Depends(require_tenant),
                     p: InstallPipeline = Depends(get_pipeline)):
    try:
        return p.propose_rollback(operation_id, tenant.actor_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/installs/{operation_id}/rollback-jobs", status_code=202)
def enqueue_rollback(operation_id: str, body: RollbackEnqueueIn, p: InstallPipeline = Depends(get_pipeline)):
    try:
        return p.enqueue_rollback(operation_id, body.approval_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.get("/jobs")
def list_jobs(p: InstallPipeline = Depends(get_pipeline)):
    return p.list_jobs()


@router.get("/jobs/{job_id}")
def get_job(job_id: str, p: InstallPipeline = Depends(get_pipeline)):
    try:
        return p.get_job(job_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/jobs/{job_id}/run")
def run_job(job_id: str, p: InstallPipeline = Depends(get_pipeline)):
    """Run one queued job inline (the Celery task does the same off-request)."""
    try:
        return p.run_job(job_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.get("/portfolio")
def portfolio(include_history: bool = False, p: InstallPipeline = Depends(get_pipeline)):
    return p.portfolio(include_history)


def get_discovery_service():
    from .routes import get_service
    return get_service()


class DiscoveryQueryIn(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class CandidateProposalIn(BaseModel):
    version: str | None = Field(default=None, max_length=80)
    entrypoint: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list)


@router.post("/discoveries", status_code=201)
async def discover_and_persist(body: DiscoveryQueryIn, p: InstallPipeline = Depends(get_pipeline),
                               service=Depends(get_discovery_service)):
    """Run the free official-registry collectors and persist ranked candidates for this tenant."""
    try:
        return await p.discover(body.query, service)
    except ERRORS as exc:
        raise _http(exc) from exc
    except OSError as exc:
        raise HTTPException(502, f"discovery source failed: {exc}") from exc


@router.get("/candidates")
def list_candidates(source: str | None = None, limit: int = 100, p: InstallPipeline = Depends(get_pipeline)):
    return p.list_candidates(source, max(1, min(limit, 500)))


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: str, p: InstallPipeline = Depends(get_pipeline)):
    try:
        return p.get_candidate(candidate_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/candidates/{candidate_id}/proposals", status_code=201)
def propose_from_candidate(candidate_id: str, body: CandidateProposalIn,
                           tenant: TenantContext = Depends(require_tenant),
                           p: InstallPipeline = Depends(get_pipeline)):
    """Fetch the candidate's artifact from PyPI/npm, check the registry digest, scan, and file a Module 0 approval."""
    try:
        return p.propose_from_candidate(candidate_id, requested_by=tenant.actor_id, version=body.version,
                                        entrypoint=body.entrypoint, permissions=body.permissions)
    except ERRORS as exc:
        raise _http(exc) from exc
