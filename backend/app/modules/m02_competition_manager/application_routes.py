"""Mounted HTTP surface for the end-to-end opportunity application browser workflow.

Module 2 owns the orchestration: it resolves the chosen opportunity or
competition to its official application URL (Module 1 records supply
opportunity URLs), drives the Module 13 paired-browser engine, and writes
submission status evidence back to the competition record only after the
site's own post-submit readback confirms the outcome.

Hard boundaries held here and in the engine:
- the owner logs in themselves inside the paired browser session;
- Atlas never accepts or stores passwords, MFA codes, cookies, or tokens;
- staging fills fields but never submits;
- the final submit executes exactly once, only against an exact, approved,
  unconsumed approval bound to tenant, actor, session, URL, selector, exact
  values hash, and screenshot hash;
- CAPTCHA, site redesign, and click failures are reported honestly and never
  written back as success.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from app.auth.context import TenantContext, require_tenant
from app.modules.m13_browser_agent.application_flow import (
    ActorMismatchError,
    ApplicationFlow,
    BlockedError,
    CredentialRejectedError,
    SessionNotFoundError,
    WorkflowStateError,
)
from app.modules.m13_browser_agent.security import NavigationBlocked

from .routes import get_service, router
from .application_schemas import (
    ApplicationResumeIn,
    ApplicationSessionCreateIn,
    ApplicationStageIn,
    ApplicationSubmitIn,
)
from .schemas import StatusEvidence, SubmissionStatus
from .service import CompetitionNotFoundError, Service

# Routes are declared directly on the parent Module 2 router (imported above):
# nested include_router mounts lose inner prefixes on the deployed FastAPI
# version, so this module shares the parent router object instead. The paths
# below are relative to that router's "/competition-manager" prefix.
_BASE = "/applications"

_flow: ApplicationFlow | None = None


def get_application_flow() -> ApplicationFlow:
    """Lazily build the default flow; overridable via FastAPI dependency_overrides."""
    global _flow
    if _flow is None:
        from app.modules.m00_approval_center.service import default_service
        from app.modules.m13_browser_agent.application_store import SQLApplicationSessionStore
        from app.modules.m13_browser_agent.playwright_adapter import PlaywrightSessions
        from app.modules.m13_browser_agent.service import Service as BrowserService
        from app.modules.m13_browser_agent.store import SQLStore
        approvals = default_service()
        browser = BrowserService(PlaywrightSessions(), approvals, SQLStore())
        _flow = ApplicationFlow(browser, SQLApplicationSessionStore(), approvals)
    return _flow


def _discovery_service():
    from app.modules.m01_opportunity_discovery.routes import get_service as get_discovery
    return get_discovery()


def _resolve_target(
    body: ApplicationSessionCreateIn, service: Service
) -> tuple[str, str, str]:
    """Resolve the official application URL and the opportunity reference.

    Precedence: an explicit URL, then the competition record, then the
    Module 1 opportunity record. Referenced records must exist.
    """
    kind, ref_id = "direct", ""
    competition_url = ""
    if body.competition_id:
        competition = service.get_competition(body.competition_id)
        competition_url = str(competition.official_rules_url)
        kind, ref_id = "competition", body.competition_id
    opportunity_url = ""
    if body.opportunity_id:
        opportunity = _discovery_service().get_opportunity(body.opportunity_id)
        if opportunity is None:
            raise HTTPException(status_code=404, detail="opportunity not found")
        opportunity_url = opportunity.url
        if not body.competition_id:
            kind, ref_id = "opportunity", body.opportunity_id
    url = body.application_url or competition_url or opportunity_url
    if not url:
        raise HTTPException(
            status_code=422,
            detail="an application_url, competition_id, or opportunity_id with a URL is required",
        )
    return url, kind, ref_id


def _flow_errors(error: Exception) -> HTTPException:
    if isinstance(error, SessionNotFoundError):
        return HTTPException(status_code=404, detail="application session not found")
    if isinstance(error, (ActorMismatchError, PermissionError)):
        return HTTPException(status_code=403, detail=str(error))
    if isinstance(error, CredentialRejectedError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, NavigationBlocked):
        return HTTPException(status_code=400, detail=str(error))
    if isinstance(error, (WorkflowStateError, BlockedError)):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=500, detail="application workflow failed")


@router.post(f"{_BASE}/sessions", status_code=201)
async def create_session(
    body: ApplicationSessionCreateIn,
    tenant: TenantContext = Depends(require_tenant),
    service: Service = Depends(get_service),
    flow: ApplicationFlow = Depends(get_application_flow),
):
    """Create the paired session and navigate to the official application URL.

    Returns ``awaiting_user_login`` with owner-visible paired-browser
    instructions when the site requires authentication.
    """
    try:
        url, kind, ref_id = _resolve_target(body, service)
        record = await flow.start(
            tenant.tenant_id, tenant.actor_id, url,
            opportunity_kind=kind, opportunity_id=ref_id, label=body.label,
        )
    except CompetitionNotFoundError as error:
        raise HTTPException(status_code=404, detail="competition not found") from error
    except HTTPException:
        raise
    except Exception as error:
        raise _flow_errors(error) from error
    return record.public_view()


@router.post(_BASE + "/sessions/{session_id}/resume")
async def resume_session(
    session_id: str,
    body: ApplicationResumeIn,
    tenant: TenantContext = Depends(require_tenant),
    flow: ApplicationFlow = Depends(get_application_flow),
):
    """Resume after the owner confirms they logged in inside the paired session."""
    try:
        record = await flow.resume(tenant.tenant_id, tenant.actor_id, session_id, body.login_confirmed)
    except Exception as error:
        raise _flow_errors(error) from error
    return record.public_view()


@router.post(_BASE + "/sessions/{session_id}/inspect")
async def inspect_session(
    session_id: str,
    tenant: TenantContext = Depends(require_tenant),
    flow: ApplicationFlow = Depends(get_application_flow),
):
    """Extract grounded form descriptors from the live page."""
    try:
        return await flow.inspect(tenant.tenant_id, tenant.actor_id, session_id)
    except Exception as error:
        raise _flow_errors(error) from error


@router.post(_BASE + "/sessions/{session_id}/stage")
async def stage_session(
    session_id: str,
    body: ApplicationStageIn,
    tenant: TenantContext = Depends(require_tenant),
    flow: ApplicationFlow = Depends(get_application_flow),
):
    """Stage only owner-approved grounded fields and return the exact preview.

    The form is filled and read back, a redacted full-page screenshot is
    captured, and nothing is submitted.
    """
    try:
        return await flow.stage(tenant.tenant_id, tenant.actor_id, session_id, body.fields, body.submit_selector)
    except Exception as error:
        raise _flow_errors(error) from error


@router.post(_BASE + "/sessions/{session_id}/submit-approval", status_code=201)
async def request_submit_approval(
    session_id: str,
    tenant: TenantContext = Depends(require_tenant),
    flow: ApplicationFlow = Depends(get_application_flow),
):
    """Create the separate final-submit approval bound to exact current facts."""
    try:
        return await flow.request_final_submit(tenant.tenant_id, tenant.actor_id, session_id)
    except Exception as error:
        raise _flow_errors(error) from error


@router.post(_BASE + "/sessions/{session_id}/submit")
async def execute_submit(
    session_id: str,
    body: ApplicationSubmitIn,
    tenant: TenantContext = Depends(require_tenant),
    service: Service = Depends(get_service),
    flow: ApplicationFlow = Depends(get_application_flow),
):
    """Execute the approved submit exactly once, then read back the site's response.

    Competition status is updated only from the post-submit source readback;
    a failed or blocked click leaves the competition unsubmitted.
    """
    try:
        result = await flow.execute_submit(tenant.tenant_id, tenant.actor_id, session_id, body.approval_id)
    except BlockedError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ActorMismatchError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise _flow_errors(error) from error

    record = flow.status(tenant.tenant_id, tenant.actor_id, session_id)
    if record.get("opportunity_kind") == "competition" and record.get("opportunity_id"):
        confirmation = result["confirmation"]
        evidence = StatusEvidence(
            source="browser_readback",
            reference=(
                f"paired browser session {session_id} submitted and read back at "
                f"{confirmation['final_url']} (approval {body.approval_id})"
            ),
            observed_at=datetime.fromtimestamp(confirmation["observed_at"], timezone.utc),
            status=SubmissionStatus.SUBMITTED,
        )
        try:
            service.update_status(record["opportunity_id"], evidence)
        except Exception as error:
            raise _flow_errors(error) from error
    return result


@router.get(_BASE + "/sessions/{session_id}")
async def session_status(
    session_id: str,
    tenant: TenantContext = Depends(require_tenant),
    flow: ApplicationFlow = Depends(get_application_flow),
):
    """Read the honest current state of one application session."""
    try:
        return flow.status(tenant.tenant_id, tenant.actor_id, session_id)
    except Exception as error:
        raise _flow_errors(error) from error
