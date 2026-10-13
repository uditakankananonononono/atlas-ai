"""Mounted student account browser operations. Final submits remain M02-owned."""
from threading import Lock
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from app.auth.context import TenantContext, require_tenant
from app.modules.m13_browser_agent.application_flow import BlockedError, WorkflowStateError
from app.modules.m02_competition_manager.application_schemas import ApplicationStageIn
from .student_browser import ADAPTERS, SQLCheckpoints, StudentBrowser
from .student_platforms import PlatformUnavailable

_browser = None
_browser_lock = Lock()


def get_student_browser():
    global _browser
    with _browser_lock:
        if _browser is None:
            from app.modules.m02_competition_manager.application_routes import get_application_flow
            _browser = StudentBrowser(get_application_flow(), SQLCheckpoints())
    return _browser


class StartIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    owner_account_confirmed: bool
    terms_permit: bool


class StageIn(ApplicationStageIn):
    plan_token: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')


class PrefillPlanIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    profile: dict[str, str] = Field(max_length=20)
    submit_selector: str = Field(min_length=1, max_length=300)


class CompetitionReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    rules_reviewed: StrictBool
    eligibility_confirmed: StrictBool
    deadline_confirmed: StrictBool
    no_cost_confirmed: StrictBool


class OpenIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    link_id: str = Field(min_length=24, max_length=24, pattern=r'^[0-9a-f]{24}$')


def failure(exc):
    if isinstance(exc, KeyError): return HTTPException(404, 'platform/session not found')
    if isinstance(exc, PermissionError): return HTTPException(403, str(exc))
    if isinstance(exc, PlatformUnavailable): return HTTPException(503, str(exc))
    if isinstance(exc, (BlockedError, WorkflowStateError)): return HTTPException(409, str(exc))
    if isinstance(exc, ValueError): return HTTPException(422, str(exc))
    return HTTPException(500, 'student browser operation failed')


def install_routes(router):
    # Register on M01's router directly, consistent with existing prefix handling.
    base = '/opportunity-discovery/student-platforms'

    @router.get(base + '/browser-capabilities')
    def capabilities(tenant: TenantContext = Depends(require_tenant)):
        return [{'platform': a.platform, 'hosts': a.hosts, 'account_workflow': a.account_workflow,
                 'caveat': a.caveat, 'adapter': 'owner_browser_dom', 'live_workflow_verified': False,
                 'extension_driven': False, 'unattended_auto_apply': False} for a in ADAPTERS.values()]

    @router.post(base + '/{platform_id}/browser-sessions', status_code=201)
    async def start(platform_id: str, body: StartIn, tenant: TenantContext = Depends(require_tenant), browser=Depends(get_student_browser)):
        try:
            return await browser.start(tenant.tenant_id, tenant.actor_id, platform_id, body.owner_account_confirmed, body.terms_permit)
        except Exception as exc:
            raise failure(exc) from exc

    @router.post(base + '/browser-sessions/{session_id}/read')
    async def read(session_id: str, tenant: TenantContext = Depends(require_tenant), browser=Depends(get_student_browser)):
        try:
            return await browser.read(tenant.tenant_id, tenant.actor_id, session_id)
        except Exception as exc:
            raise failure(exc) from exc

    @router.post(base + '/browser-sessions/{session_id}/open')
    async def open_link(session_id: str, body: OpenIn, tenant: TenantContext = Depends(require_tenant), browser=Depends(get_student_browser)):
        try:
            return await browser.open(tenant.tenant_id, tenant.actor_id, session_id, body.link_id)
        except Exception as exc:
            raise failure(exc) from exc

    @router.post(base + '/browser-sessions/{session_id}/stage')
    async def stage(session_id: str, body: StageIn, tenant: TenantContext = Depends(require_tenant), browser=Depends(get_student_browser)):
        try:
            return await browser.stage(tenant.tenant_id, tenant.actor_id, session_id, body.fields, body.submit_selector, body.plan_token)
        except Exception as exc:
            raise failure(exc) from exc

    @router.post(base + '/browser-sessions/{session_id}/prefill-plan')
    async def prefill_plan(session_id: str, body: PrefillPlanIn, tenant: TenantContext = Depends(require_tenant), browser=Depends(get_student_browser)):
        try:
            return await browser.plan_prefill(tenant.tenant_id, tenant.actor_id, session_id, body.profile, body.submit_selector)
        except Exception as exc:
            raise failure(exc) from exc

    @router.post(base + '/browser-sessions/{session_id}/competition-terms')
    async def competition_terms(session_id: str, tenant: TenantContext = Depends(require_tenant), browser=Depends(get_student_browser)):
        try:
            return await browser.competition_terms(tenant.tenant_id, tenant.actor_id, session_id)
        except Exception as exc:
            raise failure(exc) from exc

    @router.post(base + '/browser-sessions/{session_id}/competition-terms/review')
    async def review_competition_terms(session_id: str, body: CompetitionReviewIn, tenant: TenantContext = Depends(require_tenant), browser=Depends(get_student_browser)):
        try:
            return await browser.review_competition_terms(tenant.tenant_id, tenant.actor_id, session_id, **body.model_dump())
        except Exception as exc:
            raise failure(exc) from exc
