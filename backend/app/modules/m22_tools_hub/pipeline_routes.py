"""HTTP surface for the durable Tools Hub install pipeline (tenant-scoped)."""
from __future__ import annotations

import base64
import binascii
from typing import Any

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
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


_SAFE_CAP = 12


def _safe_source_errors(raw: dict[str, str]) -> dict[str, str]:
    """Per-source failure CATEGORY only. Raw exception text can carry URLs, query strings, IPs or credentials, so it is
    neither returned nor logged (only source name and category are logged). Bounded to _SAFE_CAP sources and short names."""
    out: dict[str, str] = {}
    for name, text in list(raw.items())[:_SAFE_CAP]:
        t = str(text).lower()
        kind = ("cooldown" if "cooldown" in t else "timeout" if "timed out" in t or "timeout" in t
                else "network_unreachable" if ("urlopen" in t or "network" in t or "connection" in t or "resolve" in t)
                else "http_error" if "http" in t else "source_failed")
        out[str(name)[:40]] = kind
        logging.getLogger(__name__).warning("m22 discovery source %s failed (%s)", str(name)[:40], kind)  # no raw text: may hold secrets
    return out


@router.post("/discoveries", status_code=201)
async def discover_and_persist(body: DiscoveryQueryIn, response: Response, p: InstallPipeline = Depends(get_pipeline),
                               service=Depends(get_discovery_service)):
    """Run the free official-registry collectors and persist ranked candidates for this tenant.
    Source failures are NOT hidden: if every source failed and nothing was found the answer is 502 with per-source
    errors (an empty 201 would read as 'no matches'); on partial failure the body stays the candidate list and the
    X-Atlas-Discovery-Source-Errors header carries the per-source errors as JSON."""
    try:
        if not body.query.strip():
            raise PipelineError("query is required")
        q = body.query.strip()
        if hasattr(service, "discover_report"):
            rep = await service.discover_report(q)  # call-local result, no shared-state race
        else:  # test doubles / older services: last_errors is request-global, so only best effort
            rep = {"ranked": await service.discover(q), "errors": dict(getattr(service, "last_errors", {}) or {})}
            rep.update(sources_failed=len(rep["errors"]), sources_ok=None, sources_attempted=None)
        found = p.record_candidates(rep["ranked"], q)
        errors = _safe_source_errors(rep["errors"])
        counts = {"sources_failed": rep["sources_failed"], "sources_ok": rep["sources_ok"],
                  "sources_attempted": rep["sources_attempted"]}
        all_failed = rep["sources_ok"] == 0 if rep["sources_ok"] is not None else (bool(errors) and not found)
        if all_failed and errors:
            raise HTTPException(502, {"message": "no discovery source answered; zero results is NOT 'no matches'",
                                      "source_errors": errors, **counts})
        if errors:
            import json as _json
            shown = dict(list(errors.items())[:5])  # complete, valid JSON; never a sliced string
            response.headers["X-Atlas-Discovery-Source-Errors"] = _json.dumps(
                {**counts, "shown": shown, "omitted": max(0, (rep["sources_failed"] if rep["sources_failed"] is not None else len(errors)) - len(shown))}, separators=(",", ":"))
        return found
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


class SmokeEnqueueIn(BaseModel):
    approval_id: str = Field(min_length=1)


@router.post("/installs/{operation_id}/smoke-proposals", status_code=201)
def propose_smoke(operation_id: str, tenant: TenantContext = Depends(require_tenant),
                  p: InstallPipeline = Depends(get_pipeline)):
    try:
        return p.propose_smoke(operation_id, tenant.actor_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/installs/{operation_id}/smoke-jobs", status_code=202)
def enqueue_smoke(operation_id: str, body: SmokeEnqueueIn, p: InstallPipeline = Depends(get_pipeline)):
    try:
        return p.enqueue_smoke(operation_id, body.approval_id)
    except ERRORS as exc:
        raise _http(exc) from exc
